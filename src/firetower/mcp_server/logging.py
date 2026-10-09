import json
import logging
from datetime import UTC, datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_STANDARD_LOG_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__) | {
    "asctime",
    "message",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in _STANDARD_LOG_RECORD_FIELDS and not key.startswith("_")
            }
        )
        return json.dumps(payload, default=str, separators=(",", ":"))


class SafeOAuthAccessLogMiddleware(BaseHTTPMiddleware):
    _SENSITIVE_PATHS = frozenset({"/authorize", "/consent", "/auth/callback"})

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        if request.url.path in self._SENSITIVE_PATHS:
            logging.getLogger("firetower.mcp_server.oauth_access").info(
                "MCP OAuth request",
                extra={
                    "event": "mcp_oauth_request",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )
        return response


class RedactFastMCPOAuthFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not record.name.startswith("fastmcp.server.auth.oauth_proxy"):
            return True

        message_template = str(record.msg)
        if (
            record.levelno >= logging.WARNING
            and "transaction" in message_template.lower()
        ):
            record.msg = "OAuth transaction validation failed"
            record.args = ()
        elif message_template.startswith("IdP token exchange failed:"):
            record.msg = "IdP token exchange failed"
            record.args = ()
        return True


def configure_mcp_logging() -> None:
    formatter = JsonFormatter()
    for logger_name in ("firetower.mcp_server", "firetower_sdk"):
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)

        logger = logging.getLogger(logger_name)
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)

    fastmcp_logger = logging.getLogger("fastmcp")
    for fastmcp_handler in fastmcp_logger.handlers:
        fastmcp_handler.addFilter(RedactFastMCPOAuthFilter())
