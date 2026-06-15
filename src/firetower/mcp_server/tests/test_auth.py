"""Tests for the @sentry.io Workspace gate (Hop 1), incl. signature verification."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastmcp.exceptions import FastMCPError

from firetower.mcp_server import auth
from firetower.mcp_server.auth import SentryGoogleProvider, require_sentry_account

TEST_AUD = "test-client-id.apps.googleusercontent.com"
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _id_token(
    signing_key=_KEY, aud=TEST_AUD, iss="https://accounts.google.com", **claims
):
    payload = {"aud": aud, "iss": iss, "exp": int(time.time()) + 3600, **claims}
    return jwt.encode(payload, signing_key, algorithm="RS256")


def _provider(jwks_public_key=None, audience=TEST_AUD):
    provider = object.__new__(SentryGoogleProvider)  # skip GoogleProvider.__init__
    provider._expected_audience = audience
    jwks = MagicMock()
    jwks.get_signing_key_from_jwt.return_value = SimpleNamespace(
        key=jwks_public_key or _KEY.public_key()
    )
    provider._jwks_client = jwks
    return provider


def _extract(idp_tokens: dict, **provider_kwargs) -> dict | None:
    return asyncio.run(
        _provider(**provider_kwargs)._extract_upstream_claims(idp_tokens)
    )


def test_admits_verified_sentry_account():
    token = _id_token(hd="sentry.io", email="a@sentry.io", email_verified=True)
    assert _extract({"id_token": token}) == {
        "hd": "sentry.io",
        "email": "a@sentry.io",
        "email_verified": True,
    }


def test_rejects_wrong_domain():
    token = _id_token(hd="evil.com", email="a@evil.com", email_verified=True)
    with pytest.raises(FastMCPError):
        _extract({"id_token": token})


def test_rejects_missing_hd():
    token = _id_token(email="a@gmail.com", email_verified=True)
    with pytest.raises(FastMCPError):
        _extract({"id_token": token})


def test_rejects_unverified_email():
    token = _id_token(hd="sentry.io", email="a@sentry.io", email_verified=False)
    with pytest.raises(FastMCPError):
        _extract({"id_token": token})


def test_rejects_bad_signature():
    # Signed with a key that does NOT match the JWKS public key.
    token = _id_token(signing_key=_OTHER_KEY, hd="sentry.io", email_verified=True)
    with pytest.raises(FastMCPError):
        _extract({"id_token": token}, jwks_public_key=_KEY.public_key())


def test_rejects_wrong_audience():
    token = _id_token(aud="some-other-client", hd="sentry.io", email_verified=True)
    with pytest.raises(FastMCPError):
        _extract({"id_token": token})


def test_rejects_wrong_issuer():
    token = _id_token(iss="https://evil.example", hd="sentry.io", email_verified=True)
    with pytest.raises(FastMCPError):
        _extract({"id_token": token})


def test_tolerates_refresh_without_id_token():
    assert _extract({}) is None


class _FakeToken:
    def __init__(self, claims: dict):
        self.claims = claims


def test_fallback_admits_sentry(monkeypatch):
    monkeypatch.setattr(
        auth,
        "get_access_token",
        lambda: _FakeToken(
            {"upstream_claims": {"hd": "sentry.io", "email_verified": True}}
        ),
    )
    require_sentry_account()  # no raise


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"upstream_claims": {"hd": "evil.com", "email_verified": True}},
        {"upstream_claims": {"hd": "sentry.io", "email_verified": False}},
    ],
)
def test_fallback_rejects(monkeypatch, claims):
    monkeypatch.setattr(auth, "get_access_token", lambda: _FakeToken(claims))
    with pytest.raises(FastMCPError):
        require_sentry_account()


def test_fallback_rejects_when_no_token(monkeypatch):
    monkeypatch.setattr(auth, "get_access_token", lambda: None)
    with pytest.raises(FastMCPError):
        require_sentry_account()
