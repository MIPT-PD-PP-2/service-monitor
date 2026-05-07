import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI

from app.main import lifespan


@pytest.fixture
def mock_app():
    return AsyncMock()


@pytest.fixture
def mock_scheduler_manager():
    with patch("app.main.scheduler_manager") as mock:
        yield mock


@pytest.mark.asyncio
async def test_lifespan_calls_scheduler_initialization_start_stop(mock_app, mock_scheduler_manager):
    mock_scheduler_manager.initialize_scheduler_jobs = AsyncMock()
    mock_scheduler_manager.start = AsyncMock()
    mock_scheduler_manager.stop = AsyncMock()

    app = FastAPI()

    async with lifespan(app) as context:
        pass

    mock_scheduler_manager.initialize_scheduler_jobs.assert_called_once()
    mock_scheduler_manager.start.assert_called_once()
    mock_scheduler_manager.stop.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_handles_initialization_error():

    with patch("app.main.scheduler_manager") as mock_scheduler:

        mock_scheduler.initialize_scheduler_jobs.side_effect = RuntimeError("Initialization failed")
        mock_scheduler.start = AsyncMock()
        mock_scheduler.stop = AsyncMock()

        app = FastAPI()

        with pytest.raises(RuntimeError):
            async with lifespan(app) as context:
                pass

        mock_scheduler.stop.assert_awaited_once()
        mock_scheduler.start.assert_not_called()
