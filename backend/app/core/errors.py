"""Domain errors and the handlers that turn them into HTTP.

Every failure leaves the API in one shape, `{error, message, details?}`, plus the
`x-request-id` header, so the UI has exactly one thing to parse and a failure on screen
carries an id that can be found in the logs.
"""
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    code = "error"
    status_code = 500

    def __init__(self, message: str = "", *, details: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None):
        super().__init__(message or self.code)
        self.message = message or self.code
        self.details = details or {}
        self.headers = headers or {}

    def body(self) -> dict[str, Any]:
        out: dict[str, Any] = {"error": self.code, "message": self.message}
        if self.details:
            out["details"] = self.details
        return out


class NotFound(AppError):
    code, status_code = "not_found", 404


class Conflict(AppError):
    code, status_code = "conflict", 409


class PayloadTooLarge(AppError):
    code, status_code = "payload_too_large", 413


class InvalidInput(AppError):
    """Well-formed request, unusable content (e.g. a CSV without a `text` column)."""
    code, status_code = "invalid_input", 422


class Unavailable(AppError):
    """Try again later: models still loading, or the server is busy."""
    code, status_code = "unavailable", 503


_HTTP_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 413: "payload_too_large"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, e: AppError) -> JSONResponse:
        return JSONResponse(e.body(), status_code=e.status_code, headers=e.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(err.get("loc", [])), "msg": err.get("msg", "")} for err in e.errors()]
        msg = "; ".join(f"{'.'.join(map(str, x['loc'][1:])) or 'request'}: {x['msg']}" for x in errors)
        return JSONResponse({"error": "validation_error", "message": msg or "invalid request",
                             "details": {"errors": errors}}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException) -> JSONResponse:
        return JSONResponse({"error": _HTTP_CODES.get(e.status_code, "error"), "message": str(e.detail)},
                            status_code=e.status_code, headers=getattr(e, "headers", None))
