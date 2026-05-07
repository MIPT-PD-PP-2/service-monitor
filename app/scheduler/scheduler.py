import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import settings
from app.db.database import AsyncSessionLocal
from app.repositories import EndpointRepository
from app.checker.engine import CheckEngine

logger = structlog.get_logger()
check_engine = CheckEngine()


class SchedulerManager:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()

    def is_running(self) -> bool:
        return self._scheduler.running

    def get_interval(self) -> int:
        return settings.check_interval_seconds

    async def start(self) -> None:
        if self._scheduler.running:
            return
        self._scheduler.start()
        logger.info("scheduler_started", interval_seconds=settings.check_interval_seconds)

    async def stop(self) -> None:
        if not self._scheduler.running:
            return
        self._scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")

    def trigger_now(self) -> None:
        """Run all active check jobs immediately."""
        for job in self._scheduler.get_jobs():
            job.modify(next_run_time=None)
            job.trigger = None  # type: ignore[assignment]
        logger.info("scheduler_triggered_manually")

    def get_next_run_time(self):  # type: ignore[return]
        jobs = self._scheduler.get_jobs()
        if not jobs:
            return None
        return min((j.next_run_time for j in jobs if j.next_run_time), default=None)

    # Добавление периодической задачи для проверки с интервалом
    def add_periodic_job(self, func: callable, job_id: str, interval_seconds: int = None) -> None:
        if interval_seconds is None:
            interval_seconds = settings.check_interval_seconds

        interval_trigger = IntervalTrigger(seconds=interval_seconds)
        self._scheduler.add_job(func, trigger=interval_trigger, id=job_id, replace_existing=True)
        logger.info("periodic_job_added", job_id=job_id, interval_seconds=interval_seconds)

    # Удаление периодической задачи
    def remove_job(self, job_id: str) -> None:
        try:
            self._scheduler.remove_job(job_id)
            logger.info("periodic_job_removed", job_id=job_id)
        except KeyError:
            logger.warning("job_not_found", job_id=job_id)

    # Подсчет количества задач - проверок эндпоинтов
    def get_count_jobs(self) -> int:
        return len(self._scheduler.get_jobs())

    # Инициализация списка задач - проверок активных эндпоинтов
    async def initialize_scheduler_jobs(self) -> None:
        async with AsyncSessionLocal() as session:
            endpoint_repo = EndpointRepository(session)
            active_endpoints = await endpoint_repo.get_active_endpoints()

            for endpoint in active_endpoints:

                async def make_check_job(endpoint_id=endpoint.id):
                    async def check_job():
                        await check_engine.check_endpoint(endpoint_id)

                    return check_job

                check_job_coroutine = make_check_job()

                self.add_periodic_job(
                    func=check_job_coroutine,
                    job_id=f"check_endpoint_{endpoint.id}",
                    interval_seconds=scheduler_manager.get_interval(),
                )

            logger.info("active_endpoints_registered", count=len(active_endpoints))


scheduler_manager = SchedulerManager()
