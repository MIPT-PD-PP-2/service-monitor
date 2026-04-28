from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError
from app.schemas.responsible import ResponsibleRequest
from app.services.responsible_service import ResponsibleService


def _make_responsible(resp_id: int = 1, service_id: int = 1, name: str = "Ivan", email: str = "iv@test.ru"):
    r = AsyncMock()
    r.id = resp_id
    r.service_id = service_id
    r.name = name
    r.email = email
    return r


@pytest.fixture
def service():
    s = ResponsibleService.__new__(ResponsibleService)
    s.repo = AsyncMock()
    s.service_repo = AsyncMock()
    return s


async def test_create_success(service):
    service.service_repo.get_by_id.return_value = AsyncMock(id=1)
    service.repo.create.return_value = _make_responsible()
    resp = await service.create_for_service(1, ResponsibleRequest(name="Ivan", email="iv@test.ru"))
    assert resp.id == 1
    assert resp.service_id == 1
    assert resp.name == "Ivan"
    service.repo.create.assert_awaited_once()


async def test_create_unknown_service_raises(service):
    service.service_repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.create_for_service(999, ResponsibleRequest(name="Ivan", email="iv@test.ru"))


async def test_list_for_service_returns_responsibles(service):
    service.service_repo.get_by_id.return_value = AsyncMock(id=1)
    service.repo.list_by_service.return_value = [
        _make_responsible(resp_id=1, name="A"),
        _make_responsible(resp_id=2, name="B"),
    ]
    result = await service.list_for_service(1)
    assert len(result) == 2
    assert result[0].name == "A"
    assert result[1].name == "B"


async def test_list_for_unknown_service(service):
    service.service_repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.list_for_service(999)


async def test_delete_missing_raises(service):
    service.repo.delete.return_value = False
    with pytest.raises(NotFoundError):
        await service.delete(999)


async def test_delete_success(service):
    service.repo.delete.return_value = True
    await service.delete(1)
    service.repo.delete.assert_awaited_once_with(1)
