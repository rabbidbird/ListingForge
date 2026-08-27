# SellerDrafts v1 human ship checklist

The code path is automated. Production refuses SQLite, HTTP public URLs, localhost
origins, insecure cookies, and documented/default session secrets. The container
image itself defaults to `ENV=production`, so a deploy that omits `ENV` fails
closed instead of booting a local SQLite demo.

The paid PostgreSQL/auth/billing path is now canonical on `main`. The retired
SQLite / guest-identity line remains only in Git history; do not restore it.

## Operator-owned boxes

- [ ] **Stripe live cutover:** the live Starter ($12), Pro ($29), and Agency ($79) monthly USD Products/Prices, webhook endpoint, Customer Portal, cancellation flow, and one-subscription limit are configured. Stripe reports live charges and payouts enabled. Create a least-privilege live restricted API key (`rk_live_...`) with Checkout Sessions and Customer Portal write access, store it only in Railway, and complete steps 9–11 below. The app remains intentionally connected to Stripe test mode until then.
- [x] **Secrets and database:** Railway PostgreSQL and the production-safe base variables are configured. Active Stripe variables are test-mode; live Price IDs and the live webhook signing secret are stored separately as inactive pending values. `LLM_ENABLED=false`, `EMAIL_VERIFICATION_REQUIRED=false`, and secure cookies remain in force.
- [x] **Domain:** `sellerdrafts.com` is attached to Railway port 8080 through HTTP Public Networking, with Cloudflare DNS-only records and valid TLS. `PUBLIC_BASE_URL` is `https://sellerdrafts.com`. Verified URLs:
  - `https://sellerdrafts.com/healthz`
  - `https://sellerdrafts.com/webhooks/stripe`
  - `https://sellerdrafts.com/About_Pricing?checkout=success`
  - `https://sellerdrafts.com/About_Pricing?portal=return`
- [ ] **Legal review:** `pages/6_Legal.py` identifies Johnson Solutions LLC, doing business as SellerDrafts, with the operator-supplied contact email and jurisdiction (Ohio, United States), and contains no template placeholders. Have those terms reviewed for the business before paid public traffic. MIT `LICENSE` is not a substitute for the Terms.

## Ordered execution (do this in order)

Use **test-mode Stripe first**. Do not point live Price IDs and a live key at a public domain until step 9.

1. **Complete:** Railway project, PostgreSQL, and HTTP Public Networking are configured; no app TCP Proxy is present.
2. **Complete:** production-safe base variables and Stripe test-mode values are set. LLM and email verification remain disabled.
3. **Complete:** the Railway deployment is healthy and `/healthz` returns `200`.
4. Attach the custom domain, finish DNS/TLS, set `PUBLIC_BASE_URL=https://sellerdrafts.com`, redeploy. **Complete.**
5. **Complete:** Stripe test-mode webhook, Customer Portal settings, and “limit customers to one subscription” are configured.
6. On a machine that can see the production env vars (or in a one-off Railway shell):

   ```bash
   ENV=production python -m scripts.launch_check
   ```

   Expect `public-traffic gate: blocked` while the Stripe key is test-mode. Any remaining legal placeholders would also block launch. Test mode is an intentional launch **blocker**, not a warning-only pass. Follow the printed `next:` line. The command must not print secrets.
7. **Complete:** a new production account generated one product-name-only template draft, and the draft appeared in that account's private History with the required draft warning.
8. **Complete:** Stripe Sandbox charged the standard test card $12 for Starter, returned to `?checkout=success`, and the signed webhooks changed the account from Free to active Starter. The Customer Portal opened in test mode and scheduled cancellation. The test subscription was then canceled immediately through Stripe without a Test Clock; signed cancellation webhooks returned `200`, `?portal=return` loaded, and the account fell back to Free limits.
9. Have the populated legal identity and terms reviewed, correcting them if needed. Create the least-privilege live restricted key, then replace the active Stripe variables with the live key, live Price IDs, and live webhook signing secret. Redeploy. Do not leave the inactive `STRIPE_LIVE_*_PENDING` staging variables in place after the cutover is verified.
10. Re-run `ENV=production python -m scripts.launch_check`. It must print `public-traffic gate: pass` and exit `0`. A remaining test-mode key keeps the gate blocked.
11. After `launch_check` passes against live configuration, open paid traffic and monitor the first genuine $12 Starter Checkout, webhook delivery, entitlement update, portal access, and cancellation lifecycle. Do not use test card numbers, Test Clocks, or the operator's own real payment details to test live mode.

Do not accept paid public traffic until all four boxes are complete and launch_check passes against the live variable set.
