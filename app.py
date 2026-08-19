"""
ListingForge – AI-Powered Product Listing Optimizer
Main entry point & marketing home page.
"""

import streamlit as st
from pathlib import Path
import sys

# Ensure core is importable
sys.path.insert(0, str(Path(__file__).parent))
from core.auth import auth_required, current_user, logout_button

st.set_page_config(
    page_title="ListingForge – AI Listing Optimizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished look
st.markdown("""
<style>
    .main-header {
        font-size: 3.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #818cf8 0%, #c084fc 50%, #f472b6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.35rem;
        color: #94a3b8;
        margin-bottom: 2rem;
    }
    .feature-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.5rem;
        height: 100%;
        transition: border-color 0.2s;
    }
    .metric-box {
        background: linear-gradient(145deg, #1e293b, #0f172a);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
    }
    div[data-testid="stSidebarNav"] {
        padding-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("## ⚡ ListingForge")
    st.caption("Professional listing optimizer for Etsy, Shopify & Amazon sellers")
    st.markdown("---")
    if auth_required():
        current_user()
        user_name = st.session_state.get("listingforge_name", "Signed in user")
        st.markdown(f"**Account:** {user_name}")
        logout_button()
    else:
        st.info("Auth disabled for this environment. Set LISTINGFORGE_REQUIRE_AUTH=true to enforce login.")
    st.markdown("---")
    st.markdown("### Quick Nav")
    st.page_link("app.py", label="Home", icon="🏠")
    st.page_link("pages/1_Optimizer.py", label="Single Listing Optimizer", icon="✨")
    st.page_link("pages/2_Bulk_Processor.py", label="Bulk Processor", icon="📦")
    st.page_link("pages/3_SEO_Analyzer.py", label="SEO Analyzer", icon="📊")
    st.page_link("pages/4_History.py", label="History", icon="🕘")
    st.page_link("pages/5_About_Pricing.py", label="About & Pricing", icon="💎")
    st.markdown("---")
    st.info("This is a complete, monetizable micro-SaaS MVP. See the README for deployment & monetization strategies.")

# Hero
st.markdown('<p class="main-header">ListingForge</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Turn mediocre product listings into high-converting, SEO-optimized sales machines in seconds.</p>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
    <div class="metric-box">
        <h2 style="margin:0; color:#818cf8;">13</h2>
        <p style="margin:0; color:#94a3b8;">Etsy tags optimized</p>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown("""
    <div class="metric-box">
        <h2 style="margin:0; color:#c084fc;">A+ / F</h2>
        <p style="margin:0; color:#94a3b8;">Real SEO grading</p>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown("""
    <div class="metric-box">
        <h2 style="margin:0; color:#f472b6;">Bulk</h2>
        <p style="margin:0; color:#94a3b8;">CSV in → optimized out</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("##")

# Features
st.markdown("### What ListingForge does")
f1, f2, f3 = st.columns(3)
with f1:
    st.markdown("""
    **✨ Intelligent Title Generation**  
    Multiple conversion-tested structures. Keyword front-loading, power words, length optimization for Etsy (140) and Shopify (70).
    """)
with f2:
    st.markdown("""
    **📝 High-Converting Descriptions**  
    Hook → Features → Benefits → Social proof → CTA structure used by top 1% sellers. Natural keyword weaving.
    """)
with f3:
    st.markdown("""
    **🏷️ Platform-Perfect Tags**  
    Long-tail focused, character-limit aware, material + audience + occasion coverage. Fills all 13 Etsy slots intelligently.
    """)

st.markdown("---")

# CTA
st.markdown("### Ready to optimize?")
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    if st.button("🚀 Open Optimizer", type="primary", use_container_width=True):
        st.switch_page("pages/1_Optimizer.py")
with c2:
    if st.button("📦 Try Bulk Mode", use_container_width=True):
        st.switch_page("pages/2_Bulk_Processor.py")

st.markdown("---")
st.caption("Built as a complete, sellable micro-SaaS. Deploy to Streamlit Community Cloud, Railway, or your own VPS in minutes. See README for full monetization playbook.")
