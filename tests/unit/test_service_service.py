from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError
from pydantic import ValidationError

from app.schemas.services import ServiceRequest
from app.services.service_service import ServiceService


def _make_service(service_id: int = 1, name: str = "Payment", description: str = "desc"):
    svc = AsyncMock()
    svc.id = service_id
    svc.name = name
    svc.description = description
    svc.created_at = datetime.now(timezone.utc)
    return svc


@pytest.fixture
def service():
    s = ServiceService.__new__(ServiceService)
    s.repo = AsyncMock()
    return s


async def test_create_success(service):
    service.repo.create.return_value = _make_service()
    svc = await service.create(ServiceRequest(name="Payment", description="desc"))
    assert svc.id == 1
    assert svc.name == "Payment"
    service.repo.create.assert_awaited_once()


async def test_create_empty_name_raises():
    with pytest.raises(ValidationError):
        ServiceRequest(name="   ")


async def test_create_long_name_raises():
    with pytest.raises(ValidationError):
        ServiceRequest(name="A" * 300)


async def test_create_long_description_raises():
    with pytest.raises(ValidationError):
        ServiceRequest(name="ok", description="x" * 20_000)


async def test_get_missing_raises_not_found(service):
    service.repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError) as exc:
        await service.get(999)
    assert exc.value.status_code == 404


async def test_get_existing_returns_service(service):
    service.repo.get_by_id.return_value = _make_service(service_id=5, name="Auth")
    svc = await service.get(5)
    assert svc.id == 5
    assert svc.name == "Auth"


async def test_list_all_empty(service):
    service.repo.list_all.return_value = []
    result = await service.list_all()
    assert result == []


async def test_list_all_returns_services(service):
    service.repo.list_all.return_value = [
        _make_service(service_id=1, name="A"),
        _make_service(service_id=2, name="B"),
    ]
    result = await service.list_all()
    assert len(result) == 2
    assert result[0].name == "A"
    assert result[1].name == "B"


async def test_delete_missing_raises_not_found(service):
    service.repo.delete.return_value = False
    with pytest.raises(NotFoundError):
        await service.delete(999)


async def test_delete_success(service):
    service.repo.delete.return_value = True
    await service.delete(1)
    service.repo.delete.assert_awaited_once_with(1)
