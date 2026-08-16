# Deployment notes

Railway is the primary supported production target. Follow the 12-step runbook in the root [README](../README.md#railway-production-runbook-12-steps); it is the canonical source for environment variables, PostgreSQL, Stripe webhooks, the Customer Portal, custom domains, and the live smoke sequence.

## Container contract

- External port: `$PORT` (default `8080`)
- Health check: `GET /healthz`
- Stripe webhook: `POST /webhooks/stripe`
- Startup migration: `python -m core.migrate` → `alembic upgrade head`
- Processes behind nginx: FastAPI on `127.0.0.1:8000`, Streamlit on `127.0.0.1:8501`
- Runtime user: non-root UID/GID `10001`

The health endpoint checks the migrated `users` table, not merely process liveness. A container with an unreachable or unmigrated database stays unhealthy.

Streamlit Community Cloud is not a supported paid-production target because this architecture needs a durable PostgreSQL database, a same-origin auth/webhook edge, and persistent secret-backed sessions. It may be adapted as a private UI demo only, without billing claims.
