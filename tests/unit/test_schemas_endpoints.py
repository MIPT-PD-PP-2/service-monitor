from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.endpoints import EndpointRequest, EndpointResponse, EndpointUpdateRequest


def test_endpoint_request_default_active():
    req = EndpointRequest(url="http://example.com/health")
    assert req.url == "http://example.com/health"
    assert req.is_active is True


def test_endpoint_request_explicit_inactive():
    req = EndpointRequest(url="http://example.com/health", is_active=False)
    assert req.is_active is False


def test_endpoint_request_missing_url_fails():
    with pytest.raises(ValidationError):
        EndpointRequest()


def test_endpoint_update_all_optional():
    req = EndpointUpdateRequest()
    assert req.url is None
    assert req.is_active is None


def test_endpoint_update_partial():
    req = EndpointUpdateRequest(is_active=False)
    assert req.url is None
    assert req.is_active is False


def test_endpoint_response_serialization():
    now = datetime.now(timezone.utc)
    resp = EndpointResponse(
        id=10,
        service_id=1,
        url="http://example.com/health",
        is_active=True,
        created_at=now,
    )
    dumped = resp.model_dump()
    assert dumped["id"] == 10
    assert dumped["service_id"] == 1
    assert dumped["url"] == "http://example.com/health"
    assert dumped["is_active"] is True
    assert dumped["created_at"] == now
