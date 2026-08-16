# TrueDraft v1 human ship checklist

The code path is automated. Only these operator-owned steps remain before public launch:

- [ ] **Stripe Dashboard:** create monthly recurring USD Starter ($12), Pro ($29), and Agency ($79) Prices (or update the displayed currency/copy first); create a least-privilege live restricted API key; configure the Customer Portal; add the four documented webhook events at `https://YOUR_DOMAIN/webhooks/stripe`; copy the live Price IDs and signing secret.
- [ ] **Secrets and database:** add Railway PostgreSQL and set all required production variables from `.env.example`, including a unique 32+ character session secret and separate live Stripe credentials. Leave LLM disabled unless a provider key, model, caps, and data-processing terms are approved.
- [ ] **Domain:** attach the production domain, complete DNS/TLS, and set `PUBLIC_BASE_URL` to the final `https://` origin.
- [ ] **Legal identity:** replace every `{{OPERATOR_LEGAL_NAME}}`, `{{CONTACT_EMAIL}}`, and `{{JURISDICTION}}` placeholder in `pages/6_Legal.py` after appropriate legal review.

Do not accept paid public traffic until all four boxes are complete.
