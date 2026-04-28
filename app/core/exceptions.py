from fastapi import HTTPException


class NotFoundError(HTTPException):
    def __init__(self, detail: str = "Не найдено"):
        super().__init__(status_code=404, detail=detail)


class AlreadyExistsError(HTTPException):
    def __init__(self, detail: str = "Уже существует"):
        super().__init__(status_code=400, detail=detail)


class ConflictError(HTTPException):
    def __init__(self, detail: str = "Конфликт"):
        super().__init__(status_code=409, detail=detail)


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "Доступ запрещён"):
        super().__init__(status_code=403, detail=detail)


class UnprocessableError(HTTPException):
    def __init__(self, detail: str = "Невалидные данные"):
        super().__init__(status_code=422, detail=detail)
