# Deployment notes

Railway is the primary supported production target. Follow the 12-step runbook in the root [README](../README.md#railway-production-runbook-12-steps) and the ordered operator sequence in [SHIP_CHECKLIST.md](../SHIP_CHECKLIST.md). Those two files are the canonical source for environment variables, PostgreSQL, Stripe webhooks, the Customer Portal, custom domains, and the test-mode → live verification sequence.

The four remaining launch items are operator-owned. The paid PostgreSQL/auth/billing path is canonical on `main`; the earlier SQLite / guest-identity line is retired. See the completed [merge record](MERGE_STRATEGY.md).

## Container contract

- Image default: `ENV=production` (Compose overrides to `development`)
- External port: `$PORT` (default `8080`)
- Health check: `GET /healthz`
- Stripe webhook: `POST /webhooks/stripe`
- Checkout return: `/About_Pricing?checkout=success` or `?checkout=cancelled`
- Portal return: `/About_Pricing?portal=return`
- Startup migration: `python -m core.migrate` → `alembic upgrade head`
- Processes behind nginx: FastAPI on `127.0.0.1:8000`, Streamlit on `127.0.0.1:8501`
- Streamlit: headless, viewer toolbar, usage stats off, built-in dataframe export/copy controls off so confirmed download buttons remain the export path
- Runtime user: non-root UID/GID `10001`

A bare `docker run` of this image without production variables **must fail to start**. That is intentional. Use `docker compose up --build` for the local path.

The health endpoint checks the migrated `users` table, not merely process liveness. A container with an unreachable or unmigrated database stays unhealthy.

## Production vs local

| | Local / CI | Production |
|---|---|---|
| How it starts | `docker compose up --build` | Railway from this Dockerfile |
| `ENV` | Compose sets `development` | Image default `production` |
| Database | Compose Postgres, or SQLite for unit tests | Railway PostgreSQL only |
| `PUBLIC_BASE_URL` | `http://localhost:8080` | public `https://` origin |
| `SESSION_SECRET` | documented example (rejected in prod) | unique 32+ characters |
| `SESSION_COOKIE_SECURE` | `false` | `true` |
| Stripe | empty; billing buttons disabled | test-mode first, then live restricted key + webhook + three Price IDs |
| Auth bypasses | none on this branch | none; leftover `LISTINGFORGE_*` / `*_SKIP_AUTH` vars are launch blockers |

Production refuses SQLite, HTTP or localhost `PUBLIC_BASE_URL`, insecure cookies, and documented/default `SESSION_SECRET` values. `python -m scripts.launch_check` reports remaining operator blockers, prints the next action, and exits 1 in production until the public-traffic gate passes. It never prints secrets.

Streamlit Community Cloud is not a supported paid-production target because this architecture needs a durable PostgreSQL database, a same-origin auth/webhook edge, and persistent secret-backed sessions.
