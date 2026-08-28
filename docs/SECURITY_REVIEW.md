# SellerDrafts v1 security review

Review date: 2026-08-23  
Scope: the code on this branch: authentication edge, persistence, Stripe
billing, generation controls, Docker/nginx runtime, and CI configuration.

## Executive summary

No unresolved critical, high, or medium application-security findings remain in
the reviewed v1 code. The security risks identified in this branch's review are
resolved in code and covered by automated checks. `pip-audit 2.10.1 -r
requirements.txt` reported no known vulnerabilities in the pinned dependency
set at review time.

This is a repository and container review, not a penetration test of a public
domain, and it is not a legal review. TLS, Railway network settings, live Stripe
configuration, secret access policy, backups, legal/business details, and manual
send/receive/reply tests for `support@sellerdrafts.com` and
`privacy@sellerdrafts.com` still require operator verification using
`SHIP_CHECKLIST.md`. Passing technical checks means the service can be live; it
does not authorize paid acquisition for the unreviewed pilot.

## Resolved findings

### SEC-01 — health could accept an outdated schema

- **Severity:** Medium (resolved)
- **Location:** `core/migrate.py:31` (`database_at_migration_head`),
  `core/web.py:317` (`healthz`), `tests/test_schema.py`
- **Evidence:** health now compares the database's Alembic revision set with the
  repository-declared head rather than checking only that `users` can be queried.
- **Impact before fix:** a partially migrated deployment could report healthy and
  receive traffic before a later code path touched a missing column.
- **Fix:** fail `/healthz` with 503 when the version table is missing or behind.
- **Mitigation:** container startup still runs `alembic upgrade head` before any
  service process starts.
- **False-positive notes:** none; the regression test deliberately moves the
  Alembic marker behind head and verifies rejection.

### SEC-02 — container CI did not exercise the public edge flows

- **Severity:** Medium (resolved)
- **Location:** `scripts/container_smoke.py`, `.github/workflows/ci.yml:59`
- **Evidence:** CI provisions an internal fixture, proves public production
  password registration fails closed, signs in that existing account through
  nginx, checks the HttpOnly session, opens the Streamlit WebSocket, verifies
  signed Stripe delivery and retry idempotency, logs out, and confirms the
  session is no longer accepted.
- **Impact before fix:** nginx routing, cookie forwarding, or WebSocket upgrades
  could regress while a simple `/healthz` poll remained green.
- **Fix:** run the edge smoke inside the built Compose application after health.
- **Mitigation:** unit tests continue to cover auth, CSRF, entitlement mapping,
  isolation, and webhook error cases independently.
- **False-positive notes:** the smoke uses a local signing secret and an ignored
  event type; it does not contact Stripe or create a charge.

### SEC-03 — production Host validation and baseline Streamlit CSP were absent

- **Severity:** Medium (resolved)
- **Location:** `core/web.py:35-43`, `deploy/nginx.conf.template:30`
- **Evidence:** production FastAPI routes accept the configured public hostname
  (plus loopback health traffic), and nginx sets `frame-ancestors`, `base-uri`,
  and `object-src` restrictions for the Streamlit surface.
- **Impact before fix:** arbitrary Host values reached public auth/webhook routes,
  and Streamlit lacked an edge-enforced baseline against framing/object content.
- **Fix:** add `TrustedHostMiddleware` and a Streamlit-compatible CSP baseline.
- **Mitigation:** Checkout/portal URLs are independently derived from the
  validated `PUBLIC_BASE_URL`, never from request Host.
- **False-positive notes:** Railway or another upstream proxy may add stricter
  controls; they are defense in depth rather than a replacement for app checks.

### SEC-04 — authentication abuse state and password input were not hard-bounded

- **Severity:** Low (resolved)
- **Location:** `core/auth.py:38-45,110`, `core/web.py:45-77`
- **Evidence:** email/password input is bounded before Argon2 verification, and
  per-IP soft-rate buckets are held in a 10,000-entry LRU map.
- **Impact before fix:** oversized login bodies or many distinct source addresses
  could consume avoidable CPU or retain unbounded in-process rate-limit keys.
- **Fix:** verify an inert bounded password for invalid lengths and evict the
  least-recently-used IP bucket when the cap is crossed.
- **Mitigation:** nginx also limits request bodies to 3 MB and auth routes allow
  only 40 requests per source per ten-minute window.
- **False-positive notes:** the limiter is intentionally a single-instance soft
  control; add an edge/WAF or shared limiter before horizontally scaling.

### SEC-05 — current Stripe SDK events failed after signature verification

- **Severity:** High (resolved)
- **Location:** `core/billing.py:196-208`, `tests/test_billing.py`
- **Evidence:** Stripe Python 15.4 exposes `Event.to_dict()`; the previous
  compatibility branch fell through to `dict(event)`, which raises for the
  current SDK object. A real HMAC-signed SDK event now passes in unit and
  container-edge tests.
- **Impact before fix:** valid live webhooks would return 400 after payment, so a
  customer could be charged while SellerDrafts retained Free entitlements.
- **Fix:** use the current public `to_dict()` conversion with a legacy fallback.
- **Mitigation:** the container smoke sends the same raw signed bytes through
  nginx twice and requires first-delivery processing plus retry idempotency.
- **False-positive notes:** none; the initial container run reproduced the
  failure against the pinned SDK before this fix.

### SEC-06 — output transformations could recombine facts or lose qualifiers

- **Severity:** High (resolved)
- **Location:** `core/llm.py:63` (`source_phrase_catalog`),
  `core/generator.py:338,440,518,524`, `tests/test_fact_lock.py`
- **Evidence:** the optional model now returns only opaque IDs for complete
  supplied phrases. Deterministic code validates every ID, renders fixed
  separators and description labels, and rejects all legacy/free-form prose.
  Negative phrases are not split into shorter tags, and over-limit titles/tags
  are skipped rather than truncated. Signed and mixed-number measurements are
  no longer altered by punctuation trimming or repeated-token cleanup.
- **Impact before fix:** a vocabulary-only validator could accept the same
  supplied words and numbers after a model paired a measurement with the wrong
  attribute, creating a new factual relationship without adding vocabulary.
  Generic negative input could also lose its qualifier during tag extraction or
  length truncation even when the adjective was not on a prohibited-term list;
  cosmetic cleanup could turn `-5` into `5` or `1 1/2` into `1/2`.
- **Fix:** remove free-form model prose from the output trust boundary, preserve
  complete phrase polarity and numeric notation, and add regressions for swapped
  measurements, signed/mixed values, unlisted negative attributes, and
  over-limit source text.
- **Mitigation:** model use remains disabled by default, capped per user, bounded
  by timeout/tokens, and protected by an operator kill switch.
- **False-positive notes:** none; phrase selection can change ordering but cannot
  rewrite, split, or invent the text associated with an ID.

### SEC-07 — anonymous surfaces lacked client and global edge ceilings

- **Severity:** Low (resolved)
- **Location:** `deploy/nginx.conf.template:25-35`,
  `tests/test_public_surface.py`
- **Evidence:** nginx now applies per-client and container-wide request and
  connection zones at the `server` boundary, covering Streamlit, auth, health,
  and webhook routes. On Railway, the client key comes from its injected
  `X-Real-IP` only when a valid edge marker and Railway's server-side
  `RAILWAY_ENVIRONMENT_ID` are both present; direct/local traffic ignores
  forwarding headers and uses nginx's peer address.
- **Impact before fix:** only authentication had an application soft limit; a
  high-rate anonymous client could still consume Streamlit/container capacity.
- **Fix:** preserve Railway's client address through nginx, add fair per-client
  soft limits, and retain a deliberately generous global ceiling with HTTP 429
  responses as a backstop.
- **Mitigation:** auth keeps its tighter bounded per-source limiter; use a shared
  WAF/edge limiter before horizontal scaling. Deployments outside Railway must
  configure their own trusted proxy boundary rather than setting Railway system
  variables.
- **False-positive notes:** this is an instance-local soft control, not a promise
  of distributed denial-of-service protection. The supported deployment must
  expose port 8080 only through Railway HTTP Public Networking; a direct app TCP
  Proxy would invalidate the forwarded-header trust boundary.

### SEC-08 — exported CSV cells could be interpreted as formulas

- **Severity:** Medium (resolved)
- **Location:** `core/utils.py:30` (`spreadsheet_safe_text`), `tests/test_csv.py`
- **Evidence:** every string cell in generated CSV exports is prefixed with an
  apostrophe when its first meaningful character is `=`, `+`, `-`, or `@` (or a
  tab/carriage return prefix).
- **Impact before fix:** a formula-looking value supplied in product fields could
  execute spreadsheet functionality when a recipient opened the exported CSV.
- **Fix:** neutralize formula prefixes at the export boundary without changing
  saved draft content or JSON exports.
- **Mitigation:** exports remain behind the three-point human confirmation.
- **False-positive notes:** legitimate values beginning with these characters
  display with a protective apostrophe in spreadsheet software.

### SEC-09 — migration metadata and the deployed uniqueness index could drift

- **Severity:** Low (resolved)
- **Location:** `core/models.py:124` (`Subscription.__table_args__`),
  `.github/workflows/ci.yml:31`
- **Evidence:** SQLAlchemy now declares the same named unique index created by
  Alembic, and CI runs `alembic check` immediately after applying migrations.
- **Impact before fix:** the database still enforced uniqueness, but autogenerate
  detected an index/constraint mismatch and future schema work could accidentally
  emit destructive churn instead of a clean migration.
- **Fix:** align model metadata with the existing migration and fail CI whenever
  model metadata would require an undeclared upgrade operation.
- **Mitigation:** `/healthz` independently requires the exact deployed Alembic
  head before the container receives traffic.
- **False-positive notes:** SQLite cannot reflect the expression index used for
  case-insensitive email uniqueness and emits a documented warning; it reports
  no upgrade operation. PostgreSQL is the production database.

### SEC-10 — exception text could cross response and launch-output boundaries

- **Severity:** High (resolved)
- **Location:** `core/web.py:204,258,312`, `scripts/launch_check.py:178`,
  `tests/test_web_auth.py`, `tests/test_launch_check.py`
- **Evidence:** CodeQL default setup identified exception-to-response and
  exception-to-output flows. Authentication, webhook verification, and invalid
  launch configuration now return fixed messages. The session-secret hardening
  result remains part of the readiness gate but is not interpolated into console
  output. Regression tests inject secret-like content and require that it
  remains absent.
- **Impact before fix:** current exceptions were normally concise validation
  messages, but a future lower-level exception with internal details could have
  been reflected to an unauthenticated client or launch logs.
- **Fix:** discard exception strings at these trust boundaries and preserve only
  stable, actionable public messages.
- **Mitigation:** detailed billing outcomes continue to use structured logs that
  omit emails, credentials, and payloads; launch checks report the failing gate
  without printing configuration values.
- **False-positive notes:** the alert paths were reachable even though current
  exception messages did not include stack traces. Treating them as genuine
  boundary weaknesses prevents future exception-content regressions.

## August 28, 2026 pilot-readiness supplement

This supplement is a repository review of the feature branch, not an external
penetration test, production-data audit, deployment verification, or legal
review.

### SEC-11 — matching-email Google sign-in could pre-hijack a password account

- **Severity:** High (resolved in this branch; deployment pending)
- **Evidence:** Google login now resolves only an immutable Google subject. If a
  verified Google email matches an existing unlinked account, login fails with
  instructions to authenticate with the password and link from Account.
- **Fix:** split subject lookup, new Google-user creation, and authenticated
  identity linking into explicit operations. A Google subject cannot move to a
  different user.
- **Residual operator risk:** existing dual-auth accounts are not mutated or
  locked automatically. Review production identity history separately if an
  incident or account complaint provides a reason to do so.

### SEC-12 — OAuth state was signed but not bound to the initiating browser

- **Severity:** High (resolved in this branch; deployment pending)
- **Evidence:** initiation stores a random matching value in a short-lived
  HttpOnly, SameSite=Lax cookie restricted to `/auth/google`; production adds
  Secure. Callback requires a constant-time match, validates the ID-token nonce
  through the Google library, and clears the cookie on handled success/failure.
- **Fix:** signed state now also carries login/link mode and an allowlisted plan
  intent. Link mode requires the same valid SellerDrafts session and normalized
  email, revokes other sessions, and issues a fresh current session.
- **Residual operator risk:** Google Console redirect/origin settings and OAuth
  consent configuration remain operator-managed external controls.

### SEC-13 — stale Terms consent did not block product use

- **Severity:** Medium (resolved in this branch; deployment pending)
- **Evidence:** one canonical version (`2026-08-27-v1`) is stored for password
  and Google accounts. FastAPI redirects stale sessions to an authenticated,
  CSRF-protected acceptance POST, and Streamlit stops stale sessions before any
  workspace page renders.
- **Fix:** public and authenticated legal pages now render the same canonical
  policy source, and post-acceptance destinations are an internal allowlist.
- **Residual operator risk:** independent legal/business review remains
  incomplete and is explicitly tracked in `SHIP_CHECKLIST.md`.

### SEC-14 — campaign attribution was signed but not truly first-touch

- **Severity:** Low (resolved in this branch; deployment pending)
- **Evidence:** a valid existing attribution cookie is preserved when a later
  tagged URL is visited. Invalid/expired cookies can be replaced, direct traffic
  creates no campaign attribution, and an existing user's stored acquisition
  columns are never rewritten.
- **Residual operator risk:** the first-party report measures only signups,
  users with at least one draft, and currently active paid users; it is not a
  visit, checkout, revenue, or profitability report.

## Existing controls verified

- Argon2 passwords; opaque random session tokens stored only as keyed hashes;
  Secure/HttpOnly/SameSite cookies in production; CSRF on cookie-authenticated
  state changes; production API docs disabled.
- UUID resource identifiers and owner-filtered listing read, update, delete, and
  export queries.
- PostgreSQL row locking for quota reservations and Checkout creation; no plan is
  unlimited; inactive subscription states fail closed to Free.
- Stripe instance client, current pinned API version, dynamic payment methods,
  signature verification before event processing, transactional event IDs, and
  configured-Price entitlement mapping.
- CSV size/type/row validation, per-plan bulk caps, per-row failure isolation,
  formula-safe exports, LLM timeout/token/user caps, kill switch, and
  complete-source-phrase ID rendering instead of free-form model prose.
- Non-root pinned container, request-size ceiling, security headers, secret-file
  ignores, GitHub secret-scanning push protection, Dependabot alerts/security
  updates, CodeQL default scanning for Python and Actions, and protected `main`
  checks.

## Operator security checks before public traffic

1. Store a unique session secret and least-privilege live Stripe restricted key
   in Railway's secret manager; never send them through chat or commit them.
2. Restrict Stripe key access where Railway egress permits, require passkeys or
   authenticator-app 2FA for Dashboard users, and test key rotation.
3. Verify the final domain/TLS, confirm the app has no TCP Proxy/direct origin,
   and verify Railway backups/restore, log retention, webhook signing secret,
   Customer Portal, and live downgrade behavior.
4. Assess tax registrations before enabling Stripe Tax. Automatic tax does not
   collect tax in jurisdictions where the operator has no active registration.
5. Replace every legal placeholder and complete the live signup/payment smoke in
   `SHIP_CHECKLIST.md` before opening public traffic.
