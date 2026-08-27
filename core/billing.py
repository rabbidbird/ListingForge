"""Stripe Checkout, Customer Portal, and idempotent entitlement webhooks."""

from __future__ import annotations

import logging
import secrets
import string
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import stripe
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .database import session_scope
from .models import Subscription, User, WebhookEvent
from .plans import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    PAID_PLANS,
    PLANS,
    subscription_must_use_portal,
)

STRIPE_API_VERSION = "2026-07-29.dahlia"
CHECKOUT_SESSION_TTL_SECONDS = 60 * 60
CHECKOUT_EVENTS = frozenset(
    {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }
)
SUBSCRIPTION_UPDATE_EVENTS = frozenset(
    {
        "customer.subscription.created",
        "customer.subscription.updated",
    }
)
SUBSCRIPTION_DELETE_EVENTS = frozenset({"customer.subscription.deleted"})
ACK_ONLY_EVENTS = {
    "checkout.session.async_payment_failed": "async_payment_failed",
    "checkout.session.expired": "checkout_expired",
    "invoice.payment_failed": "invoice_payment_failed_deferred_to_subscription",
    "invoice.paid": "invoice_paid_deferred_to_subscription",
}

logger = logging.getLogger("truedraft.billing")


class BillingError(RuntimeError):
    pass


class WebhookVerificationError(BillingError):
    pass


def _stripe_client() -> stripe.StripeClient:
    settings = get_settings()
    if not settings.stripe_api_key:
        raise BillingError("Stripe is not configured.")
    return stripe.StripeClient(
        settings.stripe_api_key,
        stripe_version=STRIPE_API_VERSION,
        max_network_retries=2,
    )


def stripe_enabled() -> bool:
    return get_settings().stripe_fully_configured


def _price_for_plan(plan: str) -> str:
    settings = get_settings()
    prices = {
        "starter": settings.stripe_price_starter,
        "pro": settings.stripe_price_pro,
        "agency": settings.stripe_price_agency,
    }
    if plan not in PAID_PLANS or not prices.get(plan):
        raise BillingError("That paid plan is not configured.")
    return prices[plan]


def _clear_pending_checkout(
    subscription: Subscription, checkout_session_id: str | None = None
) -> bool:
    pending_id = subscription.pending_checkout_session_id
    if not pending_id:
        return False
    if checkout_session_id is not None and pending_id != checkout_session_id:
        return False
    subscription.pending_checkout_session_id = None
    subscription.pending_checkout_url = None
    subscription.pending_checkout_plan = None
    subscription.pending_checkout_expires_at = 0
    return True


def create_checkout_session(user_id: uuid.UUID, plan: str) -> str:
    client = _stripe_client()
    settings = get_settings()
    price_id = _price_for_plan(plan)
    with session_scope() as session:
        user = session.get(User, user_id)
        subscription = session.scalar(
            select(Subscription).where(Subscription.user_id == user_id).with_for_update()
        )
        if user is None or not user.is_active:
            raise BillingError("Active account required.")
        if subscription is None:
            subscription = Subscription(user_id=user_id, plan="free", status="free")
            session.add(subscription)
            session.flush()
        if subscription_must_use_portal(
            subscription.status,
            subscription.stripe_subscription_id,
        ):
            raise BillingError("Manage the existing subscription in the billing portal.")
        now = int(time.time())
        if (
            subscription.pending_checkout_session_id
            and subscription.pending_checkout_url
            and subscription.pending_checkout_expires_at > now
        ):
            if subscription.pending_checkout_plan != plan:
                raise BillingError(
                    "A Checkout session is already open for another plan. "
                    "Complete it or wait for it to expire before choosing a different plan."
                )
            return subscription.pending_checkout_url
        _clear_pending_checkout(subscription)

        customer_id = subscription.stripe_customer_id
        email = user.email
        expires_at = now + CHECKOUT_SESSION_TTL_SECONDS
        suffix = "".join(secrets.choice(string.ascii_lowercase) for _ in range(8))
        attempt_id = uuid.uuid4().hex
        params: dict[str, Any] = {
            "mode": "subscription",
            "managed_payments": {"enabled": False},
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": f"{settings.public_base_url}/app/About_Pricing?checkout=success",
            "cancel_url": f"{settings.public_base_url}/app/About_Pricing?checkout=cancelled",
            "client_reference_id": str(user_id),
            "metadata": {"user_id": str(user_id), "plan": plan, "price_id": price_id},
            "subscription_data": {
                "metadata": {"user_id": str(user_id), "plan": plan, "price_id": price_id}
            },
            "integration_identifier": f"truedraft_{suffix}",
            "expires_at": expires_at,
        }
        if customer_id:
            params["customer"] = customer_id
        else:
            params["customer_email"] = email
        try:
            checkout = client.v1.checkout.sessions.create(
                params,
                {"idempotency_key": f"truedraft-checkout-{user_id}-{attempt_id}"},
            )
        except stripe.StripeError as exc:
            raise BillingError("Stripe could not start checkout. Try again shortly.") from exc
        if not checkout.id or not checkout.url:
            raise BillingError("Stripe did not return a complete Checkout session.")
        subscription.pending_checkout_session_id = str(checkout.id)
        subscription.pending_checkout_url = str(checkout.url)
        subscription.pending_checkout_plan = plan
        subscription.pending_checkout_expires_at = expires_at
        return str(checkout.url)


def create_customer_portal_session(user_id: uuid.UUID) -> str:
    client = _stripe_client()
    settings = get_settings()
    with session_scope() as session:
        subscription = session.scalar(select(Subscription).where(Subscription.user_id == user_id))
        customer_id = subscription.stripe_customer_id if subscription else None
    if not customer_id:
        raise BillingError("No Stripe customer is linked to this account yet.")
    try:
        portal = client.v1.billing_portal.sessions.create(
            {
                "customer": customer_id,
                "return_url": f"{settings.public_base_url}/app/About_Pricing?portal=return",
            }
        )
    except stripe.StripeError as exc:
        raise BillingError("Stripe could not open the billing portal. Try again shortly.") from exc
    if not portal.url:
        raise BillingError("Stripe did not return a billing portal URL.")
    return str(portal.url)


def construct_webhook_event(payload: bytes, signature: str | None) -> dict[str, Any]:
    secret = get_settings().stripe_webhook_secret
    if not secret or not signature:
        raise WebhookVerificationError("Missing Stripe webhook signature configuration.")
    try:
        event = stripe.Webhook.construct_event(payload, signature, secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise WebhookVerificationError("Invalid Stripe webhook signature.") from exc
    if hasattr(event, "to_dict"):
        return event.to_dict()
    if hasattr(event, "to_dict_recursive"):  # Stripe SDK compatibility before v15.
        return event.to_dict_recursive()
    return dict(event)


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _metadata(obj: dict[str, Any]) -> dict[str, Any]:
    value = obj.get("metadata") or {}
    return dict(value) if hasattr(value, "items") else {}


def _subscription_price_id(obj: dict[str, Any]) -> str | None:
    items = (obj.get("items") or {}).get("data") or []
    if not items:
        return None
    price = items[0].get("price") or {}
    if isinstance(price, str) and price:
        return price
    return price.get("id")


def _checkout_price_id(obj: dict[str, Any]) -> str | None:
    """Prefer the Price Stripe actually charged; never trust metadata.plan."""
    items = (obj.get("line_items") or {}).get("data") or []
    if items:
        price = items[0].get("price") or {}
        if isinstance(price, str) and price:
            return price
        if isinstance(price, dict) and price.get("id"):
            return str(price["id"])
    metadata = _metadata(obj)
    raw = metadata.get("price_id")
    return str(raw) if raw else None


def _subscription_period_end(obj: dict[str, Any]) -> datetime | None:
    direct = _timestamp(obj.get("current_period_end"))
    if direct is not None:
        return direct
    items = (obj.get("items") or {}).get("data") or []
    return _timestamp(items[0].get("current_period_end")) if items else None


def _find_subscription(session, obj: dict[str, Any]) -> Subscription | None:
    metadata = _metadata(obj)
    user_id = _as_uuid(metadata.get("user_id"))
    if user_id:
        by_user = session.scalar(select(Subscription).where(Subscription.user_id == user_id))
        if by_user is not None:
            return by_user
    subscription_id = obj.get("id")
    customer_id = obj.get("customer")
    conditions = []
    if subscription_id:
        conditions.append(Subscription.stripe_subscription_id == subscription_id)
    if customer_id:
        conditions.append(Subscription.stripe_customer_id == customer_id)
    if not conditions:
        return None
    return session.scalar(select(Subscription).where(or_(*conditions)))


def _apply_checkout(session, obj: dict[str, Any], event_created: int) -> dict[str, Any]:
    metadata = _metadata(obj)
    user_id = _as_uuid(obj.get("client_reference_id") or metadata.get("user_id"))
    price_id = _checkout_price_id(obj)
    plan = get_settings().stripe_price_to_plan.get(str(price_id))
    if user_id is None or plan not in PAID_PLANS:
        raise BillingError("Checkout event is missing trusted entitlement metadata.")
    payment_status = obj.get("payment_status")
    if payment_status not in {"paid", "no_payment_required"}:
        return {
            "updated": False,
            "reason": "checkout_not_paid",
            "payment_status": payment_status,
        }
    user = session.get(User, user_id)
    if user is None:
        raise BillingError("Checkout references an unknown user.")
    subscription = session.scalar(
        select(Subscription).where(Subscription.user_id == user_id).with_for_update()
    )
    if subscription is None:
        subscription = Subscription(user_id=user_id)
        session.add(subscription)
        session.flush()
    if event_created < subscription.stripe_event_created_at:
        return {"updated": False, "reason": "older_event"}
    subscription.plan = plan
    subscription.status = "trialing" if payment_status == "no_payment_required" else "active"
    subscription.stripe_customer_id = obj.get("customer") or subscription.stripe_customer_id
    subscription.stripe_subscription_id = (
        obj.get("subscription") or subscription.stripe_subscription_id
    )
    subscription.stripe_price_id = str(price_id)
    subscription.stripe_event_created_at = event_created
    _clear_pending_checkout(subscription, str(obj.get("id")))
    return {"updated": True, "user_id": str(user_id), "plan": plan, "status": subscription.status}


def _release_terminal_checkout(session, obj: dict[str, Any]) -> bool:
    metadata = _metadata(obj)
    user_id = _as_uuid(obj.get("client_reference_id") or metadata.get("user_id"))
    subscription = None
    if user_id is not None:
        subscription = session.scalar(
            select(Subscription).where(Subscription.user_id == user_id).with_for_update()
        )
    if subscription is None and obj.get("customer"):
        subscription = session.scalar(
            select(Subscription)
            .where(Subscription.stripe_customer_id == obj.get("customer"))
            .with_for_update()
        )
    if subscription is None:
        return False
    return _clear_pending_checkout(subscription, str(obj.get("id")))


def _apply_subscription(
    session, obj: dict[str, Any], event_created: int, *, deleted: bool
) -> dict[str, Any]:
    subscription = _find_subscription(session, obj)
    if subscription is None:
        raise BillingError("Subscription event could not be mapped to a user.")
    session.refresh(subscription, with_for_update=True)
    if event_created < subscription.stripe_event_created_at:
        return {"updated": False, "reason": "older_event"}
    price_id = _subscription_price_id(obj)
    stripe_status = "canceled" if deleted else str(obj.get("status") or "unknown")
    plan = get_settings().stripe_price_to_plan.get(str(price_id), "free")
    if deleted or stripe_status not in ACTIVE_SUBSCRIPTION_STATUSES:
        plan = "free"
    subscription.plan = plan
    subscription.status = stripe_status
    subscription.stripe_customer_id = obj.get("customer") or subscription.stripe_customer_id
    subscription.stripe_subscription_id = obj.get("id") or subscription.stripe_subscription_id
    subscription.stripe_price_id = price_id or subscription.stripe_price_id
    subscription.current_period_end = _subscription_period_end(obj)
    subscription.stripe_event_created_at = event_created
    return {
        "updated": True,
        "user_id": str(subscription.user_id),
        "plan": plan,
        "status": stripe_status,
    }


def process_webhook_event(event: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    event_created = int(event.get("created") or 0)
    obj = (event.get("data") or {}).get("object") or {}
    if not event_id or not event_type or not isinstance(obj, dict):
        raise BillingError("Malformed Stripe event.")
    try:
        with session_scope() as session:
            if session.get(WebhookEvent, event_id) is not None:
                result = {"ok": True, "duplicate": True, "type": event_type, "reason": "duplicate"}
                logger.info(
                    "stripe_webhook event_id=%s type=%s duplicate=true",
                    event_id,
                    event_type,
                )
                return result
            detail: dict[str, Any] = {"updated": False, "reason": "unhandled_event_type"}
            if event_type in CHECKOUT_EVENTS:
                detail = _apply_checkout(session, obj, event_created)
            elif event_type in SUBSCRIPTION_UPDATE_EVENTS:
                detail = _apply_subscription(session, obj, event_created, deleted=False)
            elif event_type in SUBSCRIPTION_DELETE_EVENTS:
                detail = _apply_subscription(session, obj, event_created, deleted=True)
            elif event_type in ACK_ONLY_EVENTS:
                detail = {"updated": False, "reason": ACK_ONLY_EVENTS[event_type]}
                if event_type.startswith("checkout.session."):
                    detail["checkout_released"] = _release_terminal_checkout(session, obj)
            session.add(
                WebhookEvent(
                    event_id=event_id,
                    event_type=event_type,
                    stripe_created_at=event_created,
                )
            )
            session.flush()
            result = {"ok": True, "duplicate": False, "type": event_type, **detail}
            logger.info(
                "stripe_webhook event_id=%s type=%s duplicate=false updated=%s reason=%s plan=%s",
                event_id,
                event_type,
                result.get("updated"),
                result.get("reason"),
                result.get("plan"),
            )
            return result
    except IntegrityError:
        logger.info(
            "stripe_webhook event_id=%s type=%s duplicate=true integrity",
            event_id,
            event_type,
        )
        return {"ok": True, "duplicate": True, "type": event_type, "reason": "duplicate"}
    except BillingError:
        logger.warning(
            "stripe_webhook event_id=%s type=%s failed_closed",
            event_id,
            event_type,
        )
        raise


def handle_webhook(payload: bytes, signature: str | None) -> dict[str, Any]:
    return process_webhook_event(construct_webhook_event(payload, signature))


def get_upgrade_options() -> list[dict[str, Any]]:
    settings = get_settings()
    prices = {
        "starter": settings.stripe_price_starter,
        "pro": settings.stripe_price_pro,
        "agency": settings.stripe_price_agency,
    }
    return [
        {
            "plan": plan,
            "name": PLANS[plan].name,
            "price": PLANS[plan].display_price,
            "price_id": prices[plan],
            "daily": PLANS[plan].daily_generations,
            "monthly": PLANS[plan].monthly_generations,
            "bulk": PLANS[plan].bulk_rows_per_job,
        }
        for plan in PAID_PLANS
    ]
