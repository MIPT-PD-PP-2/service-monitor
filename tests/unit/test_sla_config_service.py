from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError
from app.schemas.sla_config import SlaConfigRequest
from app.services.sla_config_service import SlaConfigService


def _make_sla_config(config_id: int = 1, service_id: int = 1, target_percent: float = 99.0):
    config = AsyncMock()
    config.id = config_id
    config.service_id = service_id
    config.target_percent = target_percent
    return config


@pytest.fixture
def service():
    service = SlaConfigService.__new__(SlaConfigService)
    service.repo = AsyncMock()
    service.service_repo = AsyncMock()
    return service


async def test_upsert_for_service_creates_new(service):
    service.service_repo.get_by_id.return_value = AsyncMock(id=1)
    service.repo.get_by_service_id.return_value = None
    service.repo.create.return_value = _make_sla_config(target_percent=99.5)
    resp = await service.upsert_for_service(1, SlaConfigRequest(target_percent=99.5))

    assert resp.id == 1
    assert resp.target_percent == 99.5
    service.repo.create.assert_awaited_once()
    service.repo.update.assert_not_awaited()


async def test_upsert_for_service_updates_existing(service):
    service.service_repo.get_by_id.return_value = AsyncMock(id=1)
    existing = _make_sla_config(config_id=5, service_id=1, target_percent=95.0)
    service.repo.get_by_service_id.return_value = existing
    service.repo.update.return_value = _make_sla_config(config_id=5, service_id=1, target_percent=99.9)
    resp = await service.upsert_for_service(1, SlaConfigRequest(target_percent=99.9))

    assert resp.id == 5
    assert resp.target_percent == 99.9
    service.repo.update.assert_awaited_once_with(5, {"target_percent": 99.9})
    service.repo.create.assert_not_awaited()


async def test_upsert_for_service_unknown_service_raises(service):
    service.service_repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.upsert_for_service(999, SlaConfigRequest(target_percent=99.5))


async def test_get_by_service_id_existing_returns_config(service):
    service.service_repo.get_by_id.return_value = AsyncMock(id=5)
    expected = _make_sla_config(config_id=10, service_id=5, target_percent=99.9)
    service.repo.get_by_service_id.return_value = expected
    result = await service.get_by_service_id(5)

    assert result.id == 10
    assert result.service_id == 5
    assert result.target_percent == 99.9
    service.repo.get_by_service_id.assert_awaited_once_with(5)


async def test_get_by_service_id_not_configured_returns_none(service):
    service.service_repo.get_by_id.return_value = AsyncMock(id=3)
    service.repo.get_by_service_id.return_value = None
    result = await service.get_by_service_id(3)

    assert result is None


async def test_get_by_service_id_unknown_service_raises(service):
    service.service_repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.get_by_service_id(999)
