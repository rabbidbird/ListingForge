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
from core.plans import PLANS
from core.ui import configure_page, render_sidebar
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
if checkout_state == "success":
    st.success("Checkout returned successfully. Stripe webhooks apply the entitlement shortly.")
elif checkout_state == "cancelled":
    st.info("Checkout was cancelled; your current plan is unchanged.")

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
    if not stripe_enabled():
        st.warning(
            "Live billing is not configured. The operator must set the Stripe restricted API "
            "key, signing secret, and all three Price IDs."
        )
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

st.divider()
st.subheader("How billing state is applied")
st.markdown(
    "- Checkout uses Stripe-hosted subscription Checkout with dynamic payment methods.\n"
    "- Signed, idempotent webhooks grant, change, or remove plan entitlements.\n"
    "- Active and trialing subscriptions receive paid limits; other statuses fail closed to Free.\n"
    "- The Stripe-hosted Customer Portal handles payment methods and cancellation."
)
st.caption(
    "Tax and refund obligations depend on the operator's registrations and jurisdiction; "
    "TrueDraft does not claim Stripe Tax is enabled automatically."
)
