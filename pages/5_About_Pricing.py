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
from core.copy import PLAN_BLURBS, PROMISE, plan_limit_lines
from core.plans import PAID_PLANS, PLANS
from core.ui import (
    configure_page,
    draft_banner,
    heuristic_notice,
    render_public_ctas,
    render_public_footer,
    render_quota_notice,
    render_sidebar,
)
from core.usage import get_usage

configure_page("Plans & Pricing", "💳")
user = streamlit_current_user()
render_sidebar(user)

st.title("Plans and pricing")
st.write(PROMISE)
st.write(
    "All plans use the same fact-locked generator. Paid plans raise documented quotas; "
    "none are marketed as unlimited. SellerDrafts does not publish listings or promise ranking."
)
draft_banner()

checkout_state = st.query_params.get("checkout")
portal_state = st.query_params.get("portal")
if checkout_state == "success":
    st.success(
        "Checkout returned successfully. Stripe webhooks apply the paid entitlement in a "
        "few seconds. Refresh this page if the plan below has not updated yet."
    )
    st.info("If payment is still processing, Free limits stay in force until Stripe confirms it.")
elif checkout_state == "cancelled":
    st.info("Checkout was cancelled; your current plan is unchanged.")
if portal_state == "return":
    st.info(
        "Returned from the Stripe Customer Portal. Plan changes apply after the signed "
        "webhook is processed; refresh if the status below looks stale."
    )

st.markdown("### Compare plans")
plan_cards: list[str] = []
for plan_name in ("free", "starter", "pro", "agency"):
    policy = PLANS[plan_name]
    limits = "".join(f"<li>{html.escape(line)}</li>" for line in plan_limit_lines(plan_name))
    plan_cards.append(
        '<article class="sd-pricing-card">'
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

st.caption(
    "Limits are enforced per user in database transactions. Launch generation uses the "
    "fact-locked template path. Periods are UTC."
)

if user is None:
    st.info("Create a Free account to generate drafts. Upgrade later from this page.")
    render_public_ctas(include_plans=False)
else:
    usage = get_usage(user.id)
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
                    use_container_width=True,
                ):
                    try:
                        url = create_checkout_session(user.id, option["plan"])
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
st.subheader("How billing state is applied")
st.markdown(
    "- Checkout uses Stripe-hosted subscription Checkout with dynamic payment methods.\n"
    "- Signed, idempotent webhooks grant, change, or remove plan entitlements.\n"
    "- Active and trialing subscriptions receive paid limits; other statuses fail closed to Free.\n"
    "- Past-due or unpaid invoices keep Free limits until the invoice is paid in the portal.\n"
    "- The Stripe-hosted Customer Portal handles payment methods, plan changes, and cancellation.\n"
    "- Returning from Checkout or the portal does not itself change limits; the webhook does."
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
heuristic_notice()
st.caption(
    "Tax and refund obligations depend on the operator's registrations and jurisdiction; "
    "SellerDrafts does not claim Stripe Tax is enabled automatically."
)
render_public_footer()
