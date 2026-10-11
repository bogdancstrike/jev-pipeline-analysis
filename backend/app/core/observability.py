"""Logging with a per-request id.

The id comes from the caller's `x-request-id` when it looks sane (nginx or a client can
set one), otherwise it is generated. It is echoed on the response and printed on every
log line written while the request is handled.
"""
import logging
import re
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "x-request-id"
_request_id: ContextVar[str] = ContextVar("request_id", default="-")
_VALID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s]: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())


class RequestIdMiddleware:
    """Pure ASGI (not BaseHTTPMiddleware) so it does not buffer the SSE stream."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(REQUEST_ID_HEADER.encode(), b"").decode("latin-1")
        rid = incoming if _VALID.match(incoming) else uuid.uuid4().hex
        token = _request_id.set(rid)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((REQUEST_ID_HEADER.encode(), rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            _request_id.reset(token)
