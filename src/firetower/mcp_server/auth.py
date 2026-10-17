"""Hop 1 auth: Google OAuth gated to the Sentry Google Workspace.

The Google ID token is signature-verified against Google's JWKS (audience = our
OAuth client id, issuer = accounts.google.com) and then gated on ``hd ==
sentry.io`` and ``email_verified`` during the federated login, before FastMCP
issues its own token. A per-tool fallback re-checks the embedded
``upstream_claims`` for defense in depth.

Bots (Junior) authenticate without a Google account via the RFC 7523 jwt-bearer
grant (SEP-990 ID-JAG): when configured, the token endpoint accepts short-lived
assertions signed by a trusted issuer whose JWKS we pin, and mints a FastMCP
token marked ``fastmcp_grant == "id_jag"``. Those tokens skip the Google gates
and are audited as ``bot:<subject>``.

Token refresh note: ``OAuthProxy`` re-calls ``_extract_upstream_claims`` on
every upstream refresh, passing the *merged* ``raw_token_data``. Google refresh
responses carry no ``id_token``, so the original login token is expired by then.
Initial login verifies its expiry normally. On refresh, an expired ID token is
accepted only after Google's token verifier confirms that the current access
token is active and belongs to the same verified identity and OAuth client.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any, TypeGuard

import httpx
import jwt
from fastmcp.exceptions import FastMCPError
from fastmcp.server.auth import AccessToken, IdentityAssertion
from fastmcp.server.auth.identity_assertion import IdentityAssertionValidator
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
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
BOT_GRANT = "id_jag"
BOT_JWKS_REFRESH_COOLDOWN_SECONDS = 30.0


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


class CooldownJWTVerifier(JWTVerifier):
    """JWTVerifier that rate-limits JWKS refreshes triggered by unknown key IDs.

    FastMCP's ``JWTVerifier._get_jwks_key`` refetches the JWKS whenever a token's
    ``kid`` is not cached, before any signature check, so unauthenticated callers
    could make us fetch the bot issuer's JWKS once per request by sending random
    ``kid`` values. Here, cached keys stay on the fast path; any refresh is
    serialized behind a lock and allowed at most once per cooldown globally, so
    distinct attacker key IDs cannot fan out and none of them are retained. A
    legitimately rotated key becomes usable after at most one cooldown.

    Relies on FastMCP 4.0.10 internals: ``_get_jwks_key``, ``_jwks_cache``,
    ``_jwks_cache_time``, and ``_cache_ttl``.
    """

    def __init__(
        self,
        *,
        refresh_cooldown_seconds: float = BOT_JWKS_REFRESH_COOLDOWN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._refresh_cooldown_seconds = refresh_cooldown_seconds
        self._clock = clock
        self._refresh_lock = asyncio.Lock()
        self._last_refresh_at: float | None = None

    def _has_cached_key(self, kid: str | None) -> bool:
        if time.time() - self._jwks_cache_time >= self._cache_ttl:
            return False
        if kid:
            return kid in self._jwks_cache
        return len(self._jwks_cache) == 1

    async def _get_jwks_key(self, kid: str | None) -> str:
        if self._has_cached_key(kid):
            return await super()._get_jwks_key(kid)
        async with self._refresh_lock:
            if self._has_cached_key(kid):
                return await super()._get_jwks_key(kid)
            now = self._clock()
            if (
                self._last_refresh_at is not None
                and now - self._last_refresh_at < self._refresh_cooldown_seconds
            ):
                raise ValueError("Unknown JWKS key ID; refresh is cooling down")
            self._last_refresh_at = now
            return await super()._get_jwks_key(kid)


class CooldownIdentityAssertionValidator(IdentityAssertionValidator):
    """IdentityAssertionValidator whose per-issuer verifiers rate-limit JWKS refreshes.

    Mirrors FastMCP 4.0.10's private ``_get_verifier`` (lazy, cached per issuer
    in ``_verifiers``), swapping in ``CooldownJWTVerifier``.
    """

    async def _get_verifier(self, issuer: str) -> JWTVerifier:
        verifier = self._verifiers.get(issuer)
        if verifier is not None:
            return verifier
        jwks_uri = (self.config.jwks_uris or {}).get(
            issuer
        ) or await self._discover_jwks_uri(issuer)
        verifier = CooldownJWTVerifier(
            jwks_uri=jwks_uri,
            issuer=issuer,
            audience=self.audience,
            algorithm=(self.config.algorithms or {}).get(issuer, self.config.algorithm),
        )
        self._verifiers[issuer] = verifier
        return verifier


class SentryGoogleProvider(GoogleProvider):
    """GoogleProvider that only admits verified @sentry.io Workspace accounts."""

    def __init__(
        self,
        *,
        client_id: str,
        identity_assertion: IdentityAssertion | None = None,
        **kwargs: Any,
    ) -> None:
        if not client_id:
            raise ValueError("SentryGoogleProvider requires a non-empty client_id.")
        super().__init__(client_id=client_id, **kwargs)
        # GoogleProvider does not forward identity_assertion to OAuthProxy, so
        # mirror OAuthProxy.__init__'s wiring to enable the jwt-bearer grant.
        if identity_assertion is not None:
            self._identity_assertion = identity_assertion
            self._identity_assertion_validator = CooldownIdentityAssertionValidator(
                config=identity_assertion, audience=str(self.issuer_url)
            )
        self._expected_audience = client_id
        self._jwks_client = jwt.PyJWKClient(GOOGLE_JWKS_URI)
        self._group_membership_checker = GoogleGroupMembershipChecker()

    async def verify_token(self, token: str) -> AccessToken | None:
        """Grant bot tokens the baseline scopes; they carry no Google scopes.

        The bot's trust decision already happened at the token endpoint, where
        its assertion was verified against the pinned issuer's JWKS.
        """
        result = await super().verify_token(token)
        if _is_bot(result):
            return result.model_copy(
                update={"scopes": list(self.required_scopes or [])}
            )
        return result

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
        subject = claims.get("sub")
        access_token = idp_tokens.get("access_token")
        if (
            not isinstance(email, str)
            or not isinstance(subject, str)
            or not subject
            or not access_token
            or not await self._group_membership_checker.is_member(access_token, email)
        ):
            logger.info(
                "Rejecting login: %s is not a member of %s", email, ACCESS_GROUP
            )
            raise FastMCPError(
                f"Access denied: only members of {ACCESS_GROUP} are allowed."
            )

        logger.info(
            "Admitted MCP login",
            extra={
                "event": "mcp_login_admitted",
                "actor_email": email,
                "actor_sub": subject,
            },
        )
        return {
            "sub": subject,
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
            or claims.get("sub") != id_token_claims.get("sub")
            or claims.get("email") != id_token_claims.get("email")
            or not claims.get("email_verified")
        ):
            logger.info("Rejecting refresh: current Google access token mismatch")
            raise FastMCPError("Access denied: invalid Google identity token.")


def _is_bot(token: AccessToken | None) -> TypeGuard[AccessToken]:
    return token is not None and token.claims.get("fastmcp_grant") == BOT_GRANT


def require_sentry_account() -> None:
    """Per-tool fallback gate (defense in depth) on the issued FastMCP token.

    Bot tokens are admitted: they can only be minted by our token endpoint after
    the assertion verified against a pinned trusted issuer's JWKS.
    """
    token = get_access_token()
    if _is_bot(token):
        return
    upstream = token.claims.get("upstream_claims") if token else None
    if (
        not upstream
        or not isinstance(upstream.get("sub"), str)
        or not upstream["sub"]
        or upstream.get("hd") != WORKSPACE_DOMAIN
        or not upstream.get("email_verified")
        or upstream.get("group") != ACCESS_GROUP
    ):
        raise FastMCPError(
            "Access denied: only verified @sentry.io accounts are allowed."
        )


def _requester_claim(claim: str) -> str | None:
    try:
        token = get_access_token()
    except Exception:
        return None
    if _is_bot(token):
        if claim != "sub":
            return None
        return f"bot:{token.subject or token.claims.get('sub')}"
    upstream = token.claims.get("upstream_claims") if token else None
    value = upstream.get(claim) if upstream else None
    return value if isinstance(value, str) else None


def requester_email() -> str | None:
    """Verified email of the authenticated requester (None for bots), for audit logging."""
    return _requester_claim("email")


def requester_subject() -> str | None:
    """Immutable Google subject of the requester, or ``bot:<subject>`` for bot
    tokens, for audit logging."""
    return _requester_claim("sub")
