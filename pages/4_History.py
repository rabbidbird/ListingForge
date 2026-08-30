"""Authorized listing history read/delete/export UI."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.auth import require_streamlit_user
from core.draft_review import draft_export_ready
from core.events import record_product_event
from core.ui import (
    configure_page,
    confirm_before_export,
    draft_banner,
    render_editable_draft,
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

st.metric("Saved drafts shown", len(history))

table = pd.DataFrame(
    [
        {
            "Date": row["created_at"][:16].replace("T", " "),
            "Product": row["product_name"],
            "Platform": row["platform"],
            "Checklist status": row.get("status")
            or (
                "Pass"
                if row["grade"] == "A"
                else "Review"
                if row["grade"] in {"B", "C"}
                else "Missing"
            ),
            "Draft title": row["best_title"],
        }
        for row in history
    ]
)
st.dataframe(table, width="stretch", hide_index=True)

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
    render_editable_draft(
        user,
        selected_id,
        full,
        key_prefix=f"history_{selected_id}",
    )

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
blocked_results = [result for result in full_results if not draft_export_ready(result)]
ready_results = [result for result in full_results if draft_export_ready(result)]
if blocked_results:
    st.warning(
        f"{len(blocked_results)} draft(s) with unresolved edited wording will be left out of "
        "this download. Review or explicitly verify those drafts to include them later."
    )
confirmed = confirm_before_export("history") if ready_results else False
if confirmed:
    export_frame = export_to_dataframe(ready_results)
    st.download_button(
        f"Download {len(ready_results)} ready draft(s) as CSV",
        data=export_frame.to_csv(index=False).encode("utf-8"),
        file_name="sellerdrafts_history.csv",
        mime="text/csv",
        on_click=record_product_event,
        args=(user.id, "export_completed"),
    )
elif ready_results:
    st.caption("Complete all confirmation checks to enable the history download.")
else:
    st.caption("No drafts are ready to download yet.")
