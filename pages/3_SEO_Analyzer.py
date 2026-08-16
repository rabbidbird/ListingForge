"""Authenticated transparent listing checklist."""

from __future__ import annotations

import streamlit as st

from core.auth import require_streamlit_user
from core.seo_scorer import SEOScorer
from core.ui import configure_page, heuristic_notice, render_sidebar

configure_page("Listing Checklist", "📋")
user = require_streamlit_user()
render_sidebar(user)

st.title("Listing checklist")
heuristic_notice()
st.caption(
    "This checks visible structure and a few current platform constraints. It cannot assess "
    "truth, category eligibility, ranking, buyer intent, or marketplace enforcement."
)

with st.form("checklist_form"):
    platform = st.radio("Platform", ["etsy", "shopify", "amazon"], horizontal=True)
    title = st.text_input("Current title", max_chars=500)
    primary_keyword = st.text_input("Primary phrase you selected", max_chars=300)
    description = st.text_area("Current description", height=220)
    tags_raw = st.text_input("Tags (comma separated)", max_chars=1000)
    secondary_raw = st.text_input("Other supplied phrases (comma separated)", max_chars=1000)
    submitted = st.form_submit_button("Run heuristic checklist", type="primary")

if submitted:
    if not title.strip() and not description.strip():
        st.error("Enter a title or description to check.")
    else:
        scorer = SEOScorer()
        tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]
        secondary = [value.strip() for value in secondary_raw.split(",") if value.strip()]
        title_result = scorer.score_title(title, primary_keyword, platform)
        description_result = scorer.score_description(description, primary_keyword, secondary)
        tags_result = scorer.score_tags(tags, primary_keyword, platform)
        overall = scorer.overall_score(title_result, description_result, tags_result)

        st.subheader(f"Checklist: {overall['overall']}/100 · Grade {overall['grade']}")
        st.caption(overall["summary"])
        one, two, three = st.columns(3)
        one.metric("Title checklist", f"{title_result['score']}/100")
        two.metric("Description checklist", f"{description_result['score']}/100")
        three.metric("Tags checklist", f"{tags_result['score']}/100")
        st.subheader("Review items")
        if overall["feedback"]:
            for item in overall["feedback"]:
                st.markdown(f"- {item}")
        else:
            st.write("No structural warnings found. Verify every claim and current rule manually.")
        with st.expander("Transparent check details"):
            st.json(
                {
                    "title": title_result,
                    "description": description_result,
                    "tags": tags_result,
                }
            )
else:
    st.info("Paste existing listing text to run the checklist.")
