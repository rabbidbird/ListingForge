from __future__ import annotations

from core.billing import process_webhook_event
from core.config import reset_settings_cache
from core.database import session_scope
from core.models import Subscription


def _checkout_event(user_id, *, event_id: str = "evt_checkout", created: int = 100):
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "created": created,
        "data": {
            "object": {
                "client_reference_id": str(user_id),
                "metadata": {
                    "user_id": str(user_id),
                    "plan": "pro",
                    "price_id": "price_pro",
                },
                "payment_status": "paid",
                "customer": "cus_123",
                "subscription": "sub_123",
            }
        },
    }


def test_webhook_sets_plan_and_is_idempotent(user_factory, monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_STARTER", "price_starter")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro")
    monkeypatch.setenv("STRIPE_PRICE_AGENCY", "price_agency")
    reset_settings_cache()
    user = user_factory()

    first = process_webhook_event(_checkout_event(user.id))
    duplicate = process_webhook_event(_checkout_event(user.id))
    assert first["plan"] == "pro"
    assert duplicate["duplicate"] is True
    with session_scope() as session:
        subscription = session.query(Subscription).filter_by(user_id=user.id).one()
        assert subscription.plan == "pro"
        assert subscription.stripe_subscription_id == "sub_123"

    deleted = {
        "id": "evt_deleted",
        "type": "customer.subscription.deleted",
        "created": 101,
        "data": {
            "object": {
                "id": "sub_123",
                "customer": "cus_123",
                "status": "canceled",
                "metadata": {"user_id": str(user.id)},
                "items": {"data": [{"price": {"id": "price_pro"}}]},
            }
        },
    }
    result = process_webhook_event(deleted)
    assert result["plan"] == "free"
    with session_scope() as session:
        assert session.query(Subscription).filter_by(user_id=user.id).one().plan == "free"
