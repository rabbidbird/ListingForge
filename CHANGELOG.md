# Changelog

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
