"""Authenticated transparent listing checklist."""

from __future__ import annotations

import streamlit as st

from core.auth import require_streamlit_user
from core.copy import audit_unverified_claims
from core.seo_scorer import SEOScorer
from core.ui import configure_page, draft_banner, heuristic_notice, render_sidebar

configure_page("Listing Checklist", "📋")
user = require_streamlit_user()
render_sidebar(user)

st.title("Listing checklist")
draft_banner()
heuristic_notice()
st.caption(
    "Paste an existing listing to find configured claim language that still needs a source "
    "check, followed by transparent structure heuristics. This is not a policy certificate, "
    "ranking score, or publishing tool."
)

with st.form("checklist_form"):
    platform = st.radio("Platform", ["etsy", "shopify", "amazon"], horizontal=True)
    title = st.text_input("Current title", max_chars=500)
    primary_keyword = st.text_input("Primary phrase you selected", max_chars=300)
    description = st.text_area("Current description", height=220)
    tags_raw = st.text_input("Tags (comma separated)", max_chars=1000)
    verified_source = st.text_area(
        "Verified source facts for this physical product",
        help=(
            "Paste only wording you can confirm from the product, packaging, supplier record, "
            "or another source you trust. Matching claim phrases in this field are treated as sourced."
        ),
        height=120,
    )
    secondary_raw = st.text_input("Other supplied phrases (comma separated)", max_chars=1000)
    submitted = st.form_submit_button("Audit listing", type="primary")

if submitted:
    if not title.strip() and not description.strip() and not tags_raw.strip():
        st.error("Enter a title, description, or tags to audit.")
    else:
        scorer = SEOScorer()
        tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]
        secondary = [value.strip() for value in secondary_raw.split(",") if value.strip()]
        listing_text = "\n".join([title, description, *tags])
        claim_matches = audit_unverified_claims(listing_text, verified_source)
        title_result = scorer.score_title(title, primary_keyword, platform)
        description_result = scorer.score_description(
            description,
            primary_keyword,
            secondary,
            require_draft_notice=False,
        )
        tags_result = scorer.score_tags(tags, primary_keyword, platform)
        overall = scorer.overall_score(title_result, description_result, tags_result)

        st.subheader("Claim audit")
        if claim_matches:
            for match in claim_matches:
                st.warning(
                    f"“{match['phrase']}” — {match['category']}. "
                    "Unverified in this paste — confirm against the physical product before "
                    "you keep this wording."
                )
        else:
            st.success(
                "No configured claim phrases were found unverified in this paste. This is not "
                "a policy or accuracy certificate; review the physical product and current rules."
            )

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
    st.info("Paste an existing title, description, or tags to audit the listing.")
