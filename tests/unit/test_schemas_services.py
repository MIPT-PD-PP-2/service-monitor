from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.services import ServiceRequest, ServiceResponse


def test_service_request_minimal():
    req = ServiceRequest(name="Payment Gateway")
    assert req.name == "Payment Gateway"
    assert req.description is None


def test_service_request_full():
    req = ServiceRequest(name="Payment Gateway", description="Main payment service")
    assert req.description == "Main payment service"


def test_service_request_missing_name_fails():
    with pytest.raises(ValidationError):
        ServiceRequest()


def test_service_response_serialization():
    now = datetime.now(timezone.utc)
    resp = ServiceResponse(
        id=1,
        name="Payment Gateway",
        description="Main payment service",
        created_at=now,
    )
    dumped = resp.model_dump()
    assert dumped["id"] == 1
    assert dumped["name"] == "Payment Gateway"
    assert dumped["description"] == "Main payment service"
    assert dumped["created_at"] == now


def test_service_response_with_null_description():
    resp = ServiceResponse(
        id=2,
        name="Auth",
        description=None,
        created_at=datetime.now(timezone.utc),
    )
    assert resp.description is None
