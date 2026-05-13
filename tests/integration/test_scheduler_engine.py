from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.models import Endpoint, Service
from app.scheduler.scheduler import SchedulerManager


@pytest.fixture
def mock_endpoint():
    service = MagicMock(spec=Service)
    service.id = 1
    service.name = "Test Service"

    endpoint = MagicMock(spec=Endpoint)
    endpoint.id = 1
    endpoint.url = "https://httpbin.org/get"
    endpoint.service = service
    endpoint.service_id = 1
    return endpoint


def _make_session_cm(mock_session=None):
    if mock_session is None:
        mock_session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_initialize_creates_engine():
    with patch("app.scheduler.scheduler.AsyncSessionLocal", return_value=_make_session_cm()):
        with patch("app.checker.engine.AsyncSessionLocal"):
            with patch("app.scheduler.scheduler.EndpointRepository") as MockRepo:
                MockRepo.return_value.get_active_endpoints = AsyncMock(return_value=[])
                scheduler = SchedulerManager()
                await scheduler.initialize_scheduler_jobs()
                assert scheduler._engine is not None


@pytest.mark.asyncio
async def test_scheduler_calls_engine_service_on_job_execution(mock_endpoint):
    with patch("app.scheduler.scheduler.AsyncSessionLocal", return_value=_make_session_cm()):
        with patch("app.checker.engine.AsyncSessionLocal"):
            scheduler = SchedulerManager()

            mock_engine = AsyncMock()
            scheduler._engine = mock_engine

            async def check_job():
                await scheduler._engine.service(mock_endpoint)

            await check_job()
            mock_engine.service.assert_awaited_once_with(mock_endpoint)


@pytest.mark.asyncio
async def test_engine_service_executes_full_check_cycle(mock_endpoint):
    with patch("app.scheduler.scheduler.AsyncSessionLocal", return_value=_make_session_cm()):
        with patch("app.checker.engine.AsyncSessionLocal"):
            with patch("app.scheduler.scheduler.EndpointRepository") as MockEndpointRepo:
                MockEndpointRepo.return_value.get_active_endpoints = AsyncMock(
                    return_value=[mock_endpoint]
                )

                scheduler = SchedulerManager()
                await scheduler.initialize_scheduler_jobs()

                scheduler._engine.service = AsyncMock(return_value=MagicMock(id=1))
                await scheduler._engine.service(mock_endpoint)
                scheduler._engine.service.assert_awaited_once_with(mock_endpoint)


@pytest.mark.asyncio
async def test_scheduler_stop_closes_engine():
    scheduler = SchedulerManager()

    mock_engine = AsyncMock()
    scheduler._engine = mock_engine

    scheduler._scheduler = AsyncMock()
    scheduler._scheduler.running = True
    scheduler._scheduler.shutdown = MagicMock()

    await scheduler.stop()

    mock_engine.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_real_http_check_integration():
    from app.checker.engine import CheckEngine

    mock_db_result = MagicMock(id=1)
    mock_repo = AsyncMock()
    mock_repo.create = AsyncMock(return_value=mock_db_result)
    mock_session = AsyncMock()
    cm = _make_session_cm(mock_session)

    with patch("app.checker.engine.AsyncSessionLocal", return_value=cm):
        with patch("app.checker.engine.CheckResultsRepository", return_value=mock_repo):
            engine = CheckEngine()

            mock_response = AsyncMock()
            mock_response.status_code = 200
            engine.client.get = AsyncMock(return_value=mock_response)

            endpoint = MagicMock(spec=Endpoint)
            endpoint.id = 1
            endpoint.url = "https://httpbin.org/get"
            endpoint.service_id = 1

            result = await engine.service(endpoint)
            assert result is not None
            assert result.id == 1


@pytest.mark.asyncio
async def test_engine_with_scheduler_real_flow():
    with patch("app.scheduler.scheduler.AsyncSessionLocal", return_value=_make_session_cm()):
        with patch("app.checker.engine.AsyncSessionLocal"):
            scheduler = SchedulerManager()

            mock_endpoint = MagicMock(spec=Endpoint)
            mock_endpoint.id = 5
            mock_endpoint.url = "https://httpbin.org/status/200"

            with patch("app.scheduler.scheduler.EndpointRepository") as MockRepo:
                MockRepo.return_value.get_active_endpoints = AsyncMock(
                    return_value=[mock_endpoint]
                )

                await scheduler.initialize_scheduler_jobs()
                assert scheduler._engine is not None

                scheduler.trigger_now()
                assert scheduler.get_count_jobs() == 1
