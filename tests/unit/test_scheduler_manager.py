from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from collections.abc import Callable

import pytest
from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from app.scheduler.scheduler import SchedulerManager
from app.repositories.endpoints import EndpointRepository


@pytest.fixture
def mock_scheduler():
    with patch("app.scheduler.scheduler.AsyncIOScheduler") as mock:
        # Создаем мок-объект планировщика
        scheduler_instance = MagicMock(spec=AsyncIOScheduler)
        scheduler_instance.running = False
        scheduler_instance.get_jobs.return_value = []
        mock.return_value = scheduler_instance
        yield scheduler_instance


@pytest.fixture
def scheduler_manager(mock_scheduler):
    manager = SchedulerManager()
    manager._scheduler = mock_scheduler
    return manager


@pytest.mark.asyncio
async def test_scheduler_initialization(scheduler_manager, mock_scheduler):
    assert not scheduler_manager.is_running()
    assert scheduler_manager._scheduler is mock_scheduler


@pytest.mark.asyncio
async def test_start_scheduler_not_running(scheduler_manager, mock_scheduler):
    mock_scheduler.running = False
    await scheduler_manager.start()
    mock_scheduler.start.assert_called_once()


@pytest.mark.asyncio
async def test_start_scheduler_already_running(scheduler_manager, mock_scheduler):
    mock_scheduler.running = True
    await scheduler_manager.start()
    mock_scheduler.start.assert_not_called()


@pytest.mark.asyncio
async def test_stop_scheduler_running(scheduler_manager, mock_scheduler):
    mock_scheduler.running = True
    await scheduler_manager.stop()
    mock_scheduler.shutdown.assert_called_once_with(wait=False)


@pytest.mark.asyncio
async def test_stop_scheduler_not_running(scheduler_manager, mock_scheduler):
    mock_scheduler.running = False
    await scheduler_manager.stop()
    mock_scheduler.shutdown.assert_not_called()


@pytest.mark.asyncio
async def test_add_periodic_job(scheduler_manager, mock_scheduler):
    mock_func: Callable = AsyncMock()
    scheduler_manager.add_periodic_job(mock_func, "test_job", 30)

    assert mock_scheduler.add_job.called
    call_args = mock_scheduler.add_job.call_args
    assert call_args[0][0] is mock_func
    assert call_args[1]["id"] == "test_job"
    assert call_args[1]["replace_existing"] is True


@pytest.mark.asyncio
async def test_remove_job_exists(scheduler_manager, mock_scheduler):
    scheduler_manager.remove_job("existing_job")
    mock_scheduler.remove_job.assert_called_once_with("existing_job")


@pytest.mark.asyncio
async def test_remove_job_not_exists(scheduler_manager, mock_scheduler):
    mock_scheduler.remove_job.side_effect = KeyError("Job not found")
    scheduler_manager.remove_job("nonexistent_job")
    mock_scheduler.remove_job.assert_called_once_with("nonexistent_job")


@pytest.mark.asyncio
async def test_get_count_jobs(scheduler_manager, mock_scheduler):
    # Только задачи с префиксом check_endpoint_ должны учитываться
    check_job1 = MagicMock(spec=Job)
    check_job1.id = "check_endpoint_1"
    check_job2 = MagicMock(spec=Job)
    check_job2.id = "check_endpoint_2"
    other_job = MagicMock(spec=Job)
    other_job.id = "other_job"
    mock_scheduler.get_jobs.return_value = [check_job1, check_job2, other_job]

    count = scheduler_manager.get_count_jobs()

    assert count == 2
    mock_scheduler.get_jobs.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_scheduler_jobs_no_endpoints(scheduler_manager, mock_scheduler):
    mock_session = AsyncMock(spec=AsyncSession)

    with patch("app.scheduler.scheduler.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value = mock_session

        with patch("app.scheduler.scheduler.EndpointRepository") as MockEndpointRepo:
            mock_endpoint_repo = MockEndpointRepo.return_value
            mock_endpoint_repo.get_active_endpoints = AsyncMock(return_value=[])

            await scheduler_manager.initialize_scheduler_jobs()

            mock_session_local.assert_called_once()
            MockEndpointRepo.assert_called_once_with(mock_session)
            mock_endpoint_repo.get_active_endpoints.assert_awaited_once()

            assert scheduler_manager._engine is not None
            mock_scheduler.add_job.assert_not_called()


@pytest.mark.asyncio
async def test_initialize_scheduler_jobs_with_endpoints(scheduler_manager, mock_scheduler):
    mock_endpoint1 = MagicMock()
    mock_endpoint1.id = 1
    mock_endpoint2 = MagicMock()
    mock_endpoint2.id = 2

    mock_session = AsyncMock(spec=AsyncSession)

    with patch("app.scheduler.scheduler.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value = mock_session

        with patch("app.scheduler.scheduler.EndpointRepository") as MockEndpointRepo:
            mock_endpoint_repo = MockEndpointRepo.return_value
            mock_endpoint_repo.get_active_endpoints = AsyncMock(
                return_value=[mock_endpoint1, mock_endpoint2]
            )

            await scheduler_manager.initialize_scheduler_jobs()

            mock_session_local.assert_called_once()
            MockEndpointRepo.assert_called_once_with(mock_session)
            mock_endpoint_repo.get_active_endpoints.assert_awaited_once()

            assert scheduler_manager._engine is not None
            assert mock_scheduler.add_job.call_count == 2

            called_ids = [call[1]["id"] for call in mock_scheduler.add_job.call_args_list]
            assert "check_endpoint_1" in called_ids
            assert "check_endpoint_2" in called_ids


@pytest.mark.asyncio
async def test_trigger_now(scheduler_manager, mock_scheduler):
    job1 = MagicMock(spec=Job)
    job2 = MagicMock(spec=Job)
    mock_scheduler.get_jobs.return_value = [job1, job2]

    scheduler_manager.trigger_now()

    mock_scheduler.get_jobs.assert_called_once()
    # trigger_now теперь передаёт datetime вместо None
    call_args1 = job1.modify.call_args
    call_args2 = job2.modify.call_args
    assert isinstance(call_args1[1]["next_run_time"], datetime)
    assert isinstance(call_args2[1]["next_run_time"], datetime)


@pytest.mark.asyncio
async def test_get_next_run_time_no_jobs(scheduler_manager, mock_scheduler):
    mock_scheduler.get_jobs.return_value = []

    next_run_time = scheduler_manager.get_next_run_time()

    assert next_run_time is None


@pytest.mark.asyncio
async def test_get_next_run_time_with_jobs(scheduler_manager, mock_scheduler):
    job1 = MagicMock(spec=Job)
    job1.next_run_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    job2 = MagicMock(spec=Job)
    job2.next_run_time = datetime.now(timezone.utc) + timedelta(minutes=3)
    job3 = MagicMock(spec=Job)
    job3.next_run_time = None

    mock_scheduler.get_jobs.return_value = [job1, job2, job3]

    next_run_time = scheduler_manager.get_next_run_time()

    assert next_run_time == job2.next_run_time
