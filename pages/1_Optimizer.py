"""
Single Listing Optimizer – core experience of ListingForge
"""

import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.generator import ListingGenerator
from core.utils import save_listing, export_to_dataframe
import json

st.set_page_config(page_title="Optimizer | ListingForge", page_icon="✨", layout="wide")

st.title("✨ Single Listing Optimizer")
st.caption("Generate a complete, scored, ready-to-publish listing in under 10 seconds.")

from core.llm import is_llm_available
llm_ready = is_llm_available()
if llm_ready:
    st.success("🟢 Real LLM backend detected — generations will use AI when available.")
else:
    st.info("🟡 Running on high-quality template engine (no API key required). Add OPENAI_API_KEY or XAI_API_KEY for real LLM output.")

generator = ListingGenerator()

with st.form("listing_form", clear_on_submit=False):
    col_a, col_b = st.columns(2)

    with col_a:
        product_name = st.text_input(
            "Product Name *",
            placeholder="e.g. Sterling Silver Moon Pendant Necklace",
            help="The core name of your product"
        )
        primary_keyword = st.text_input(
            "Primary Keyword",
            placeholder="e.g. moon pendant necklace",
            help="Main search term you want to rank for. Leave blank to use product name."
        )
        category = st.selectbox(
            "Category",
            options=["jewelry", "home_decor", "apparel", "art_prints", "beauty", "digital", "default"],
            format_func=lambda x: x.replace("_", " ").title(),
            help="Influences language, benefits, and emotional tone"
        )
        platform = st.radio("Platform", ["etsy", "shopify", "amazon"], horizontal=True)

    with col_b:
        material = st.text_input("Material / Key Attribute", placeholder="e.g. sterling silver, organic cotton")
        audience = st.text_input("Target Audience", placeholder="e.g. women, brides, minimalists, new moms")
        features_raw = st.text_area(
            "Key Features (one per line)",
            placeholder="Hypoallergenic\nAdjustable chain\nGift box included",
            height=100
        )
        extra_keywords = st.text_input(
            "Extra Keywords (comma separated)",
            placeholder="celestial, boho, layering necklace"
        )
        force_template = st.checkbox("Force template engine (skip LLM)", value=False)

    submitted = st.form_submit_button("Generate Optimized Listing", type="primary", use_container_width=True)

if submitted:
    if not product_name.strip():
        st.error("Product Name is required.")
        st.stop()

    features = [f.strip() for f in features_raw.split("\n") if f.strip()] if features_raw else []
    extras = [k.strip() for k in extra_keywords.split(",") if k.strip()] if extra_keywords else []

    with st.spinner("Forging your high-converting listing..."):
        result = generator.generate_full_listing(
            product_name=product_name.strip(),
            primary_keyword=primary_keyword.strip(),
            category=category,
            material=material.strip(),
            audience=audience.strip(),
            features=features,
            extra_keywords=extras,
            platform=platform,
            force_template=force_template,
        )

    # Save to history
    listing_id = save_listing(result)
    source = result["meta"].get("source", "template")
    model = result["meta"].get("model")
    source_msg = f"via **{source.upper()}**" + (f" ({model})" if model else "")
    st.success(f"Listing generated {source_msg} and saved to history (ID: {listing_id})")

    # Overall score banner
    overall = result["scores"]["overall"]
    score_color = "#22c55e" if overall["overall"] >= 80 else "#eab308" if overall["overall"] >= 65 else "#ef4444"
    st.markdown(f"""
    <div style="background:#1e293b; border:1px solid #334155; border-radius:12px; padding:1.5rem; margin:1rem 0;">
        <h2 style="margin:0; color:{score_color};">{overall['overall']}/100 — Grade {overall['grade']}</h2>
        <p style="margin:0.5rem 0 0; color:#94a3b8;">{overall['summary']}</p>
    </div>
    """, unsafe_allow_html=True)

    # Score breakdown
    s1, s2, s3 = st.columns(3)
    s1.metric("Title Score", f"{result['scores']['title']['score']}/100")
    s2.metric("Description Score", f"{result['scores']['description']['score']}/100")
    s3.metric("Tags Score", f"{result['scores']['tags']['score']}/100")

    st.markdown("---")

    # Titles
    st.subheader("📝 Title Options")
    for i, title in enumerate(result["titles"]):
        cols = st.columns([0.85, 0.15])
        cols[0].code(title, language=None)
        cols[1].button("Copy", key=f"copy_title_{i}", help="Select and Ctrl+C")

    st.markdown(f"**Recommended (highest potential):** `{result['best_title']}`")

    # Description
    st.subheader("📄 Optimized Description")
    st.text_area("Description", value=result["description"], height=380, label_visibility="collapsed")

    # Tags
    st.subheader(f"🏷️ Tags ({len(result['tags'])})")
    tag_str = ", ".join(result["tags"])
    st.code(tag_str)
    st.caption("Copy the entire line above and paste into Etsy/Shopify tag field.")

    # Feedback
    with st.expander("🔍 Detailed SEO Feedback & Recommendations"):
        for fb in overall["feedback"]:
            st.markdown(f"- {fb}")
        if not overall["feedback"]:
            st.write("No major issues found. Strong listing.")

    # Export
    st.markdown("---")
    st.subheader("Export")
    df = export_to_dataframe([result])
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download as CSV",
        data=csv,
        file_name=f"listingforge_{product_name[:30].replace(' ', '_')}.csv",
        mime="text/csv",
    )

    json_str = json.dumps(result, indent=2)
    st.download_button(
        "⬇️ Download full JSON",
        data=json_str,
        file_name=f"listingforge_{product_name[:30].replace(' ', '_')}.json",
        mime="application/json",
    )
else:
    st.info("Fill in the form above and click **Generate Optimized Listing** to begin.")
    st.markdown("""
    **Tips for best results:**
    - Be specific with the product name and primary keyword
    - Add 3–6 real features (customers notice authenticity)
    - Choose the closest category — it changes the language bank used
    - For Etsy, the system prioritizes long-tail tags and 13-slot fill
    """)
