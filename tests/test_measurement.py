"""Content-free outcome measurement at trusted application boundaries."""

from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from fastapi.testclient import TestClient

from core.auth import create_user_session, get_user_by_session_token
from core.config import reset_settings_cache
from core.database import session_scope
from core.events import (
    aggregate_product_events,
    copy_event_ticket,
    record_copy_acknowledgment,
    record_export_action,
    record_product_event,
    record_product_event_once,
)
from core.generation_service import generate_for_user
from core.models import ProductMilestone, UsageEvent, User, UserSession, utcnow
from core.utils import delete_listing
from scripts.acquisition_report import build_measurement_report


def test_simultaneous_first_draft_event_is_unique(user_factory):
    user = user_factory()
    with ThreadPoolExecutor(max_workers=4) as pool:
        recorded = list(
            pool.map(
                lambda _: record_product_event_once(user.id, "first_draft_generated"), range(8)
            )
        )
    assert sum(recorded) == 1
    with session_scope() as session:
        assert session.query(ProductMilestone).filter_by(user_id=user.id).count() == 1
        assert session.query(UsageEvent).filter_by(kind="first_draft_generated").count() == 1


def test_output_action_requires_owned_saved_draft_and_measures_unique_user(user_factory):
    owner, other = user_factory(), user_factory()
    _, listing_id = generate_for_user(owner.id, {"product_name": "5 x 5 inch print"})
    ticket = copy_event_ticket(owner.id, str(listing_id), "title_copied")
    assert not record_copy_acknowledgment(other.id, "title_copied", ticket)
    assert not record_copy_acknowledgment(owner.id, "description_copied", ticket)
    assert not record_copy_acknowledgment(owner.id, "title_copied", ticket + "tampered")
    record_export_action(other.id, [str(listing_id)])
    assert record_copy_acknowledgment(owner.id, "title_copied", ticket)
    assert record_copy_acknowledgment(owner.id, "title_copied", ticket)
    record_export_action(owner.id, [str(listing_id)])
    with session_scope() as session:
        assert session.query(ProductMilestone).filter_by(kind="first_output_used").count() == 1
        assert all(
            row.details_json == {} for row in session.query(UsageEvent).filter_by(mode="product")
        )
    delete_listing(owner.id, listing_id)
    assert not record_copy_acknowledgment(owner.id, "title_copied", ticket)


def test_return_window_fixture_exclusion_and_recurring_errors(user_factory, monkeypatch):
    user = user_factory()
    fixture = user_factory()
    now = utcnow()
    with session_scope() as session:
        session.get(User, user.id).is_test_fixture = False
        token = create_user_session(session, user.id)
    generate_for_user(user.id, {"product_name": "Pendant"})
    generate_for_user(fixture.id, {"product_name": "Fixture pendant"})
    with session_scope() as session:
        assert get_user_by_session_token(session, token, touch=True) is not None
        assert session.get(ProductMilestone, (user.id, "second_activity_session")) is None
        session.query(UserSession).filter_by(user_id=user.id).one().last_seen_at = now - timedelta(
            minutes=31
        )
        session.get(ProductMilestone, (user.id, "first_draft_generated")).created_at = (
            now - timedelta(days=7, hours=1)
        )
    with session_scope() as session:
        assert get_user_by_session_token(session, token, touch=True) is not None
    for _ in range(2):
        record_product_event(user.id, "generation_failed")
    with session_scope() as session:
        report = build_measurement_report(session, now=now)
        assert report["signups"] == 1
        assert report["first_draft_generated"] == 1
        assert report["second_activity_session"] == 1
        assert report["day_7_eligible_users"] == 0
        assert report["day_7_returned_users"] == 0
        matured = build_measurement_report(session, now=now + timedelta(days=1))
        assert matured["day_7_eligible_users"] == matured["day_7_returned_users"] == 1
        assert report["users_with_recurring_generation_errors"] == 1
        assert aggregate_product_events(session)["first_draft_generated"] == 1
        assert (
            aggregate_product_events(session, include_fixtures=True)["first_draft_generated"] == 2
        )


def test_signed_payment_only_conversion_is_separate_from_test_and_trial(user_factory, monkeypatch):
    import core.web

    user = user_factory()
    secret = "whsec_local-measurement-fixture"
    monkeypatch.setenv("STRIPE_PRICE_STARTER", "price_fixture_starter")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", secret)
    reset_settings_cache()
    web = importlib.reload(core.web)
    timestamp = int(time.time())
    with TestClient(web.app) as client:
        for index, (live, status, amount) in enumerate(
            [
                (False, "paid", 1200),
                (True, "no_payment_required", 0),
                (True, "unpaid", 1200),
                (True, "paid", 1200),
                (True, "paid", 1200),
            ]
        ):
            payload = json.dumps(
                {
                    "id": f"evt_measure_{index}",
                    "object": "event",
                    "type": "checkout.session.completed",
                    "created": timestamp + index,
                    "livemode": live,
                    "data": {
                        "object": {
                            "id": f"cs_measure_{index}",
                            "client_reference_id": str(user.id),
                            "metadata": {"price_id": "price_fixture_starter"},
                            "payment_status": status,
                            "amount_total": amount,
                            "customer": "cus_fixture",
                            "subscription": "sub_fixture",
                        }
                    },
                }
            ).encode()
            digest = hmac.new(
                secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
            ).hexdigest()
            signature = f"t={timestamp},v1={digest}"
            assert (
                client.post(
                    "/webhooks/stripe", content=payload, headers={"stripe-signature": "invalid"}
                ).status_code
                == 400
            )
            assert (
                client.post(
                    "/webhooks/stripe", content=payload, headers={"stripe-signature": signature}
                ).status_code
                == 200
            )
            with session_scope() as session:
                expected = 0 if index < 3 else 1
                assert (
                    session.query(ProductMilestone).filter_by(kind="first_paid_conversion").count()
                    == expected
                )
        assert (
            client.post(
                "/webhooks/stripe", content=payload, headers={"stripe-signature": signature}
            ).status_code
            == 200
        )
    with session_scope() as session:
        assert session.query(ProductMilestone).filter_by(kind="test_paid_conversion").count() == 1
        assert session.query(ProductMilestone).filter_by(kind="first_paid_conversion").count() == 1
        # A signed live-mode fixture is still excluded from genuine customer counts.
        assert build_measurement_report(session)["first_paid_conversion"] == 0
