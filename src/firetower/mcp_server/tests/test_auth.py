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
    signing_key=_KEY,
    aud=TEST_AUD,
    iss="https://accounts.google.com",
    exp=None,
    **claims,
):
    payload = {
        "aud": aud,
        "iss": iss,
        "exp": exp if exp is not None else int(time.time()) + 3600,
        **claims,
    }
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


def test_tolerates_token_set_without_id_token():
    # A token set with no id_token at all yields no claims (rather than raising).
    assert _extract({}) is None


def test_admits_refresh_with_access_token_and_no_id_token():
    # fastmcp re-extracts on refresh from the merged raw_token_data. A Google
    # refresh response carries an access_token but no id_token; if the merged set
    # has no id_token, we must NOT raise (would lock out the user).
    assert _extract({"access_token": "opaque-google-token"}) is None


def test_admits_refresh_with_expired_login_id_token():
    # The real refresh case: fastmcp merges {**stored, **refresh_response}, so the
    # ORIGINAL (now-expired) login id_token survives. We must still admit, since
    # the successful upstream refresh proves liveness and identity is immutable.
    expired = _id_token(
        exp=int(time.time()) - 3600,
        hd="sentry.io",
        email="a@sentry.io",
        email_verified=True,
    )
    assert _extract({"id_token": expired, "access_token": "opaque"}) == {
        "hd": "sentry.io",
        "email": "a@sentry.io",
        "email_verified": True,
    }


def test_rejects_expired_token_with_bad_signature():
    # Skipping exp must NOT weaken signature verification: an expired token signed
    # by the wrong key is still rejected.
    expired_bad = _id_token(
        signing_key=_OTHER_KEY,
        exp=int(time.time()) - 3600,
        hd="sentry.io",
        email_verified=True,
    )
    with pytest.raises(FastMCPError):
        _extract({"id_token": expired_bad}, jwks_public_key=_KEY.public_key())


def test_rejects_expired_token_for_wrong_domain():
    # Skipping exp must NOT weaken the domain gate either.
    expired_evil = _id_token(
        exp=int(time.time()) - 3600, hd="evil.com", email_verified=True
    )
    with pytest.raises(FastMCPError):
        _extract({"id_token": expired_evil})


def test_rejects_when_jwks_fetch_fails():
    # A transient JWKS fetch failure (or a token kid with no matching key) raises
    # jwt.PyJWKClientError, which is NOT a subclass of InvalidTokenError. It must
    # still surface as a controlled FastMCPError, not propagate raw.
    provider = _provider()
    provider._jwks_client.get_signing_key_from_jwt.side_effect = jwt.PyJWKClientError(
        "boom"
    )
    token = _id_token(hd="sentry.io", email="a@sentry.io", email_verified=True)
    with pytest.raises(FastMCPError):
        asyncio.run(provider._extract_upstream_claims({"id_token": token}))


def test_init_requires_client_id():
    with pytest.raises(ValueError):
        SentryGoogleProvider(client_id="", client_secret="x", base_url="https://x")


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
