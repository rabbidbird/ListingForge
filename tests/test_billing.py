from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.billing as billing
from core.billing import (
    BillingError,
    create_checkout_session,
    create_customer_portal_session,
    process_webhook_event,
)
from core.config import reset_settings_cache
from core.database import session_scope
from core.models import Subscription
from core.plans import subscription_must_use_portal
from core.usage import get_usage, reserve_generation


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
    event_type: str = "checkout.session.completed",
    include_user: bool = True,
    session_id: str = "cs_123",
):
    obj = {
        "id": session_id,
        "client_reference_id": str(user_id) if include_user else None,
        "metadata": {
            "user_id": str(user_id) if include_user else "not-a-uuid",
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
        "type": event_type,
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
    event_type: str | None = None,
    include_metadata: bool = True,
):
    obj = {
        "id": "sub_123",
        "customer": "cus_123",
        "status": status,
        "items": {"data": [{"price": {"id": price_id}}]},
    }
    if include_metadata:
        obj["metadata"] = {"user_id": str(user_id)}
    return {
        "id": event_id,
        "type": event_type
        or ("customer.subscription.deleted" if deleted else "customer.subscription.updated"),
        "created": created,
        "data": {"object": obj},
    }


def test_webhook_sets_plan_and_is_idempotent(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()

    first = process_webhook_event(_checkout_event(user.id))
    duplicate = process_webhook_event(_checkout_event(user.id))
    assert first["plan"] == "pro"
    assert first["status"] == "active"
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


def test_checkout_maps_metadata_price_when_line_items_absent(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    result = process_webhook_event(
        _checkout_event(user.id, price_id="price_agency", plan_metadata="starter")
    )
    assert result["plan"] == "agency"


def test_unpaid_checkout_does_not_grant_entitlement(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    result = process_webhook_event(_checkout_event(user.id, payment_status="unpaid"))
    assert result["updated"] is False
    assert result["reason"] == "checkout_not_paid"
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


def test_checkout_missing_user_fails_closed(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user_factory()
    with pytest.raises(BillingError, match="trusted entitlement"):
        process_webhook_event(_checkout_event("not-a-user", include_user=False))


def test_no_payment_required_checkout_is_trialing(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    result = process_webhook_event(
        _checkout_event(user.id, payment_status="no_payment_required", price_id="price_starter")
    )
    assert result["plan"] == "starter"
    assert result["status"] == "trialing"
    usage = get_usage(user.id)
    assert usage["plan"] == "starter"
    assert usage["status"] == "trialing"


def test_async_payment_succeeded_grants_entitlement(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    process_webhook_event(_checkout_event(user.id, event_id="evt_unpaid", payment_status="unpaid"))
    result = process_webhook_event(
        _checkout_event(
            user.id,
            event_id="evt_async",
            created=120,
            payment_status="paid",
            event_type="checkout.session.async_payment_succeeded",
        )
    )
    assert result["plan"] == "pro"
    assert get_usage(user.id)["plan"] == "pro"


def test_async_payment_failed_is_acknowledged_without_entitlement(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    result = process_webhook_event(
        {
            "id": "evt_async_fail",
            "type": "checkout.session.async_payment_failed",
            "created": 50,
            "data": {"object": {"id": "cs_123", "payment_status": "unpaid"}},
        }
    )
    assert result["ok"] is True
    assert result["updated"] is False
    assert result["reason"] == "async_payment_failed"
    assert get_usage(user.id)["plan"] == "free"


def test_invoice_payment_failed_is_deferred_to_subscription_event(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    process_webhook_event(_checkout_event(user.id, created=100, price_id="price_pro"))
    result = process_webhook_event(
        {
            "id": "evt_invoice_failed",
            "type": "invoice.payment_failed",
            "created": 140,
            "data": {"object": {"id": "in_123", "customer": "cus_123"}},
        }
    )
    assert result["reason"] == "invoice_payment_failed_deferred_to_subscription"
    assert get_usage(user.id)["plan"] == "pro"


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
    usage = get_usage(user.id)
    assert usage["plan"] == "free"
    assert usage["status"] == "past_due"
    assert usage["payment_failed"] is True
    assert usage["manage_in_portal"] is True


@pytest.mark.parametrize("status", ["unpaid", "incomplete", "paused", "canceled", "unknown"])
def test_inactive_subscription_statuses_fail_closed_to_free(user_factory, monkeypatch, status):
    _configure_prices(monkeypatch)
    user = user_factory()
    process_webhook_event(_checkout_event(user.id, created=100, price_id="price_pro"))
    result = process_webhook_event(
        _subscription_event(user.id, event_id=f"evt_{status}", created=150, status=status)
    )
    assert result["plan"] == "free"
    usage = get_usage(user.id)
    assert usage["plan"] == "free"
    assert usage["status"] == status


def test_unknown_price_on_active_subscription_fails_closed(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    process_webhook_event(_checkout_event(user.id, created=100, price_id="price_pro"))
    result = process_webhook_event(
        _subscription_event(
            user.id,
            event_id="evt_unknown_price",
            created=160,
            status="active",
            price_id="price_not_configured",
        )
    )
    assert result["plan"] == "free"
    assert get_usage(user.id)["plan"] == "free"


def test_subscription_created_maps_by_customer_without_metadata(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    process_webhook_event(_checkout_event(user.id, created=100, price_id="price_starter"))
    result = process_webhook_event(
        _subscription_event(
            user.id,
            event_id="evt_created",
            created=180,
            status="active",
            price_id="price_pro",
            event_type="customer.subscription.created",
            include_metadata=False,
        )
    )
    assert result["plan"] == "pro"
    assert get_usage(user.id)["plan"] == "pro"


def test_webhook_does_not_change_another_users_plan(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    owner = user_factory(email="owner-bill@example.com")
    stranger = user_factory(email="stranger-bill@example.com")
    process_webhook_event(_checkout_event(owner.id, price_id="price_pro"))
    assert get_usage(stranger.id)["plan"] == "free"
    assert get_usage(owner.id)["plan"] == "pro"


def _fake_stripe_client():
    checkout_calls: list[tuple[dict, dict]] = []

    def create_checkout(params, options):
        checkout_calls.append((params, options))
        number = len(checkout_calls)
        return SimpleNamespace(id=f"cs_fake_{number}", url=f"https://checkout.stripe.test/{number}")

    client = SimpleNamespace(
        v1=SimpleNamespace(
            checkout=SimpleNamespace(
                sessions=SimpleNamespace(create=create_checkout),
            ),
        )
    )
    return client, checkout_calls


def test_open_checkout_is_reused_instead_of_creating_a_second_subscription(
    user_factory, monkeypatch
):
    _configure_prices(monkeypatch)
    client, calls = _fake_stripe_client()
    monkeypatch.setattr(billing, "_stripe_client", lambda: client)
    user = user_factory()

    first = create_checkout_session(user.id, "pro")
    second = create_checkout_session(user.id, "pro")

    assert first == second == "https://checkout.stripe.test/1"
    assert len(calls) == 1
    params, options = calls[0]
    assert params["mode"] == "subscription"
    assert params["expires_at"] > 0
    assert "payment_method_types" not in params
    assert options["idempotency_key"].startswith(f"truedraft-checkout-{user.id}-")
    with session_scope() as session:
        subscription = session.query(Subscription).filter_by(user_id=user.id).one()
        assert subscription.pending_checkout_session_id == "cs_fake_1"
        assert subscription.pending_checkout_plan == "pro"


def test_open_checkout_blocks_switching_to_another_plan(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    client, calls = _fake_stripe_client()
    monkeypatch.setattr(billing, "_stripe_client", lambda: client)
    user = user_factory()

    create_checkout_session(user.id, "starter")
    with pytest.raises(BillingError, match="already open for another plan"):
        create_checkout_session(user.id, "pro")
    assert len(calls) == 1


def test_expired_checkout_webhook_releases_pending_session(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    client, calls = _fake_stripe_client()
    monkeypatch.setattr(billing, "_stripe_client", lambda: client)
    user = user_factory()

    create_checkout_session(user.id, "pro")
    result = process_webhook_event(
        _checkout_event(
            user.id,
            event_id="evt_expired",
            event_type="checkout.session.expired",
            payment_status="unpaid",
            session_id="cs_fake_1",
        )
    )
    second = create_checkout_session(user.id, "pro")

    assert result["checkout_released"] is True
    assert second == "https://checkout.stripe.test/2"
    assert len(calls) == 2


def test_customer_portal_uses_linked_customer_and_instance_client(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    portal_calls: list[dict] = []

    def create_portal(params):
        portal_calls.append(params)
        return SimpleNamespace(url="https://billing.stripe.test/session")

    client = SimpleNamespace(
        v1=SimpleNamespace(
            billing_portal=SimpleNamespace(
                sessions=SimpleNamespace(create=create_portal),
            )
        )
    )
    monkeypatch.setattr(billing, "_stripe_client", lambda: client)
    user = user_factory()
    with session_scope() as session:
        subscription = session.query(Subscription).filter_by(user_id=user.id).one()
        subscription.stripe_customer_id = "cus_linked"

    url = create_customer_portal_session(user.id)

    assert url == "https://billing.stripe.test/session"
    assert portal_calls == [
        {
            "customer": "cus_linked",
            "return_url": "http://localhost:8080/About_Pricing?portal=return",
        }
    ]


def test_unhandled_event_is_recorded_without_entitlement_change(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    user = user_factory()
    result = process_webhook_event(
        {
            "id": "evt_ping",
            "type": "ping",
            "created": 1,
            "data": {"object": {"id": "ok"}},
        }
    )
    assert result["ok"] is True
    assert result["updated"] is False
    assert result["reason"] == "unhandled_event_type"
    assert get_usage(user.id)["plan"] == "free"


def test_existing_incomplete_subscription_must_use_portal(user_factory, monkeypatch):
    _configure_prices(monkeypatch)
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_launch_check")
    reset_settings_cache()
    user = user_factory()
    with session_scope() as session:
        subscription = session.query(Subscription).filter_by(user_id=user.id).one()
        subscription.stripe_subscription_id = "sub_existing"
        subscription.stripe_customer_id = "cus_existing"
        subscription.status = "past_due"
        subscription.plan = "free"
    assert subscription_must_use_portal("past_due", "sub_existing") is True
    with pytest.raises(BillingError, match="billing portal"):
        create_checkout_session(user.id, "pro")


def test_canceled_subscription_does_not_require_portal():
    assert subscription_must_use_portal("canceled", "sub_old") is False
    assert subscription_must_use_portal("active", None) is False


def test_usage_layer_ignores_stale_paid_plan_when_status_is_past_due(user_factory):
    from datetime import timedelta

    from core.models import utcnow
    from core.usage import UsageLimitError, complete_generation

    user = user_factory(plan="pro")
    with session_scope() as session:
        subscription = session.query(Subscription).filter_by(user_id=user.id).one()
        subscription.status = "past_due"
        subscription.plan = "pro"
    usage = get_usage(user.id)
    assert usage["plan"] == "free"
    assert usage["stored_plan"] == "pro"
    assert usage["daily_limit"] == 8
    start = utcnow().replace(hour=3, minute=0, second=0, microsecond=0)
    for index in range(8):
        event_id, plan = reserve_generation(
            user.id,
            mode="single",
            provider="template",
            now=start + timedelta(seconds=61 * index),
        )
        assert plan == "free"
        complete_generation(event_id, user.id)
    with pytest.raises(UsageLimitError) as blocked:
        reserve_generation(
            user.id,
            mode="single",
            provider="template",
            now=start + timedelta(minutes=20),
        )
    assert blocked.value.code == "daily_limit"
