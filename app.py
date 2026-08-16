"""TrueDraft public landing page and authenticated product home."""

from __future__ import annotations

import streamlit as st

from core.auth import streamlit_current_user
from core.ui import configure_page, draft_banner, heuristic_notice, render_sidebar
from core.usage import get_usage

configure_page("Home", "✍️")
user = streamlit_current_user()
render_sidebar(user)

st.title("TrueDraft")
st.subheader("Fact-locked product listing drafts from facts you supply")
st.write(
    "Create draft titles, descriptions, and tags for Etsy, Shopify, and Amazon-style "
    "marketplaces without silently filling in missing product attributes."
)
draft_banner()

if user is None:
    st.markdown("### Start with a free account")
    st.write("Free accounts include 8 generations per UTC day and 40 per UTC month.")
    left, right, _ = st.columns([1, 1, 2])
    with left:
        st.link_button("Create account", "/auth/signup", type="primary", use_container_width=True)
    with right:
        st.link_button("Sign in", "/auth/login", use_container_width=True)
else:
    usage = get_usage(user.id)
    st.success(f"Welcome back, {user.name}.")
    first, second, third = st.columns(3)
    first.metric("Plan", str(usage["plan"]).title())
    second.metric("Today (UTC)", f"{usage['daily']} / {usage['daily_limit']}")
    third.metric("This month (UTC)", f"{usage['monthly']} / {usage['monthly_limit']}")
    left, right, _ = st.columns([1, 1, 2])
    with left:
        if st.button("Create one draft", type="primary", use_container_width=True):
            st.switch_page("pages/1_Optimizer.py")
    with right:
        if st.button("Process a CSV", use_container_width=True):
            st.switch_page("pages/2_Bulk_Processor.py")

st.divider()
st.markdown("### What is locked")
one, two, three = st.columns(3)
with one:
    st.markdown(
        "**No silent product facts**  \n"
        "Materials, construction, ratings, certifications, shipping claims, and social proof "
        "must come from your input."
    )
with two:
    st.markdown(
        "**One account, one history**  \n"
        "Listings and usage are keyed to your immutable user ID and authorized on every read, "
        "update, and delete."
    )
with three:
    st.markdown(
        "**Review stays mandatory**  \n"
        "Exports remain behind a confirmation checklist. TrueDraft does not publish to a "
        "marketplace for you."
    )

heuristic_notice()
st.caption("TrueDraft v1 · Output is always a starting draft · See Legal for Terms and Privacy")
