# Firetower MCP Server — Design

Status: design resolved, built + dual-reviewed; pending deploy (2026-06-16)
Branch/worktree: `spalmurray/mcp` (`/Users/spencer/code/spalmurray/mcp`); terraform on
`spalmurray/firetower-mcp` in `~/code/ops` (`terraform/eng-tools/firetower/`)

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

## Client rollout: Claude first, then jr, then others

**Rollout order (resolved): start with Claude (Code + claude.ai/Desktop), then expand to
`jr`, then codex/whatever.** There is no formal phasing gate — adding a client is just an
edit to `MCP_ALLOWED_REDIRECT_URIS` (+ the Google console redirect URIs), plus, for jr, a
small plugin PR. The server shape is identical for all of them (OAuth + PKCE).

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
- **HTTPS everywhere; exact redirect-uri matching; accept `localhost:*` for Claude Code.**
- **Workspace gate:** validate signed `hd` claim (== sentry.io) + `email_verified`; anchor
  on `sub` + workspace id, not email domain. (Caveat: domain-resale attacks exist — `hd`
  is necessary, not a perfect anchor; acceptable for read-only org-confidential incident data.)

## Deployment

- New Cloud Run service (e.g. `firetower-mcp-{test,prod}`), sibling to the slack bot.
- **Not** behind IAP (it has its own OAuth). Confirm ingress/LB wiring.
- Secrets: Google OAuth client id/secret; the firetower SA credentials for Hop 2.
- Reuse existing deploy workflow patterns (`.github/workflows/deploy.yml`).
- **FastMCP dependency policy (resolved): track latest, don't dependency-pin.** Floor at
  `fastmcp>=3.4.1`; **Dependabot** (uv ecosystem, `.github/dependabot.yml`) opens weekly bump
  PRs — **no auto-merge**. On each fastmcp bump, re-run the auth unit tests and do a live
  OAuth + token-refresh smoke, because the `hd` hook depends on `OAuthProxy` internals that
  are semver-exempt. (Earlier drafts said "pin to an exact version" — reversed: we'd rather
  stay current and absorb the occasional break behind a reviewed PR than freeze.)
- **`jwt_signing_key` from env (stable across restarts).** Set it from Secret Manager so a
  restart doesn't invalidate already-issued FastMCP tokens via a new signing key.
- **No persistent `client_storage` in v1 — and that's deliberate.** FastMCP reference tokens
  do a hard `client_storage` lookup on *every* request, so losing the store (in-memory,
  per-instance) breaks all active sessions immediately, not gracefully. The fix isn't a DB;
  it's **not redeploying the service.** Today the shared image means every firetower deploy
  would restart the MCP server and force a re-auth. We solve that with the **deploy gate**
  (below), so the server only restarts on actual MCP changes — rare. Revisit persistent
  storage (e.g. the Linear-token DB pattern) only if restart frequency becomes a problem.
- **Deploy gate (resolved):** `deploy.yml` has a `changes` job that git-diffs MCP-relevant
  paths (`src/firetower/mcp_server/`, `sdk/`, `docker/entrypoint.sh`, `docker/backend.Dockerfile`,
  `pyproject.toml`, `uv.lock`); the `firetower-mcp*` services only deploy when `mcp == true`
  (non-push events still deploy, to keep manual runs working). This keeps the MCP server off
  the every-firetower-deploy restart treadmill, which is what makes in-memory storage viable.
- **Observability (resolved):** Datadog via serverless-init (`DD_API_KEY`/`DD_APP_KEY` env on
  both MCP services, mirroring the slack/async siblings) + Cloud Logging for the structured
  audit lines. Per-request token validation cost (FastMCP's `client_storage` lookup, and any
  tokeninfo call) is accepted — the request volume is low.
- **Cloud Armor (resolved — required, house convention):** a dedicated
  `google_compute_security_policy "firetower-mcp-security-policy"` attached to *only* the MCP
  backends — adaptive L7 DDoS protection (PREMIUM), a per-IP rate-limit throttle
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
  - *Google console* (upstream client): register `https://<our-origin>/auth/callback`
    (FastMCP default `redirect_path`), plus `https://claude.ai/api/mcp/auth_callback` and
    `https://claude.com/api/mcp/auth_callback`, plus `https://claude.ai`/`https://claude.com`
    as Authorized JavaScript origins. Loopback (`localhost`/`127.0.0.1`) needs no port
    enumeration — Google allows any loopback port.
  - *`MCP_ALLOWED_REDIRECT_URIS`* (FastMCP `allowed_client_redirect_uris`): validates the
    *downstream* MCP client callback. Set to
    `https://claude.ai/api/mcp/auth_callback,https://claude.com/api/mcp/auth_callback,http://localhost:*,http://127.0.0.1:*`.
    **Verified against current FastMCP source:** the matcher is component-wise — port `*`
    plus root-path-matches-any handles ephemeral-port loopback correctly (an earlier ≤3.1.1
    bug rejecting dynamic-port loopback is not present on our floor). `None` = allow all,
    empty = block all; our `config.py` `_require()`s a non-empty value so neither happens by
    accident.

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
4. ~~Cloud Run ingress / LB wiring~~ — **resolved:** terraform in `~/code/ops` adds
   `firetower-mcp-{test,prod}` (ingress `INTERNAL_LOAD_BALANCER`, no IAP, `allUsers` invoker)
   behind the external LB with NEG/backend/URL-map/managed-cert/DNS, mirroring siblings.
5. ~~Rate limiting / abuse~~ — **resolved:** Cloud Armor security policy (adaptive L7 DDoS +
   per-IP throttle) attached to the MCP backends only. See Deployment.
6. ~~FastMCP `OAuthProxy` accepts public-client DCR + PKCE~~ — **confirmed** (jr's shape;
   also how Claude registers).
7. jr integration PR (phase 2): declarative `mcp:` plugin in `getsentry/junior` pointing at
   the deployed server URL + `allowedTools`. Deferred until after the Claude rollout.

## Build checklist

Done (built + dual-reviewed on `spalmurray/mcp` and ops `spalmurray/firetower-mcp`):

- [x] `SentryGoogleProvider` (`auth.py`) — JWKS-verified `hd`/`email_verified` gate, refresh
      survival, per-tool fallback gate, `requester_email()` for audit.
- [x] Read-only tool surface (`tools.py`) — `list_incidents` + `get_incident`, SDK-only,
      sanitized errors, `_audit()` per-user logging.
- [x] Hop 2 via `firetower_sdk` path dep (`firetower.py`); config (`config.py`); server
      wiring (`server.py`); 30 unit tests passing.
- [x] Docker entrypoint `mcp` mode + Dockerfile `sdk/` copy + `mcp` uv group; `.env.mcp.example`.
- [x] Deploy gate (`deploy.yml` `changes` job) + Dependabot (uv).
- [x] Terraform: Cloud Run `firetower-mcp-{test,prod}`, NEG/backend/URL-map, dedicated test
      DNS-auth + cert for `mcp.test.firetower.getsentry.net`, Cloud Armor policy, IAM
      `firetower-api-mcp` SA, secrets scaffolding.

Pending (user-driven, mostly out-of-sandbox):

- [ ] Commit the uncommitted changes on both branches.
- [ ] Create the Google OAuth client + Internal consent screen by hand in the console
      (redirect `https://mcp.test.firetower.getsentry.net/auth/callback` + claude.ai/.com).
- [ ] Populate Secret Manager (client secret, jwt signing key) + `mcp_google_client_id_test`.
- [ ] Confirm the `allUsers` invoker org policy allows the public MCP service.
- [ ] `terraform fmt/validate/plan/apply` (cloudrun → frontend → iam); push `spalmurray/mcp`;
      `gh workflow run deploy.yml --ref spalmurray/mcp -f environment=test`.
- [ ] Live OAuth test from Claude Code + a claude.ai connector (verify same-origin behavior).
- [ ] Phase 2: jr plugin PR.

## References

- MCP authorization spec (2025-06-18 / 2025-11-25): https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- MCP security best practices: https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices
- FastMCP auth: https://gofastmcp.com/servers/auth/authentication , https://gofastmcp.com/integrations/google
- Claude connector auth: https://claude.com/docs/connectors/building/authentication
- Google hd/email_verified verification: https://developers.google.com/identity/openid-connect/openid-connect
- Existing in-repo: `firetower_sdk` (Hop 2 auth precedent), `incidents/models.py::filter_visible_to_user` (privacy filter)
