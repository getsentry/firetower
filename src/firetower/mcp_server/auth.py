"""Hop 1 auth: Google OAuth gated to the Sentry Google Workspace.

The Google ID token is signature-verified against Google's JWKS (audience = our
OAuth client id, issuer = accounts.google.com) and then gated on ``hd ==
sentry.io`` and ``email_verified`` during the federated login, before FastMCP
issues its own token. A per-tool fallback re-checks the embedded
``upstream_claims`` for defense in depth.
"""

import logging
from typing import Any

import jwt
from fastmcp.exceptions import FastMCPError
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.dependencies import get_access_token

from firetower.mcp_server.config import WORKSPACE_DOMAIN

logger = logging.getLogger(__name__)

GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class SentryGoogleProvider(GoogleProvider):
    """GoogleProvider that only admits verified @sentry.io Workspace accounts."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._expected_audience = kwargs.get("client_id")
        self._jwks_client = jwt.PyJWKClient(GOOGLE_JWKS_URI)

    async def _extract_upstream_claims(
        self, idp_tokens: dict[str, Any]
    ) -> dict[str, Any] | None:
        id_token = idp_tokens.get("id_token")
        if id_token is None:  # refresh exchange has no id_token; already gated at login
            return None

        signing_key = self._jwks_client.get_signing_key_from_jwt(id_token)
        try:
            claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._expected_audience,
            )
        except jwt.InvalidTokenError as exc:
            logger.info("Rejecting login: invalid Google id token: %s", exc)
            raise FastMCPError("Access denied: invalid Google identity token.") from exc

        if claims.get("iss") not in GOOGLE_ISSUERS:
            logger.info("Rejecting login: unexpected issuer %s", claims.get("iss"))
            raise FastMCPError("Access denied: unexpected token issuer.")
        if claims.get("hd") != WORKSPACE_DOMAIN or not claims.get("email_verified"):
            logger.info(
                "Rejecting login: hd=%s email_verified=%s",
                claims.get("hd"),
                claims.get("email_verified"),
            )
            raise FastMCPError(
                "Access denied: only verified @sentry.io accounts are allowed."
            )

        logger.info("Admitted login for %s", claims.get("email"))
        return {
            "hd": claims["hd"],
            "email": claims.get("email"),
            "email_verified": claims["email_verified"],
        }


def require_sentry_account() -> None:
    """Per-tool fallback gate (defense in depth) on the issued FastMCP token."""
    token = get_access_token()
    upstream = token.claims.get("upstream_claims") if token else None
    if (
        not upstream
        or upstream.get("hd") != WORKSPACE_DOMAIN
        or not upstream.get("email_verified")
    ):
        raise FastMCPError(
            "Access denied: only verified @sentry.io accounts are allowed."
        )
