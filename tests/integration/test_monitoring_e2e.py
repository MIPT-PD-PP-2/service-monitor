import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from sqlalchemy import select

from app.checker.engine import CheckEngine
from app.models.models import CheckResult, Endpoint
from app.repositories.check_results import CheckResultsRepository
from app.repositories.endpoints import EndpointRepository

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
async def e2e_engine(db_session):
    """CheckEngine с реальной БД, замоканными HTTP-клиентом и Notifier."""
    engine = CheckEngine(db_session)
    engine.client = AsyncMock()
    engine.notifier = AsyncMock()
    yield engine
    await engine.close()


def _mock_http_ok(status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status = MagicMock()
    return response


def _mock_http_error(status_code: int = 500) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            f"{status_code}",
            request=MagicMock(),
            response=response,
        )
    )
    return response


def _mock_connect_error() -> None:
    return httpx.ConnectError("Connection refused")


async def _load_endpoint(db_session, endpoint_id: int) -> Endpoint:
    repo = EndpointRepository(db_session)
    endpoint = await repo.get_by_id(endpoint_id)
    assert endpoint is not None, f"Endpoint {endpoint_id} not found in DB"
    return endpoint


async def _count_check_results(db_session, endpoint_id: int) -> int:
    repo = CheckResultsRepository(db_session)
    results = await repo.list_by_endpoint(endpoint_id)
    return len(results)


# ---------------------------------------------------------------------------
# Тест 1: Добавить сервис → добавить эндпоинт → триггернуть проверку
#         → убедиться, что результат записан в check_results
# ---------------------------------------------------------------------------
async def test_e2e_check_success_records_result(client, db_session, e2e_engine):
    engine = e2e_engine

    svc = await client.post(
        "/services",
        json={"name": "E2E Success Svc", "description": "Test"},
    )
    assert svc.status_code == 201
    svc_id = svc.json()["id"]

    ep = await client.post(
        f"/services/{svc_id}/endpoints",
        json={"url": "https://ok.local/health", "is_active": True},
    )
    assert ep.status_code == 201
    ep_id = ep.json()["id"]

    endpoint = await _load_endpoint(db_session, ep_id)

    engine.client.get = AsyncMock(return_value=_mock_http_ok(200))

    result = await engine.service(endpoint)

    assert result.is_available is True
    assert result.status_code == 200
    assert result.response_time_ms is not None
    assert result.error_message is None
    assert result.endpoint_id == ep_id

    assert await _count_check_results(db_session, ep_id) == 1


# ---------------------------------------------------------------------------
# Тест 2: Мок HTTP-клиента возвращает 500 → проверка записана как
#         is_available=False → Notifier вызван с нужными параметрами
# ---------------------------------------------------------------------------
async def test_e2e_check_failure_notifies_responsible(client, db_session, e2e_engine):
    engine = e2e_engine

    svc = await client.post(
        "/services",
        json={"name": "E2E Fail Svc", "description": "Test"},
    )
    svc_id = svc.json()["id"]

    await client.post(
        f"/services/{svc_id}/responsible",
        json={"name": "Admin", "email": "admin@company.ru"},
    )

    ep = await client.post(
        f"/services/{svc_id}/endpoints",
        json={"url": "https://fail.local/api", "is_active": True},
    )
    ep_id = ep.json()["id"]

    endpoint = await _load_endpoint(db_session, ep_id)

    engine.client.get = AsyncMock(return_value=_mock_http_error(500))

    result = await engine.service(endpoint)

    assert result.is_available is False
    assert result.status_code == 500
    assert result.error_message is not None

    assert await _count_check_results(db_session, ep_id) == 1

    engine.notifier.send_notification.assert_called_once()
    call_args = engine.notifier.send_notification.call_args[0]
    assert call_args[2] == "DOWN"
    assert "admin@company.ru" in call_args[4]


# ---------------------------------------------------------------------------
# Тест 3: Сервис недоступен → через CHECK_INTERVAL снова недоступен
#         → уведомление отправлено только один раз
# ---------------------------------------------------------------------------
async def test_e2e_no_duplicate_down_notification(client, db_session, e2e_engine):
    engine = e2e_engine

    svc = await client.post(
        "/services",
        json={"name": "E2E Dedup Svc", "description": "Test"},
    )
    svc_id = svc.json()["id"]

    await client.post(
        f"/services/{svc_id}/responsible",
        json={"name": "OnCall", "email": "oncall@company.ru"},
    )

    ep = await client.post(
        f"/services/{svc_id}/endpoints",
        json={"url": "https://dedup.local/api", "is_active": True},
    )
    ep_id = ep.json()["id"]

    endpoint = await _load_endpoint(db_session, ep_id)

    engine.client.get = AsyncMock(return_value=_mock_http_error(500))

    await engine.service(endpoint)
    assert engine.notifier.send_notification.call_count == 1

    await engine.service(endpoint)
    assert engine.notifier.send_notification.call_count == 1, (
        "Повторное уведомление не должно отправляться в окне NOTIFY_REPEAT_MINUTES"
    )

    assert await _count_check_results(db_session, ep_id) == 2


# ---------------------------------------------------------------------------
# Тест 4: Сервис недоступен → стал доступен → отправлено уведомление
#         о восстановлении
# ---------------------------------------------------------------------------
async def test_e2e_recovery_notification_sent(client, db_session, e2e_engine):
    engine = e2e_engine

    svc = await client.post(
        "/services",
        json={"name": "E2E Recovery Svc", "description": "Test"},
    )
    svc_id = svc.json()["id"]

    await client.post(
        f"/services/{svc_id}/responsible",
        json={"name": "OnCall", "email": "oncall@company.ru"},
    )

    ep = await client.post(
        f"/services/{svc_id}/endpoints",
        json={"url": "https://rec.local/api", "is_active": True},
    )
    ep_id = ep.json()["id"]

    endpoint = await _load_endpoint(db_session, ep_id)

    engine.client.get = AsyncMock(return_value=_mock_http_error(500))
    await engine.service(endpoint)

    first_call_args = engine.notifier.send_notification.call_args[0]
    assert first_call_args[2] == "DOWN"

    engine.client.get = AsyncMock(return_value=_mock_http_ok(200))
    await engine.service(endpoint)

    assert engine.notifier.send_notification.call_count == 2
    second_call_args = engine.notifier.send_notification.call_args[0]
    assert second_call_args[2] == "UP"

    assert await _count_check_results(db_session, ep_id) == 2


# ---------------------------------------------------------------------------
# Доп. тест: Connection error записывается корректно (status_code=None)
# ---------------------------------------------------------------------------
async def test_e2e_connection_error_records_result(client, db_session, e2e_engine):
    engine = e2e_engine

    svc = await client.post(
        "/services",
        json={"name": "E2E ConnErr Svc", "description": "Test"},
    )
    svc_id = svc.json()["id"]

    ep = await client.post(
        f"/services/{svc_id}/endpoints",
        json={"url": "https://unreachable.local/h", "is_active": True},
    )
    ep_id = ep.json()["id"]

    endpoint = await _load_endpoint(db_session, ep_id)

    engine.client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    result = await engine.service(endpoint)

    assert result.is_available is False
    assert result.status_code is None
    assert result.error_message is not None
    assert "Connection error" in result.error_message

    assert await _count_check_results(db_session, ep_id) == 1


# ---------------------------------------------------------------------------
# Доп. тест: Неактивный эндпоинт не проверяется
# ---------------------------------------------------------------------------
async def test_e2e_inactive_endpoint_not_checked(client, db_session, e2e_engine):
    engine = e2e_engine

    svc = await client.post(
        "/services",
        json={"name": "E2E Inactive Svc", "description": "Test"},
    )
    svc_id = svc.json()["id"]

    ep = await client.post(
        f"/services/{svc_id}/endpoints",
        json={"url": "https://inactive.local/h", "is_active": False},
    )
    ep_id = ep.json()["id"]

    assert ep.status_code == 201

    engine.client.get = AsyncMock(return_value=_mock_http_ok(200))

    assert await _count_check_results(db_session, ep_id) == 0
    engine.client.get.assert_not_called()
