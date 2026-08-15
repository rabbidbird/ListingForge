"""
About & honest status for ListingForge v0.1
"""

import streamlit as st

st.set_page_config(page_title="About | ListingForge", page_icon="💎", layout="wide")

st.title("About ListingForge (v0.1 Alpha)")

st.markdown("""
## What this is

ListingForge is a **self-hosted draft generator** for product titles, descriptions, and tags.

It is designed to help you start from the facts *you* provide, then produce a draft you must review and edit before publishing.

### Core rule
**It does not invent product facts.**  
Materials, ratings, shipping claims, “handmade”, certifications, stock status, and similar statements only appear if you supplied them.

---

## Current limits (local free-tier style)

- 8 generations per day  
- 40 generations per month  

Tracked locally. Suitable for personal or single-user use.

---

## Recommended next steps if you want a commercial product

1. **Rename** — “ListingForge” is already used by other live products in the same space. Choose a distinctive name and clear domains / trademarks.
2. **Real accounts + authorization** — per-user isolation, not a shared SQLite file.
3. **Managed database** (PostgreSQL) with migrations and backups.
4. **Stripe + real entitlements** — Checkout, webhooks, per-plan limits.
5. **Marketplace-specific adapters** with current official rules for Etsy, Amazon, Shopify.
6. **CI, tests, pinned deploys, monitoring**.
7. **Legal pages** — privacy, terms, acceptable use, disclosure that output is a draft.

Until those are done, treat this as a private / self-hosted tool, not a public paid SaaS.

---

## How to run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Optional password gate:

```bash
export LISTINGFORGE_REQUIRE_AUTH=true
export LISTINGFORGE_PASSWORD=your-secret
```

---

## Ownership

MIT licensed. You own the code.
""")

st.info("All generated content is a draft. Verify every claim against your actual product before publishing.")
