# TrueDraft v1 human ship checklist

The code path is automated. Production refuses SQLite, HTTP public URLs, localhost
origins, insecure cookies, and documented/default session secrets. Only these
operator-owned steps remain before public launch:

- [ ] **Stripe Dashboard:** create monthly recurring USD Starter ($12), Pro ($29), and Agency ($79) Prices (or update the displayed currency/copy first); create a least-privilege live restricted API key; configure the Customer Portal; add the four documented webhook events at `https://YOUR_DOMAIN/webhooks/stripe`; copy the live Price IDs and signing secret.
- [ ] **Secrets and database:** add Railway PostgreSQL and set all required production variables from `.env.example`, including a unique 32+ character `SESSION_SECRET` that is not a documented example value, plus separate live Stripe credentials. Leave LLM disabled unless a provider key, model, caps, and data-processing terms are approved.
- [ ] **Domain:** attach the production domain, complete DNS/TLS, and set `PUBLIC_BASE_URL` to the final `https://` origin (not localhost).
- [ ] **Legal identity:** replace every `{{OPERATOR_LEGAL_NAME}}`, `{{CONTACT_EMAIL}}`, and `{{JURISDICTION}}` placeholder in `pages/6_Legal.py` after appropriate legal review.

Verify with `ENV=production python -m scripts.launch_check` after secrets are loaded. Do not accept paid public traffic until all four boxes are complete.
