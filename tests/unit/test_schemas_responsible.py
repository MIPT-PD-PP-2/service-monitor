import pytest
from pydantic import ValidationError

from app.schemas.responsible import ResponsibleRequest, ResponsibleResponse


def test_responsible_request_valid():
    req = ResponsibleRequest(name="Ivan Ivanov", email="ivanov@company.ru")
    assert req.name == "Ivan Ivanov"
    assert req.email == "ivanov@company.ru"


def test_responsible_request_missing_name_fails():
    with pytest.raises(ValidationError):
        ResponsibleRequest(email="ivanov@company.ru")


def test_responsible_request_missing_email_fails():
    with pytest.raises(ValidationError):
        ResponsibleRequest(name="Ivan Ivanov")


def test_responsible_request_invalid_email_fails():
    with pytest.raises(ValidationError):
        ResponsibleRequest(name="Ivan Ivanov", email="not-an-email")


def test_responsible_request_empty_name_fails():
    with pytest.raises(ValidationError):
        ResponsibleRequest(name="", email="ivanov@company.ru")


def test_responsible_response_serialization():
    resp = ResponsibleResponse(
        id=5,
        service_id=1,
        name="Ivan Ivanov",
        email="ivanov@company.ru",
    )
    dumped = resp.model_dump()
    assert dumped["id"] == 5
    assert dumped["service_id"] == 1
    assert dumped["name"] == "Ivan Ivanov"
    assert dumped["email"] == "ivanov@company.ru"
