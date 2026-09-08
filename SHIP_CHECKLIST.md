# SellerDrafts v1 human ship checklist

## September 8, 2026 repair checkpoint

**Hold product expansion and paid acquisition.** Activation, repeat use, actual
payments, and support load are unknown in this repair session. Passing code checks
is not business validation. See [repair evidence and rollout](docs/REPAIR_EVIDENCE.md)
and [measurement definitions](docs/MEASUREMENT.md).

- [x] Rechecked `origin/main` at `d5116320051670519a29bd5f19cb5989d1b473e2`;
  the working tree was clean and no repository AGENTS.md was present.
- [x] Pilot-readiness changes are already merged through PR #22. The previous
  instruction to merge that branch was stale.
- [x] Implemented rendered signup-link, complete-fact, validator, sample,
  paginated-history, and content-free measurement repairs on an isolated branch.
- [x] Verified local regression suite and the supported PostgreSQL/nginx/Streamlit
  container edge. Exact commands and outcomes are in the evidence record.
- [ ] Review, merge, and deploy this repair PR. Public `/auth/signup` still emitted
  the faulty link at the start of this session. No production deployment was made.
- [ ] Restore the operator's Railway login, then verify the deployed revision,
  production launch check, rendered Google links for every plan, and existing-account
  access. `railway status --json` returned Unauthorized; no production variables,
  customer records, or metrics were read. OAuth code/QA is complete with provider
  boundary fixtures; no external Google account was created for the owner.
- [ ] Verify mailbox routing and reply ownership for support and privacy, legal
  review, and the genuine paid lifecycle. Historical completion claims below are
  retained as operator records, not fresh verification or permission for outreach.

No price/tier, provider, inference-spending, marketplace-publishing, repository
visibility, or production account operation is part of this repair.

The code path is automated. Production refuses SQLite, HTTP public URLs, localhost
origins, insecure cookies, and documented/default session secrets. The container
image itself defaults to `ENV=production`, so a deploy that omits `ENV` fails
closed instead of booting a local SQLite demo.

The paid PostgreSQL/auth/billing path is now canonical on `main`. The retired
SQLite / guest-identity line remains only in Git history; do not restore it.

## Operator-owned boxes

- [x] **Pilot-readiness branch:** merged as PR #22. Deployment revision and current production auth/Terms behavior still require the release checks above.
- [ ] **Auth hardening after deploy:** verify production hides password registration, a direct password-signup POST fails closed, Google creates a genuinely new account, an existing matching-email password account is not auto-linked, and authenticated Account linking succeeds only with the same Google email.
- [ ] **Terms reacceptance after deploy:** verify an account storing an older Terms version is sent to the current `2026-08-27-v1` acceptance page, cannot enter `/app/` first, and can continue only after the CSRF-protected acceptance POST.
- [x] **Stripe live cutover:** the live Starter ($12), Pro ($29), and Agency ($79) monthly USD Products/Prices, webhook endpoint, Customer Portal, cancellation flow, and one-subscription limit are configured. Stripe reports live charges and payouts enabled. A least-privilege live restricted API key with Checkout Sessions and Customer Portal write access is stored only in Railway. The active application variables now use the live key, live Price IDs, and live webhook signing secret.
- [x] **Secrets and database:** Railway PostgreSQL and the production-safe base variables are configured. The inactive `STRIPE_LIVE_*_PENDING` staging variables were removed after cutover, the session secret was rotated, and `LLM_ENABLED=false`, `EMAIL_VERIFICATION_REQUIRED=false`, and secure cookies remain in force.
- [x] **Domain:** `sellerdrafts.com` is attached to Railway port 8080 through HTTP Public Networking, with Cloudflare DNS-only records and valid TLS. `PUBLIC_BASE_URL` is `https://sellerdrafts.com`. Verified URLs:
  - `https://sellerdrafts.com/healthz`
  - `https://sellerdrafts.com/webhooks/stripe`
  - `https://sellerdrafts.com/app/About_Pricing?checkout=success`
  - `https://sellerdrafts.com/app/About_Pricing?portal=return`
- [ ] **Legal/business review:** the public legal copy identifies Johnson Solutions LLC, doing business as SellerDrafts, with its contact and jurisdiction (Ohio, United States), and contains no template placeholders. Have the terms and privacy disclosures reviewed for the business before paid public traffic. Do not describe this as a completed legal review until it has occurred. MIT `LICENSE` is not a substitute for the Terms.
- [ ] **Support and privacy channels:** manually send a test message to and receive a reply from `support@sellerdrafts.com` and `privacy@sellerdrafts.com` through the intended mailbox/channel. Confirm routing, reply ownership, and the process for privacy requests without recording credentials or customer content in this repository.
- [ ] **First genuine customer lifecycle:** the earlier operator record describes hourly read-only monitoring for a genuine $12 Starter Checkout, webhook, entitlement, portal, and cancellation/fallback. Its current status and outcomes were not verified in this repair session; do not manufacture a live payment.
- [ ] **Founding-seller pilot evidence:** manually recruit founding Etsy sellers and record only aggregate activation/payment outcomes. Paid advertising stays paused until security/Terms changes are deployed, legal and email-channel gates pass, and the pilot produces real activation and payment evidence.

## Historical cutover record (not reverified by the September repair)

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

The earlier technical public-traffic gate passed and live billing was enabled.
Those are historical operator records. Current production readiness and customer
demand are unverified here. Keep paid ads and expansion paused until the current
release, legal, mailbox, activation, repeat-use, payment, and support checks pass.
