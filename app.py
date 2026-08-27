"""SellerDrafts public landing page and authenticated product home."""

from __future__ import annotations

import streamlit as st

from core.auth import streamlit_current_user
from core.copy import HERO_SUPPORT, PRODUCT_NAME, PROMISE, TAGLINE
from core.ui import (
    configure_page,
    draft_banner,
    heuristic_notice,
    render_claim_categories,
    render_feature_grid,
    render_how_it_works,
    render_plan_teaser,
    render_positioning,
    render_public_ctas,
    render_public_footer,
    render_quota_notice,
    render_sidebar,
    render_trust_grid,
)
from core.usage import get_usage

configure_page(
    "Home",
    "✍️",
    browser_title=f"{PRODUCT_NAME} — Fact-locked listing drafts",
)
user = streamlit_current_user()
render_sidebar(user)

if user is None:
    st.markdown('<p class="sd-eyebrow">Etsy-first listing workflow</p>', unsafe_allow_html=True)
    st.title("Etsy listing drafts that stay inside the facts")
    st.markdown(f'<p class="sd-lede">{PROMISE}</p>', unsafe_allow_html=True)
    st.write(HERO_SUPPORT)
    st.caption(TAGLINE)
    draft_banner()
    render_public_ctas(include_plans=False)
    st.caption(
        "Create account → generate one template draft → find it later in private History. "
        "Already registered? Sign in."
    )
    st.divider()
    render_positioning()
    st.divider()
    render_how_it_works()
    st.divider()
    render_feature_grid()
    st.divider()
    render_trust_grid()
    st.divider()
    render_claim_categories()
    st.divider()
    render_plan_teaser()
    heuristic_notice()
    render_public_footer()
else:
    st.markdown(f'<p class="sd-eyebrow">{PRODUCT_NAME}</p>', unsafe_allow_html=True)
    st.title("Draft workspace")
    st.caption(TAGLINE)
    draft_banner()
    usage = get_usage(user.id)
    st.success(f"Welcome back, {user.name}.")
    first, second, third = st.columns(3)
    first.metric("Plan", str(usage["plan"]).title())
    second.metric("Today (UTC)", f"{usage['daily']} / {usage['daily_limit']}")
    third.metric("This month (UTC)", f"{usage['monthly']} / {usage['monthly_limit']}")
    render_quota_notice(usage)
    left, middle, right = st.columns(3)
    with left:
        if st.button("Create one draft", type="primary", use_container_width=True):
            st.switch_page("pages/1_Optimizer.py")
    with middle:
        if st.button("Process a CSV", use_container_width=True):
            st.switch_page("pages/2_Bulk_Processor.py")
    with right:
        if st.button("View plans", use_container_width=True):
            st.switch_page("pages/5_About_Pricing.py")
    st.divider()
    render_how_it_works()
    render_claim_categories()
    heuristic_notice()
    render_public_footer()
