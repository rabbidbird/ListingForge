# SellerDrafts

SellerDrafts is a fact-locked **draft** listing generator for Etsy, Shopify, and Amazon-style marketplaces. It creates a title, description, and tags only from product facts the user supplies. Every result remains a starting draft that requires human review.

The repository name remains ListingForge. The public product and all current user-facing copy use SellerDrafts.

## Release status

The technical service is live at `https://sellerdrafts.com`, with database accounts, per-user authorization, PostgreSQL migrations, transactional quotas, Stripe subscription webhooks, abuse controls, legal pages, a public marketing home, a non-root container, CI, and automated tests. It remains an unreviewed commercial pilot: do not intentionally promote it or activate paid acquisition until the separate pilot gates in [SHIP_CHECKLIST.md](SHIP_CHECKLIST.md) are completed. Changes on a feature branch are not live until reviewed, merged, and deployed.

The paid SellerDrafts v1 path is now the canonical `main` branch. An earlier local SQLite / guest-identity demo line is retained only in Git history and must not be restored. See the completed [merge record](docs/MERGE_STRATEGY.md).

The logged-out home is a conversion landing page (promise, how it works, trust, plan teaser). It does not invent testimonials, user counts, or marketplace-publish claims. Signed-in users still see plan/usage metrics and draft actions.

SellerDrafts never promises ranking, conversion, or sales. Its visible Pass/Review/Verify/Missing statuses are transparent heuristic checklist prompts only; legacy numeric fields remain internal for saved-record compatibility.
The dated first-party sources and qualifications behind the small platform checklist are recorded in [docs/PLATFORM_RULES.md](docs/PLATFORM_RULES.md); users must verify current category rules before publishing.

## Safety invariants

- Product facts such as materials, dimensions, origin, certifications, ratings, scarcity, and shipping claims must come from user input.
- An optional LLM is disabled by default. When enabled, it has per-user caps, a timeout, a token ceiling, and a kill switch. The model may select and order only opaque IDs for complete supplied phrases; deterministic code renders the draft, and invalid plans fall back to templates. Free-form model prose never reaches output.
- Every generation and export displays **DRAFT — verify before publishing**.
- Every listing read, update, delete, and export is filtered by `user_id` on the server.
- Production refuses SQLite, insecure session configuration, documented default secrets, and localhost public URLs.
- Paid entitlements fail closed: unknown Price IDs, unpaid Checkout, and any subscription status other than `active` / `trialing` keep Free limits.

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

- Streamlit provides the authenticated product UI under `/app/`.
- FastAPI owns crawlable public pages, Google-backed production account creation, existing password-account login/logout, HttpOnly session cookies, health checks, and Stripe webhooks. Password registration remains available only in development and tests.
- nginx exposes both processes on one origin and proxies Streamlit WebSockets.
- SQLAlchemy and Alembic manage PostgreSQL. SQLite is allowed only with `ENV=development` or `ENV=test`.
- Stripe-hosted Checkout and Customer Portal handle payment UI; verified, idempotent webhooks control entitlements.

nginx applies per-client request/connection limits using Railway's injected client IP plus a generous container-wide backstop on every public route. Authentication also has a tighter bounded per-source soft limit in FastAPI; add a shared edge/WAF limiter before horizontal scaling.

Minimum tables are `users`, `listings`, `usage_events`, and `subscriptions`; v1 also uses `user_sessions` and `webhook_events`. Optional first-touch UTM labels are stored on a newly created user and never overwrite an existing account.

## Search discovery and campaign measurement

FastAPI server-renders the public home, pricing, legal page, and three Etsy seller guides. `/robots.txt` allows public search crawlers and OAI-SearchBot while excluding the authenticated workspace; `/sitemap.xml` lists canonical public URLs only. Private Streamlit and authentication routes send or receive `noindex` directives. SellerDrafts does not use `llms.txt` or claim that indexing, ranking, or AI citation is guaranteed.

Submit `https://sellerdrafts.com/sitemap.xml` to Google Search Console and Bing Webmaster Tools after verifying the domain. Use each service's URL inspection tool to confirm the public HTML, canonical, and sitemap status.

Campaign links may include `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, and `utm_term`. A signed first-party cookie retains those labels for up to 30 days and attaches them only when a new account is created. It is not a TikTok or X advertising pixel. Aggregate outcomes can be inspected without account identifiers:

```bash
python -m scripts.acquisition_report --since 2026-08-27
```

The report measures signups, users with at least one draft, and users who are currently active on a paid plan. It does not measure visits, Checkout starts, or completed Checkouts.

The intended customer channels are `support@sellerdrafts.com` and `privacy@sellerdrafts.com`. Before any public promotion, manually send and receive a test through each channel and confirm the published mailbox routing and reply process; do not treat aliases as working merely because they appear in copy.

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

The paid SellerDrafts path is already on `main`. Use **test-mode Stripe first**.
The numbered order in [SHIP_CHECKLIST.md](SHIP_CHECKLIST.md) is authoritative
if anything here disagrees.

1. Create a Railway project from the repository. Railway will use `railway.toml` and the root `Dockerfile`. Expose the app only through Railway HTTP Public Networking; do not add a TCP Proxy or another direct public route to container port 8080.
2. Add a Railway PostgreSQL service and expose its `DATABASE_URL` to the SellerDrafts service.
3. In Stripe **test** mode, create one Product per plan, each with one monthly recurring USD Price matching the displayed copy: Starter $12, Pro $29, and Agency $79. Copy the `price_...` IDs (never `prod_...`). Create the separate live Products/Prices later, at the live switch, only after the test-mode Checkout cycle passes.
4. Create a least-privilege Stripe restricted API key for the Checkout, Customer, Subscription, and Billing Portal operations used here. Start with `rk_test_...` / `sk_test_...`. Do not put keys in Git.
5. Set the initial production variables from `.env.example`: `ENV=production` (already the image default), `DATABASE_URL`, the Railway HTTPS origin as `PUBLIC_BASE_URL`, a 32+ character `SESSION_SECRET`, `SESSION_COOKIE_SECURE=true`, `PORT=8080`, and the **test-mode** Stripe credentials. Billing buttons stay disabled until the signing secret is added. A container started without production variables fails closed instead of serving a local SQLite demo.
6. Deploy. Container startup runs `alembic upgrade head`; `/healthz` becomes healthy only after the migrated database is reachable.
7. Add the Railway custom domain, point DNS as Railway instructs, then set `PUBLIC_BASE_URL=https://YOUR_DOMAIN` and redeploy.
8. In Stripe **test** Workbench, add `https://YOUR_DOMAIN/webhooks/stripe` and subscribe at least `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `customer.subscription.created`, `customer.subscription.updated`, and `customer.subscription.deleted`. Copy its `whsec_...` value to `STRIPE_WEBHOOK_SECRET` and redeploy. Recommended extras: `invoice.payment_failed`, `invoice.paid`, `checkout.session.async_payment_failed`, `checkout.session.expired`.
9. Enable the Stripe Customer Portal (test mode) for subscription changes, cancellation, and payment-method management. Limit customers to one subscription as defense in depth; SellerDrafts also persists and reuses one open Checkout session per user.
10. Review the operator identity, contact email, Ohio jurisdiction, Terms, Privacy Policy, and Acceptable Use Policy before each public legal revision.
11. Run `ENV=production python -m scripts.launch_check` against the production variable set. Follow the printed `next:` line and the printed `verify:` sequence: signup → template draft → history, then test-mode Checkout → webhook → portal. A test-mode key is an expected **blocker** during verification and can never pass the public-traffic gate. Then switch Stripe variables to **live** (`rk_live_...`, live `price_...`, live `whsec_...`), redeploy, and re-run launch_check until it prints `public-traffic gate: pass` and exits 0.
12. Require the GitHub Actions `test` and `container-smoke` jobs on the default branch, then accept paid public traffic.

Do not enable Stripe automatic tax unless the operator has the registrations required for Stripe to calculate and collect tax. Use separate Stripe keys for test and live environments.

## Configuration

Copy `.env.example` only for local reference. Railway variables should be entered in its secret manager. `DATABASE_URL` accepts Railway's `postgres://`/`postgresql://` forms and is normalized to psycopg 3.

Email verification is an intentionally disabled v1 stub (`EMAIL_VERIFICATION_REQUIRED=false`). Do not turn it on until an email delivery adapter is connected. Production therefore supports Google for new accounts and keeps password login only for existing accounts; development/test password signup remains available. Every new account records the current Terms version, and stale accounts must reaccept before using the workspace.

Do not set `LISTINGFORGE_SKIP_AUTH`, `TRUEDRAFT_SKIP_AUTH`, `LISTINGFORGE_REQUIRE_AUTH`, `LISTINGFORGE_USER_ID`, `STRIPE_SUCCESS_URL`, or `STRIPE_CANCEL_URL`. Those names belong to the abandoned local-demo path. Checkout and portal URLs are derived from `PUBLIC_BASE_URL`.

## Quality checks

```bash
ruff check .
ruff format --check .
pytest
python -m core.migrate
python -m scripts.smoke
python -m scripts.launch_check
```

`python -m scripts.launch_check` is read-only. In `ENV=production` it exits 1 unless every public-traffic gate passes. It prints the next operator action and never prints secrets. Add `--strict` to fail in non-production environments as well.

CI runs lint, migrations, the fact-lock/auth/usage/billing/CSV suite, an import smoke test, and a Docker/PostgreSQL edge smoke. The auth suite proves production password signup is blocked. The container smoke provisions an internal fixture, verifies that the signup surface matches the stack environment, exercises existing-account login/session/logout through nginx, upgrades a Streamlit WebSocket, and checks signed/idempotent webhook delivery.

The final repository security review and residual operator checks are recorded in [docs/SECURITY_REVIEW.md](docs/SECURITY_REVIEW.md). Vulnerabilities should be disclosed privately through [SECURITY.md](SECURITY.md), not a public issue.

## Stripe webhook behavior

- Stripe signatures are verified before parsing event data.
- Processed event IDs are stored transactionally, so retries are idempotent.
- Checkout metadata and, when present, Checkout line-item Prices map a signed event to an immutable SellerDrafts user and a configured Price. The `plan` metadata field is never trusted. Line items do not need to be expanded in the Stripe dashboard; `metadata.price_id` is a signed fallback.
- One unexpired Checkout session is stored per user and plan. Repeated clicks reuse its URL; choosing another plan is blocked until that session completes or expires. Paid, failed, and expired Checkout events clear the pending session.
- `checkout.session.async_payment_succeeded` is handled the same as a paid completed Checkout so delayed payment methods can still grant entitlements.
- Subscription changes derive plan from the current Stripe Price. Unknown Prices fail closed to Free even when Stripe status is `active`.
- Deleted, unpaid, incomplete, paused, past_due, or otherwise inactive subscriptions fail closed to Free limits. Past-due accounts must use the Customer Portal; a second Checkout session is blocked.
- Older out-of-order events cannot overwrite newer entitlement state.
- Unhandled event types are acknowledged and recorded so Stripe does not retry them, but they never change entitlements. Invoice paid/failed events are acknowledged and deferred to `customer.subscription.updated`.

The integration pins Stripe API version `2026-07-29.dahlia` and Stripe Python `15.4.0`.

## License

MIT. See [LICENSE](LICENSE).
