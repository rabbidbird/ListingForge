"""
Standalone SEO Analyzer – score any existing listing
"""

import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.auth import user_id
from core.seo_scorer import SEOScorer

st.set_page_config(page_title="SEO Analyzer | ListingForge", page_icon="📊", layout="wide")

st.title("📊 SEO Listing Analyzer")
st.caption("Paste any existing title, description, and tags to get an honest score and actionable feedback.")
user_id()

scorer = SEOScorer()

with st.form("analyze_form"):
    platform = st.radio("Platform", ["etsy", "shopify", "amazon"], horizontal=True)
    title = st.text_input("Current Title", placeholder="Paste your current product title")
    primary_keyword = st.text_input("Primary Keyword you are targeting")
    description = st.text_area("Current Description", height=200, placeholder="Paste full description")
    tags_raw = st.text_input("Tags (comma separated)", placeholder="tag1, tag2, tag3...")
    secondary = st.text_input("Secondary keywords (comma separated, optional)")

    analyze = st.form_submit_button("Analyze Listing", type="primary")

if analyze:
    if not title and not description:
        st.warning("Please provide at least a title or description.")
        st.stop()

    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
    secondary_list = [k.strip() for k in secondary.split(",") if k.strip()] if secondary else []

    title_res = scorer.score_title(title or "", primary_keyword, platform)
    desc_res = scorer.score_description(description or "", primary_keyword, secondary_list)
    tags_res = scorer.score_tags(tags, primary_keyword, platform)
    overall = scorer.overall_score(title_res, desc_res, tags_res)

    # Banner
    color = "#22c55e" if overall["overall"] >= 80 else "#eab308" if overall["overall"] >= 65 else "#ef4444"
    st.markdown(f"""
    <div style="background:#1e293b; border:1px solid #334155; border-radius:12px; padding:1.5rem; margin:1rem 0;">
        <h2 style="margin:0; color:{color};">{overall['overall']}/100 — Grade {overall['grade']}</h2>
        <p style="margin:0.5rem 0 0; color:#94a3b8;">{overall['summary']}</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Title", f"{title_res['score']}/100", help=f"Length: {title_res.get('length', 0)} chars")
    c2.metric("Description", f"{desc_res['score']}/100", help=f"{desc_res.get('word_count', 0)} words")
    c3.metric("Tags", f"{tags_res['score']}/100", help=f"{tags_res.get('count', 0)} tags")

    st.markdown("### Actionable Feedback")
    if overall["feedback"]:
        for item in overall["feedback"]:
            st.markdown(f"- {item}")
    else:
        st.success("No major issues detected. Strong foundation.")

    with st.expander("Raw score details"):
        st.json({
            "title": title_res,
            "description": desc_res,
            "tags": tags_res,
            "overall": overall,
        })
else:
    st.info("Paste an existing listing above to receive a detailed SEO audit.")
