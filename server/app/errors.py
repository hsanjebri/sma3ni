"""The error envelope of `docs/API.md`, and the guard that keeps exceptions out of the logs."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.schemas import ErrorBody, ErrorCode, ErrorResponse

logger = logging.getLogger(__name__)

# HTTP status per error code, from the table in docs/API.md.
STATUS = {
    ErrorCode.INVALID_REQUEST: 400,
    ErrorCode.INVALID_AUDIO: 400,
    ErrorCode.UNSUPPORTED_FORMAT: 400,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.AUDIO_TOO_LARGE: 413,
    ErrorCode.AUDIO_TOO_LONG: 413,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.MODEL_LOADING: 503,
    ErrorCode.BUSY: 503,
}


class ApiError(Exception):
    """Raise anywhere in a request to answer with the contract's error envelope."""

    def __init__(
        self, code: ErrorCode, message: str, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.message = message
        self.headers = headers


def error_response(
    code: ErrorCode, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(
        status_code=STATUS[code], content=body.model_dump(mode="json"), headers=headers
    )


async def _handle_api_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return error_response(exc.code, exc.message, exc.headers)


async def _handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Field names only: FastAPI's default 422 body echoes the submitted values.
    fields = sorted({str(error["loc"][-1]) for error in exc.errors() if error.get("loc")})
    return error_response(
        ErrorCode.INVALID_REQUEST, f"Missing or invalid field: {', '.join(fields)}."
    )


class CatchAllMiddleware:
    """Answer any unhandled exception with `internal_error`, logging only its type.

    Starlette's own `Exception` handler re-raises after responding so the server
    can log the traceback, and an exception message can quote a transcript.
    Here the exception stops: only its class and the route are logged.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            logger.error(
                "unhandled %s on %s %s", type(exc).__name__, scope["method"], scope["path"]
            )
            if not started:
                response = error_response(ErrorCode.INTERNAL_ERROR, "Something went wrong.")
                await response(scope, receive, send)


def install_error_handling(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_middleware(CatchAllMiddleware)
