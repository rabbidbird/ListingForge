"""Authenticated single-draft workflow."""

from __future__ import annotations

import json

import streamlit as st

from core.auth import require_streamlit_user
from core.generation_service import GenerationInputError, generate_for_user
from core.llm import is_llm_available
from core.ui import (
    configure_page,
    confirm_before_export,
    copy_button,
    draft_banner,
    heuristic_notice,
    render_claim_categories,
    render_export_reminder,
    render_quota_notice,
    render_sidebar,
    safe_filename,
)
from core.usage import UsageLimitError, get_usage
from core.utils import export_to_dataframe

configure_page("Single Draft", "✍️")
user = require_streamlit_user()
render_sidebar(user)
usage = get_usage(user.id)

st.title("Single listing draft")
st.caption(
    "Supply only facts you can verify. TrueDraft will not fill in a missing material, "
    "certification, origin, rating, or shipping claim."
)
draft_banner()
st.caption(
    f"{str(usage['plan']).title()} plan: {usage['daily_remaining']} remaining today and "
    f"{usage['monthly_remaining']} this month (UTC)."
)
render_quota_notice(usage)
render_claim_categories()

llm_ready = is_llm_available()
if llm_ready:
    st.caption(
        "Optional LLM mode is enabled with a timeout, token cap, daily user cap, and strict "
        "fact-lock fallback."
    )
else:
    st.caption("Using the deterministic, fact-locked template engine.")

with st.form("listing_form", clear_on_submit=False):
    left, right = st.columns(2)
    with left:
        product_name = st.text_input(
            "Product name *", placeholder="e.g. Moon pendant", max_chars=300
        )
        primary_keyword = st.text_input(
            "Primary search phrase", placeholder="e.g. moon pendant necklace", max_chars=300
        )
        category = st.selectbox(
            "Category label",
            ["jewelry", "home_decor", "apparel", "art_prints", "beauty", "digital", "default"],
            format_func=lambda value: value.replace("_", " ").title(),
        )
        platform = st.radio("Draft format", ["etsy", "shopify", "amazon"], horizontal=True)
    with right:
        material = st.text_input(
            "Material / attribute (only if verified — leave blank if unsure)",
            max_chars=300,
        )
        audience = st.text_input("Audience (only if applicable)", max_chars=300)
        features_raw = st.text_area(
            "Verified product details (one per line, up to 8). Do not add claims you cannot prove.",
            height=120,
        )
        extra_keywords = st.text_input(
            "Additional supplied phrases (comma separated)", max_chars=500
        )
        force_template = st.checkbox(
            "Use deterministic template mode", value=not llm_ready, disabled=not llm_ready
        )
    submitted = st.form_submit_button(
        "Generate fact-locked draft",
        type="primary",
        use_container_width=True,
        disabled=not usage["can_generate"],
    )

if submitted:
    payload = {
        "product_name": product_name,
        "primary_keyword": primary_keyword,
        "category": category,
        "material": material,
        "audience": audience,
        "features": features_raw.splitlines(),
        "extra_keywords": extra_keywords.split(","),
        "platform": platform,
        "force_template": force_template,
    }
    try:
        with st.spinner("Creating a source-locked draft..."):
            result, listing_id = generate_for_user(user.id, payload)
        st.session_state["latest_single_draft"] = {
            "user_id": str(user.id),
            "listing_id": str(listing_id),
            "result": result,
        }
        st.success("Draft created and saved to your private history.")
    except UsageLimitError as exc:
        st.error(str(exc))
        if exc.code in {"daily_limit", "monthly_limit"}:
            st.page_link("pages/5_About_Pricing.py", label="Upgrade to raise this limit", icon="💳")
    except GenerationInputError as exc:
        st.error(str(exc))
    except Exception:
        st.error("The draft could not be generated. Your usage reservation was released.")

stored = st.session_state.get("latest_single_draft")
if stored and stored.get("user_id") == str(user.id):
    result = stored["result"]
    listing_id = stored["listing_id"]
    draft_banner()
    if result["meta"].get("llm_fact_lock_fallback"):
        st.info(
            "The LLM response failed source checks, so TrueDraft used the safe template fallback."
        )

    overall = result["scores"]["overall"]
    st.subheader(f"Checklist: {overall['overall']}/100 · Grade {overall['grade']}")
    st.caption(overall["summary"])
    score_one, score_two, score_three = st.columns(3)
    score_one.metric("Title checklist", f"{result['scores']['title']['score']}/100")
    score_two.metric("Description checklist", f"{result['scores']['description']['score']}/100")
    score_three.metric("Tags checklist", f"{result['scores']['tags']['score']}/100")
    heuristic_notice()
    render_export_reminder()

    st.subheader("Title options")
    for index, title in enumerate(result["titles"], start=1):
        st.code(title, language=None)
        copy_button(title, label=f"Copy title {index}")

    st.subheader("Description draft")
    st.text_area(
        "Description",
        value=result["description"],
        height=330,
        key=f"description_{listing_id}",
        disabled=True,
    )
    copy_button(result["description"], label="Copy description")

    st.subheader(f"Tags ({len(result['tags'])})")
    tag_text = ", ".join(result["tags"])
    st.code(tag_text, language=None)
    copy_button(tag_text, label="Copy tags")

    with st.expander("Checklist feedback"):
        feedback = overall.get("feedback") or []
        if feedback:
            for item in feedback:
                st.markdown(f"- {item}")
        else:
            st.write("No checklist warnings. Human verification is still required.")

    st.divider()
    confirmed = confirm_before_export(f"single_{listing_id}")
    filename = safe_filename(result["meta"]["product_name"])
    if confirmed:
        export_frame = export_to_dataframe([result])
        csv_data = export_frame.to_csv(index=False).encode("utf-8")
        first, second = st.columns(2)
        first.download_button(
            "Download CSV draft",
            data=csv_data,
            file_name=f"truedraft_{filename}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        second.download_button(
            "Download JSON draft",
            data=json.dumps(result, indent=2, ensure_ascii=False),
            file_name=f"truedraft_{filename}.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        st.caption("Complete all confirmation checks to enable downloads.")
else:
    st.info(
        "Supply only facts you can verify, then generate a starting draft. "
        "Blank fields stay blank in the output."
    )
