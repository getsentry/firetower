# Firetower MCP Server — Design

Status: design resolved, built + dual-reviewed; pending deploy (2026-06-16)
Branch/worktree: `spalmurray/mcp` (`/Users/spencer/code/spalmurray/mcp`); terraform on
`spalmurray/firetower-mcp` in `~/code/ops` (`terraform/eng-tools/firetower/`)

## Goal

Let users and agents (including pi, Claude, and other standards-compliant MCP
clients) query firetower incident data to ask questions and gain insights. Read-only,
**non-private incidents only**, exposed as a hosted remote MCP server gated to Sentry
Google Workspace accounts.

## Scope (decided)

- **Transport:** hosted remote MCP server, Streamable HTTP. New Cloud Run service,
  sibling to `firetower-slack-app` / `firetower-async`.
- **Operations:** read-only (v1). No create/update/status/tag-write, even though the
  SDK supports them. An explicit unauthenticated `GET /health` returns a small 200
  response for service probes; the `/mcp` transport remains OAuth-protected.
- **Data:** non-private incidents only (`is_private = False`). NOTE: "non-private" means
  **org-confidential — visible to any authenticated Sentry employee, NOT public to the world.**
  So the `@sentry.io` gate is a real confidentiality boundary, not a convenience.
- **Identity:** single service identity for data access (Hop 2). Per-user login only
  gates access + provides an audit trail (Hop 1).
- **Access & governance (resolved):**
  - **Open to all verified `@sentry.io` Workspace accounts** — no allowlist beyond the `hd`
    gate. Non-private incident metadata is data any employee already sees.
  - **LLM egress is compliance-cleared** — sending this data to Claude (and later other
    models) raises no new concern beyond existing compliance discussions. No field redaction.
  - **Per-user audit logging is implemented** (`tools.py::_audit`): logs the verified
    requester email + tool + non-None params on every call, since firetower's own logs only
    see the shared SA. This is where per-user attribution lives.
  - **No per-user revocation mechanism, and none needed** — offboarding via Google account
    deactivation is the kill switch (sessions die within ~1h once the refresh stops working,
    see "Auth on key/account loss" below). Revoking the single Google OAuth client / SA
    revokes everyone at once if ever required.

## Architecture — two auth hops

The IAP concern from the original idea dissolves: the server→firetower hop reuses the
existing programmatic auth path, and the client→server hop is standard remote-MCP OAuth.

```
MCP client ──OAuth (PKCE + audience-bound token)──▶ MCP server (our domain)
                                                       │ federates login to
                                                       ▼
                                               Google  (Workspace, hd=sentry.io)
server validates hd + email_verified, mints OUR short-lived audience-bound token
MCP client ──Bearer (our token)──▶ MCP server (resource server, validates token)
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
Dynamic Client Registration* — it presents a spec-compliant face to MCP clients (DCR
bridging, PKCE/S256, RFC 9728 Protected Resource Metadata inherited from the official MCP SDK,
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
   Track latest **fastmcp** (`>=3.4.1` floor) — Dependabot opens bump PRs (no auto-merge);
   re-run the auth tests + a live OAuth/refresh smoke on each bump, since this hook rides
   `OAuthProxy` internals that are semver-exempt. Caveat: the refresh path has no `id_token`
   — guard with `if id_token is None: return None` (initial login already gated).
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
- **Native MCP clients:** standards-compliant DCR/CIMD + PKCE clients can use an HTTP
  loopback callback on any port. The allowlist covers `localhost` and `127.0.0.1`
  explicitly; it does not permit custom schemes, non-loopback HTTP, or arbitrary HTTPS.
- **pi:** registers as the public DCR client `pi mcp-client` with
  `token_endpoint_auth_method: none`, authorization-code + refresh-token grants, response
  type `code`, and callback `http://localhost:8910/oauth/callback`. This exact flow has an
  integration regression test.
- **Claude Code:** `claude mcp add --transport http <url>` runs the same browser OAuth flow,
  stores tokens locally, and uses an ephemeral loopback callback.
- **Claude.ai / Desktop connectors:** fixed callbacks under
  `https://claude.ai/api/mcp/auth_callback` and `https://claude.com/api/mcp/auth_callback`
  are explicitly trusted; tokens are stored encrypted Anthropic-side. The data is
  org-confidential, so this is a real trust dependency, mitigated by read-only scope and
  short-lived audience-bound tokens.
- DCR is **SHOULD**, not MUST. FastMCP keeps both standard DCR and CIMD enabled.
- Static bearer tokens are not the integration path; authless access would lose the
  Workspace gate, so clients use OAuth.

## Client rollout

The server supports standards-compliant native clients (including pi and Claude Code) and
explicitly trusted hosted Claude callbacks from the first test deployment. `jr` remains the
next client integration; adding a hosted client requires an explicit downstream callback
allowlist entry, while safe native loopback clients need no per-client entry. No downstream
MCP callback is registered in the Google console.

### Phase 2 client: `jr` (getsentry/junior)

**jr** is Sentry's internal agent (Slack bot, Vercel-hosted, headless/event-driven). It's
the natural second client; the facts below confirm our server shape already fits it:

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
- **HTTPS everywhere; validate redirect URIs; accept loopback HTTP only for native clients.**
- **Workspace gate:** validate signed `hd` claim (== sentry.io) + `email_verified`; anchor
  on `sub` + workspace id, not email domain. (Caveat: domain-resale attacks exist — `hd`
  is necessary, not a perfect anchor; acceptable for read-only org-confidential incident data.)

## Deployment

- One test-only Cloud Run service, `firetower-mcp-test`, sibling to the slack bot. There
  is deliberately no production MCP deploy job in the Firetower workflow yet.
- **Not** behind IAP (it has its own OAuth). Confirm ingress/LB wiring.
- Cloud Run and load-balancer probes use the public `GET /health` route. Authentication
  middleware still protects `/mcp`; the route test asserts both behaviors together.
- Secrets: Google OAuth client id/secret; the firetower SA credentials for Hop 2.
- `docker/mcp.Dockerfile` builds the server and in-repo SDK into a dedicated image tagged
  `firetower-mcp:${{ github.sha }}`. It installs the `mcp` dependency group, not `prod`, runs as
  the existing UID 1100 user, and keeps Datadog's native serverless-init wrapper. The MCP
  entrypoint therefore invokes Python directly instead of using unavailable `ddtrace-run`.
- The ordinary backend image no longer copies the SDK or installs the MCP dependency group.
- **FastMCP dependency policy (resolved): track latest, don't dependency-pin.** Floor at
  `fastmcp>=3.4.1`; **Dependabot** (uv ecosystem, `.github/dependabot.yml`) opens weekly bump
  PRs — **no auto-merge**. On each fastmcp bump, re-run the auth unit tests and do a live
  OAuth + token-refresh smoke, because the `hd` hook depends on `OAuthProxy` internals that
  are semver-exempt. (Earlier drafts said "pin to an exact version" — reversed: we'd rather
  stay current and absorb the occasional break behind a reviewed PR than freeze.)
- **`jwt_signing_key` from env (stable across restarts).** Set it from Secret Manager so a
  restart doesn't invalidate already-issued FastMCP tokens via a new signing key.
- **No persistent `client_storage` in v1 — and that's deliberate.** FastMCP reference tokens
  do a hard `client_storage` lookup on *every* request, so losing the per-instance store
  breaks all active sessions immediately, not gracefully. The dedicated image prevents
  ordinary Firetower releases from restarting MCP; the deploy gate below limits MCP
  restarts to its own changes. Revisit persistent storage only if restart frequency becomes
  a problem.
- **Build/deploy gate (resolved):** `deploy.yml` git-diffs `src/firetower/mcp_server/`,
  `sdk/`, `docker/mcp.Dockerfile`, `docker/entrypoint.sh`, `pyproject.toml`, `uv.lock`, and
  the workflow itself. Relevant pushes build and push `MCP_IMAGE_REF`; manual runs always
  count as changed. A separate `deploy-mcp-test` job consumes that image, while the ordinary
  backend/static build and deployment matrix remain unchanged and no production MCP job is
  present.
- **Bootstrap flow:** manual input `mcp_build_only=true` builds and pushes only the MCP image;
  it skips the backend/static build, migrations, and every service deploy. Use this once to
  make the SHA-tagged Artifact Registry image exist before Terraform creates Cloud Run.
- **Observability (resolved):** Datadog via serverless-init (`DD_API_KEY`/`DD_APP_KEY` env on
  the test MCP service, mirroring the slack/async siblings) + Cloud Logging for structured
  audit lines. Per-request token validation cost (FastMCP's `client_storage` lookup and any
  tokeninfo call) is accepted — request volume is low.
- **Cloud Armor (resolved — required, house convention):** a dedicated
  `google_compute_security_policy "firetower-mcp-security-policy"` attached to the MCP test
  backend — adaptive L7 DDoS protection (PREMIUM), a per-IP rate-limit throttle
  (10000/10s → deny 429), and a catch-all allow rule at the lowest priority. Public-facing
  IPs get Cloud Armor per the ⛅ Notion convention; this is the one public firetower surface,
  so it gets a policy of its own (the IAP-protected services don't need one).
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
  - *Google console* (upstream client): register exactly the single callback FastMCP uses
    with Google: `https://mcp.test.firetower.getsentry.net/auth/callback`. Google always
    returns to the proxy at that URL; it never calls pi, Claude, or another downstream MCP
    client's callback directly.
  - *`MCP_ALLOWED_REDIRECT_URIS`* (FastMCP `allowed_client_redirect_uris`): validates each
    *downstream* MCP client callback. Set it to
    `https://claude.ai/api/mcp/auth_callback,https://claude.com/api/mcp/auth_callback,http://localhost:*,http://127.0.0.1:*`.
    The loopback patterns support native clients such as pi without accepting arbitrary
    schemes or external hosts; hosted callbacks remain explicitly trusted. **Verified
    against locked FastMCP 3.4.1:** the matcher is component-wise, and port `*` plus
    root-path-matches-any handles ephemeral loopback ports. Leaving the option as `None`
    is unsafe: 3.4.1 accepts `javascript:` and non-loopback HTTP in that mode. An empty list
    blocks all callbacks; `config.py` requires a non-empty value so neither state happens
    accidentally.

## Auth on key/account loss (offboarding + kill switches)

- **Offboarding a user:** deactivating their Google Workspace account is the kill switch.
  Their existing FastMCP token keeps working only until its short TTL expires, and the next
  upstream refresh fails (Google rejects the deactivated account) → the session dies within
  **~1h**. No per-user revocation endpoint needed.
- **Losing the in-memory token store** (instance restart with no persistence): breaks *all*
  active sessions immediately — every request does a hard `client_storage` lookup. Mitigated
  by the deploy gate (restarts are rare). Users just re-auth.
- **Rotating the Google OAuth client secret / SA key:** the client secret rotation forces all
  clients to re-auth (acceptable, rare); the Hop 2 SA key rotation is transparent to clients.
- **Global kill switch:** disable the Google OAuth client (or the firetower-api-mcp SA) to cut
  everyone off at once.

## Open questions / to verify before coding

1. ~~FastMCP hook for the `hd` gate~~ — **resolved (v3.4.1):** subclass `GoogleProvider`,
   override `_extract_upstream_claims`, raise on `hd != sentry.io` / not `email_verified`;
   propagate claims for a per-tool fallback. Concrete code in the Hop 1 section.
2. RFC coverage — resolved: RFC 9728 PRM **confirmed implemented**; RFC 8707 resource
   indicators **confirmed** (auto-included). RFC 8414 AS metadata is very likely but not
   doc-confirmed — verify by curling `/.well-known/oauth-authorization-server` on a running
   instance.
3. ~~Hop 2 SA mechanics~~ — **resolved:** reuse `firetower_sdk` directly as a uv path dep;
   it already obtains SA creds + signs the IAP-audience JWT. `firetower.py::get_client()`
   wraps it.
4. ~~Cloud Run ingress / LB wiring~~ — **resolved for test:** terraform in `~/code/ops`
   adds `firetower-mcp-test` (ingress `INTERNAL_LOAD_BALANCER`, no IAP, `allUsers` invoker)
   behind the external LB with NEG/backend/URL-map/managed-cert/DNS, mirroring siblings.
5. ~~Rate limiting / abuse~~ — **resolved:** Cloud Armor security policy (adaptive L7 DDoS +
   per-IP throttle) attached to the MCP test backend. See Deployment.
6. ~~FastMCP `OAuthProxy` accepts public-client DCR + PKCE~~ — **confirmed** with pi's
   actual DCR metadata and loopback callback (and separately with jr's expected shape).
7. jr integration PR (phase 2): declarative `mcp:` plugin in `getsentry/junior` pointing at
   the deployed server URL + `allowedTools`. Deferred until after the Claude rollout.

## Build checklist

Done (built + dual-reviewed on `spalmurray/mcp` and ops `spalmurray/firetower-mcp`):

- [x] `SentryGoogleProvider` (`auth.py`) — JWKS-verified `hd`/`email_verified` gate, refresh
      survival, per-tool fallback gate, `requester_email()` for audit.
- [x] Read-only tool surface (`tools.py`) — `list_incidents` + `get_incident`, SDK-only,
      sanitized errors, `_audit()` per-user logging.
- [x] Hop 2 via `firetower_sdk` path dep (`firetower.py`); config (`config.py`); server
      wiring (`server.py`), including public `GET /health` with protected `/mcp`; MCP tests
      passing.
- [x] Dedicated `docker/mcp.Dockerfile` with the SDK + `mcp` uv group, non-root runtime,
      Datadog serverless-init, and direct-Python MCP entrypoint; backend image restored.
- [x] Path-gated MCP build, separate test deploy, and `mcp_build_only` bootstrap input in
      `deploy.yml`; Dependabot covers uv dependencies.
- [x] Terraform: test Cloud Run service, NEG/backend/URL-map, dedicated test DNS-auth + cert
      for `mcp.test.firetower.getsentry.net`, Cloud Armor policy, IAM `firetower-api-mcp` SA,
      and secrets scaffolding.

Pending (user-driven, mostly out-of-sandbox):

- [ ] Create the Google OAuth client + Internal consent screen by hand in the console with
      the single upstream redirect `https://mcp.test.firetower.getsentry.net/auth/callback`.
      Claude and loopback callbacks belong only in `MCP_ALLOWED_REDIRECT_URIS`.
- [ ] Populate Secret Manager (client secret, jwt signing key) + `mcp_google_client_id_test`.
- [ ] Confirm the `allUsers` invoker org policy allows the public MCP service.
- [ ] Push `spalmurray/mcp`, then bootstrap the exact HEAD image before creating Cloud Run:
      `gh workflow run deploy.yml --ref spalmurray/mcp -f environment=test -f mcp_build_only=true`.
- [ ] Pass that HEAD SHA to Ops, then run the Terraform validation/plan/apply sequence and a
      normal test deployment.
- [ ] Live OAuth tests from pi, Claude Code, and a claude.ai connector; verify same-origin
      behavior, refresh, public `/health`, and protected `/mcp`.
- [ ] Phase 2: jr plugin PR.

## References

- MCP authorization spec (2025-06-18 / 2025-11-25): https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- MCP security best practices: https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices
- FastMCP auth: https://gofastmcp.com/servers/auth/authentication , https://gofastmcp.com/integrations/google
- Claude connector auth: https://claude.com/docs/connectors/building/authentication
- Google hd/email_verified verification: https://developers.google.com/identity/openid-connect/openid-connect
- Existing in-repo: `firetower_sdk` (Hop 2 auth precedent), `incidents/models.py::filter_visible_to_user` (privacy filter)
