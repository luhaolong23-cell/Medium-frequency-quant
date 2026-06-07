from fastapi import FastAPI
from fastapi.responses import JSONResponse

from packages.shared.api_models import ApiError, ErrorDetail
from packages.shared.errors import AppError


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_, exc: AppError) -> JSONResponse:
        payload = ApiError(error=ErrorDetail(code=exc.code, message=exc.message))
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())
