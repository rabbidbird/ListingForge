# TrueDraft v1 human ship checklist

The code path is automated. Production refuses SQLite, HTTP public URLs, localhost
origins, insecure cookies, and documented/default session secrets. The container
image itself defaults to `ENV=production`, so a deploy that omits `ENV` fails
closed instead of booting a local SQLite demo.

The paid PostgreSQL/auth/billing path is now canonical on `main`. The retired
SQLite / guest-identity line remains only in Git history; do not restore it.

## Operator-owned boxes

- [ ] **Stripe Dashboard:** create a separate Product for Starter ($12), Pro ($29), and Agency ($79), each with its own monthly recurring USD Price (or update the displayed currency/copy in `core/plans.py` first). Copy the three `price_...` IDs — never Product IDs (`prod_...`). Create a least-privilege live restricted API key (`rk_live_...`). Enable the Customer Portal for plan changes, payment-method updates, and cancellation. **Limit customers to one subscription** as defense in depth; the app also reuses one persisted open Checkout per user. Subscribe these events at `https://YOUR_DOMAIN/webhooks/stripe`:
  - required: `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`
  - recommended: `invoice.payment_failed`, `invoice.paid`, `checkout.session.async_payment_failed`, `checkout.session.expired`
  - copy the `whsec_...` signing secret
- [ ] **Secrets and database:** add Railway PostgreSQL and set every required production variable from `.env.example`. `ENV=production` (already the image default). Unique 32+ character `SESSION_SECRET` that is not a documented example. `SESSION_COOKIE_SECURE=true`. Separate Stripe credentials (`STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_AGENCY`). Do not set `LISTINGFORGE_*`, `TRUEDRAFT_SKIP_AUTH`, `STRIPE_SUCCESS_URL`, or `STRIPE_CANCEL_URL`. Leave LLM disabled unless a provider key, model, caps, and data-processing terms are approved; the model only orders complete source-phrase IDs and free-form prose is rejected. Keep `EMAIL_VERIFICATION_REQUIRED=false` until an email adapter exists.
- [x] **Domain:** `sellerdrafts.com` is attached to Railway port 8080 through HTTP Public Networking, with Cloudflare DNS-only records and valid TLS. `PUBLIC_BASE_URL` is `https://sellerdrafts.com`. Verified URLs:
  - `https://sellerdrafts.com/healthz`
  - `https://sellerdrafts.com/webhooks/stripe`
  - `https://sellerdrafts.com/About_Pricing?checkout=success`
  - `https://sellerdrafts.com/About_Pricing?portal=return`
- [ ] **Legal review:** `pages/6_Legal.py` contains the operator-supplied identity (Jaylen Johnson), contact email, and jurisdiction (Ohio, United States), with no template placeholders remaining. Have those terms reviewed for the business before paid public traffic. MIT `LICENSE` is not a substitute for the Terms.

## Ordered execution (do this in order)

Use **test-mode Stripe first**. Do not point live Price IDs and a live key at a public domain until step 9.

1. Create the Railway project from this repo. Add Railway PostgreSQL and expose `DATABASE_URL`. Use Railway HTTP Public Networking for the app; do not create an app TCP Proxy.
2. Set production variables. For the first deploy, Stripe values may be **test-mode** (`rk_test_...` / `sk_test_...`, test `price_...`, test `whsec_...`). Still set `ENV=production`, a unique `SESSION_SECRET`, `SESSION_COOKIE_SECURE=true`, and a temporary `PUBLIC_BASE_URL` of the Railway HTTPS origin.
3. Deploy. `/healthz` must return ok. If the container will not start, read the boot logs — production fail-closed refuses SQLite, documented secrets, and localhost URLs.
4. Attach the custom domain, finish DNS/TLS, set `PUBLIC_BASE_URL=https://sellerdrafts.com`, redeploy. **Complete.**
5. In Stripe **test** mode, add the webhook URL and Customer Portal settings from the first box. Confirm “limit customers to one subscription”.
6. On a machine that can see the production env vars (or in a one-off Railway shell):

   ```bash
   ENV=production python -m scripts.launch_check
   ```

   Expect `public-traffic gate: blocked` while the Stripe key is test-mode and until legal placeholders are gone. Test mode is an intentional launch **blocker**, not a warning-only pass. Follow the printed `next:` line. The command must not print secrets.
7. **Product smoke (test mode):** create an account → generate one template draft → confirm it appears only in that account’s History.
8. **Billing smoke (test mode):** Checkout Starter or Pro → return `?checkout=success` → refresh until the plan is paid → open the Customer Portal → cancel or change payment method → confirm return `?portal=return` and that inactive statuses fall back to Free limits.
9. Have the populated legal identity and terms reviewed, correcting them if needed. Switch Stripe variables to **live** (`rk_live_...`, live `price_...`, live `whsec_...`). Redeploy.
10. Re-run `ENV=production python -m scripts.launch_check`. It must print `public-traffic gate: pass` and exit `0`. A remaining test-mode key keeps the gate blocked.
11. After `launch_check` passes against live configuration, open paid traffic and monitor the first genuine $12 Starter Checkout, webhook delivery, entitlement update, portal access, and cancellation lifecycle. Do not use test card numbers, Test Clocks, or the operator's own real payment details to test live mode.

Do not accept paid public traffic until all four boxes are complete and launch_check passes against the live variable set.
