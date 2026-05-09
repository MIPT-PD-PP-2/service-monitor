from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.checker.engine import CheckEngine
from app.models.models import Endpoint, Service
from app.scheduler.scheduler import SchedulerManager


@pytest.fixture
def mock_db_session():
    session = AsyncMock(spec=AsyncSession)
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_endpoint():
    service = MagicMock(spec=Service)
    service.id = 1
    service.name = "Test Service"
    service.email = "test@example.com"

    endpoint = MagicMock(spec=Endpoint)
    endpoint.id = 1
    endpoint.url = "https://httpbin.org/get"
    endpoint.service = service
    endpoint.service_id = 1
    return endpoint


@pytest.fixture
def mock_endpoint_repo():
    repo = AsyncMock()
    repo.get_active_endpoints = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_initialize_creates_engine_and_session(mock_db_session):
    with patch("app.scheduler.scheduler.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value = mock_db_session

        with patch("app.scheduler.scheduler.CheckEngine") as MockCheckEngine:
            mock_engine = AsyncMock()
            MockCheckEngine.return_value = mock_engine

            with patch("app.scheduler.scheduler.EndpointRepository") as MockRepo:
                mock_repo = MockRepo.return_value
                mock_repo.get_active_endpoints = AsyncMock(return_value=[])

                scheduler = SchedulerManager()
                await scheduler.initialize_scheduler_jobs()

                assert scheduler._session is not None
                assert scheduler._engine is not None
                MockCheckEngine.assert_called_once_with(mock_db_session)

@pytest.mark.asyncio
async def test_scheduler_calls_engine_service_on_job_execution(
    mock_db_session, mock_endpoint
):
    with patch("app.scheduler.scheduler.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value = mock_db_session

        scheduler = SchedulerManager()

        mock_engine = AsyncMock()
        scheduler._engine = mock_engine
        scheduler._session = mock_db_session

        def make_check_job(endpoint: Endpoint):
            async def check_job():
                await scheduler._engine.service(endpoint)

            return check_job

        check_job = make_check_job(mock_endpoint)

        await check_job()

        mock_engine.service.assert_awaited_once_with(mock_endpoint)


@pytest.mark.asyncio
async def test_engine_service_executes_full_check_cycle(mock_db_session, mock_endpoint):
    with patch("app.scheduler.scheduler.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value = mock_db_session

        with patch("app.scheduler.scheduler.CheckEngine") as MockCheckEngine:
            mock_engine = AsyncMock()
            mock_engine.service = AsyncMock()
            MockCheckEngine.return_value = mock_engine

            with patch("app.scheduler.scheduler.EndpointRepository") as MockEndpointRepo:
                mock_repo = AsyncMock()
                mock_repo.get_active_endpoints = AsyncMock(return_value=[mock_endpoint])
                MockEndpointRepo.return_value = mock_repo

                scheduler = SchedulerManager()
                await scheduler.initialize_scheduler_jobs()

                await scheduler._engine.service(mock_endpoint)
                scheduler._engine.service.assert_awaited_once_with(mock_endpoint)


@pytest.mark.asyncio
async def test_scheduler_stop_closes_engine(mock_db_session):
    with patch("app.scheduler.scheduler.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value = mock_db_session

        scheduler = SchedulerManager()

        mock_engine = AsyncMock()
        scheduler._engine = mock_engine
        scheduler._session = mock_db_session

        scheduler._scheduler = AsyncMock()
        scheduler._scheduler.running = True
        scheduler._scheduler.shutdown = MagicMock()

        await scheduler.stop()

        mock_engine.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_real_http_check_integration(mock_db_session):
    with patch("app.scheduler.scheduler.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value = mock_db_session

        engine = CheckEngine(mock_db_session)

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        engine.client.get = AsyncMock(return_value=mock_response)
        engine.repo.create = AsyncMock(return_value=MagicMock(id=1))

        service = MagicMock(spec=Service)
        service.id = 1
        service.name = "Integration Test"

        endpoint = MagicMock(spec=Endpoint)
        endpoint.id = 1
        endpoint.url = "https://httpbin.org/get"
        endpoint.service = service
        endpoint.service_id = 1

        result = await engine.service(endpoint)

        assert result is not None
        assert result.id == 1


@pytest.mark.asyncio
async def test_engine_with_scheduler_real_flow(mock_db_session):
    with patch("app.scheduler.scheduler.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value = mock_db_session

        scheduler = SchedulerManager()

        mock_endpoint = MagicMock(spec=Endpoint)
        mock_endpoint.id = 5
        mock_endpoint.url = "https://httpbin.org/status/200"

        with patch("app.scheduler.scheduler.EndpointRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_active_endpoints = AsyncMock(return_value=[mock_endpoint])

            with patch("app.scheduler.scheduler.CheckEngine") as MockEngine:
                mock_engine = AsyncMock()
                mock_engine.service = AsyncMock(return_value=MagicMock(id=1))
                MockEngine.return_value = mock_engine

                await scheduler.initialize_scheduler_jobs()

                assert scheduler._engine is not None

                scheduler.trigger_now()

                assert scheduler.get_count_jobs() == 1
