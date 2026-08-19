"""Authenticated, capped, row-isolated CSV draft workflow."""

from __future__ import annotations

import uuid

import pandas as pd
import streamlit as st

from core.auth import require_streamlit_user
from core.config import get_settings
from core.csv_processor import CSVValidationError, read_csv_bytes, validate_csv_rows
from core.generation_service import GenerationInputError, generate_for_user
from core.llm import is_llm_available
from core.ui import (
    configure_page,
    confirm_before_export,
    draft_banner,
    render_quota_notice,
    render_sidebar,
)
from core.usage import UsageLimitError, assert_bulk_job_allowed, get_usage
from core.utils import export_to_dataframe

configure_page("Bulk Drafts", "📦")
user = require_streamlit_user()
render_sidebar(user)
usage = get_usage(user.id)
row_cap = int(usage["bulk_rows_per_job"])

st.title("Bulk CSV drafts")
draft_banner()
st.caption(
    f"{str(usage['plan']).title()} jobs are capped at {row_cap} rows. Each successful row "
    "uses one generation; invalid rows are reported without stopping the job."
)
render_quota_notice(usage)
st.code(
    "product_name,primary_keyword,category,material,audience,features,extra_keywords,platform",
    language=None,
)
st.caption(
    "Only product_name is required. Separate features with | and extra phrases with commas. "
    f"Maximum upload: {get_settings().max_upload_bytes / 1_000_000:g} MB."
)

sample = pd.DataFrame(
    [
        {
            "product_name": "Moon Pendant",
            "primary_keyword": "moon pendant necklace",
            "category": "jewelry",
            "material": "",
            "audience": "",
            "features": "",
            "extra_keywords": "celestial pendant",
            "platform": "etsy",
        }
    ]
)
st.download_button(
    "Download safe sample CSV",
    data=sample.to_csv(index=False).encode("utf-8"),
    file_name="truedraft_sample.csv",
    mime="text/csv",
)

uploaded = st.file_uploader("Upload UTF-8 CSV", type=["csv"])
if uploaded is not None:
    try:
        frame = read_csv_bytes(uploaded.getvalue())
    except CSVValidationError as exc:
        st.error(str(exc))
        frame = None

    if frame is not None:
        if frame.empty:
            st.warning("The CSV has headers but no product rows.")
        else:
            st.write(f"Loaded {len(frame)} rows. Preview:")
            st.dataframe(frame.head(10), use_container_width=True, hide_index=True)
            selected_count = st.number_input(
                "Rows to process from the top",
                min_value=1,
                max_value=min(len(frame), row_cap),
                value=min(len(frame), row_cap),
                step=1,
            )
            force_template = st.checkbox(
                "Use deterministic template mode for this job",
                value=True,
                disabled=not is_llm_available(),
            )
            if len(frame) > row_cap:
                st.info(
                    f"This file has more than your per-job cap. This run can process at most {row_cap} rows."
                )

            if st.button(
                "Generate CSV drafts",
                type="primary",
                disabled=not usage["can_generate"],
            ):
                validated = validate_csv_rows(frame, limit=int(selected_count))
                try:
                    assert_bulk_job_allowed(user.id, len(validated))
                except UsageLimitError as exc:
                    st.error(str(exc))
                    if exc.code == "bulk_cap":
                        st.page_link(
                            "pages/5_About_Pricing.py",
                            label="Upgrade to raise the bulk-row cap",
                            icon="💳",
                        )
                else:
                    results: list[dict] = []
                    errors: list[dict[str, object]] = []
                    progress = st.progress(0)
                    status = st.empty()
                    for index, row in enumerate(validated, start=1):
                        if row.error or row.payload is None:
                            errors.append({"CSV row": row.row_number, "Error": row.error})
                        else:
                            status.caption(f"Processing CSV row {row.row_number}...")
                            payload = {**row.payload, "force_template": force_template}
                            try:
                                result, _listing_id = generate_for_user(
                                    user.id, payload, mode="bulk"
                                )
                                results.append(result)
                            except (GenerationInputError, UsageLimitError) as exc:
                                errors.append({"CSV row": row.row_number, "Error": str(exc)})
                            except Exception:
                                errors.append(
                                    {
                                        "CSV row": row.row_number,
                                        "Error": "Generation failed; no usage was charged.",
                                    }
                                )
                        progress.progress(index / len(validated))
                    status.empty()
                    batch_id = uuid.uuid4().hex
                    st.session_state["latest_bulk_drafts"] = {
                        "user_id": str(user.id),
                        "batch_id": batch_id,
                        "results": results,
                        "errors": errors,
                    }

stored = st.session_state.get("latest_bulk_drafts")
if stored and stored.get("user_id") == str(user.id):
    results = stored["results"]
    errors = stored["errors"]
    if results:
        draft_banner()
        st.success(f"Created {len(results)} drafts and saved them to your private history.")
        summary = [
            {
                "Product": result["meta"]["product_name"],
                "Draft title": result["best_title"],
                "Checklist": result["scores"]["overall"]["overall"],
                "Source": result["meta"]["source"],
            }
            for result in results
        ]
        st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
    else:
        st.warning("No valid drafts were created in the last job.")
    if errors:
        st.subheader("Rows not processed")
        st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)

    if results:
        st.divider()
        confirmed = confirm_before_export(f"bulk_{stored['batch_id']}")
        if confirmed:
            export_frame = export_to_dataframe(results)
            st.download_button(
                "Download bulk CSV drafts",
                data=export_frame.to_csv(index=False).encode("utf-8"),
                file_name="truedraft_bulk_drafts.csv",
                mime="text/csv",
                type="primary",
            )
        else:
            st.caption("Complete all confirmation checks to enable the bulk download.")
elif uploaded is None:
    st.info("Upload a CSV to validate and generate source-locked drafts.")
