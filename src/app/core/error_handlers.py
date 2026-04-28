"""Global error handlers that normalize error responses to a common shape.

All API error responses are serialized as::

    {"message": "<human readable>", "errorCode": "<MACHINE_READABLE>"}

``errorCode`` defaults to the canonical HTTP status name (e.g. ``FORBIDDEN``,
``NOT_FOUND``).  Callers may override either field by raising
``HTTPException(detail={"message": "...", "errorCode": "..."})``.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request


def _default_error_code(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).name
    except ValueError:
        return "ERROR"


async def http_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)

    detail: Any = exc.detail
    body: dict[str, Any]

    if isinstance(detail, dict) and ("message" in detail or "errorCode" in detail):
        body = {
            "message": str(detail.get("message") or HTTPStatus(exc.status_code).phrase),
            "errorCode": str(
                detail.get("errorCode") or _default_error_code(exc.status_code)
            ),
        }
    else:
        body = {
            "message": (str(detail) if detail else HTTPStatus(exc.status_code).phrase),
            "errorCode": _default_error_code(exc.status_code),
        }

    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        headers=getattr(exc, "headers", None) or None,
    )


async def validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return JSONResponse(
        status_code=422,
        content={
            "message": "Request validation failed",
            "errorCode": "VALIDATION_ERROR",
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
