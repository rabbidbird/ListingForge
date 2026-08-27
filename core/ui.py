"""Shared Streamlit presentation helpers."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from .auth import render_account_sidebar
from .copy import (
    CLAIM_CATEGORIES,
    COPY_SUCCESS,
    DRAFT_BANNER,
    EXPORT_REMINDER,
    FEATURES,
    FOOTER_CAPTION,
    HEURISTIC_NOTICE,
    HOW_IT_WORKS,
    PLAN_BLURBS,
    POSITIONING,
    PRODUCT_NAME,
    TAGLINE,
    TRUST_POINTS,
    plan_limit_lines,
)
from .models import User
from .plans import PLANS
from .usage import get_usage


def configure_page(title: str, icon: str, *, browser_title: str | None = None) -> None:
    st.set_page_config(
        page_title=browser_title or f"{title} | {PRODUCT_NAME}",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )


def render_quota_notice(usage: dict[str, Any]) -> None:
    """Explain failed payments and hard caps without inventing paid entitlements."""
    status = str(usage.get("status") or "free")
    if usage.get("payment_failed"):
        st.error(
            "A payment is past due, so Free limits apply. Open Plans & Pricing and use the "
            "Stripe Customer Portal to update the payment method."
        )
        return
    if status == "incomplete":
        st.warning(
            "Checkout payment is still incomplete. Free limits apply until Stripe confirms "
            "payment and the webhook updates this account."
        )
        return
    if status == "canceled":
        st.info(
            "The paid subscription is canceled. Free limits apply. Start a new plan from "
            "Plans & Pricing if you want paid quotas again."
        )
        return
    if not usage.get("can_generate"):
        plan = str(usage.get("plan") or "free").title()
        st.warning(
            f"{plan} generation limit reached "
            f"({usage['daily']}/{usage['daily_limit']} today, "
            f"{usage['monthly']}/{usage['monthly_limit']} this month, UTC). "
            "Upgrade on Plans & Pricing or wait for the next UTC period."
        )
        st.page_link("pages/5_About_Pricing.py", label="View plans and upgrade", icon="💳")


def render_sidebar(user: User | None = None) -> None:
    with st.sidebar:
        st.markdown(f"## {PRODUCT_NAME}")
        st.caption(TAGLINE)
        st.page_link("app.py", label="Home", icon="🏠")
        st.page_link("pages/1_Optimizer.py", label="Single Draft", icon="✍️")
        st.page_link("pages/2_Bulk_Processor.py", label="Bulk Drafts", icon="📦")
        st.page_link("pages/3_SEO_Analyzer.py", label="Listing Checklist", icon="📋")
        st.page_link("pages/4_History.py", label="History", icon="🕘")
        st.page_link("pages/5_About_Pricing.py", label="Plans & Pricing", icon="💳")
        st.page_link("pages/6_Legal.py", label="Legal", icon="📜")
        st.divider()
        if user is None:
            st.caption("Home → Plans → Create account")
            st.markdown("[Create account](/auth/signup) · [Sign in](/auth/login)")
        else:
            usage = get_usage(user.id)
            st.caption(
                f"{str(usage['plan']).title()} · {usage['daily']}/{usage['daily_limit']} today · "
                f"{usage['monthly']}/{usage['monthly_limit']} this month (UTC)"
            )
            if usage.get("payment_failed"):
                st.caption("Payment past due · Free limits")
                st.page_link("pages/5_About_Pricing.py", label="Update billing", icon="💳")
            elif not usage.get("can_generate"):
                st.caption("Generation limit reached")
                st.page_link("pages/5_About_Pricing.py", label="Upgrade plan", icon="💳")
            render_account_sidebar(user)


def draft_banner() -> None:
    st.warning(DRAFT_BANNER)


def heuristic_notice() -> None:
    st.info(HEURISTIC_NOTICE)


def render_public_ctas(*, include_plans: bool = True) -> None:
    cols = st.columns([1, 1, 1, 1] if include_plans else [1, 1, 2])
    cols[0].link_button("Create account", "/auth/signup", type="primary", use_container_width=True)
    cols[1].link_button("Sign in", "/auth/login", use_container_width=True)
    if include_plans:
        with cols[2]:
            st.page_link("pages/5_About_Pricing.py", label="View plans", icon="💳")


def render_how_it_works() -> None:
    st.markdown("### How it works")
    top = st.columns(2)
    bottom = st.columns(2)
    for column, (title, body) in zip([*top, *bottom], HOW_IT_WORKS, strict=True):
        with column:
            st.markdown(f"**{title}**")
            st.write(body)


def render_feature_grid() -> None:
    st.markdown("### What you can do")
    first = st.columns(3)
    second = st.columns(2)
    slots = [*first, *second]
    for column, (title, body) in zip(slots, FEATURES, strict=True):
        with column:
            st.markdown(f"**{title}**")
            st.write(body)


def render_trust_grid() -> None:
    st.markdown("### Why the drafts stay honest")
    top = st.columns(2)
    bottom = st.columns(2)
    for column, (title, body) in zip([*top, *bottom], TRUST_POINTS, strict=True):
        with column:
            st.markdown(f"**{title}**")
            st.write(body)


def render_positioning() -> None:
    st.markdown("### Honest positioning")
    cols = st.columns(3)
    for column, (title, body) in zip(cols, POSITIONING, strict=True):
        with column:
            st.markdown(f"**{title}**")
            st.write(body)


def render_claim_categories(*, expanded: bool = False) -> None:
    st.markdown("### What SellerDrafts will not invent")
    with st.expander("See blocked claim categories", expanded=expanded):
        st.markdown(
            "These claims appear only when you type them. Leaving a field blank does not "
            "let the generator fill it in."
        )
        for title, examples in CLAIM_CATEGORIES:
            st.markdown(f"**{title}** — {examples}")


def render_plan_teaser() -> None:
    st.markdown("### Plans at a glance")
    st.caption("Same generator on every plan. Paid plans raise documented quotas only.")
    top = st.columns(2)
    bottom = st.columns(2)
    for column, key in zip([*top, *bottom], ["free", "starter", "pro", "agency"], strict=True):
        policy = PLANS[key]
        with column:
            st.markdown(f"**{policy.name}** · {policy.display_price}")
            st.caption(PLAN_BLURBS[key])
            for line in plan_limit_lines(key):
                st.write(line)
    st.page_link("pages/5_About_Pricing.py", label="Compare plans and billing rules", icon="💳")


def render_export_reminder() -> None:
    st.caption(EXPORT_REMINDER)


def render_public_footer() -> None:
    st.divider()
    st.markdown("[Home](/) · [Plans & Pricing](/About_Pricing) · [Legal](/Legal)")
    st.caption(FOOTER_CAPTION)


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
  try {{ await navigator.clipboard.writeText({payload}); status.textContent = "{COPY_SUCCESS}"; }}
  catch (_) {{ status.textContent = "Copy failed — select the text manually"; }}
}});
</script>
""",
        height=42,
    )


def confirm_before_export(key_prefix: str) -> bool:
    st.subheader("Confirm before export")
    st.caption("Export stays locked until all three checks are confirmed. " + EXPORT_REMINDER)
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
