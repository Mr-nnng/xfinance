"""Map service errors to a stable JSON error shape."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..services.errors import ServiceError


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error(_request: Request, error: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status,
            content={"error": {"code": error.code, "message": error.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        messages = []
        for item in error.errors():
            location = ".".join(str(part) for part in item.get("loc", ())[1:])
            messages.append(f"{location}: {item.get('msg')}" if location else item.get("msg", ""))
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": "参数不合法",
                    "details": messages,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(
        request: Request, error: StarletteHTTPException
    ) -> JSONResponse:
        if request.url.path.startswith("/api"):
            return JSONResponse(
                status_code=error.status_code,
                content={
                    "error": {
                        "code": "not_found" if error.status_code == 404 else "http_error",
                        "message": str(error.detail),
                    }
                },
            )
        return JSONResponse(
            status_code=error.status_code, content={"detail": error.detail}
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, error: Exception) -> JSONResponse:
        logger.exception("unhandled error on {}: {}", request.url.path, error)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "服务器内部错误，请查看后端日志",
                }
            },
        )
