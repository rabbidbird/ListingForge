"""
About, pricing, and launch readiness for ListingForge
"""

import streamlit as st

from core.auth import user_id
from core.usage import get_usage
from core.billing import get_upgrade_options, stripe_enabled
from core.usage import PLANS


st.set_page_config(page_title="About & Pricing | ListingForge", page_icon="💎", layout="wide")

st.title("About ListingForge")

viewer_user_id = user_id()
usage = get_usage(viewer_user_id)
st.markdown(
    f"### Account status\n"
    f"Current plan: **{usage['plan_label']}**  \n"
    f"Today's usage: **{usage['daily']}** / {usage['daily_limit'] or 'unlimited'}  \n"
    f"Monthly usage: **{usage['monthly']}** / {usage['monthly_limit'] or 'unlimited'}  \n"
    f"Remaining this period: "
    f"{usage['remaining_total'] if usage['remaining_total'] is not None else 'unlimited'}"
)

st.markdown(
    """
## What this is

ListingForge is a **self-hosted draft generator** for product titles, descriptions, and tags.
It is designed to help you produce high-quality listing drafts that you can quickly review and edit before publishing.

### Current limits

- Free: {free_daily} generations/day, {free_monthly} generations/month (local SQLite history)
- Starter: {starter_daily} generations/day, {starter_monthly} generations/month
- Pro / Agency: unlimited generation

### Launch readiness checklist

1. [x] Local usage limits + plan metadata
2. [x] SEO scoring + template + optional LLM backend
3. [x] Global auth helpers and per-user usage/history isolation wired through `core.auth`
4. [ ] Managed database + backups (PostgreSQL or equivalent)
5. [ ] Production Stripe webhooks + reconciliation
6. [ ] Marketplace-specific policy compliance checks

This is functional for controlled launch and pilot traffic.
""".format(
        free_daily=PLANS["free"]["daily"],
        free_monthly=PLANS["free"]["monthly"],
        starter_daily=PLANS["starter"]["daily"],
        starter_monthly=PLANS["starter"]["monthly"],
    )
)

st.markdown("### Plans")
if stripe_enabled():
    st.success("Stripe is configured. Add a production checkout endpoint before launch.")
else:
    st.info("Stripe is not configured. Set STRIPE_* env vars when enabling paid plans.")

for option in get_upgrade_options():
    st.markdown(
        f"- **{option['label']}** (`{option['plan']}`): "
        f"{option['price']} — {option['desc']} "
        f"(price_id: `{option['price_id'] or 'not set'}`)"
    )

st.markdown(
    """
### Billing behavior

Webhook events are expected to carry a `plan` in metadata or a known Stripe `price_id`.
When a payment event is received, the user plan is updated in the local `usage_users` table.
"""
)

st.markdown(
    """
### Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Optional single-tenant auth for early demos:

```bash
export LISTINGFORGE_SKIP_AUTH=true
export LISTINGFORGE_PASSWORD=your-secret
```

`LISTINGFORGE_USER_ID` can also be set for per-install usage tracking.
"""
)
