# Firetower MCP Server — Design

Status: draft for review (2026-06-15)
Branch/worktree: `spalmurray/mcp` (`/Users/spencer/code/spalmurray/mcp`)

## Goal

Let users and agents (via Claude) query firetower incident data to ask questions
and gain insights. Read-only, **non-private incidents only**, exposed as a hosted
remote MCP server gated to Sentry Google Workspace accounts.

## Scope (decided)

- **Transport:** hosted remote MCP server, Streamable HTTP. New Cloud Run service,
  sibling to `firetower-slack-app` / `firetower-async`.
- **Operations:** read-only (v1). No create/update/status/tag-write, even though the
  SDK supports them.
- **Data:** non-private incidents only (`is_private = False`). NOTE: "non-private" means
  **org-confidential — visible to any authenticated Sentry employee, NOT public to the world.**
  So the `@sentry.io` gate is a real confidentiality boundary, not a convenience.
- **Identity:** single service identity for data access (Hop 2). Per-user login only
  gates access + provides an audit trail (Hop 1).

## Architecture — two auth hops

The IAP concern from the original idea dissolves: the server→firetower hop reuses the
existing programmatic auth path, and the client→server hop is standard remote-MCP OAuth.

```
Claude client ──OAuth (PKCE + audience-bound token)──▶ MCP server (our domain)
                                                          │ federates login to
                                                          ▼
                                                  Google  (Workspace, hd=sentry.io)
   server validates hd + email_verified, mints OUR short-lived audience-bound token
Claude client ──Bearer (our token)──▶ MCP server (resource server, validates token)
                                            │ Hop 2 — single service account
                                            ▼
                                      firetower API → non-private incidents only
```

- **Hop 1 (client → MCP server):** authenticate the *human* (gate + attribution). Per-user.
- **Hop 2 (MCP server → firetower):** serve *non-private (org-confidential) incident data* as
  one shared identity. Not per-user.

## Hop 1 — client → MCP server (OAuth, Google-gated)

Use **FastMCP** (`jlowin/fastmcp`, Python/Starlette/ASGI, production-grade). Its
`GoogleProvider` is built on the `OAuthProxy` pattern *specifically because Google lacks
Dynamic Client Registration* — it presents a spec-compliant face to Claude (DCR bridging,
PKCE/S256, RFC 9728 Protected Resource Metadata inherited from the official MCP SDK,
RFC 8414 AS metadata, audience-bound token issuance) while using our fixed Google client
credentials upstream.

```python
from fastmcp import FastMCP
from fastmcp.server.auth.providers.google import GoogleProvider

auth = GoogleProvider(client_id=..., client_secret=..., base_url=..., scopes=[...])
mcp = FastMCP(name="firetower", auth=auth)
```

What we build on top of the library:

1. **Workspace gate.** `GoogleProvider` gives "sign in with Google"; we enforce Sentry by
   validating the Google **ID token `hd` claim == sentry.io AND `email_verified`** during
   the federated login. The `hd` *request* param is only a UI hint (Google says don't trust
   it) — the signed *claim* is the gate. Gate on `hd`, **not** the email domain (Google:
   email domain is insufficient to prove org membership). Anchor identity on `sub` (+ the
   workspace id), not email.
   **Resolved (FastMCP v3.4.1 source):** no built-in `hd` enforcement, but there's a clean,
   documented hook. **Subclass `GoogleProvider` and override `_extract_upstream_claims(self,
   idp_tokens)`** — it runs after the Google code exchange and *before* FastMCP issues its own
   token (`oauth_proxy/proxy.py:1195` → `1200`). Decode the Google `id_token` (present because
   `openid` is a default scope), and **raise to reject** when `hd != "sentry.io"` or not
   `email_verified` — the FastMCP token is never minted. Return `{hd, email, email_verified}`
   so it propagates into the issued JWT (`upstream_claims`), readable by a per-tool
   `get_access_token().claims["upstream_claims"]` fallback check (defense in depth).
   Pin **FastMCP v3.4.1** (auth module is semver-exempt). Caveat: the refresh path has no
   `id_token` — guard with `if id_token is None: return None` (initial login already gated).
   **Implemented (`auth.py`):** the `id_token` is **signature-verified against Google's JWKS**
   (`jwt.PyJWKClient`), with **`aud` == our client_id** and **`iss` in {accounts.google.com,
   https://accounts.google.com}** checked, *then* the `hd`/`email_verified` gate. Since the
   data is org-confidential (not world-public), this is load-bearing, not optional.

   ```python
   import jwt
   from fastmcp.server.auth.providers.google import GoogleProvider
   from fastmcp.exceptions import FastMCPError

   GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
   GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

   class SentryGoogleProvider(GoogleProvider):
       def __init__(self, *a, **kw):
           super().__init__(*a, **kw)
           self._expected_audience = kw.get("client_id")
           self._jwks_client = jwt.PyJWKClient(GOOGLE_JWKS_URI)

       async def _extract_upstream_claims(self, idp_tokens: dict) -> dict | None:
           id_token = idp_tokens.get("id_token")
           if id_token is None:            # refresh exchange — already gated at login
               return None
           key = self._jwks_client.get_signing_key_from_jwt(id_token)
           try:
               c = jwt.decode(id_token, key.key, algorithms=["RS256"], audience=self._expected_audience)
           except jwt.InvalidTokenError as e:
               raise FastMCPError("Access denied: invalid Google identity token.") from e
           if c.get("iss") not in GOOGLE_ISSUERS:
               raise FastMCPError("Access denied: unexpected token issuer.")
           if c.get("hd") != "sentry.io" or not c.get("email_verified"):
               raise FastMCPError("Access denied: @sentry.io verified accounts only.")
           return {"hd": c["hd"], "email": c.get("email"), "email_verified": c["email_verified"]}
   ```
2. **Same-origin AS + resource server.** Known claude.ai bug: it ignores
   `authorization_endpoint`/`token_endpoint` from AS metadata and constructs `/authorize`
   and `/token` from the MCP server's base URL. Keep the AS endpoints on the *same origin*
   as the MCP server (one service) so claude.ai connectors work. (Claude Code does this
   correctly regardless.)

### Client support notes
- **Claude Code:** `claude mcp add --transport http <url>`; runs the browser OAuth flow,
  stores tokens locally; ephemeral `localhost:*` callback (accept any local port, or pin
  with `--callback-port`).
- **Claude.ai / Desktop connectors:** fixed callback `https://claude.ai/api/mcp/auth_callback`;
  tokens stored encrypted Anthropic-side. Acceptable, but note the data is org-confidential
  (not world-public), so this is a real (if modest) trust dependency, mitigated by read-only
  scope + short-lived audience-bound tokens.
- DCR is **SHOULD**, not MUST — Claude can also use CIMD or Anthropic-held creds, but the
  `GoogleProvider`/`OAuthProxy` DCR bridge covers it.
- Static bearer tokens are **not supported** by Claude clients — OAuth (or authless) only.
  Authless loses the gate, so OAuth it is.

## Primary consumer: `jr` (getsentry/junior)

The target client is Sentry's internal agent **jr** (Slack bot, Vercel-hosted, headless/
event-driven). Key facts that shape the design:

- **jr is already a remote MCP client over Streamable HTTP** (`@modelcontextprotocol/sdk`),
  with a **built-in OAuth client**: DCR + PKCE, `token_endpoint_auth_method: none` (public
  client). On a `401` it **pauses the run and DMs the triggering Slack user a Google
  authorize link**, then resumes after callback. Tokens cached per-user in Redis
  (`<userId>:<provider>`). → Our FastMCP `GoogleProvider` (OAuthProxy) is *exactly* the
  server shape jr expects. **No headless/service-token path needed.**
- **Identity is per-Slack-user, and that's fine here.** The human who consents is the
  triggering Sentry employee, so the `@sentry.io` `hd` gate applies cleanly and we get real
  attribution. Hop 2 still serves non-private incidents as the single SA regardless of who asked.
- **jr is on Vercel, not GCP** — it cannot present a Google service-account / IAP token. So
  Google service-to-service auth is a non-option for jr (irrelevant: Hop 1 is OAuth, and
  Hop 2's IAP is handled by *our* server's SA, not jr).
- **jr's `mcp.headers` config can't carry a bearer** (`Authorization` is a forbidden header
  name; no env interpolation). So "drop a static token in config" is out — OAuth is the path.
- **Integration surface:** a new declarative jr plugin — `plugin.yaml` with an `mcp:` block
  (`transport: http`, `url`, optional `allowedTools`), registered in the app's `plugins.ts`.
  A small PR to `getsentry/junior`. (A custom code plugin presenting a shared static bearer
  is the alternative if we ever want single-identity instead of per-user — not needed now.)
- **To verify:** FastMCP `OAuthProxy`/`GoogleProvider` accepts public-client DCR
  (`token_endpoint_auth_method: none`) + PKCE — the standard MCP-client registration shape.

## Hop 2 — MCP server → firetower (single SA, non-private only)

**Decision (recommended for v1): #1 — reuse the existing SDK / IAP path.**
The MCP server authenticates to firetower's IAP-protected API as a single Google service
account, exactly like `firetower_sdk` does today (SA-signed JWT, audience = IAP client ID).
IAP provisions the SA as a Django user. Because that user is captain/reporter/participant
of nothing, `Incident.filter_visible_to_user` returns **only non-private incidents** — the
privacy guarantee falls out for free, no new filter to maintain.

- ✅ Zero firetower changes, reuses a proven path.
- The "SA as a non-private-only Django user" is a feature here, not a hack.

Alternative considered — **#2: dedicated service-to-service auth in firetower** (Cloud Run
IAM, bypass IAP). Cleaner long-term internal API, but real firetower work + depends on
Cloud Run ingress settings. Defer unless an internal service API becomes worthwhile.

Rejected — **#3: direct DB/read-replica.** Bypasses serializers + the canonical visibility
filter; would force reimplementing the privacy gate. Too risky.

## Tool surface (read-only, v1)

**Constraint: wrap only methods that exist in `firetower_sdk` — no raw endpoint access.**
That keeps the server a pure SDK wrapper (no coupling to `_request`/URLs that could drift),
and the SDK already routes through `filter_visible_to_user`. The SDK's read methods are:

- `list_incidents` — filters: status, severity, service_tier, created_after/before, tags
  (affected_service / root_cause / impact_type / affected_region), captain, reporter; paginated.
- `get_incident(id)` — detail incl. participants, tags, external links, timeline milestones.

Deliberately **not** exposed (no SDK method): tags, users, availability — would require raw
endpoint calls, so out of scope until/unless the SDK adds them. (`get_incident_status` exists
in the SDK but needs the `view_all_incident_statuses` permission the SA won't have, and is
redundant with `get_incident` — omitted.)

## Data sensitivity & privacy guarantee

**"Non-private" ≠ public to the world.** A non-private incident is visible to *any
authenticated Sentry employee* (firetower's `filter_visible_to_user`: `is_private=False OR
captain/reporter/participant`). It is **org-confidential internal data**. Private incidents
(restricted to participants) are a further-restricted subset we never expose.

- **Single SA → only ever sees `is_private = False` incidents** via the canonical filter, so
  no *private* (participant-restricted) data reaches the MCP layer; no tool can leak it.
- **But the data we DO serve is still confidential to Sentry.** The `@sentry.io` Workspace
  gate is the boundary keeping it from non-employees — treat it, audience-bound tokens, short
  TTLs, and signature verification as **load-bearing**, not low-stakes. A leaked/mis-issued
  token would expose internal incident data to a non-employee (not catastrophic — it's
  incident metadata an ordinary employee already sees, not secrets/PII at scale — but it is a
  real confidentiality breach, so don't be cavalier about token handling).

## Security must-dos (from MCP auth spec + Google)

- **Audience binding (RFC 8707):** MCP server MUST reject tokens not issued for it; tokens
  audience-bound to the MCP server URI. (FastMCP handles issuance; verify enforcement.)
- **PKCE S256** on all auth requests (library-provided).
- **No token passthrough:** server mints its OWN tokens; never forwards the Google token
  upstream/downstream (confused-deputy / broken audit trail).
- **Confused-deputy:** `OAuthProxy` uses a static upstream Google client_id → spec requires
  per-client consent + CSRF/`state` protection. FastMCP handles most of this — verify.
- **Short-lived tokens + refresh rotation** (public clients); secure token storage.
- **HTTPS everywhere; exact redirect-uri matching; accept `localhost:*` for Claude Code.**
- **Workspace gate:** validate signed `hd` claim (== sentry.io) + `email_verified`; anchor
  on `sub` + workspace id, not email domain. (Caveat: domain-resale attacks exist — `hd`
  is necessary, not a perfect anchor; acceptable for read-only org-confidential incident data.)

## Deployment

- New Cloud Run service (e.g. `firetower-mcp-{test,prod}`), sibling to the slack bot.
- **Not** behind IAP (it has its own OAuth). Confirm ingress/LB wiring.
- Secrets: Google OAuth client id/secret; the firetower SA credentials for Hop 2.
- Reuse existing deploy workflow patterns (`.github/workflows/deploy.yml`).
- **Pin FastMCP to an exact version** — its `fastmcp.server.auth` module is semver-exempt
  (breaking changes possible even on patch releases).
- Production `GoogleProvider` config: set `jwt_signing_key` from env + persistent
  `client_storage` (otherwise tokens/registrations don't survive restarts).
- **Reverse-proxy gotcha (FastMCP #2889):** behind a path-rewriting LB/proxy, the RFC 9728
  `resource_metadata` URL in the `WWW-Authenticate` header can come out wrong. Set
  `base_url` correctly and verify the emitted metadata URL against the public origin.
- **OAuth client is console-only — NOT Terraformable.** Verified: there is no Terraform
  resource for a consumer "Web application" OAuth client (the lookalikes are all wrong —
  `google_iap_brand`/`google_iap_client` lock redirect URIs to IAP and are deprecated
  (shutdown Mar 2026); `google_iam_oauth_client`/`gcloud iam oauth-clients` are Workforce
  Identity Federation; `google_identity_platform_*` consume an existing client). Google
  exposes no public API for it (TF issues #6074, #16452 closed as not-possible). So:
  **create the Web OAuth client + consent screen by hand in the console** (consent =
  Internal → Workspace-gated, a free extra layer), then **store client_id/secret in Secret
  Manager via Terraform** (`google_secret_manager_secret` + `_version`) and reference from
  the Cloud Run service. The secret-management half is the only Terraformable part.
- **Two distinct redirect-URI concerns** (don't conflate):
  - *Google console* (upstream client): register `https://<our-origin>/auth/callback`
    (FastMCP default `redirect_path`), plus `https://claude.ai/api/mcp/auth_callback` and
    `https://claude.com/api/mcp/auth_callback`, plus `https://claude.ai`/`https://claude.com`
    as Authorized JavaScript origins. Loopback (`localhost`/`127.0.0.1`) needs no port
    enumeration — Google allows any loopback port.
  - *`MCP_ALLOWED_REDIRECT_URIS`* (FastMCP `allowed_client_redirect_uris`): validates the
    *downstream* MCP client callback (claude.ai/.com + localhost). FastMCP ≤3.1.1 had a bug
    rejecting dynamic-port loopback — watch for it on the pinned version.

## Open questions / to verify before coding

1. ~~FastMCP hook for the `hd` gate~~ — **resolved (v3.4.1):** subclass `GoogleProvider`,
   override `_extract_upstream_claims`, raise on `hd != sentry.io` / not `email_verified`;
   propagate claims for a per-tool fallback. Concrete code in the Hop 1 section.
2. RFC coverage — resolved: RFC 9728 PRM **confirmed implemented**; RFC 8707 resource
   indicators **confirmed** (auto-included). RFC 8414 AS metadata is very likely but not
   doc-confirmed — verify by curling `/.well-known/oauth-authorization-server` on a running
   instance.
3. Hop 2 SA mechanics: how `firetower_sdk` obtains SA creds + the IAP audience today; reuse
   directly vs. extract the auth into the MCP service.
4. Cloud Run ingress / load-balancer wiring for a new non-IAP service in the firetower project.
5. Rate limiting / abuse considerations for the MCP endpoint.
6. Confirm FastMCP `OAuthProxy` accepts jr's public-client DCR (`token_endpoint_auth_method:
   none`) + PKCE registration shape.
7. jr integration PR: declarative `mcp:` plugin in `getsentry/junior` pointing at the
   deployed server URL + `allowedTools`.

## Build checklist (phased)

- [ ] Spike (Hop 1 only — Hop 2 is proven by existing SA-through-IAP examples): FastMCP
      server with `GoogleProvider` + Workspace `hd` gate. Acceptance test: a **public-client
      DCR + PKCE** OAuth flow (jr's shape) completes against Google, a non-`@sentry.io`
      account is rejected, and an authenticated call reaches a trivial tool. Wire the SA→
      firetower call after, copying the existing example.
- [ ] Fill out the read-only tool surface.
- [ ] Token/audience validation + security checklist hardening.
- [ ] Cloud Run service + deploy workflow + secrets.
- [ ] Connect from Claude Code and a Claude.ai connector; verify the claude.ai same-origin
      behavior.
- [ ] Docs: how to add the connector.

## References

- MCP authorization spec (2025-06-18 / 2025-11-25): https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- MCP security best practices: https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices
- FastMCP auth: https://gofastmcp.com/servers/auth/authentication , https://gofastmcp.com/integrations/google
- Claude connector auth: https://claude.com/docs/connectors/building/authentication
- Google hd/email_verified verification: https://developers.google.com/identity/openid-connect/openid-connect
- Existing in-repo: `firetower_sdk` (Hop 2 auth precedent), `incidents/models.py::filter_visible_to_user` (privacy filter)
