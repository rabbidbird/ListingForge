from __future__ import annotations

import pytest

from core.billing import BillingError, process_webhook_event
from core.config import reset_settings_cache
from core.database import session_scope
from core.models import Subscription


def _configure_prices(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_PRICE_STARTER", "price_starter")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro")
    monkeypatch.setenv("STRIPE_PRICE_AGENCY", "price_agency")
    reset_settings_cache()


def _checkout_event(
    user_id,
    *,
    event_id: str = "evt_checkout",
    created: int = 100,
    payment_status: str = "paid",
    price_id: str = "price_pro",
    line_item_price: str | None = None,
    plan_metadata: str = "agency",
):
    obj = {
        "client_reference_id": str(user_id),
        "metadata": {
            "user_id": str(user_id),
            "plan": plan_metadata,
            "price_id": price_id,
        },
        "payment_status": payment_status,
        "customer": "cus_123",
        "subscription": "sub_123",
    }
    if line_item_price is not None:
        obj["line_items"] = {"data": [{"price": {"id": line_item_price}}]}
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "created": created,
        "data": {"object": obj},
    }


def _subscription_event(
    user_id,
    *,
    event_id: str,
    created: int,
    status: str,
    deleted: bool = False,
    price_id: str = "price_pro",
):
    return {
        "id": event_id,
        "type": "customer.subscription.deleted" if deleted else "customer.subscription.updated",
        "created": created,
        "data": {
            "object": {
                "id": "sub_123",
                "customer": "cus_123",
                "status": status,
                "metadata": {"user_id": str(user_id)},
                "items": {"data": [{"price": {"id": price_id}}]},
            }
        },
    }


def test_webhook_sets_plan_and_is_idempotent(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()

    first = process_webhook_event(_checkout_event(user.id))
    duplicate = process_webhook_event(_checkout_event(user.id))
    assert first["plan"] == "pro"
    assert duplicate["duplicate"] is True
    with session_scope() as session:
        subscription = session.query(Subscription).filter_by(user_id=user.id).one()
        assert subscription.plan == "pro"
        assert subscription.stripe_subscription_id == "sub_123"

    result = process_webhook_event(
        _subscription_event(
            user.id, event_id="evt_deleted", created=101, status="canceled", deleted=True
        )
    )
    assert result["plan"] == "free"
    with session_scope() as session:
        assert session.query(Subscription).filter_by(user_id=user.id).one().plan == "free"


def test_checkout_ignores_metadata_plan_and_prefers_line_item_price(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    result = process_webhook_event(
        _checkout_event(
            user.id,
            price_id="price_pro",
            line_item_price="price_starter",
            plan_metadata="agency",
        )
    )
    assert result["plan"] == "starter"
    with session_scope() as session:
        assert session.query(Subscription).filter_by(user_id=user.id).one().plan == "starter"


def test_unpaid_checkout_does_not_grant_entitlement(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    result = process_webhook_event(_checkout_event(user.id, payment_status="unpaid"))
    assert result["updated"] is False
    with session_scope() as session:
        subscription = session.query(Subscription).filter_by(user_id=user.id).one()
        assert subscription.plan == "free"


def test_unknown_price_id_fails_closed(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    with pytest.raises(BillingError, match="trusted entitlement"):
        process_webhook_event(_checkout_event(user.id, price_id="price_unknown"))
    with session_scope() as session:
        assert session.query(Subscription).filter_by(user_id=user.id).one().plan == "free"


def test_older_webhook_cannot_overwrite_newer_entitlement(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    process_webhook_event(_checkout_event(user.id, created=200, price_id="price_pro"))
    older = process_webhook_event(
        _checkout_event(user.id, event_id="evt_older", created=50, price_id="price_starter")
    )
    assert older["updated"] is False
    with session_scope() as session:
        assert session.query(Subscription).filter_by(user_id=user.id).one().plan == "pro"


def test_past_due_subscription_fails_closed_to_free(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    process_webhook_event(_checkout_event(user.id, created=100, price_id="price_pro"))
    result = process_webhook_event(
        _subscription_event(user.id, event_id="evt_pastdue", created=150, status="past_due")
    )
    assert result["plan"] == "free"
    with session_scope() as session:
        subscription = session.query(Subscription).filter_by(user_id=user.id).one()
        assert subscription.plan == "free"
        assert subscription.status == "past_due"
