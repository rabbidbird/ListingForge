"""Public plan table and authenticated Stripe billing actions."""

from __future__ import annotations

import streamlit as st

from core.auth import streamlit_current_user
from core.billing import (
    BillingError,
    create_checkout_session,
    create_customer_portal_session,
    get_upgrade_options,
    stripe_enabled,
)
from core.plans import PAID_PLANS, PLANS
from core.ui import configure_page, render_quota_notice, render_sidebar
from core.usage import get_usage

configure_page("Plans & Billing", "💳")
user = streamlit_current_user()
render_sidebar(user)

st.title("Plans and billing")
st.write(
    "All plans use the same fact-locked generator. Paid plans raise documented quotas; "
    "none are marketed as unlimited."
)
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

columns = st.columns(4)
for column, plan_name in zip(columns, ["free", "starter", "pro", "agency"], strict=True):
    policy = PLANS[plan_name]
    with column:
        st.subheader(policy.name)
        st.markdown(f"**{policy.display_price}**")
        st.write(f"{policy.daily_generations:,} drafts / UTC day")
        st.write(f"{policy.monthly_generations:,} drafts / UTC month")
        st.write(f"{policy.bulk_rows_per_job:,} rows / bulk job")
        st.write(f"{policy.daily_llm_generations:,} LLM attempts / UTC day")

st.caption(
    "Limits are enforced per user in database transactions. LLM attempts can fall back to "
    "template output when source-lock checks fail."
)

if user is None:
    st.info("Sign in to start or manage a subscription.")
    left, right, _ = st.columns([1, 1, 2])
    left.link_button("Create account", "/auth/signup", type="primary", use_container_width=True)
    right.link_button("Sign in", "/auth/login", use_container_width=True)
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
st.caption(
    "Tax and refund obligations depend on the operator's registrations and jurisdiction; "
    "TrueDraft does not claim Stripe Tax is enabled automatically."
)
