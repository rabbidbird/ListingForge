"""Shared Streamlit presentation helpers."""

from __future__ import annotations

import json
import re
import uuid

import streamlit as st
import streamlit.components.v1 as components

from .auth import render_account_sidebar
from .models import User
from .usage import get_usage


def configure_page(title: str, icon: str) -> None:
    st.set_page_config(
        page_title=f"{title} | TrueDraft",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )


def render_sidebar(user: User | None = None) -> None:
    with st.sidebar:
        st.markdown("## TrueDraft")
        st.caption("Fact-locked product listing drafts")
        st.page_link("app.py", label="Home", icon="🏠")
        st.page_link("pages/1_Optimizer.py", label="Single Draft", icon="✍️")
        st.page_link("pages/2_Bulk_Processor.py", label="Bulk Drafts", icon="📦")
        st.page_link("pages/3_SEO_Analyzer.py", label="Listing Checklist", icon="📋")
        st.page_link("pages/4_History.py", label="History", icon="🕘")
        st.page_link("pages/5_About_Pricing.py", label="Plans & Billing", icon="💳")
        st.page_link("pages/6_Legal.py", label="Legal", icon="📜")
        st.divider()
        if user is None:
            st.markdown("[Sign in](/auth/login) · [Sign up](/auth/signup)")
        else:
            usage = get_usage(user.id)
            st.caption(
                f"{str(usage['plan']).title()} · {usage['daily']}/{usage['daily_limit']} today · "
                f"{usage['monthly']}/{usage['monthly_limit']} this month (UTC)"
            )
            render_account_sidebar(user)


def draft_banner() -> None:
    st.warning(
        "DRAFT — verify before publishing. Confirm every material, claim, rating, "
        "shipping statement, and product attribute against the actual product."
    )


def heuristic_notice() -> None:
    st.info(
        "Checklist scores are transparent heuristics only. They do not predict search "
        "ranking, conversion, or sales. Marketplace rules can change."
    )


def copy_button(text: str, *, label: str = "Copy") -> None:
    payload = (
        json.dumps(str(text), ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    element_id = f"copy-{uuid.uuid4().hex}"
    components.html(
        f"""
<button id="{element_id}" style="border:1px solid #64748b;border-radius:7px;padding:.45rem .8rem;background:#1e293b;color:#f1f5f9;cursor:pointer">{label}</button>
<span id="{element_id}-status" style="margin-left:.5rem;color:#94a3b8;font:13px system-ui"></span>
<script>
const button = document.getElementById("{element_id}");
button.addEventListener("click", async () => {{
  const status = document.getElementById("{element_id}-status");
  try {{ await navigator.clipboard.writeText({payload}); status.textContent = "Copied"; }}
  catch (_) {{ status.textContent = "Copy failed — select the text manually"; }}
}});
</script>
""",
        height=42,
    )


def confirm_before_export(key_prefix: str) -> bool:
    st.subheader("Confirm before export")
    st.caption("Export stays locked until all three checks are confirmed.")
    checks = [
        st.checkbox(
            "I checked every factual claim against the actual product.",
            key=f"{key_prefix}_facts",
        ),
        st.checkbox(
            "I checked current marketplace rules, restricted terms, and category limits.",
            key=f"{key_prefix}_platform",
        ),
        st.checkbox(
            "I understand this is a draft and I am responsible for what I publish.",
            key=f"{key_prefix}_draft",
        ),
    ]
    return all(checks)


def safe_filename(value: str, fallback: str = "draft") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")[:50]
    return cleaned or fallback
