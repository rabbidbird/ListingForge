"""
Listing History – view and manage previously generated listings
"""

import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.auth import user_id
from core.utils import get_history, get_listing_by_id, delete_listing, export_to_dataframe
import json

st.set_page_config(page_title="History | ListingForge", page_icon="🕘", layout="wide")

st.title("🕘 Generation History")
st.caption("All listings you generate are automatically saved locally (SQLite).")

viewer_user_id = user_id()
history = get_history(limit=100, user_id=viewer_user_id)

if not history:
    st.info("No listings generated yet. Go to the Optimizer and create your first one.")
    st.stop()

# Summary metrics
scores = [h["overall_score"] for h in history if h["overall_score"] is not None]
avg_score = sum(scores) / len(scores) if scores else 0
st.metric("Listings in history", len(history))
st.metric("Average overall score", f"{avg_score:.1f}")

st.markdown("---")

# Table
df_display = []
for h in history:
    df_display.append({
        "ID": h["id"],
        "Date": h["created_at"][:16].replace("T", " "),
        "Product": h["product_name"][:50],
        "Platform": h["platform"],
        "Score": h["overall_score"],
        "Grade": h["grade"],
        "Title": (h["best_title"] or "")[:60],
    })

import pandas as pd
st.dataframe(pd.DataFrame(df_display), use_container_width=True, hide_index=True)

st.markdown("### Inspect or delete a listing")
selected_id = st.number_input("Listing ID", min_value=1, value=history[0]["id"] if history else 1, step=1)

col1, col2 = st.columns(2)
with col1:
    if st.button("🔍 View Full Listing"):
        full = get_listing_by_id(int(selected_id), user_id=viewer_user_id)
        if full:
            st.subheader(full["best_title"])
            st.write(f"**Score:** {full['scores']['overall']['overall']} ({full['scores']['overall']['grade']})")
            st.text_area("Description", full["description"], height=300)
            st.code(", ".join(full["tags"]))
            st.json(full["scores"])
        else:
            st.error("Listing not found.")

with col2:
    if st.button("🗑️ Delete Listing", type="secondary"):
        if delete_listing(int(selected_id), user_id=viewer_user_id):
            st.success("Deleted.")
            st.rerun()
        else:
            st.error("Could not delete.")

# Export all
if st.button("⬇️ Export entire history as CSV"):
    full_results = []
    for h in history:
        full = get_listing_by_id(h["id"], user_id=viewer_user_id)
        if full:
            full_results.append(full)
    if full_results:
        export_df = export_to_dataframe(full_results)
        csv = export_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download History CSV", data=csv, file_name="listingforge_history.csv", mime="text/csv")
