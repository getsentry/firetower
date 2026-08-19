"""Integration tests for the Firetower MCP HTTP and OAuth routes."""

import re
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastmcp import settings as fastmcp_settings
from starlette.testclient import TestClient

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


@pytest.fixture
def mcp_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(fastmcp_settings, "home", tmp_path)
    config = MCPConfig(
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
    with TestClient(create_mcp(config).http_app(), follow_redirects=False) as client:
        yield client


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
    }


def test_unallowed_external_callback_fails_redirect_validation(
    mcp_client: TestClient,
):
    metadata = {**PI_DCR_METADATA, "redirect_uris": [UNALLOWED_CALLBACK]}
    registration_response = mcp_client.post("/register", json=metadata)

    assert registration_response.status_code == 201
    client_id = registration_response.json()["client_id"]
    assert isinstance(client_id, str)
    authorization_response = mcp_client.get(
        "/authorize", params=_authorization_params(client_id, UNALLOWED_CALLBACK)
    )

    assert authorization_response.status_code == 400
    assert "location" not in authorization_response.headers
    assert authorization_response.json() == {
        "error": "invalid_request",
        "error_description": (
            f"Redirect URI '{UNALLOWED_CALLBACK}' does not match allowed patterns."
        ),
        "state": "test-state",
    }
