from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError, UnprocessableError
from app.schemas.endpoints import EndpointRequest, EndpointUpdateRequest
from app.services.endpoint_service import EndpointService


def _make_endpoint(endpoint_id: int = 1, service_id: int = 1, url: str = "http://x.test/h"):
    ep = AsyncMock()
    ep.id = endpoint_id
    ep.service_id = service_id
    ep.url = url
    ep.is_active = True
    ep.created_at = datetime.now(timezone.utc)
    return ep


@pytest.fixture
def service():
    s = EndpointService.__new__(EndpointService)
    s.repo = AsyncMock()
    s.service_repo = AsyncMock()
    return s


async def test_create_success(service):
    service.service_repo.get_by_id.return_value = AsyncMock(id=1)
    service.repo.create.return_value = _make_endpoint()
    result = await service.create_for_service(1, EndpointRequest(url="http://x.test/h"))
    assert result["id"] == 1
    assert result["service_id"] == 1
    assert result["is_active"] is True


async def test_create_default_is_active_true(service):
    service.service_repo.get_by_id.return_value = AsyncMock(id=1)
    service.repo.create.return_value = _make_endpoint()
    await service.create_for_service(1, EndpointRequest(url="http://x.test/h"))
    call_args = service.repo.create.call_args[0][0]
    assert call_args["is_active"] is True


async def test_create_explicit_is_active_false(service):
    service.service_repo.get_by_id.return_value = AsyncMock(id=1)
    service.repo.create.return_value = _make_endpoint()
    await service.create_for_service(1, EndpointRequest(url="http://x.test/h", is_active=False))
    call_args = service.repo.create.call_args[0][0]
    assert call_args["is_active"] is False


async def test_create_unknown_service_raises(service):
    service.service_repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.create_for_service(999, EndpointRequest(url="http://x.test/h"))


async def test_create_invalid_url_no_scheme(service):
    service.service_repo.get_by_id.return_value = AsyncMock(id=1)
    with pytest.raises(UnprocessableError) as exc:
        await service.create_for_service(1, EndpointRequest(url="example.com/h"))
    assert "http://" in exc.value.detail


async def test_create_invalid_url_empty(service):
    service.service_repo.get_by_id.return_value = AsyncMock(id=1)
    with pytest.raises(UnprocessableError):
        await service.create_for_service(1, EndpointRequest(url="   "))


async def test_create_invalid_url_too_long(service):
    service.service_repo.get_by_id.return_value = AsyncMock(id=1)
    long_url = "http://" + ("a" * 2050)
    with pytest.raises(UnprocessableError):
        await service.create_for_service(1, EndpointRequest(url=long_url))


async def test_list_for_unknown_service(service):
    service.service_repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.list_for_service(999)


async def test_list_for_service_returns_dicts(service):
    service.service_repo.get_by_id.return_value = AsyncMock(id=1)
    service.repo.list_by_service.return_value = [
        _make_endpoint(endpoint_id=1, url="http://a.test/h"),
        _make_endpoint(endpoint_id=2, url="http://b.test/h"),
    ]
    result = await service.list_for_service(1)
    assert len(result) == 2
    assert result[0]["url"] == "http://a.test/h"


async def test_update_no_fields_raises(service):
    with pytest.raises(UnprocessableError) as exc:
        await service.update(1, EndpointUpdateRequest())
    assert exc.value.detail == "Нечего обновлять"


async def test_update_invalid_url_raises(service):
    with pytest.raises(UnprocessableError):
        await service.update(1, EndpointUpdateRequest(url="bad-url"))


async def test_update_missing_endpoint_raises(service):
    service.repo.update.return_value = None
    with pytest.raises(NotFoundError):
        await service.update(999, EndpointUpdateRequest(is_active=False))


async def test_update_only_is_active(service):
    service.repo.update.return_value = _make_endpoint()
    result = await service.update(1, EndpointUpdateRequest(is_active=False))
    call_args = service.repo.update.call_args[0]
    assert call_args[0] == 1
    assert call_args[1] == {"is_active": False}
    assert "url" not in call_args[1]
    assert result["id"] == 1


async def test_delete_missing_raises(service):
    service.repo.delete.return_value = False
    with pytest.raises(NotFoundError):
        await service.delete(999)


async def test_delete_success(service):
    service.repo.delete.return_value = True
    await service.delete(1)
    service.repo.delete.assert_awaited_once_with(1)
