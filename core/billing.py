"""
Stripe billing skeleton for TrueDraft.
"""

from __future__ import annotations

import os
from typing import Optional

try:
    import stripe
    HAS_STRIPE = True
except ImportError:
    HAS_STRIPE = False

from .usage import set_plan, PLANS

PRICE_TO_PLAN = {
    os.getenv("STRIPE_PRICE_STARTER", "price_starter"): "starter",
    os.getenv("STRIPE_PRICE_PRO", "price_pro"): "pro",
    os.getenv("STRIPE_PRICE_AGENCY", "price_agency"): "agency",
}


def stripe_enabled() -> bool:
    return HAS_STRIPE and bool(os.getenv("STRIPE_SECRET_KEY"))


def create_checkout_session(
    user_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    customer_email: Optional[str] = None,
) -> Optional[str]:
    if not stripe_enabled():
        return None

    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    params = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": user_id,
        "metadata": {"user_id": user_id},
    }
    if customer_email:
        params["customer_email"] = customer_email

    session = stripe.checkout.Session.create(**params)
    return session.url


def handle_webhook_event(payload: bytes, sig_header: str) -> dict:
    if not stripe_enabled():
        return {"ok": False, "error": "Stripe not configured"}

    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id") or session.get("metadata", {}).get("user_id")
        plan = "pro"
        if user_id:
            set_plan(user_id, plan)
            return {"ok": True, "user_id": user_id, "plan": plan}

    return {"ok": True, "type": event["type"]}


def get_upgrade_options() -> list:
    return [
        {"plan": "starter", "price": "$12/mo", "price_id": os.getenv("STRIPE_PRICE_STARTER", ""), "desc": "50 generations/day"},
        {"plan": "pro", "price": "$29/mo", "price_id": os.getenv("STRIPE_PRICE_PRO", ""), "desc": "Unlimited generations"},
        {"plan": "agency", "price": "$79/mo", "price_id": os.getenv("STRIPE_PRICE_AGENCY", ""), "desc": "Unlimited + multi-seat"},
    ]
