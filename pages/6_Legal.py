"""Authenticated legal and trust page rendered from canonical policy copy."""

from __future__ import annotations

import streamlit as st

from core.auth import streamlit_current_user
from core.legal import (
    ACCEPTABLE_USE_MARKDOWN,
    OPERATOR_NAME,
    PRIVACY_MARKDOWN,
    TERMS_EFFECTIVE_DATE,
    TERMS_MARKDOWN,
    TERMS_VERSION,
)
from core.ui import configure_page, render_public_footer, render_sidebar

configure_page("Legal", "📜")
render_sidebar(streamlit_current_user())

st.title("Legal and trust")
st.write(
    "SellerDrafts creates starting drafts from facts you supply. You are responsible for "
    "every claim you publish."
)
st.info(
    f"Current policies: {TERMS_EFFECTIVE_DATE} ({TERMS_VERSION}). Operator: {OPERATOR_NAME}. "
    "Independent legal review remains an operator launch action."
)
terms_tab, privacy_tab, use_tab = st.tabs(["Terms of Service", "Privacy Policy", "Acceptable Use"])

with terms_tab:
    st.markdown(TERMS_MARKDOWN)

with privacy_tab:
    st.markdown(PRIVACY_MARKDOWN)

with use_tab:
    st.markdown(ACCEPTABLE_USE_MARKDOWN)

render_public_footer()
