"""
Bulk Listing Processor – upload CSV, optimize many products at once
"""

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.generator import ListingGenerator
from core.auth import user_id
from core.utils import save_listing, export_to_dataframe
from core.usage import get_usage, is_limit_reached, record_generation

st.set_page_config(page_title="Bulk Processor | ListingForge", page_icon="📦", layout="wide")

st.title("📦 Bulk Listing Processor")
st.caption("Upload a CSV of products → get fully optimized titles, descriptions, tags, and scores back.")

generator = ListingGenerator()
active_user_id = user_id()


def _display_limits(user_id: str):
    usage = get_usage(user_id)
    unlimited_daily = "unlimited" if usage["daily_limit"] is None else usage["daily_limit"]
    unlimited_monthly = "unlimited" if usage["monthly_limit"] is None else usage["monthly_limit"]
    remaining_daily = "unlimited" if usage["daily_remaining"] is None else usage["daily_remaining"]
    remaining_monthly = "unlimited" if usage["monthly_remaining"] is None else usage["monthly_remaining"]
    st.caption(
        f"Plan: **{usage['plan_label']}** | "
        f"Daily usage: {usage['daily']}/{unlimited_daily} • "
        f"Monthly usage: {usage['monthly']}/{unlimited_monthly} • "
        f"Remaining: {remaining_daily} today / {remaining_monthly} this month"
    )
    return usage

st.markdown("### Expected CSV columns")
st.code("product_name, primary_keyword, category, material, audience, features, extra_keywords, platform")
st.caption("Only `product_name` is required. Other columns are optional. Features should be pipe-separated (|). Platform defaults to etsy.")

# Sample download
sample_data = pd.DataFrame([
    {
        "product_name": "Sterling Silver Moon Pendant Necklace",
        "primary_keyword": "moon pendant necklace",
        "category": "jewelry",
        "material": "sterling silver",
        "audience": "women",
        "features": "Hypoallergenic|Adjustable 18-inch chain|Gift box included",
        "extra_keywords": "celestial, boho, layering",
        "platform": "etsy"
    },
    {
        "product_name": "Minimalist Ceramic Vase Set",
        "primary_keyword": "ceramic vase set",
        "category": "home_decor",
        "material": "ceramic",
        "audience": "homeowners",
        "features": "Set of 3|Matte finish|Waterproof",
        "extra_keywords": "modern, nordic, shelf decor",
        "platform": "shopify"
    },
])
sample_csv = sample_data.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download sample CSV", data=sample_csv, file_name="listingforge_sample.csv", mime="text/csv")

st.markdown("---")

uploaded = st.file_uploader("Upload your product CSV", type=["csv"])
usage = get_usage(active_user_id)
_display_limits(active_user_id)

if not usage["can_generate"]:
    st.error("🚫 You’ve reached your listing generation limit.")
    st.info("Upgrade from Pricing to continue.")
    st.stop()

if uploaded:
    try:
        df = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        st.stop()

    st.write(f"**Loaded {len(df)} rows**")
    st.dataframe(df.head(10), use_container_width=True)

    if "product_name" not in df.columns:
        st.error("CSV must contain a `product_name` column.")
        st.stop()

    # Fill defaults
    for col in ["primary_keyword", "category", "material", "audience", "features", "extra_keywords", "platform"]:
        if col not in df.columns:
            df[col] = ""

    max_rows = st.slider("Process first N rows (for testing)", min_value=1, max_value=min(100, len(df)), value=min(10, len(df)))
    if usage["remaining_total"] is not None:
        max_rows = min(max_rows, usage["remaining_total"])

    if st.button("🚀 Process Bulk Listings", type="primary"):
        results = []
        progress = st.progress(0)
        status = st.empty()

        subset = df.head(max_rows)
        for idx, row in subset.iterrows():
            if is_limit_reached(active_user_id):
                status.text("Quota reached. Upgrade to continue.")
                break

            status.text(f"Processing {idx+1}/{len(subset)}: {row['product_name'][:50]}...")
            features = [f.strip() for f in str(row.get("features", "")).split("|") if f.strip()]
            extras = [k.strip() for k in str(row.get("extra_keywords", "")).split(",") if k.strip()]
            platform = str(row.get("platform", "etsy")).lower().strip() or "etsy"
            if platform not in ("etsy", "shopify", "amazon"):
                platform = "etsy"

            result = generator.generate_full_listing(
                product_name=str(row["product_name"]).strip(),
                primary_keyword=str(row.get("primary_keyword", "")).strip(),
                category=str(row.get("category", "default")).strip() or "default",
                material=str(row.get("material", "")).strip(),
                audience=str(row.get("audience", "")).strip(),
                features=features,
                extra_keywords=extras,
                platform=platform,
            )
            usage = record_generation(active_user_id)
            save_listing(result, user_id=active_user_id)
            results.append(result)
            progress.progress((idx + 1) / len(subset))

        status.text("Done!")
        st.success(f"Successfully optimized {len(results)} listings. They have also been saved to History.")

        # Show summary table
        summary = []
        for r in results:
            summary.append({
                "Product": r["meta"]["product_name"],
                "Best Title": r["best_title"][:80] + ("..." if len(r["best_title"]) > 80 else ""),
                "Score": r["scores"]["overall"]["overall"],
                "Grade": r["scores"]["overall"]["grade"],
                "Tags": len(r["tags"]),
            })
        st.dataframe(pd.DataFrame(summary), use_container_width=True)

        # Full export
        export_df = export_to_dataframe(results)
        csv_data = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Full Optimized CSV",
            data=csv_data,
            file_name="listingforge_bulk_optimized.csv",
            mime="text/csv",
            type="primary"
        )

        with st.expander("Preview first optimized description"):
            st.text(results[0]["description"])
else:
    st.info("Upload a CSV to begin bulk optimization.")
