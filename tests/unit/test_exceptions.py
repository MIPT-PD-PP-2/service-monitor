from app.core.exceptions import (
    AlreadyExistsError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnprocessableError,
)


def test_not_found_default():
    err = NotFoundError()
    assert err.status_code == 404
    assert err.detail == "Not found"


def test_not_found_custom_detail():
    err = NotFoundError(detail="Service not found")
    assert err.status_code == 404
    assert err.detail == "Service not found"


def test_already_exists_default():
    err = AlreadyExistsError()
    assert err.status_code == 400
    assert err.detail == "Already exists"


def test_conflict_default():
    err = ConflictError()
    assert err.status_code == 409
    assert err.detail == "Conflict"


def test_forbidden_default():
    err = ForbiddenError()
    assert err.status_code == 403
    assert err.detail == "Forbidden"


def test_unprocessable_default():
    err = UnprocessableError()
    assert err.status_code == 422
    assert err.detail == "Unprocessable entity"


def test_unprocessable_custom_detail():
    err = UnprocessableError(detail="URL cannot be empty")
    assert err.status_code == 422
    assert err.detail == "URL cannot be empty"
