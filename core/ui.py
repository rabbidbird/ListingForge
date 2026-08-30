"""Shared Streamlit presentation helpers."""

from __future__ import annotations

import html
import json
import re
import uuid
from pathlib import Path
from typing import Any

import streamlit as st

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

_STYLE_PATH = Path(__file__).resolve().parent.parent / "static" / "sellerdrafts.css"


def configure_page(title: str, icon: str, *, browser_title: str | None = None) -> None:
    st.set_page_config(
        page_title=browser_title or f"{title} | {PRODUCT_NAME}",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="auto",
    )
    st.markdown(f"<style>{_STYLE_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def _card_grid(items: list[tuple[str, str]], *, extra_class: str = "") -> None:
    cards = "".join(
        f'<article class="sd-card"><h3>{html.escape(title)}</h3><p>{html.escape(body)}</p></article>'
        for title, body in items
    )
    st.markdown(
        f'<section class="sd-grid {html.escape(extra_class)}">{cards}</section>',
        unsafe_allow_html=True,
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
    if user is None:
        st.markdown(
            """
<nav class="sd-topbar" aria-label="SellerDrafts">
  <a class="sd-wordmark" href="/"><span>S</span>SellerDrafts</a>
  <div>
    <a href="/pricing">Plans</a>
    <a href="/legal">Legal</a>
    <a class="sd-header-signin" href="/auth/login">Sign in</a>
  </div>
</nav>
""",
            unsafe_allow_html=True,
        )
        return

    with st.sidebar:
        st.markdown(
            f'<div class="sd-side-brand"><span>S</span>{PRODUCT_NAME}</div>', unsafe_allow_html=True
        )
        st.caption(TAGLINE)
        st.page_link("app.py", label="Home")
        st.page_link("pages/1_Optimizer.py", label="Single Draft")
        st.page_link("pages/2_Bulk_Processor.py", label="Bulk")
        st.page_link("pages/3_SEO_Analyzer.py", label="Checklist")
        st.page_link("pages/4_History.py", label="History")
        st.page_link("pages/5_About_Pricing.py", label="Plans")
        st.page_link("pages/6_Legal.py", label="Legal")
        st.markdown(
            '<a class="sd-account-link" href="/auth/account">Account</a>', unsafe_allow_html=True
        )
        st.divider()
        usage = get_usage(user.id)
        st.caption(
            f"{str(usage['plan']).title()} · {usage['daily']}/{usage['daily_limit']} today · "
            f"{usage['monthly']}/{usage['monthly_limit']} this month (UTC)"
        )
        if usage.get("payment_failed"):
            st.caption("Payment past due · Free limits")
            st.page_link("pages/5_About_Pricing.py", label="Update billing")
        elif not usage.get("can_generate"):
            st.caption("Generation limit reached")
            st.page_link("pages/5_About_Pricing.py", label="Upgrade plan")
        render_account_sidebar(user)


def draft_banner(*, compact: bool = False) -> None:
    css_class = "sd-draft-banner sd-draft-banner-compact" if compact else "sd-draft-banner"
    st.markdown(
        f'<div class="{css_class}" role="alert">{html.escape(DRAFT_BANNER)}</div>',
        unsafe_allow_html=True,
    )


def heuristic_notice() -> None:
    st.info(HEURISTIC_NOTICE)


def render_public_ctas(*, include_plans: bool = False) -> None:
    plans = (
        '<a class="sd-cta sd-cta-tertiary" href="/pricing">View plans</a>' if include_plans else ""
    )
    st.markdown(
        f"""
<div class="sd-cta-row">
  <a class="sd-cta sd-cta-primary" href="/auth/signup">Create account</a>
  <a class="sd-cta sd-cta-secondary" href="/auth/login">Sign in</a>
  {plans}
</div>
""",
        unsafe_allow_html=True,
    )


def render_how_it_works() -> None:
    st.markdown("### How it works")
    _card_grid(list(HOW_IT_WORKS))


def render_feature_grid() -> None:
    st.markdown("### What you can do")
    _card_grid(list(FEATURES))


def render_trust_grid() -> None:
    st.markdown("### Why the drafts stay honest")
    _card_grid(list(TRUST_POINTS))


def render_positioning() -> None:
    st.markdown("### Honest positioning")
    _card_grid(list(POSITIONING))


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
    items: list[tuple[str, str]] = []
    for key in ("free", "starter", "pro", "agency"):
        policy = PLANS[key]
        items.append(
            (
                f"{policy.name} · {policy.display_price}",
                f"{PLAN_BLURBS[key]} {' · '.join(plan_limit_lines(key)[:3])}",
            )
        )
    _card_grid(items, extra_class="sd-plan-grid")
    st.page_link("pages/5_About_Pricing.py", label="Compare plans and billing rules")


def render_export_reminder() -> None:
    st.caption(EXPORT_REMINDER)


def render_public_footer() -> None:
    st.divider()
    st.markdown("[Home](/) · [Guides](/guides) · [Plans & Pricing](/pricing) · [Legal](/legal)")
    st.caption(FOOTER_CAPTION)


def copy_button(text: str, *, label: str = "Copy", event_name: str | None = None) -> None:
    payload = (
        json.dumps(str(text), ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    element_id = f"copy-{uuid.uuid4().hex}"
    event_script = ""
    if event_name:
        event_payload = json.dumps({"event": event_name})
        event_script = f"""
  try {{
    await fetch("/events/product", {{
      method: "POST",
      credentials: "include",
      headers: {{"Content-Type": "application/json"}},
      body: {json.dumps(event_payload)}
    }});
  }} catch (_) {{ /* Copying must still work if measurement is unavailable. */ }}
"""
    st.iframe(
        f"""
<button id="{element_id}" style="border:1px solid #64748b;border-radius:7px;padding:.45rem .8rem;background:#1e293b;color:#f1f5f9;cursor:pointer">{label}</button>
<span id="{element_id}-status" style="margin-left:.5rem;color:#94a3b8;font:13px system-ui"></span>
<script>
const button = document.getElementById("{element_id}");
button.addEventListener("click", async () => {{
  const status = document.getElementById("{element_id}-status");
  try {{
    await navigator.clipboard.writeText({payload});
    status.textContent = "{COPY_SUCCESS}";
    {event_script}
  }}
  catch (_) {{ status.textContent = "Copy failed — select the text manually"; }}
}});
</script>
""",
        height=46,
        width="stretch",
    )


def render_editable_draft(
    user: User,
    listing_id: str,
    result: dict[str, Any],
    *,
    key_prefix: str,
) -> None:
    """Render one authorized saved draft with edit, audit, and copy actions."""

    from .draft_review import recheck_edited_draft
    from .events import record_product_event
    from .generation_service import GenerationInputError, regenerate_for_user
    from .usage import UsageLimitError
    from .utils import update_listing

    title_key = f"{key_prefix}_title"
    description_key = f"{key_prefix}_description"
    tags_key = f"{key_prefix}_tags"
    verified_key = f"{key_prefix}_verified"

    if st.session_state.pop(f"{key_prefix}_saved_notice", False):
        st.success("Changes saved and claims re-checked against the original facts.")
    if st.session_state.pop(f"{key_prefix}_regenerated_notice", False):
        st.success("Draft regenerated from the original facts and saved.")

    review = result.get("edit_review") if isinstance(result.get("edit_review"), dict) else {}
    warnings = review.get("warnings") if isinstance(review, dict) else []
    st.subheader("Saved draft")
    st.caption(EXPORT_REMINDER)
    st.markdown(
        '<section class="sd-output-field"><h3>Title</h3>'
        f"<div>{html.escape(result['best_title'])}</div></section>",
        unsafe_allow_html=True,
    )
    copy_button(result["best_title"], label="Copy title", event_name="title_copied")
    description_html = html.escape(result["description"]).replace("\n", "<br>")
    st.markdown(
        '<section class="sd-output-field"><h3>Description</h3>'
        f"<div>{description_html}</div></section>",
        unsafe_allow_html=True,
    )
    copy_button(result["description"], label="Copy description", event_name="description_copied")
    tag_text = ", ".join(result["tags"])
    tags_html = "<br>".join(html.escape(tag) for tag in result["tags"])
    tags_display = tags_html or '<span class="sd-output-empty">No supplied tag phrases fit.</span>'
    st.markdown(
        f'<section class="sd-output-field"><h3>Tags</h3><div>{tags_display}</div></section>',
        unsafe_allow_html=True,
    )
    copy_button(tag_text, label="Copy tags", event_name="tags_copied")
    st.caption("Tags copy as one comma-separated line.")

    with st.expander("Edit and re-check", expanded=bool(warnings)):
        st.caption(
            "Edit the saved fields below. SellerDrafts compares saved edits with the original "
            "fact inventory; unsaved changes are not copied or downloaded."
        )
        if warnings:
            st.warning("This saved edit contains wording that needs confirmation before download.")
            for warning in warnings:
                st.markdown(f"- {warning['message']}")
            if review.get("explicitly_verified"):
                st.success("You explicitly verified the flagged wording for this saved draft.")

        st.session_state.setdefault(title_key, result["best_title"])
        st.session_state.setdefault(description_key, result["description"])
        st.session_state.setdefault(tags_key, "\n".join(result["tags"]))

        with st.form(f"{key_prefix}_edit_form"):
            edited_title = st.text_input(
                "Title",
                max_chars=500,
                key=title_key,
            )
            edited_description = st.text_area(
                "Description",
                height=330,
                key=description_key,
            )
            edited_tags = st.text_area(
                "Tags — one per line",
                height=180,
                key=tags_key,
            )
            explicitly_verified = st.checkbox(
                "I verified any newly added wording against this exact product.",
                help=(
                    "This confirmation unlocks downloads only after the edited draft is saved "
                    "and re-checked. It does not certify marketplace compliance."
                ),
                key=verified_key,
            )
            save_column, revert_column, regenerate_column = st.columns(3)
            save = save_column.form_submit_button(
                "Save changes & re-check claims", type="primary", width="stretch"
            )
            revert = revert_column.form_submit_button("Revert unsaved changes", width="stretch")
            regenerate = regenerate_column.form_submit_button(
                "Regenerate original facts", width="stretch"
            )

    if revert:
        for key in (title_key, description_key, tags_key, verified_key):
            st.session_state.pop(key, None)
        st.rerun()
    if regenerate:
        try:
            regenerate_for_user(user.id, listing_id)
            for key in (title_key, description_key, tags_key, verified_key):
                st.session_state.pop(key, None)
            st.session_state[f"{key_prefix}_regenerated_notice"] = True
            st.rerun()
        except (GenerationInputError, UsageLimitError) as exc:
            st.error(str(exc))
        except Exception:
            st.error("The draft could not be regenerated. Your usage reservation was released.")
    if save:
        tags = [line.strip() for line in edited_tags.splitlines() if line.strip()]
        updated = recheck_edited_draft(
            result,
            title=edited_title.strip(),
            description=edited_description.strip(),
            tags=tags,
            explicitly_verified=explicitly_verified,
        )
        if update_listing(user.id, listing_id, updated):
            changed = (
                edited_title.strip() != result["best_title"]
                or edited_description.strip() != result["description"]
                or tags != result["tags"]
            )
            if changed:
                record_product_event(user.id, "draft_edited_saved")
            for key in (title_key, description_key, tags_key, verified_key):
                st.session_state.pop(key, None)
            st.session_state[f"{key_prefix}_saved_notice"] = True
            st.rerun()
        else:
            st.error("Draft not found or not authorized.")


def confirm_before_export(key_prefix: str) -> bool:
    st.subheader("Confirm before download")
    st.caption("Downloads stay locked until all three checks are confirmed. " + EXPORT_REMINDER)
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
