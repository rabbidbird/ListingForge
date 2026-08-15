# TrueDraft (v0.2)

**Fact-locked draft generator for product listings — with accounts, plans, and Stripe-ready billing.**

TrueDraft helps sellers create **draft** titles, descriptions, and tags from the facts they supply.  
It does **not** invent materials, ratings, shipping claims, or other product attributes.

## Status

Closer to paid launch than v0.1, but still requires:

- Final brand/domain/trademark clearance for “TrueDraft”
- Production PostgreSQL (SQLite is fine for early users only)
- Live Stripe price IDs + webhook endpoint
- Operator legal entity + filled-in contact details on Legal pages

## Features

- Fact-locked generation (template + optional LLM)
- User accounts (streamlit-authenticator)
- Per-user history and usage isolation
- Free / Starter / Pro / Agency plan limits
- Stripe Checkout skeleton
- Bulk CSV mode
- SEO checklist scores
- Terms, Privacy, Acceptable Use pages
- Docker (non-root, healthcheck)
- Basic automated tests (`tests/test_fact_lock.py`)

## Quick start

```bash
git clone https://github.com/rabbidbird/ListingForge.git
cd ListingForge
pip install -r requirements.txt
streamlit run app.py
```

Default demo login: **demo** / **secret**  
(Change in `config/credentials.yaml`)

Skip auth for local solo use:

```bash
export TRUEDRAFT_SKIP_AUTH=true
```

## Stripe (optional)

```bash
export STRIPE_SECRET_KEY=sk_live_...
export STRIPE_WEBHOOK_SECRET=whsec_...
export STRIPE_PRICE_STARTER=price_...
export STRIPE_PRICE_PRO=price_...
export STRIPE_PRICE_AGENCY=price_...
```

Upgrade buttons appear on the Pricing page when configured.

## License

MIT
