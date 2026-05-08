from fastapi import APIRouter
from app.scheduler import scheduler_manager
from app.schemas.monitoring import StatusResponse, TriggerResponse

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    is_running = scheduler_manager.is_running()
    interval = scheduler_manager.get_interval()
    jobs_count = scheduler_manager.get_count_jobs()
    return StatusResponse(is_running=is_running, interval=interval, endpoints_count=jobs_count)


@router.post("/trigger", status_code=202, response_model=TriggerResponse)
async def trigger_checks_manually() -> TriggerResponse:
    scheduler_manager.trigger_now()
    return TriggerResponse(detail="All checks triggered manually")
