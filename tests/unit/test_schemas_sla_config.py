import pytest
from pydantic import ValidationError

from app.schemas.sla_config import SlaConfigRequest, SlaConfigResponse


def test_sla_config_request_valid():
    req = SlaConfigRequest(target_percent=95.0)
    assert req.target_percent == 95.0


def test_sla_config_request_missing_target_percent():
    req = SlaConfigRequest()
    assert req.target_percent == 99.0


def test_sla_config_request_validation_min_fails():
    with pytest.raises(ValidationError):
        SlaConfigRequest(target_percent=-5)


def test_sla_config_request_validation_max_fails():
    with pytest.raises(ValidationError):
        SlaConfigRequest(target_percent=105)


def test_sla_config_response_serialization():
    resp = SlaConfigResponse(
        id=5,
        service_id=1,
        target_percent=99.0
    )
    dumped = resp.model_dump()
    assert dumped["id"] == 5
    assert dumped["service_id"] == 1
    assert dumped["target_percent"] == 99.0
