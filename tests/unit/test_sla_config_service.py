from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError
from app.schemas.sla_config import SlaConfigRequest
from app.services.sla_config_service import SlaConfigService


def _make_service(service_id: int = 1, name: str = "Payment Service"):
    service = AsyncMock()
    service.id = service_id
    service.name = name
    service.created_at = datetime.now(timezone.utc)
    return service


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


async def test_create_for_service_success(service):
    service.service_repo.get_by_id.return_value = _make_service(service_id=1)
    service.repo.create.return_value = _make_sla_config(target_percent=99.5)
    resp = await service.create_for_service(1, SlaConfigRequest(target_percent=99.5))

    assert resp.id == 1
    assert resp.service_id == 1
    assert resp.target_percent == 99.5
    service.repo.create.assert_awaited_once()


async def test_create_for_service_unknown_service_raises(service):
    service.service_repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.create_for_service(999, SlaConfigRequest(target_percent=99.5))


async def test_get_by_service_id_existing_returns_service(service):
    expected_config = _make_sla_config(config_id=10, service_id=5, target_percent=99.9)
    service.repo.get_by_service_id.return_value = expected_config
    svc = await service.get_by_service_id(5)

    assert svc.id == 10
    assert svc.service_id == 5
    assert svc.target_percent == 99.9
    service.repo.get_by_service_id.assert_awaited_once_with(5)


async def test_get_by_service_id_not_found_raises(service):
    service.repo.get_by_service_id.return_value = None
    with pytest.raises(NotFoundError) as exc:
        await service.get_by_service_id(999)

    assert exc.value.detail == "SLA config not found for this service"


async def test_create_for_service_with_default_target(service):
    service.service_repo.get_by_id.return_value = _make_service(service_id=1)
    service.repo.create.return_value = _make_sla_config(target_percent=99.0)
    resp = await service.create_for_service(1, SlaConfigRequest())

    assert resp.target_percent == 99.0
    service.repo.create.assert_awaited_once_with({
        "service_id": 1,
        "target_percent": 99.0
    })
