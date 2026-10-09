import json
import logging
from datetime import UTC, datetime
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

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


class SafeOAuthAccessLogMiddleware:
    _SENSITIVE_PATHS = frozenset({"/authorize", "/consent", "/auth/callback"})

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] not in self._SENSITIVE_PATHS:
            await self.app(scope, receive, send)
            return

        async def send_with_access_log(message: Message) -> None:
            if message["type"] == "http.response.start":
                logging.getLogger("firetower.mcp_server.oauth_access").info(
                    "MCP OAuth request",
                    extra={
                        "event": "mcp_oauth_request",
                        "method": scope["method"],
                        "path": scope["path"],
                        "status_code": message["status"],
                    },
                )
            await send(message)

        await self.app(scope, receive, send_with_access_log)


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

    oauth_handler = logging.StreamHandler()
    oauth_handler.setFormatter(formatter)
    oauth_handler.addFilter(RedactFastMCPOAuthFilter())

    oauth_logger = logging.getLogger("fastmcp.server.auth.oauth_proxy")
    oauth_logger.handlers = [oauth_handler]
    oauth_logger.propagate = False
    oauth_logger.setLevel(logging.INFO)
