# SellerDrafts v1 human ship checklist

The code path is automated. Production refuses SQLite, HTTP public URLs, localhost
origins, insecure cookies, and documented/default session secrets. The container
image itself defaults to `ENV=production`, so a deploy that omits `ENV` fails
closed instead of booting a local SQLite demo.

The paid PostgreSQL/auth/billing path is now canonical on `main`. The retired
SQLite / guest-identity line remains only in Git history; do not restore it.

## Operator-owned boxes

- [x] **Stripe live cutover:** the live Starter ($12), Pro ($29), and Agency ($79) monthly USD Products/Prices, webhook endpoint, Customer Portal, cancellation flow, and one-subscription limit are configured. Stripe reports live charges and payouts enabled. A least-privilege live restricted API key with Checkout Sessions and Customer Portal write access is stored only in Railway. The active application variables now use the live key, live Price IDs, and live webhook signing secret.
- [x] **Secrets and database:** Railway PostgreSQL and the production-safe base variables are configured. The inactive `STRIPE_LIVE_*_PENDING` staging variables were removed after cutover, the session secret was rotated, and `LLM_ENABLED=false`, `EMAIL_VERIFICATION_REQUIRED=false`, and secure cookies remain in force.
- [x] **Domain:** `sellerdrafts.com` is attached to Railway port 8080 through HTTP Public Networking, with Cloudflare DNS-only records and valid TLS. `PUBLIC_BASE_URL` is `https://sellerdrafts.com`. Verified URLs:
  - `https://sellerdrafts.com/healthz`
  - `https://sellerdrafts.com/webhooks/stripe`
  - `https://sellerdrafts.com/app/About_Pricing?checkout=success`
  - `https://sellerdrafts.com/app/About_Pricing?portal=return`
- [ ] **Legal review:** `pages/6_Legal.py` identifies Johnson Solutions LLC, doing business as SellerDrafts, with the operator-supplied contact email and jurisdiction (Ohio, United States), and contains no template placeholders. Have those terms reviewed for the business before paid public traffic. MIT `LICENSE` is not a substitute for the Terms.
- [ ] **First genuine customer lifecycle:** hourly read-only monitoring is active for the first genuine $12 Starter Checkout, successful webhook delivery, entitlement update, portal access, and customer-initiated cancellation/fallback. The live baseline contained no completed Checkout Sessions; do not manufacture one.

## Ordered execution (do this in order)

Use **test-mode Stripe first**. Do not point live Price IDs and a live key at a public domain until step 9.

1. **Complete:** Railway project, PostgreSQL, and HTTP Public Networking are configured; no app TCP Proxy is present.
2. **Complete:** production-safe base variables and Stripe test-mode values are set. LLM and email verification remain disabled.
3. **Complete:** the Railway deployment is healthy and `/healthz` returns `200`.
4. Attach the custom domain, finish DNS/TLS, set `PUBLIC_BASE_URL=https://sellerdrafts.com`, redeploy. **Complete.**
5. **Complete:** Stripe test-mode webhook, Customer Portal settings, and “limit customers to one subscription” are configured.
6. **Complete:** in the Railway production console:

   ```bash
   ENV=production python -m scripts.launch_check
   ```

   The final live-configuration run printed `public-traffic gate: pass` and exited `0`. The command did not print secrets.
7. **Complete:** a new production account generated one product-name-only template draft, and the draft appeared in that account's private History with the required draft warning.
8. **Complete:** Stripe Sandbox charged the standard test card $12 for Starter, returned to `?checkout=success`, and the signed webhooks changed the account from Free to active Starter. The Customer Portal opened in test mode and scheduled cancellation. The test subscription was then canceled immediately through Stripe without a Test Clock; signed cancellation webhooks returned `200`, `?portal=return` loaded, and the account fell back to Free limits.
9. **Technical cutover complete:** the least-privilege live restricted key and live billing values are active, the service was redeployed successfully, and no inactive `STRIPE_LIVE_*_PENDING` variables remain. Legal review is still required in the operator-owned box above.
10. **Complete:** `ENV=production python -m scripts.launch_check` printed `public-traffic gate: pass` and exited `0` against the live Railway configuration.
11. **Monitoring active:** paid Checkout is enabled and an hourly read-only monitor is watching for the first genuine $12 Starter Checkout, webhook delivery, entitlement update, portal access, and cancellation lifecycle. Do not use test card numbers, Test Clocks, or the operator's own real payment details to test live mode.

The technical public-traffic gate passes and live billing is enabled. Complete the legal review before intentionally promoting paid traffic; the first genuine customer lifecycle remains an observed event, never a synthetic live test.
