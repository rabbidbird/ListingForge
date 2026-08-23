# TrueDraft v1 security review

Review date: 2026-08-23  
Scope: the public `main` application, authentication edge, persistence, Stripe
billing, generation controls, Docker/nginx runtime, and CI configuration.

## Executive summary

No unresolved critical, high, or medium application-security findings remain in
the reviewed v1 code. Five defense/proof gaps found during the final review were
fixed and covered by automated checks. `pip-audit 2.10.1 -r requirements.txt`
reported no known vulnerabilities in the pinned dependency set at review time.

This is a repository and container review, not a penetration test of the future
public domain. TLS, Railway network settings, live Stripe configuration, secret
access policy, backups, and legal identity still require operator verification
using `SHIP_CHECKLIST.md`.

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
- **Evidence:** CI now signs up a user through nginx, checks the HttpOnly session,
  opens the Streamlit WebSocket, verifies signed Stripe delivery and retry
  idempotency, logs out, and confirms the session is no longer accepted.
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
  customer could be charged while TrueDraft retained Free entitlements.
- **Fix:** use the current public `to_dict()` conversion with a legacy fallback.
- **Mitigation:** the container smoke sends the same raw signed bytes through
  nginx twice and requires first-delivery processing plus retry idempotency.
- **False-positive notes:** none; the initial container run reproduced the
  failure against the pinned SDK before this fix.

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
  LLM timeout/token/user caps, kill switch, and source-vocabulary rejection.
- Non-root pinned container, request-size ceiling, security headers, secret-file
  ignores, GitHub secret-scanning push protection, Dependabot alerts/security
  updates, and protected `main` checks.

## Operator security checks before public traffic

1. Store a unique session secret and least-privilege live Stripe restricted key
   in Railway's secret manager; never send them through chat or commit them.
2. Restrict Stripe key access where Railway egress permits, require passkeys or
   authenticator-app 2FA for Dashboard users, and test key rotation.
3. Verify the final domain/TLS, Railway backups/restore procedure, log retention,
   webhook signing secret, Customer Portal, and live downgrade behavior.
4. Assess tax registrations before enabling Stripe Tax. Automatic tax does not
   collect tax in jurisdictions where the operator has no active registration.
5. Replace every legal placeholder and complete the live signup/payment smoke in
   `SHIP_CHECKLIST.md` before opening public traffic.
