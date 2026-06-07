class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class NotFoundError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(status_code=404, code=code, message=message)


class ValidationError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(status_code=400, code=code, message=message)
