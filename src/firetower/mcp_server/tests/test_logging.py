import json
import logging
from collections.abc import AsyncIterator
from io import StringIO
from unittest.mock import MagicMock

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse, StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from firetower.mcp_server.logging import (
    JsonFormatter,
    RedactFastMCPOAuthFilter,
    SafeOAuthAccessLogMiddleware,
    configure_mcp_logging,
)


def test_json_formatter_preserves_structured_audit_fields():
    record = logging.LogRecord(
        name="firetower.mcp_server.tools",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="MCP tool call",
        args=(),
        exc_info=None,
    )
    record.event = "mcp_tool_call"
    record.actor_sub = "google-subject"
    record.params = {"incident_id": "INC-2000"}

    payload = json.loads(JsonFormatter().format(record))

    assert payload["severity"] == "INFO"
    assert payload["message"] == "MCP tool call"
    assert payload["event"] == "mcp_tool_call"
    assert payload["actor_sub"] == "google-subject"
    assert payload["params"] == {"incident_id": "INC-2000"}


def test_oauth_access_log_omits_query_parameters(monkeypatch):
    log = MagicMock()
    monkeypatch.setattr(
        logging.getLogger("firetower.mcp_server.oauth_access"), "info", log
    )

    async def callback(_request):
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[Route("/auth/callback", callback)],
        middleware=[Middleware(SafeOAuthAccessLogMiddleware)],
    )

    with TestClient(app) as client:
        response = client.get("/auth/callback?code=secret-code&state=secret-state")

    assert response.status_code == 200
    log.assert_called_once_with(
        "MCP OAuth request",
        extra={
            "event": "mcp_oauth_request",
            "method": "GET",
            "path": "/auth/callback",
            "status_code": 200,
        },
    )
    assert "secret-code" not in str(log.call_args)
    assert "secret-state" not in str(log.call_args)


def test_oauth_access_log_preserves_streaming_responses(monkeypatch):
    log = MagicMock()
    monkeypatch.setattr(
        logging.getLogger("firetower.mcp_server.oauth_access"), "info", log
    )

    async def stream() -> AsyncIterator[bytes]:
        yield b"first"
        yield b"second"

    async def callback(_request):
        return StreamingResponse(stream())

    app = Starlette(
        routes=[Route("/authorize", callback)],
        middleware=[Middleware(SafeOAuthAccessLogMiddleware)],
    )

    with TestClient(app) as client:
        response = client.get("/authorize?state=secret-state")

    assert response.status_code == 200
    assert response.content == b"firstsecond"
    log.assert_called_once()


def test_fastmcp_filter_redacts_oauth_transaction_identifier():
    record = logging.LogRecord(
        name="fastmcp.server.auth.oauth_proxy.proxy",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Consent binding cookie invalid for transaction %s",
        args=("sensitive-transaction-id",),
        exc_info=None,
    )

    assert RedactFastMCPOAuthFilter().filter(record)
    assert record.getMessage() == "OAuth transaction validation failed"


def test_fastmcp_filter_redacts_identity_provider_error():
    record = logging.LogRecord(
        name="fastmcp.server.auth.oauth_proxy.proxy",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="IdP token exchange failed: %s",
        args=("raw upstream response",),
        exc_info=None,
    )

    assert RedactFastMCPOAuthFilter().filter(record)
    assert record.getMessage() == "IdP token exchange failed"


def test_configure_logging_installs_filter_on_oauth_logger():
    loggers = [
        logging.getLogger(name)
        for name in (
            "firetower.mcp_server",
            "firetower_sdk",
            "fastmcp.server.auth.oauth_proxy",
        )
    ]
    original_states = [
        (list(logger.handlers), logger.propagate, logger.level) for logger in loggers
    ]

    try:
        configure_mcp_logging()

        oauth_logger = logging.getLogger("fastmcp.server.auth.oauth_proxy")
        assert oauth_logger.propagate is False
        assert len(oauth_logger.handlers) == 1

        handler = oauth_logger.handlers[0]
        assert any(
            isinstance(log_filter, RedactFastMCPOAuthFilter)
            for log_filter in handler.filters
        )

        output = StringIO()
        handler.setStream(output)
        record = logging.LogRecord(
            name="fastmcp.server.auth.oauth_proxy.proxy",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="IdP token exchange failed: %s",
            args=("raw upstream response",),
            exc_info=None,
        )
        handler.handle(record)

        payload = json.loads(output.getvalue())
        assert payload["message"] == "IdP token exchange failed"
        assert "raw upstream response" not in output.getvalue()
    finally:
        for logger, (handlers, propagate, level) in zip(
            loggers, original_states, strict=True
        ):
            logger.handlers = handlers
            logger.propagate = propagate
            logger.setLevel(level)
