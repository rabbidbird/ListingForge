# ListingForge (v0.1 — Self-Hosted Alpha)

**Fact-locked draft generator for product listings.**

This is a **self-hosted / single-user alpha**, not a production multi-tenant SaaS.

It helps sellers draft titles, descriptions, and tags for Etsy, Shopify, and similar platforms.  
All output is a **draft that requires human verification** before publishing.

## What it does

- Generates draft titles, descriptions, and tags from the details *you* supply
- Scores the draft with a transparent heuristic checklist
- Supports bulk CSV processing
- Optional real LLM backend (OpenAI-compatible / xAI Grok) when an API key is present
- Local history and export
- Free-tier style usage limits (local tracking)

## Critical design rules (fact-locking)

- The generator **does not invent** materials, ratings, “bestseller”, shipping claims, “handmade”, certifications, or other factual attributes you did not provide.
- Missing fields stay missing.
- Every generation is clearly labeled as a draft that must be reviewed.

## Quick start

```bash
git clone https://github.com/rabbidbird/ListingForge.git
cd ListingForge
pip install -r requirements.txt
streamlit run app.py
```

Optional:

```bash
export OPENAI_API_KEY=sk-...          # or XAI_API_KEY for Grok
export LISTINGFORGE_REQUIRE_AUTH=true # enable simple password gate
export LISTINGFORGE_PASSWORD=yourpass
```

## What this is not

- Not a multi-user production SaaS
- Not a ranking predictor
- Not a substitute for reviewing your own product claims
- Not ready for public paid launch under the current name without further work (auth, database, billing, brand clearance)

## Free-tier limits (local)

- 8 generations per day
- 40 generations per month

These are enforced locally via `core/usage.py`. They are not a substitute for real per-user billing.

## License

MIT — you own the code. You may rebrand, sell, or modify it.

## Honest status

v0.1 self-hosted alpha. Suitable for personal use or closed testing after review.  
See the independent audit notes in project history for the full list of requirements before any public paid release.
