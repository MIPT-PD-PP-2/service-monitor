from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import endpoints, monitoring, reports, responsible, services
from app.scheduler import scheduler_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await scheduler_manager.initialize_scheduler_jobs()
    await scheduler_manager.start()
    try:
        yield
    finally:
        await scheduler_manager.stop()


app = FastAPI(
    title="Service Monitor",
    description="REST endpoint monitoring system",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(reports.router)
app.include_router(services.router)
app.include_router(monitoring.router)
app.include_router(endpoints.router)
app.include_router(responsible.router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok"}
