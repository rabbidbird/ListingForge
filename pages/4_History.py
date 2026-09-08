"""Authorized listing history read/delete/export UI."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.auth import require_streamlit_user
from core.draft_review import draft_export_ready
from core.events import record_export_action
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
    get_history_page,
    get_listing_by_id,
    get_listings_by_ids,
)

configure_page("History", "🕘")
user = require_streamlit_user()
render_sidebar(user)

st.title("Private draft history")
st.caption("Only you can view the drafts saved in this account.")

search = st.text_input(
    "Search saved drafts",
    placeholder="Product, keyword, platform, category, or title",
    key="history_filter_search",
)
platform = st.text_input(
    "Filter by platform",
    placeholder="For example: etsy",
    key="history_filter_platform",
)
scope = (search.strip().casefold(), platform.strip().casefold())
if st.session_state.get("history_scope") != scope:
    st.session_state.history_scope = scope
    st.session_state.history_page = 0
    st.session_state.history_cursors = [None]

page_number = st.session_state.get("history_page", 0)
cursors = st.session_state.get("history_cursors", [None])
if page_number >= len(cursors):
    page_number = 0
    cursors = [None]
    st.session_state.history_page = page_number
    st.session_state.history_cursors = cursors
try:
    history_page = get_history_page(
        user.id,
        cursor=cursors[page_number],
        search=search,
        platform=platform,
    )
except ValueError:
    # This can only happen after a stale browser state or a changed filter.
    st.session_state.history_page = 0
    st.session_state.history_cursors = [None]
    st.rerun()

history = history_page["rows"]
if not history:
    if page_number:
        st.info(
            "There are no drafts on this page. Return to the previous page to continue browsing."
        )
        if st.button("Previous page"):
            st.session_state.history_page = page_number - 1
            st.rerun()
        st.stop()
    else:
        st.info(
            "No saved drafts match this search. Generate a starting draft from facts you can verify."
        )
        if st.button("Create one draft", type="primary"):
            st.switch_page("pages/1_Optimizer.py")
        st.stop()

st.metric("Drafts on this page", len(history))

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

previous, next_page = st.columns(2)
with previous:
    if st.button("Previous page", disabled=page_number == 0):
        st.session_state.history_page = page_number - 1
        st.rerun()
with next_page:
    if st.button("Next page", disabled=history_page["next_cursor"] is None):
        if len(cursors) == page_number + 1:
            cursors.append(history_page["next_cursor"])
        else:
            cursors[page_number + 1] = history_page["next_cursor"]
        st.session_state.history_cursors = cursors
        st.session_state.history_page = page_number + 1
        st.rerun()
st.caption(f"Page {page_number + 1}")

st.divider()
st.subheader("Export this page")
full_results = get_listings_by_ids(user.id, [row["id"] for row in history])
blocked_results = [result for result in full_results.values() if not draft_export_ready(result)]
ready_results = [result for result in full_results.values() if draft_export_ready(result)]
ready_ids = [
    listing_id for listing_id, result in full_results.items() if draft_export_ready(result)
]
if blocked_results:
    st.warning(
        f"{len(blocked_results)} draft(s) on this page with unresolved edited wording will be "
        "left out of this download. Review or explicitly verify those drafts to include them later."
    )
confirmed = confirm_before_export("history") if ready_results else False
if confirmed:
    export_frame = export_to_dataframe(ready_results)
    st.download_button(
        f"Download {len(ready_results)} ready draft(s on this page) as CSV",
        data=export_frame.to_csv(index=False).encode("utf-8"),
        file_name="sellerdrafts_history.csv",
        mime="text/csv",
        on_click=record_export_action,
        args=(user.id, ready_ids),
    )
elif ready_results:
    st.caption("Complete all confirmation checks to enable the page download.")
else:
    st.caption("No drafts are ready to download yet.")
