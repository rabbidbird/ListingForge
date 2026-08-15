"""
About, Pricing & Monetization guide for ListingForge
"""

import streamlit as st

st.set_page_config(page_title="About & Pricing | ListingForge", page_icon="💎", layout="wide")

st.title("💎 About ListingForge & Pricing")

st.markdown("""
## What is ListingForge?

ListingForge is a complete micro-SaaS that turns basic product info into high-converting, SEO-optimized titles, descriptions, and tags for Etsy, Shopify, and Amazon sellers.

It is built to be deployed and sold.

---

## Current Free Tier

- **8 generations per day**
- **40 generations per month**
- Full access to Optimizer, Bulk mode, SEO Analyzer, and History

When you hit the limit you will see a clear upgrade message.

---

## Recommended Paid Plans

| Plan | Price | What you get |
|------|-------|--------------|
| **Starter** | $9–12 / month | 100 generations / month + bulk |
| **Pro** | $19–29 / month | Unlimited generations |
| **Agency** | $49–79 / month | Unlimited + white-label + multi-user |
| **Lifetime** | $97–147 one-time | Unlimited forever |

These price points are proven in the Etsy/Shopify tool space.

---

## How to turn this into revenue

1. **Deploy** the app (Streamlit Community Cloud is free and takes 2 minutes)
2. **Gate the free tier** (already implemented via `core/usage.py`)
3. **Add Stripe Checkout** for the paid plans
4. **Promote** in Etsy seller groups, Reddit, Product Hunt, and YouTube

### Stripe (high-level)

- Create 3–4 products in your Stripe Dashboard
- Add a “Upgrade” button that creates a Checkout Session
- On successful payment, raise or remove the limits in `core/usage.py` (or move limits to a real user database)

Full notes are in `docs/DEPLOYMENT.md`.

---

## Technical overview

- **Template engine** works offline with zero API cost
- **Optional real LLM** (OpenAI / xAI Grok) activates automatically when an API key is present
- History is stored in local SQLite
- All scoring logic is transparent and adjustable

---

## Ownership

You own this codebase. Sell it, rebrand it, open-source it, or keep it private.
""")

st.success("This is a functional, sellable product. Deploy it and start charging.")
