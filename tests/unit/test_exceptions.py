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
    assert err.detail == "Не найдено"


def test_not_found_custom_detail():
    err = NotFoundError(detail="Сервис не найден")
    assert err.status_code == 404
    assert err.detail == "Сервис не найден"


def test_already_exists_default():
    err = AlreadyExistsError()
    assert err.status_code == 400
    assert err.detail == "Уже существует"


def test_conflict_default():
    err = ConflictError()
    assert err.status_code == 409
    assert err.detail == "Конфликт"


def test_forbidden_default():
    err = ForbiddenError()
    assert err.status_code == 403
    assert err.detail == "Доступ запрещён"


def test_unprocessable_default():
    err = UnprocessableError()
    assert err.status_code == 422
    assert err.detail == "Невалидные данные"


def test_unprocessable_custom_detail():
    err = UnprocessableError(detail="URL не может быть пустым")
    assert err.status_code == 422
    assert err.detail == "URL не может быть пустым"
