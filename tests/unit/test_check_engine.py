from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.checker.engine import CheckEngine
from app.models.models import Endpoint, Service
from app.schemas.check_results import CheckResultsCreate, CheckResultsResponse, RequestResult


@pytest.fixture
def mock_db():
    """Мок сессии БД"""
    return AsyncMock()


@pytest.fixture
def check_engine(mock_db):
    """Создает экземпляр CheckEngine с замоканной БД"""
    with patch("app.checker.engine.CheckResultsRepository") as MockCheckRepo, \
         patch("app.checker.engine.ResponsibleRepository") as MockRespRepo, \
         patch("app.checker.engine.ServiceRepository") as MockSvcRepo:
        MockCheckRepo.return_value = AsyncMock()
        MockRespRepo.return_value = AsyncMock()
        MockSvcRepo.return_value = AsyncMock()
        engine = CheckEngine(mock_db)
        engine.repo = AsyncMock()
        engine.client = AsyncMock()
        return engine


@pytest.fixture
def sample_endpoint():
    """Создает тестовый эндпоинт"""
    service = MagicMock(spec=Service)
    service.id = 1
    service.name = "Test Service"

    endpoint = MagicMock(spec=Endpoint)
    endpoint.id = 1
    endpoint.url = "https://httpbin.org/get"
    endpoint.service = service
    endpoint.service_id = 1
    return endpoint


def test_init_default_values(mock_db):
    with patch("app.checker.engine.CheckResultsRepository"), \
         patch("app.checker.engine.ResponsibleRepository"), \
         patch("app.checker.engine.ServiceRepository"):
        engine = CheckEngine(mock_db)
        assert engine._checker_timeout == 10
        assert engine._notify_repeat_minutes == 30
        assert engine.last_down_time == {}


async def test_check_endpoint_success(check_engine, sample_endpoint):
    with patch.object(check_engine, "send_request") as mock_send:
        mock_result = RequestResult(
            checked_at=datetime.now(timezone.utc),
            is_available=True,
            status_code=200,
            response_time_ms=150,
            error_message=None,
        )
        mock_send.return_value = mock_result

        result = await check_engine.check_endpoint(sample_endpoint)

        assert isinstance(result, CheckResultsCreate)
        assert result.endpoint_id == sample_endpoint.id
        assert result.is_available is True
        assert result.status_code == 200
        assert result.response_time_ms == 150
        assert result.error_message is None
        mock_send.assert_called_once_with(sample_endpoint.url)


async def test_check_endpoint_http_error(check_engine, sample_endpoint):
    with patch.object(check_engine, "send_request") as mock_send:
        mock_result = RequestResult(
            checked_at=datetime.now(timezone.utc),
            is_available=False,
            status_code=500,
            response_time_ms=None,
            error_message="HTTP 500",
        )
        mock_send.return_value = mock_result

        result = await check_engine.check_endpoint(sample_endpoint)

        assert result.is_available is False
        assert result.status_code == 500
        assert result.error_message == "HTTP 500"


async def test_send_request_success_200(check_engine):
    with patch.object(check_engine.client, "get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = await check_engine.send_request("http://test.com")

        assert result.is_available is True
        assert result.status_code == 200
        assert result.error_message is None
        assert result.response_time_ms is not None
        assert result.checked_at.tzinfo == timezone.utc


async def test_send_request_success_302(check_engine):
    with patch.object(check_engine.client, "get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 302
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = await check_engine.send_request("http://test.com")

        assert result.is_available is True
        assert result.status_code == 302


async def test_send_request_404_error(check_engine):
    with patch.object(check_engine.client, "get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=mock_response)
        )
        mock_get.return_value = mock_response

        result = await check_engine.send_request("http://test.com")

        assert result.is_available is False
        assert result.status_code == 404
        assert "HTTP 404" in result.error_message
        assert result.response_time_ms is not None


async def test_send_request_timeout(check_engine):
    with patch.object(check_engine.client, "get") as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Timeout")

        result = await check_engine.send_request("http://test.com")

        assert result.is_available is False
        assert result.status_code is None
        assert "Timeout" in result.error_message


async def test_send_request_connection_error(check_engine):
    with patch.object(check_engine.client, "get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        result = await check_engine.send_request("http://test.com")

        assert result.is_available is False
        assert result.status_code is None
        assert "Connection error" in result.error_message


async def test_send_request_response_time_calculation(check_engine):
    with patch.object(check_engine.client, "get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = await check_engine.send_request("http://test.com")

        assert result.response_time_ms is not None
        assert isinstance(result.response_time_ms, int)
        assert result.response_time_ms >= 0


async def test_service_success(check_engine, sample_endpoint):
    mock_check_result = CheckResultsCreate(
        endpoint_id=1,
        checked_at=datetime.now(timezone.utc),
        is_available=True,
        status_code=200,
        response_time_ms=150,
        error_message=None,
    )

    mock_db_result = MagicMock(spec=CheckResultsResponse)
    mock_db_result.id = 1
    mock_db_result.endpoint_id = 1
    mock_db_result.checked_at = datetime.now(timezone.utc)
    mock_db_result.is_available = True
    mock_db_result.status_code = 200
    mock_db_result.response_time_ms = 150
    mock_db_result.error_message = None

    with patch.object(check_engine, "check_endpoint", return_value=mock_check_result):
        with patch.object(check_engine.repo, "create", return_value=mock_db_result):
            with patch.object(check_engine, "handle_notification") as mock_notify:
                result = await check_engine.service(sample_endpoint)

                assert result == mock_db_result
                check_engine.repo.create.assert_called_once()
                mock_notify.assert_called_once_with(sample_endpoint, mock_db_result)


async def test_handle_notification_down(check_engine, sample_endpoint):
    check_result = CheckResultsCreate(
        endpoint_id=1,
        checked_at=datetime.now(timezone.utc),
        is_available=False,
        status_code=500,
        response_time_ms=200,
        error_message="HTTP 500",
    )

    with patch.object(check_engine, "notify_if_needed") as mock_notify:
        with patch.object(check_engine, "check_after_recovery") as mock_recovery:
            await check_engine.handle_notification(sample_endpoint, check_result)

            mock_notify.assert_called_once_with(sample_endpoint, check_result)
            mock_recovery.assert_not_called()


async def test_handle_notification_up(check_engine, sample_endpoint):
    check_result = CheckResultsCreate(
        endpoint_id=1,
        checked_at=datetime.now(timezone.utc),
        is_available=True,
        status_code=200,
        response_time_ms=150,
        error_message=None,
    )

    with patch.object(check_engine, "notify_if_needed") as mock_notify:
        with patch.object(check_engine, "check_after_recovery") as mock_recovery:
            await check_engine.handle_notification(sample_endpoint, check_result)

            mock_recovery.assert_called_once_with(sample_endpoint, check_result)
            mock_notify.assert_not_called()


async def test_notify_first_down(check_engine, sample_endpoint):
    check_result = CheckResultsCreate(
        endpoint_id=1,
        checked_at=datetime.now(timezone.utc),
        is_available=False,
        status_code=500,
        response_time_ms=200,
        error_message="HTTP 500",
    )

    with patch.object(check_engine, "send_to_notifier") as mock_send:
        await check_engine.notify_if_needed(sample_endpoint, check_result)

        mock_send.assert_called_once_with(sample_endpoint, check_result, status="DOWN")
        assert sample_endpoint.id in check_engine.last_down_time


async def test_notify_down_duplicate_within_window(check_engine, sample_endpoint):
    check_result = CheckResultsCreate(
        endpoint_id=1,
        checked_at=datetime.now(timezone.utc),
        is_available=False,
        status_code=500,
        response_time_ms=200,
        error_message="HTTP 500",
    )

    check_engine.last_down_time[sample_endpoint.id] = datetime.now(timezone.utc)

    with patch.object(check_engine, "send_to_notifier") as mock_send:
        await check_engine.notify_if_needed(sample_endpoint, check_result)

        mock_send.assert_not_called()


async def test_notify_down_after_window(check_engine, sample_endpoint):
    check_result = CheckResultsCreate(
        endpoint_id=1,
        checked_at=datetime.now(timezone.utc),
        is_available=False,
        status_code=500,
        response_time_ms=200,
        error_message="HTTP 500",
    )

    check_engine.last_down_time[sample_endpoint.id] = datetime.now(timezone.utc) - timedelta(
        minutes=31
    )

    with patch.object(check_engine, "send_to_notifier") as mock_send:
        await check_engine.notify_if_needed(sample_endpoint, check_result)

        mock_send.assert_called_once_with(sample_endpoint, check_result, status="DOWN")
        assert check_engine.last_down_time[sample_endpoint.id] is not None


async def test_recovery_notification(check_engine, sample_endpoint):
    check_result = CheckResultsCreate(
        endpoint_id=1,
        checked_at=datetime.now(timezone.utc),
        is_available=True,
        status_code=200,
        response_time_ms=150,
        error_message=None,
    )

    check_engine.last_down_time[sample_endpoint.id] = datetime.now(timezone.utc) - timedelta(
        minutes=5
    )

    with patch.object(check_engine, "send_to_notifier") as mock_send:
        await check_engine.check_after_recovery(sample_endpoint, check_result)

        mock_send.assert_called_once_with(sample_endpoint, check_result, status="UP")
        assert sample_endpoint.id not in check_engine.last_down_time


async def test_recovery_notification_only_once(check_engine, sample_endpoint):
    check_result = CheckResultsCreate(
        endpoint_id=1,
        checked_at=datetime.now(timezone.utc),
        is_available=True,
        status_code=200,
        response_time_ms=150,
        error_message=None,
    )

    assert sample_endpoint.id not in check_engine.last_down_time

    with patch.object(check_engine, "send_to_notifier") as mock_send:
        await check_engine.check_after_recovery(sample_endpoint, check_result)

        mock_send.assert_not_called()


async def test_full_down_recovery_cycle(check_engine, sample_endpoint):
    down_result = CheckResultsCreate(
        endpoint_id=1,
        checked_at=datetime.now(timezone.utc),
        is_available=False,
        status_code=500,
        response_time_ms=200,
        error_message="HTTP 500",
    )

    up_result = CheckResultsCreate(
        endpoint_id=1,
        checked_at=datetime.now(timezone.utc),
        is_available=True,
        status_code=200,
        response_time_ms=150,
        error_message=None,
    )

    with patch.object(check_engine, "send_to_notifier") as mock_send:
        await check_engine.handle_notification(sample_endpoint, down_result)
        assert mock_send.call_count == 1
        assert mock_send.call_args[1]["status"] == "DOWN"

        await check_engine.handle_notification(sample_endpoint, up_result)
        assert mock_send.call_count == 2
        assert mock_send.call_args[1]["status"] == "UP"

        assert sample_endpoint.id not in check_engine.last_down_time


async def test_multiple_endpoints_independent(check_engine):
    endpoint1 = MagicMock(spec=Endpoint)
    endpoint1.id = 1
    endpoint1.url = "http://test1.com"

    endpoint2 = MagicMock(spec=Endpoint)
    endpoint2.id = 2
    endpoint2.url = "http://test2.com"

    down_result = CheckResultsCreate(
        endpoint_id=1,
        checked_at=datetime.now(timezone.utc),
        is_available=False,
        status_code=500,
        response_time_ms=200,
        error_message="HTTP 500",
    )

    with patch.object(check_engine, "send_to_notifier") as mock_send:
        await check_engine.handle_notification(endpoint1, down_result)

        up_result = CheckResultsCreate(
            endpoint_id=2,
            checked_at=datetime.now(timezone.utc),
            is_available=True,
            status_code=200,
            response_time_ms=150,
            error_message=None,
        )
        await check_engine.handle_notification(endpoint2, up_result)

        assert endpoint1.id in check_engine.last_down_time
        assert endpoint2.id not in check_engine.last_down_time


async def test_multiple_down_notifications_after_window(check_engine, sample_endpoint):
    check_result = CheckResultsCreate(
        endpoint_id=1,
        checked_at=datetime.now(timezone.utc),
        is_available=False,
        status_code=500,
        response_time_ms=200,
        error_message="HTTP 500",
    )

    with patch.object(check_engine, "send_to_notifier") as mock_send:
        await check_engine.notify_if_needed(sample_endpoint, check_result)
        assert mock_send.call_count == 1

        check_engine.last_down_time[sample_endpoint.id] = datetime.now(timezone.utc) - timedelta(
            minutes=31
        )

        await check_engine.notify_if_needed(sample_endpoint, check_result)
        assert mock_send.call_count == 2
