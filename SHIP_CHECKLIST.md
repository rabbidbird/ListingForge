# TrueDraft v1 human ship checklist

The code path is automated. Production refuses SQLite, HTTP public URLs, localhost
origins, insecure cookies, and documented/default session secrets. Only these
operator-owned steps remain before public launch.

Do not merge `main`'s local SQLite / guest-identity commits into this branch.
See [docs/MERGE_STRATEGY.md](docs/MERGE_STRATEGY.md).

- [ ] **Stripe Dashboard:** create monthly recurring USD Starter ($12), Pro ($29), and Agency ($79) Prices (or update the displayed currency/copy in `core/plans.py` first); create a least-privilege live restricted API key (`rk_live_...`); enable the Customer Portal for plan changes, payment-method updates, and cancellation; subscribe the four entitlement events plus the two deferred invoice events at `https://YOUR_DOMAIN/webhooks/stripe`:
  - `checkout.session.completed`
  - `checkout.session.async_payment_succeeded`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - optional but recommended: `invoice.payment_failed`, `invoice.paid`, `checkout.session.async_payment_failed`, `checkout.session.expired`
  - copy the three live `price_...` IDs and the `whsec_...` signing secret
- [ ] **Secrets and database:** add Railway PostgreSQL and set every required production variable from `.env.example`. `ENV=production`. Unique 32+ character `SESSION_SECRET` that is not a documented example. `SESSION_COOKIE_SECURE=true`. Separate live Stripe credentials (`STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_AGENCY`). Do not set `LISTINGFORGE_*`, `TRUEDRAFT_SKIP_AUTH`, `STRIPE_SUCCESS_URL`, or `STRIPE_CANCEL_URL` — those belong to the abandoned local-demo path. Leave LLM disabled unless a provider key, model, caps, and data-processing terms are approved. Keep `EMAIL_VERIFICATION_REQUIRED=false` until an email adapter exists.
- [ ] **Domain:** attach the production domain, complete DNS/TLS, and set `PUBLIC_BASE_URL` to the final `https://` origin (not localhost, not `http://`). Derived URLs that must work after this:
  - `https://YOUR_DOMAIN/healthz`
  - `https://YOUR_DOMAIN/webhooks/stripe`
  - `https://YOUR_DOMAIN/About_Pricing?checkout=success`
  - `https://YOUR_DOMAIN/About_Pricing?portal=return`
- [ ] **Legal identity:** replace every `{{OPERATOR_LEGAL_NAME}}`, `{{CONTACT_EMAIL}}`, and `{{JURISDICTION}}` placeholder in `pages/6_Legal.py` after appropriate legal review. MIT `LICENSE` is not a substitute for those Terms.

Verify with:

```bash
ENV=production python -m scripts.launch_check
```

That command must print `public-traffic gate: pass` and exit `0`. In production it exits `1` on any remaining blocker (including a config error that would otherwise crash the process). It never prints secrets.

Do not accept paid public traffic until all four boxes are complete and launch_check passes in the production environment.
