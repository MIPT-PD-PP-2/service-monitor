from collections.abc import Callable
from datetime import datetime, timezone
from typing import Optional

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.checker.engine import CheckEngine
from app.config import settings
from app.db.database import AsyncSessionLocal
from app.repositories import EndpointRepository

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

    # Немедленный запуск всех задач проверок
    def trigger_now(self) -> None:
        now = datetime.now(timezone.utc)
        for job in self._scheduler.get_jobs():
            job.modify(next_run_time=now)
        logger.info("scheduler_triggered_manually")

    def get_next_run_time(self) -> Optional[datetime]:
        jobs = self._scheduler.get_jobs()
        if not jobs:
            return None
        return min((j.next_run_time for j in jobs if j.next_run_time), default=None)

    # Добавление периодической задачи для проверки с интервалом
    def add_periodic_job(
        self, func: Callable, job_id: str, interval_seconds: Optional[int] = None
    ) -> None:
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

    # Подсчет количества задач проверок эндпоинтов
    def get_count_jobs(self) -> int:
        return sum(1 for j in self._scheduler.get_jobs() if j.id.startswith("check_endpoint_"))

    # Инициализация списка задач — проверок активных эндпоинтов
    async def initialize_scheduler_jobs(self) -> None:
        async with AsyncSessionLocal() as session:
            endpoint_repo = EndpointRepository(session)
            active_endpoints = await endpoint_repo.get_active_endpoints()

            for endpoint in active_endpoints:

                def make_check_job(endpoint_id: int = endpoint.id) -> Callable:
                    async def check_job() -> None:
                        await check_engine.check_endpoint(endpoint_id)
                    return check_job

                check_job_func = make_check_job()

                self.add_periodic_job(
                    func=check_job_func,
                    job_id=f"check_endpoint_{endpoint.id}",
                    interval_seconds=self.get_interval(),
                )

            logger.info("active_endpoints_registered", count=len(active_endpoints))


scheduler_manager = SchedulerManager()
