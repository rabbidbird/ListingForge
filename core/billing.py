"""
Stripe integration helpers for ListingForge.
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
    if not stripe_enabled() or not price_id:
        return None

    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    params = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": user_id,
        "metadata": {
            "user_id": user_id,
            "plan": PRICE_TO_PLAN.get(price_id, "pro"),
            "price_id": price_id,
        },
    }
    if customer_email:
        params["customer_email"] = customer_email

    session = stripe.checkout.Session.create(**params)
    return session.url


def _extract_plan_from_event(session: dict) -> Optional[str]:
    metadata = session.get("metadata") or {}
    if metadata.get("plan") in PLANS:
        return metadata.get("plan")

    price_id = metadata.get("price_id")
    if price_id and price_id in PRICE_TO_PLAN:
        return PRICE_TO_PLAN.get(price_id)

    line_items = session.get("line_items", {})
    if isinstance(line_items, dict):
        items = line_items.get("data", [])
        if items:
            price = items[0].get("price") or {}
            if price.get("id") in PRICE_TO_PLAN:
                return PRICE_TO_PLAN.get(price["id"])

    # Invoice events may include line_items directly on the invoice payload.
    invoice_lines = session.get("lines", {})
    if isinstance(invoice_lines, dict):
        items = invoice_lines.get("data", [])
        if items:
            price = items[0].get("price") or {}
            if price.get("id") in PRICE_TO_PLAN:
                return PRICE_TO_PLAN.get(price["id"])

    # Last-resort scan: if this webhook includes a subscription object with items.
    subscription = session.get("subscription")
    if isinstance(subscription, dict):
        items = subscription.get("items", {})
        if isinstance(items, dict):
            data = items.get("data", [])
            if data:
                price = data[0].get("price") or {}
                if price.get("id") in PRICE_TO_PLAN:
                    return PRICE_TO_PLAN.get(price["id"])

    return None


def handle_webhook_event(payload: bytes, sig_header: str) -> dict:
    if not stripe_enabled():
        return {"ok": False, "error": "Stripe not configured"}

    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    event_type = event.get("type")
    if event_type not in ("checkout.session.completed", "invoice.payment_succeeded"):
        return {"ok": True, "type": event_type}

    session = event["data"]["object"]
    user_id = session.get("client_reference_id") or session.get("metadata", {}).get("user_id")
    if user_id:
        plan = _extract_plan_from_event(session)
        if plan:
            set_plan(user_id, plan)
            return {"ok": True, "user_id": user_id, "plan": plan, "type": event_type}

    return {"ok": True, "type": event_type}


def get_upgrade_options() -> list:
    return [
        {
            "plan": "starter",
            "label": PLANS["starter"]["label"],
            "price": "$12/mo",
            "price_id": os.getenv("STRIPE_PRICE_STARTER", ""),
            "desc": "50 generations/day, 500/month",
        },
        {
            "plan": "pro",
            "label": PLANS["pro"]["label"],
            "price": "$29/mo",
            "desc": "Unlimited generations",
            "price_id": os.getenv("STRIPE_PRICE_PRO", ""),
        },
        {
            "plan": "agency",
            "label": PLANS["agency"]["label"],
            "price": "$79/mo",
            "desc": "Unlimited + multi-seat workflow",
            "price_id": os.getenv("STRIPE_PRICE_AGENCY", ""),
        },
    ]
