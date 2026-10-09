import json
import logging
from unittest.mock import MagicMock

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from firetower.mcp_server.logging import (
    JsonFormatter,
    RedactFastMCPOAuthFilter,
    SafeOAuthAccessLogMiddleware,
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
