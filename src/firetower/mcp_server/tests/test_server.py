"""Integration tests for the Firetower MCP HTTP and OAuth routes."""

import dataclasses
import http.server
import json
import logging
import re
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastmcp import settings as fastmcp_settings
from jwt.algorithms import RSAAlgorithm
from starlette.testclient import TestClient

from firetower.mcp_server import firetower, server
from firetower.mcp_server.auth import GOOGLE_GROUPS_READ_SCOPE
from firetower.mcp_server.branding import FIRETOWER_ICON
from firetower.mcp_server.config import MCPConfig
from firetower.mcp_server.server import create_mcp

PI_CALLBACK = "http://localhost:8910/oauth/callback"
PI_DCR_METADATA: dict[str, object] = {
    "redirect_uris": [PI_CALLBACK],
    "token_endpoint_auth_method": "none",
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
    "client_name": "pi mcp-client",
}
UNALLOWED_CALLBACK = "https://untrusted.example/oauth/callback"
BASE_URL = "https://mcp-test.firetower.getsentry.net"
BOT_ISSUER = "https://junior.example"
BOT_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
MCP_ACCEPT = {"Accept": "application/json, text/event-stream"}


@pytest.fixture
def mcp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MCPConfig:
    monkeypatch.setattr(fastmcp_settings, "home", tmp_path)
    return MCPConfig(
        google_client_id="test-client-id.apps.googleusercontent.com",
        google_client_secret="test-client-secret",
        base_url="https://mcp-test.firetower.getsentry.net",
        service_account="test@example.iam.gserviceaccount.com",
        firetower_url=None,
        jwt_signing_key="test-jwt-signing-key",
        allowed_redirect_uris=(
            "https://claude.ai/api/mcp/auth_callback",
            "https://claude.com/api/mcp/auth_callback",
            "http://localhost:*",
            "http://127.0.0.1:*",
        ),
        host="127.0.0.1",
        port=8080,
    )


@pytest.fixture
def mcp_client(mcp_config: MCPConfig) -> Iterator[TestClient]:
    with TestClient(
        create_mcp(mcp_config).http_app(), follow_redirects=False
    ) as client:
        yield client


class _JWKSServer(http.server.HTTPServer):
    requests = 0


@pytest.fixture
def bot_jwks_server() -> Iterator[_JWKSServer]:
    jwk = json.loads(RSAAlgorithm.to_jwk(BOT_KEY.public_key())) | {
        "kid": "junior-test",
        "alg": "RS256",
        "use": "sig",
    }
    body = json.dumps({"keys": [jwk]}).encode()

    class JWKSHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            server.requests += 1
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            pass

    server = _JWKSServer(("127.0.0.1", 0), JWKSHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()


@pytest.fixture
def bot_mcp_config(mcp_config: MCPConfig, bot_jwks_server: _JWKSServer) -> MCPConfig:
    return dataclasses.replace(
        mcp_config,
        bot_issuer=BOT_ISSUER,
        bot_jwks_url=f"http://127.0.0.1:{bot_jwks_server.server_port}/jwks.json",
    )


def _bot_token(
    client: TestClient,
    signing_key: rsa.RSAPrivateKey = BOT_KEY,
    kid: str = "junior-test",
) -> httpx.Response:
    registration = client.post(
        "/register",
        json={
            "client_name": "firetower",
            "redirect_uris": ["http://localhost"],
            "token_endpoint_auth_method": "none",
        },
    )
    client_id = registration.json()["client_id"]
    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": BOT_ISSUER,
            "sub": "firetower",
            "aud": f"{BASE_URL}/",
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid.uuid4()),
            "client_id": client_id,
            "resource": f"{BASE_URL}/mcp",
        },
        signing_key,
        algorithm="RS256",
        headers={"typ": "oauth-id-jag+jwt", "kid": kid},
    )
    return client.post(
        "/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
            "client_id": client_id,
        },
    )


def _mcp_result(response: httpx.Response) -> dict:
    assert response.status_code == 200, response.text
    if response.headers["content-type"].startswith("text/event-stream"):
        data = [
            line.removeprefix("data:").strip()
            for line in response.text.splitlines()
            if line.startswith("data:")
        ]
        return json.loads(data[-1])
    return response.json()


def _authorization_params(client_id: str, redirect_uri: str) -> dict[str, str]:
    return {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": "A" * 43,
        "code_challenge_method": "S256",
        "state": "test-state",
    }


def test_health_is_public_while_mcp_requires_oauth(mcp_client: TestClient):
    health_response = mcp_client.get("/health")
    mcp_response = mcp_client.get("/mcp")

    assert health_response.status_code == 200
    assert health_response.text == "ok"
    assert mcp_response.status_code == 401
    assert mcp_response.headers["www-authenticate"].startswith("Bearer ")


def test_favicon_is_public_and_firetower_branded(mcp_client: TestClient):
    response = mcp_client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert "<svg" in response.text


def test_oauth_metadata_disables_cimd(mcp_client: TestClient):
    response = mcp_client.get("/.well-known/oauth-authorization-server")

    assert response.status_code == 200
    assert response.json().get("client_id_metadata_document_supported") is not True


def test_pi_dcr_registration_accepts_loopback_callback(mcp_client: TestClient):
    registration_response = mcp_client.post("/register", json=PI_DCR_METADATA)

    assert registration_response.status_code == 201
    registration = registration_response.json()
    assert registration["client_name"] == "pi mcp-client"
    assert registration["token_endpoint_auth_method"] == "none"
    assert registration["grant_types"] == ["authorization_code", "refresh_token"]
    assert registration["response_types"] == ["code"]
    assert registration["redirect_uris"] == [PI_CALLBACK]
    assert "client_secret" not in registration

    client_id = registration["client_id"]
    assert isinstance(client_id, str)
    authorization_response = mcp_client.get(
        "/authorize", params=_authorization_params(client_id, PI_CALLBACK)
    )

    assert authorization_response.status_code == 302
    assert urlparse(authorization_response.headers["location"]).path == "/consent"


def test_google_authorization_requests_openid_and_email_scopes(
    mcp_client: TestClient,
):
    registration_response = mcp_client.post("/register", json=PI_DCR_METADATA)
    client_id = registration_response.json()["client_id"]
    authorization_response = mcp_client.get(
        "/authorize", params=_authorization_params(client_id, PI_CALLBACK)
    )
    consent_url = authorization_response.headers["location"]
    consent_response = mcp_client.get(consent_url)
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', consent_response.text)

    assert consent_response.status_code == 200
    assert csrf_token is not None
    assert 'alt="Firetower"' in consent_response.text
    assert f'src="{FIRETOWER_ICON.src}"' in consent_response.text
    assert (
        "https://gofastmcp.com/assets/brand/blue-logo.png" not in consent_response.text
    )
    consent_response = mcp_client.post(
        consent_url,
        data={
            "txn_id": parse_qs(urlparse(consent_url).query)["txn_id"][0],
            "csrf_token": csrf_token.group(1),
            "action": "approve",
        },
    )

    assert consent_response.status_code == 302
    google_authorization_url = urlparse(consent_response.headers["location"])
    assert google_authorization_url.netloc == "accounts.google.com"
    assert google_authorization_url.path == "/o/oauth2/v2/auth"
    assert set(parse_qs(google_authorization_url.query)["scope"][0].split()) == {
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        GOOGLE_GROUPS_READ_SCOPE,
    }


def test_unallowed_external_callback_is_rejected_at_registration(
    mcp_client: TestClient,
):
    metadata = {**PI_DCR_METADATA, "redirect_uris": [UNALLOWED_CALLBACK]}
    registration_response = mcp_client.post("/register", json=metadata)

    assert registration_response.status_code == 400
    assert "location" not in registration_response.headers


def test_server_uses_configured_logger_namespace():
    assert server.logger.name == "firetower.mcp_server.server"


def test_main_configures_audit_logging_and_disables_access_logs(monkeypatch):
    config = MagicMock(host="0.0.0.0", port=8080)
    mcp = MagicMock()
    configure_logging = MagicMock()
    monkeypatch.setattr(server, "configure_mcp_logging", configure_logging)
    monkeypatch.setattr(server.MCPConfig, "from_env", lambda: config)
    monkeypatch.setattr(server, "create_mcp", lambda _config: mcp)

    server.main()

    configure_logging.assert_called_once_with()
    mcp.run.assert_called_once()
    run_kwargs = mcp.run.call_args.kwargs
    assert run_kwargs["transport"] == "http"
    assert run_kwargs["host"] == "0.0.0.0"
    assert run_kwargs["port"] == 8080
    assert run_kwargs["uvicorn_config"] == {"access_log": False}
    assert len(run_kwargs["middleware"]) == 1
    assert run_kwargs["middleware"][0].cls is server.SafeOAuthAccessLogMiddleware


def test_bot_assertion_mints_token_that_can_call_read_tools(
    bot_mcp_config: MCPConfig,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    sdk = MagicMock()
    sdk.list_incidents.return_value = {"count": 0, "results": []}
    monkeypatch.setattr(firetower, "get_client", lambda: sdk)

    with TestClient(
        create_mcp(bot_mcp_config).http_app(), follow_redirects=False
    ) as client:
        assert (
            _bot_token(client, rsa.generate_private_key(65537, 2048)).status_code == 401
        )
        token_response = _bot_token(client)
        assert token_response.status_code == 200, token_response.text
        headers = {
            **MCP_ACCEPT,
            "Authorization": f"Bearer {token_response.json()['access_token']}",
        }
        init = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "junior", "version": "0"},
                },
            },
        )
        _mcp_result(init)
        if session_id := init.headers.get("mcp-session-id"):
            headers["mcp-session-id"] = session_id
        client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        with caplog.at_level(logging.INFO, logger="firetower.mcp_server.tools"):
            call = client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "list_incidents", "arguments": {}},
                },
            )

    result = _mcp_result(call)["result"]
    assert result.get("isError") is not True, result
    sdk.list_incidents.assert_called_once()
    [audit] = [
        r for r in caplog.records if getattr(r, "event", None) == "mcp_tool_call"
    ]
    assert audit.actor_sub == "bot:firetower"
    assert audit.actor_email is None


def test_unknown_bot_key_ids_do_not_refetch_jwks_during_cooldown(
    bot_mcp_config: MCPConfig, bot_jwks_server: _JWKSServer
):
    with TestClient(
        create_mcp(bot_mcp_config).http_app(), follow_redirects=False
    ) as client:
        responses = [
            _bot_token(client, kid=f"attacker-{uuid.uuid4()}") for _ in range(3)
        ]
        valid = _bot_token(client)

    assert [r.status_code for r in responses] == [401, 401, 401]
    assert valid.status_code == 200, valid.text
    assert bot_jwks_server.requests == 1


def test_bot_assertions_are_rejected_when_not_configured(
    mcp_client: TestClient,
):
    response = _bot_token(mcp_client)

    assert response.status_code == 400
    assert response.json()["error"] == "unsupported_grant_type"
