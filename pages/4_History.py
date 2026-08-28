"""Authorized listing history read/delete/export UI."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.auth import require_streamlit_user
from core.ui import (
    configure_page,
    confirm_before_export,
    copy_button,
    draft_banner,
    render_export_reminder,
    render_sidebar,
)
from core.utils import (
    delete_listing,
    export_to_dataframe,
    get_full_history,
    get_history,
    get_listing_by_id,
)

configure_page("History", "🕘")
user = require_streamlit_user()
render_sidebar(user)

st.title("Private draft history")
st.caption("Only you can view the drafts saved in this account.")
history = get_history(user.id, limit=500)
if not history:
    st.info("No saved drafts yet. Generate a starting draft from facts you can verify.")
    if st.button("Create one draft", type="primary"):
        st.switch_page("pages/1_Optimizer.py")
    st.stop()

scores = [row["overall_score"] for row in history if row["overall_score"] is not None]
first, second = st.columns(2)
first.metric("Saved drafts shown", len(history))
second.metric("Average checklist", f"{sum(scores) / len(scores):.1f}" if scores else "—")

table = pd.DataFrame(
    [
        {
            "Date": row["created_at"][:16].replace("T", " "),
            "Product": row["product_name"],
            "Platform": row["platform"],
            "Checklist": row["overall_score"],
            "Grade": row["grade"],
            "Draft title": row["best_title"],
        }
        for row in history
    ]
)
st.dataframe(table, use_container_width=True, hide_index=True)

labels = {
    row["id"]: (f"{row['created_at'][:16].replace('T', ' ')} UTC · {row['product_name'][:70]}")
    for row in history
}
selected_id = st.selectbox(
    "Inspect a saved draft",
    options=[row["id"] for row in history],
    format_func=lambda value: labels[value],
)
full = get_listing_by_id(user.id, selected_id)
if full is None:
    st.error("Draft not found or not authorized.")
else:
    draft_banner()
    render_export_reminder()
    st.subheader(full["best_title"])
    copy_button(full["best_title"], label="Copy title")
    st.text_area(
        "Description",
        value=full["description"],
        height=280,
        key=f"history_description_{selected_id}",
        disabled=True,
    )
    copy_button(full["description"], label="Copy description")
    tags = ", ".join(full["tags"])
    st.code(tags, language=None)
    copy_button(tags, label="Copy tags")

    confirm_delete = st.checkbox(
        "I understand this permanently deletes this saved draft.",
        key=f"delete_confirm_{selected_id}",
    )
    if st.button("Delete selected draft", disabled=not confirm_delete):
        if delete_listing(user.id, selected_id):
            st.success("Draft deleted.")
            st.rerun()
        else:
            st.error("Draft not found or not authorized.")

st.divider()
st.subheader("Export saved drafts")
full_results = get_full_history(user.id, limit=500)
confirmed = confirm_before_export("history")
if confirmed and full_results:
    export_frame = export_to_dataframe(full_results)
    st.download_button(
        "Download shown history as CSV",
        data=export_frame.to_csv(index=False).encode("utf-8"),
        file_name="sellerdrafts_history.csv",
        mime="text/csv",
    )
elif not confirmed:
    st.caption("Complete all confirmation checks to enable the history download.")
