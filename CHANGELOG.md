# Changelog

## v1.0.8 CodeQL response hardening — 2026-08-23

- Replaced authentication, Stripe signature, and launch-configuration exception text at public or operator-facing boundaries with fixed safe messages.
- Added regressions that inject secret-like exception content and prove it cannot reach auth HTML, webhook JSON, or rendered launch-check output.

## v1.0.7 invariant and edge hardening — 2026-08-23

- Removed free-form LLM prose from the output trust boundary. The optional model can now select and order only opaque IDs for complete supplied phrases; deterministic code renders the result and invalid/free-form responses fall back to templates.
- Prevented generic negation loss and lossy cosmetic edits: negative phrases are never split into affirmative tags, over-limit titles/tags are skipped instead of cutting away qualifying context, and signed or mixed-number measurements remain unchanged.
- Added per-client nginx request/connection soft limits using Railway's injected client IP only inside the documented Railway HTTP-edge trust boundary, preserved the public HTTPS scheme to upstream processes, and added a container-wide backstop for every anonymous surface plus the tighter bounded authentication limiter.
- Container startup now validates the rendered nginx configuration before starting processes, and the production-shaped CI stack checks Alembic metadata against PostgreSQL.
- Neutralized spreadsheet-formula prefixes in CSV exports and added regressions for phrase reassociation, generic negation, over-limit source text, edge limits, and formula-looking cells.
- Aligned the pending-Checkout uniqueness index with Alembic metadata and made `alembic check` a required CI schema-drift gate.
- Added a dated first-party platform-rules record and clarified that Shopify's 70-character value is an SEO-title target rather than a universal product-title limit.

## v1.0.6 final review hardening — 2026-08-23

- Negated supplied claims remain negated: phrases such as “not waterproof” can no longer be shortened into affirmative `waterproof` tags or LLM copy.
- Production `launch_check` now blocks public traffic for test-mode, unrecognized, or placeholder Stripe credentials and for the intentionally disabled email-verification stub. Production also rejects base URLs that are not plain HTTPS origins.
- Checkout uses an instance-scoped Stripe client and the current pinned API version. One expiring open Checkout is persisted per user, reused on repeated clicks, and released by terminal Checkout webhooks.
- Built-in Streamlit dataframe export/copy controls are disabled so CSV downloads remain behind the confirmation checklist; the incompatible CORS override was removed.
- Added the pending-Checkout Alembic migration and regression coverage for claim polarity, live-payment gates, duplicate Checkout prevention, and export configuration.
- CI now uses the current Node 24-based official checkout/setup actions and avoids duplicate push + pull-request runs on feature branches.
- PR #1 landed the paid PostgreSQL/auth/billing tree on `main`; the final ship checklist now contains only operator-owned launch work.
- Final production proof now rejects outdated Alembic schemas at `/healthz`, validates production Host headers, bounds authentication inputs/rate-limit memory, and applies baseline CSP headers at nginx.
- The container smoke now exercises signup/session/logout, signed webhook idempotency, and the Streamlit WebSocket proxy through nginx. Dependency audit found no known vulnerabilities in the pinned lock.
- Fixed Stripe Python 15.4 event conversion (`Event.to_dict()`); a real SDK-signed webhook regression test now protects paid entitlement delivery in addition to mocked handler tests.
- Enabled GitHub Dependabot alerts/security updates and private vulnerability reporting; added the repository security policy and review record.

## v1.0.5 public landing and pricing story — 2026-08-19

- Logged-out Home is a conversion landing page: hero, honest positioning, how-it-works, feature grid, trust, blocked-claim categories, and a plan teaser. Logged-in Home still shows plan metrics and draft/CSV actions.
- Plans & Pricing now includes a comparison table, honest plan blurbs, and billing FAQ. Checkout, portal, and fail-closed entitlement rules are unchanged.
- Shared `core/copy.py` keeps TrueDraft naming, draft/heuristic disclaimers, and forbidden marketing phrases consistent. Signup/sign-in pages repeat the same promise.
- Optimizer, bulk, checklist, history, and export confirmations make the no-invention and human-review rules visible.

## v1.0.4 land-as-main commands — 2026-08-19

- `docs/MERGE_STRATEGY.md` now has the two safe landing commands (force-point `main` at this tip, or `merge -s ours` **while on this branch** so GitHub Merge works). It states that `-s ours` on `main` would keep the guest/SQLite tree.
- README Railway runbook no longer says to create live Stripe Prices first. Test-mode first, live switch after the Checkout cycle, matching `SHIP_CHECKLIST.md`.

## v1.0.3 operator fail-closed defaults — 2026-08-19

- The production image now defaults to `ENV=production`, so a Railway deploy that forgets `ENV` fails closed instead of serving SQLite with the documented session secret. Compose still overrides to `development`.
- Streamlit telemetry and the developer toolbar are off (`.streamlit/config.toml` + supervisord flags). Uvicorn no longer sends a `Server` header.
- `launch_check` prints the next operator action, flags Stripe Product IDs (`prod_...`) used as Price IDs, and prints the test-mode → live verification sequence in production.
- `SHIP_CHECKLIST.md` is now an ordered test-mode → live runbook, including the required “limit customers to one subscription” Stripe setting.

## v1.0.2 pre-launch polish — 2026-08-19

- `python -m scripts.launch_check` is now a structured pre-flight report: Postgres vs SQLite, secret class, public HTTPS host, cookie flag, individual Stripe fields, duplicate/placeholder Price IDs, legal placeholders, leftover `LISTINGFORGE_*` / skip-auth variables, and derived webhook/portal URLs. It never prints secrets. In `ENV=production` it exits 1 unless every blocker is gone.
- Existing Stripe subscriptions in `active`, `trialing`, `past_due`, `unpaid`, `incomplete`, or `paused` must be changed in the Customer Portal. A second Checkout session is blocked so a paying user cannot be double-charged while a payment is failing.
- Delayed Checkout payments (`checkout.session.async_payment_succeeded`) now grant the Price-mapped plan. Failed/expired Checkout and invoice events are acknowledged without changing entitlements.
- Webhook responses include a `reason` for non-updates, and operators get structured logs without emails or secrets.
- Usage snapshots now expose billing status, portal-required, and payment-failed flags. Home, Single Draft, Bulk, sidebar, and Plans & Billing explain Free-cap, past-due, and portal-return states honestly.
- Expanded tests for production fail-closed settings, Price mapping, unpaid/past_due/unknown/inactive statuses, failed-generation non-consumption, session revoke, cross-user isolation, and fact-lock extras.
- Documented the merge strategy vs `main`: do not import the local SQLite / guest-identity path.

## v1.0.1 launch hardening — 2026-08-19

- Production now fails closed on documented/default session secrets, repeated-character secrets, and localhost `PUBLIC_BASE_URL` values. `get_settings()` runs this check for every process, not only the FastAPI import path.
- Checkout entitlements map from the Stripe Price that was charged (line items first, then `metadata.price_id`) and never from `metadata.plan`.
- Unpaid checkout, unknown Price IDs, older webhooks, and `past_due` subscriptions now have explicit fail-closed tests.
- Failed generation reservations no longer consume quota; inactive users cannot reserve usage; revoked sessions cannot authenticate.
- Added Alembic-vs-model schema coverage, an operator `python -m scripts.launch_check` report, and extra fact-lock terms for ethically sourced / fair trade / locally made / nickel-free / lead-free / small-batch claims.

## v1.0.0 release candidate — 2026-08-15

- Replaced YAML/demo authentication with PostgreSQL users, Argon2 passwords, Terms acceptance, opaque hashed sessions, HttpOnly cookies, login, logout, and signup.
- Added SQLAlchemy models and an Alembic migration for users, sessions, listings, usage events, subscriptions, and idempotent webhook events; production now rejects SQLite.
- Enforced user ownership on listing read, update, delete, history, and export.
- Centralized Free/Starter/Pro/Agency quotas, transactional reservations, per-minute limits, LLM caps, and bulk row caps.
- Implemented Stripe-hosted subscription Checkout, Customer Portal, signature verification, Price-based entitlements, idempotency, deletion downgrade, and out-of-order event protection.
- Hardened fact-locking, expanded prohibited claims, removed unsafe claim suggestion banks, and made unsourced LLM vocabulary or numbers fail closed to deterministic templates.
- Added CSV upload ceilings, empty-file handling, `nan` cleanup, and row-isolated validation failures.
- Reworked all UI copy around TrueDraft, mandatory draft review, real clipboard controls, honest heuristic checklists, and confirmation-before-export.
- Expanded Terms, Privacy, and Acceptable Use with launch-blocking operator placeholders and LLM-provider disclosure.
- Added a fully pinned dependency lock, non-root nginx/FastAPI/Streamlit container, PostgreSQL Compose smoke path, Railway config, GitHub Actions CI, and release documentation.
