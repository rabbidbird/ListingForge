# TrueDraft

TrueDraft is a fact-locked **draft** listing generator for Etsy, Shopify, and Amazon-style marketplaces. It creates titles, descriptions, and tags only from product facts the user supplies. Every result remains a starting draft that requires human review.

This repository was formerly named ListingForge. The product and all current user-facing copy are TrueDraft.

## Release status

The v1 code path includes database accounts, per-user authorization, PostgreSQL migrations, transactional quotas, Stripe subscription webhooks, abuse controls, legal pages, a non-root container, CI, and automated tests. It is not a live service until the operator completes [SHIP_CHECKLIST.md](SHIP_CHECKLIST.md).

TrueDraft never promises ranking, conversion, or sales. Its scores are transparent heuristic checklists only.

## Safety invariants

- Product facts such as materials, dimensions, origin, certifications, ratings, scarcity, and shipping claims must come from user input.
- An optional LLM is disabled by default. When enabled, it has per-user caps, a timeout, a token ceiling, a kill switch, and a strict source-vocabulary validator. Rejected output falls back to deterministic templates.
- Every generation and export displays **DRAFT — verify before publishing**.
- Every listing read, update, delete, and export is filtered by `user_id` on the server.
- Production refuses SQLite and insecure session configuration.

## Plans and enforced limits

All periods use UTC. These values come from `core/plans.py`, the single source of truth used by UI and enforcement.

| Plan | Per day | Per month | Bulk rows/job | LLM attempts/day |
|---|---:|---:|---:|---:|
| Free | 8 | 40 | 5 | 4 |
| Starter | 50 | 1,000 | 25 | 25 |
| Pro | 250 | 5,000 | 100 | 100 |
| Agency | 1,000 | 25,000 | 250 | 500 |

No plan is unlimited.

## Architecture

- Streamlit provides the product UI.
- FastAPI owns signup/login/logout, HttpOnly session cookies, health checks, and Stripe webhooks.
- nginx exposes both processes on one origin and proxies Streamlit WebSockets.
- SQLAlchemy and Alembic manage PostgreSQL. SQLite is allowed only with `ENV=development` or `ENV=test`.
- Stripe-hosted Checkout and Customer Portal handle payment UI; verified, idempotent webhooks control entitlements.

Minimum tables are `users`, `listings`, `usage_events`, and `subscriptions`; v1 also uses `user_sessions` and `webhook_events`.

## Local production-like run

Docker is the supported one-command local path:

```bash
docker compose up --build
```

Open <http://localhost:8080>. This starts PostgreSQL, runs Alembic migrations, then starts FastAPI, Streamlit, and nginx. Stop with `docker compose down`; add `-v` only when you intentionally want to delete the local database volume.

For Python-only generator/test work, create a virtual environment, install the lock, and use the development SQLite fallback:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
ENV=development .venv/bin/alembic upgrade head
ENV=test .venv/bin/pytest
```

On Windows, use `.venv\Scripts\python.exe` and `.venv\Scripts\pip.exe`.

## Railway production runbook (12 steps)

1. Fork this repository and create a Railway project from the fork. Railway will use `railway.toml` and the root `Dockerfile`.
2. Add a Railway PostgreSQL service and expose its `DATABASE_URL` to the TrueDraft service.
3. In Stripe live mode, create monthly recurring USD Prices matching the displayed plan copy: Starter $12, Pro $29, and Agency $79. Keep the resulting `price_...` IDs; if currency or prices change, update `core/plans.py` copy before deployment.
4. Create a least-privilege Stripe restricted API key for the Checkout, Customer, Subscription, and Billing Portal operations used here. Do not put keys in Git.
5. Set the initial production variables from `.env.example`: `ENV=production`, `DATABASE_URL`, the Railway HTTPS origin as `PUBLIC_BASE_URL`, a 32+ character `SESSION_SECRET`, `SESSION_COOKIE_SECURE=true`, `PORT=8080`, the Stripe restricted key, and three Price IDs. Billing buttons stay disabled until the signing secret is added.
6. Deploy. Container startup runs `alembic upgrade head`; `/healthz` becomes healthy only after the migrated database is reachable.
7. Add the Railway custom domain, point DNS as Railway instructs, then set `PUBLIC_BASE_URL=https://YOUR_DOMAIN` and redeploy.
8. In Stripe Workbench, add `https://YOUR_DOMAIN/webhooks/stripe` and subscribe to `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, and `customer.subscription.deleted`. Copy its `whsec_...` value to `STRIPE_WEBHOOK_SECRET` and redeploy.
9. Enable and configure the Stripe Customer Portal for subscription changes, cancellation, and payment-method management. Dynamic payment methods are controlled in Stripe; the code intentionally does not hard-code `payment_method_types`.
10. Replace `{{OPERATOR_LEGAL_NAME}}`, `{{CONTACT_EMAIL}}`, and `{{JURISDICTION}}` in `pages/6_Legal.py`.
11. Run one live signup → template draft → private history smoke check, then a Stripe test-mode Checkout/webhook/cancel cycle before switching all Stripe variables to live mode.
12. Require the GitHub Actions `test` and `container-smoke` jobs on the default branch, then release.

Do not enable Stripe automatic tax unless the operator has the registrations required for Stripe to calculate and collect tax. Use separate Stripe keys for test and live environments.

## Configuration

Copy `.env.example` only for local reference. Railway variables should be entered in its secret manager. `DATABASE_URL` accepts Railway's `postgres://`/`postgresql://` forms and is normalized to psycopg 3.

Email verification is an intentionally disabled v1 stub (`EMAIL_VERIFICATION_REQUIRED=false`). Do not turn it on until an email delivery adapter is connected. Signup still requires Terms acceptance.

## Quality checks

```bash
ruff check .
ruff format --check .
pytest
python -m scripts.smoke
```

CI runs lint, migrations, the fact-lock/auth/usage/billing/CSV suite, an import smoke test, a Docker build, and an HTTP container health check against PostgreSQL.

## Stripe webhook behavior

- Stripe signatures are verified before parsing event data.
- Processed event IDs are stored transactionally, so retries are idempotent.
- Checkout metadata maps a signed event to an immutable TrueDraft user and configured Price.
- Subscription changes derive plan from the current Stripe Price.
- Deleted, unpaid, incomplete, or otherwise inactive subscriptions fail closed to Free limits.
- Older out-of-order events cannot overwrite newer entitlement state.

The integration pins Stripe API version `2026-06-24.dahlia` and Stripe Python `15.3.1`.

## License

MIT. See [LICENSE](LICENSE).
