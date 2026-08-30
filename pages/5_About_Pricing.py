"""Public plan comparison and authenticated Stripe billing actions."""

from __future__ import annotations

import html

import streamlit as st

from core.auth import streamlit_current_user
from core.billing import (
    BillingError,
    create_checkout_session,
    create_customer_portal_session,
    get_upgrade_options,
    stripe_enabled,
)
from core.copy import PLAN_BLURBS, plan_limit_lines
from core.events import record_product_event, record_product_event_once
from core.plans import PAID_PLANS, PLANS
from core.ui import (
    configure_page,
    render_public_ctas,
    render_public_footer,
    render_quota_notice,
    render_sidebar,
)
from core.usage import get_usage

configure_page("Plans & Pricing", "💳")
user = streamlit_current_user()
render_sidebar(user)
if user is not None and not st.session_state.get("pricing_view_recorded"):
    record_product_event_once(user.id, "pricing_viewed")
    st.session_state["pricing_view_recorded"] = True

st.title("Choose the draft volume that fits your shop")
st.write(
    "Every plan uses the same fact-locked generator. Start Free, then upgrade when you need "
    "more drafts or larger CSV jobs. No plan is unlimited or changes the review requirement."
)

checkout_state = st.query_params.get("checkout")
portal_state = st.query_params.get("portal")
selected_plan = str(st.query_params.get("plan") or "").lower()
if selected_plan not in {"starter", "pro", "agency"}:
    selected_plan = ""
if checkout_state == "success":
    st.success(
        "Payment confirmation is processing. Your paid plan should appear here in a few "
        "seconds; refresh if it has not updated yet."
    )
    st.info("If payment is still processing, Free limits stay in force until Stripe confirms it.")
elif checkout_state == "cancelled":
    st.info("Checkout was cancelled; your current plan is unchanged.")
if portal_state == "return":
    st.info(
        "Returned from the Stripe Customer Portal. Refresh if a recent plan change is not "
        "shown below yet."
    )

st.markdown("### Compare plans")
plan_cards: list[str] = []
for plan_name in ("free", "starter", "pro", "agency"):
    policy = PLANS[plan_name]
    limits = "".join(f"<li>{html.escape(line)}</li>" for line in plan_limit_lines(plan_name)[:3])
    featured = plan_name == "starter"
    use_case = {
        "free": "Try it first",
        "starter": "Recommended for regular shops",
        "pro": "Higher-volume work",
        "agency": "Highest-volume work",
    }[plan_name]
    plan_cards.append(
        f'<article class="sd-pricing-card{" sd-pricing-featured" if featured else ""}">'
        f'<p class="sd-plan-kicker">{html.escape(use_case)}</p>'
        f"<h3>{html.escape(policy.name)}</h3>"
        f'<p class="sd-plan-price">{html.escape(policy.display_price)}</p>'
        f'<p class="sd-plan-blurb">{html.escape(PLAN_BLURBS[plan_name])}</p>'
        f'<ul class="sd-plan-limits">{limits}</ul>'
        "</article>"
    )
st.markdown(
    f'<section class="sd-pricing-grid">{"".join(plan_cards)}</section>',
    unsafe_allow_html=True,
)

st.caption("Limits apply to each account and reset on the documented UTC schedule.")

if user is None:
    st.info("Create a Free account to generate drafts. Upgrade later from this page.")
    render_public_ctas(include_plans=False)
else:
    usage = get_usage(user.id)
    if selected_plan:
        selected = PLANS[selected_plan]
        st.info(
            f"You selected {selected.name} — {selected.display_price}. "
            "Review the limits below, then explicitly choose the plan to open Stripe Checkout."
        )
    st.subheader(f"Current plan: {str(usage['plan']).title()}")
    st.caption(
        f"Billing status: {str(usage['status'])}. "
        f"{usage['daily_remaining']} drafts left today and "
        f"{usage['monthly_remaining']} this month (UTC)."
    )
    render_quota_notice(usage)
    if not stripe_enabled():
        st.warning(
            "Live billing is not configured. The operator must set the Stripe restricted API "
            "key, signing secret, and all three Price IDs."
        )

    if usage.get("manage_in_portal"):
        st.info(
            "This account already has a Stripe subscription. Use the billing portal to "
            "change plan, update the payment method, or cancel. Starting a second Checkout "
            "session is blocked so you cannot be double-charged."
        )
    else:
        options = get_upgrade_options()
        action_columns = st.columns(3)
        for column, option in zip(action_columns, options, strict=True):
            with column:
                if st.button(
                    f"Choose {option['name']}",
                    key=f"checkout_{option['plan']}",
                    disabled=not stripe_enabled(),
                    width="stretch",
                ):
                    try:
                        url = create_checkout_session(user.id, option["plan"])
                        record_product_event(user.id, "checkout_initiated")
                        st.session_state["stripe_checkout"] = {
                            "user_id": str(user.id),
                            "plan": option["plan"],
                            "url": url,
                        }
                    except BillingError as exc:
                        st.error(str(exc))

        pending = st.session_state.get("stripe_checkout")
        if pending and pending.get("user_id") == str(user.id):
            st.link_button(
                f"Continue to Stripe Checkout for {str(pending['plan']).title()}",
                pending["url"],
                type="primary",
            )

    if usage.get("has_stripe_customer") or usage.get("manage_in_portal"):
        if st.button("Open Stripe billing portal", disabled=not stripe_enabled()):
            try:
                portal_url = create_customer_portal_session(user.id)
                st.session_state["stripe_portal"] = {
                    "user_id": str(user.id),
                    "url": portal_url,
                }
            except BillingError as exc:
                st.error(str(exc))
        portal = st.session_state.get("stripe_portal")
        if portal and portal.get("user_id") == str(user.id):
            st.link_button("Continue to Stripe billing portal", portal["url"])
    elif str(usage["plan"]) in PAID_PLANS:
        st.caption("The billing portal appears after Stripe links a customer to this account.")

st.divider()
st.subheader("Billing basics")
st.markdown(
    "- Stripe securely handles checkout and payment methods.\n"
    "- Paid limits begin after Stripe confirms payment.\n"
    "- Use the billing portal to change plans, update payment details, or cancel.\n"
    "- If a subscription becomes inactive, Free limits apply."
)
st.subheader("Billing questions")
st.markdown(
    "- **When does a paid plan start?** After Stripe confirms payment and the signed webhook "
    "updates this account. The Checkout return page is not itself an entitlement.\n"
    "- **What if payment fails later?** Free limits apply. Use the Customer Portal — do not "
    "start a second Checkout.\n"
    "- **Is any plan uncapped?** No. Every plan has a documented daily and monthly generation cap.\n"
    "- **Does upgrading change the generator?** No. Paid plans only raise quotas."
)
render_public_footer()
