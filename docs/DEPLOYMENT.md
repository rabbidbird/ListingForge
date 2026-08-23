# Deployment notes

Railway is the primary supported production target. Follow the 12-step runbook in the root [README](../README.md#railway-production-runbook-12-steps) and the ordered operator sequence in [SHIP_CHECKLIST.md](../SHIP_CHECKLIST.md). Those two files are the canonical source for environment variables, PostgreSQL, Stripe webhooks, the Customer Portal, custom domains, and the test-mode → live verification sequence.

The four remaining launch items are operator-owned. The paid PostgreSQL/auth/billing path is canonical on `main`; the earlier SQLite / guest-identity line is retired. See the completed [merge record](MERGE_STRATEGY.md).

## Container contract

- Image default: `ENV=production` (Compose overrides to `development`)
- External port: `$PORT` (default `8080`)
- Health check: `GET /healthz` (database reachable and exactly at the repository's Alembic head)
- Stripe webhook: `POST /webhooks/stripe`
- Checkout return: `/About_Pricing?checkout=success` or `?checkout=cancelled`
- Portal return: `/About_Pricing?portal=return`
- Startup migration: `python -m core.migrate` → `alembic upgrade head`
- Processes behind nginx: FastAPI on `127.0.0.1:8000`, Streamlit on `127.0.0.1:8501`
- Streamlit: headless, viewer toolbar, usage stats off, built-in dataframe export/copy controls off so confirmed download buttons remain the export path
- Runtime user: non-root UID/GID `10001`
- Abuse edge: nginx applies per-client request/connection limits using Railway's injected [`X-Real-IP`](https://docs.railway.com/networking/public-networking/specs-and-limits) only when the server-side [`RAILWAY_ENVIRONMENT_ID`](https://docs.railway.com/variables/reference) and a valid edge marker are present. Direct/local deployments ignore those headers and use the network peer. A container-wide backstop covers every route; auth also has a tighter bounded per-source limiter in FastAPI.
- Network trust boundary: production supports Railway HTTP Public Networking only. Do not add a TCP Proxy or another direct public route to port 8080; forwarded client addresses are trusted only behind Railway's edge, which terminates TLS and forwards requests to the deployment.

A bare `docker run` of this image without production variables **must fail to start**. That is intentional. Use `docker compose up --build` for the local path.

The health endpoint checks both a database query and the current Alembic revision. A container with an unreachable, unmigrated, or outdated database stays unhealthy.

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

If adapting the image to another host, replace the Railway-specific forwarded-IP map with that host's documented trusted-proxy/network configuration. Do not expose the container directly while trusting client-supplied forwarding headers.
