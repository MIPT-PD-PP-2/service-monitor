import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings

logger = structlog.get_logger()


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


scheduler_manager = SchedulerManager()
