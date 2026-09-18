"""Hop 1 auth: Google OAuth gated to the Sentry Google Workspace.

The Google ID token is signature-verified against Google's JWKS (audience = our
OAuth client id, issuer = accounts.google.com) and then gated on ``hd ==
sentry.io`` and ``email_verified`` during the federated login, before FastMCP
issues its own token. A per-tool fallback re-checks the embedded
``upstream_claims`` for defense in depth.

Token refresh note: ``OAuthProxy`` re-calls ``_extract_upstream_claims`` on
every upstream refresh, passing the *merged* ``raw_token_data``. Google refresh
responses carry no ``id_token``, so the original login token is expired by then.
Initial login verifies its expiry normally. On refresh, an expired ID token is
accepted only after Google's token verifier confirms that the current access
token is active and belongs to the same verified identity and OAuth client.
"""

import logging
from typing import Any

import httpx
import jwt
from fastmcp.exceptions import FastMCPError
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.dependencies import get_access_token

from firetower.mcp_server.config import WORKSPACE_DOMAIN

logger = logging.getLogger(__name__)

GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
GOOGLE_GROUPS_LOOKUP_URL = "https://cloudidentity.googleapis.com/v1/groups:lookup"
GOOGLE_GROUPS_API_URL = "https://cloudidentity.googleapis.com/v1"
GOOGLE_GROUPS_READ_SCOPE = (
    "https://www.googleapis.com/auth/cloud-identity.groups.readonly"
)
ACCESS_GROUP = "team@sentry.io"


class GoogleGroupMembershipChecker:
    async def is_member(self, access_token: str, email: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"Authorization": f"Bearer {access_token}"}
                lookup = await client.get(
                    GOOGLE_GROUPS_LOOKUP_URL,
                    params={"groupKey.id": ACCESS_GROUP},
                    headers=headers,
                )
                if lookup.status_code != 200:
                    logger.info(
                        "Rejecting login: Google group lookup failed with %s",
                        lookup.status_code,
                    )
                    return False
                group_name = lookup.json().get("name")
                if not isinstance(group_name, str) or not group_name.startswith(
                    "groups/"
                ):
                    logger.info("Rejecting login: Google group lookup was malformed")
                    return False

                membership = await client.get(
                    f"{GOOGLE_GROUPS_API_URL}/{group_name}/memberships:checkTransitiveMembership",
                    params={"query": f"member_key_id == '{email}'"},
                    headers=headers,
                )
                return membership.status_code == 200 and (
                    membership.json().get("hasMembership") is True
                )
        except (httpx.HTTPError, ValueError):
            logger.info("Rejecting login: Google group membership check failed")
            return False


class SentryGoogleProvider(GoogleProvider):
    """GoogleProvider that only admits verified @sentry.io Workspace accounts."""

    def __init__(self, *, client_id: str, **kwargs: Any) -> None:
        if not client_id:
            raise ValueError("SentryGoogleProvider requires a non-empty client_id.")
        super().__init__(client_id=client_id, **kwargs)
        self._expected_audience = client_id
        self._jwks_client = jwt.PyJWKClient(GOOGLE_JWKS_URI)
        self._group_membership_checker = GoogleGroupMembershipChecker()

    async def _extract_upstream_claims(
        self, idp_tokens: dict[str, Any]
    ) -> dict[str, Any] | None:
        id_token = idp_tokens.get("id_token")
        if id_token is None:  # no id_token at all (e.g. non-OIDC refresh)
            return None

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(id_token)
            claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._expected_audience,
            )
        except jwt.ExpiredSignatureError:
            try:
                claims = jwt.decode(
                    id_token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=self._expected_audience,
                    options={"verify_exp": False, "verify_nbf": False},
                )
            except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
                logger.info("Rejecting refresh: invalid Google id token: %s", exc)
                raise FastMCPError(
                    "Access denied: invalid Google identity token."
                ) from exc
            await self._verify_refresh_identity(idp_tokens, claims)
        except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
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

        email = claims.get("email")
        access_token = idp_tokens.get("access_token")
        if (
            not isinstance(email, str)
            or not access_token
            or not await self._group_membership_checker.is_member(access_token, email)
        ):
            logger.info(
                "Rejecting login: %s is not a member of %s", email, ACCESS_GROUP
            )
            raise FastMCPError(
                f"Access denied: only members of {ACCESS_GROUP} are allowed."
            )

        logger.info("Admitted login for %s", email)
        return {
            "hd": claims["hd"],
            "email": email,
            "email_verified": claims["email_verified"],
            "group": ACCESS_GROUP,
        }

    async def _verify_refresh_identity(
        self, idp_tokens: dict[str, Any], id_token_claims: dict[str, Any]
    ) -> None:
        access_token = idp_tokens.get("access_token")
        verified = (
            await self._token_validator.verify_token(access_token)
            if access_token
            else None
        )
        claims = verified.claims if verified else {}
        if (
            claims.get("aud") != self._expected_audience
            or claims.get("email") != id_token_claims.get("email")
            or not claims.get("email_verified")
        ):
            logger.info("Rejecting refresh: current Google access token mismatch")
            raise FastMCPError("Access denied: invalid Google identity token.")


def require_sentry_account() -> None:
    """Per-tool fallback gate (defense in depth) on the issued FastMCP token."""
    token = get_access_token()
    upstream = token.claims.get("upstream_claims") if token else None
    if (
        not upstream
        or upstream.get("hd") != WORKSPACE_DOMAIN
        or not upstream.get("email_verified")
        or upstream.get("group") != ACCESS_GROUP
    ):
        raise FastMCPError(
            "Access denied: only verified @sentry.io accounts are allowed."
        )


def requester_email() -> str | None:
    """Verified email of the authenticated requester, for audit logging.

    Returns None outside a request context (e.g. in tests) so callers can log
    defensively without depending on the gate having run.
    """
    try:
        token = get_access_token()
    except Exception:
        return None
    upstream = token.claims.get("upstream_claims") if token else None
    return upstream.get("email") if upstream else None
