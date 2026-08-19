# ListingForge (v0.2)

AI-assisted product listing optimizer for Etsy, Shopify, and Amazon.
Generates draft-friendly titles, descriptions, tags, and SEO checks from your input.

## Status

ListingForge is close to production-ready for controlled launches.

- Local usage limits and plans are now enforced
- Optional LLM generation (OpenAI / xAI compatible) is integrated
- Billing symbols now map to actual plan metadata
- CI scaffold and launch checklist are in progress

## Features

- Fact-locked template engine (no hallucinated product facts)
- Optional LLM generation when an API key is configured
- Single and bulk listing optimization
- SEO scoring with per-section feedback
- Local history in SQLite
- Local usage tracking + plan configuration
- Optional payment upgrade surfaces (Stripe-ready)

## Quick start

```bash
git clone https://github.com/rabbidbird/ListingForge.git
cd ListingForge
pip install -r requirements.txt
streamlit run app.py
```

### Env / secrets

```bash
OPENAI_API_KEY=sk-...
# or
XAI_API_KEY=xai-...
OPENAI_BASE_URL=https://api.x.ai/v1

# Optional demo auth bypass
LISTINGFORGE_SKIP_AUTH=true
LISTINGFORGE_REQUIRE_AUTH=false
LISTINGFORGE_USER_ID=local

# Optional usage tuning
LISTINGFORGE_DEFAULT_PLAN=free
LISTINGFORGE_FREE_DAILY_LIMIT=8
LISTINGFORGE_FREE_MONTHLY_LIMIT=40
```

## Stripe (optional)

```bash
export STRIPE_SECRET_KEY=sk_live_...
export STRIPE_WEBHOOK_SECRET=whsec_...
export STRIPE_PRICE_STARTER=price_...
export STRIPE_PRICE_PRO=price_...
export STRIPE_PRICE_AGENCY=price_...
```

Upgrade buttons/links appear on `pages/5_About_Pricing.py` when Stripe is configured.

## Notes

`LISTINGFORGE_REQUIRE_AUTH=true` is intended for production launch. Keep it `false` during local demo/development.
`LISTINGFORGE_SKIP_AUTH=true` and `TRUEDRAFT_SKIP_AUTH=true` are intended for local/dev only.
When auth is disabled and `LISTINGFORGE_USER_ID` is not set, each browser session gets a generated guest user ID so usage/history remain isolated across sessions.

## License

MIT
