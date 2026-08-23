from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from core.generation_service import generate_for_user
from core.models import utcnow
from core.usage import (
    UsageLimitError,
    assert_bulk_job_allowed,
    complete_generation,
    fail_generation,
    get_usage,
    reserve_generation,
)
from core.utils import get_full_history


def _record_generations(user_id, count: int, *, start=None, provider: str = "template") -> None:
    start = start or utcnow().replace(hour=2, minute=0, second=0, microsecond=0)
    for index in range(count):
        event_id, _ = reserve_generation(
            user_id,
            mode="single",
            provider=provider,
            now=start + timedelta(seconds=61 * index),
        )
        complete_generation(event_id, uuid.uuid4())


def test_free_user_is_blocked_after_daily_limit(user_factory):
    user = user_factory()
    _record_generations(user.id, 8)
    with pytest.raises(UsageLimitError) as blocked:
        reserve_generation(
            user.id,
            mode="single",
            provider="template",
            now=utcnow().replace(hour=2, minute=20, second=0, microsecond=0),
        )
    assert blocked.value.code == "daily_limit"
    assert get_usage(user.id)["daily_limit"] == 8


def test_pro_user_is_not_bound_by_free_limit(user_factory):
    user = user_factory(plan="pro")
    _record_generations(user.id, 9)
    usage = get_usage(user.id)
    assert usage["plan"] == "pro"
    assert usage["daily"] == 9
    assert usage["daily_limit"] > 8
    assert usage["status"] == "active"
    assert usage["can_generate"] is True


def test_failed_generation_does_not_consume_quota(user_factory):
    user = user_factory()
    event_id, _ = reserve_generation(user.id, mode="single", provider="template")
    fail_generation(event_id)
    usage = get_usage(user.id)
    assert usage["daily"] == 0
    assert usage["can_generate"] is True


def test_generate_for_user_releases_quota_when_generation_raises(user_factory, monkeypatch):
    user = user_factory()

    def boom(self, **_kwargs):
        raise RuntimeError("generator exploded")

    monkeypatch.setattr(
        "core.generation_service.ListingGenerator.generate_full_listing",
        boom,
    )
    with pytest.raises(RuntimeError, match="generator exploded"):
        generate_for_user(
            user.id,
            {
                "product_name": "Plain Cup",
                "primary_keyword": "plain cup",
                "platform": "etsy",
                "force_template": True,
            },
        )
    usage = get_usage(user.id)
    assert usage["daily"] == 0
    assert usage["can_generate"] is True
    assert get_full_history(user.id) == []


def test_reserved_events_expire_from_quota_after_five_minutes(user_factory):
    user = user_factory()
    now = utcnow().replace(hour=4, minute=30, second=0, microsecond=0)
    reserve_generation(user.id, mode="single", provider="template", now=now - timedelta(minutes=6))
    usage = get_usage(user.id, now=now)
    assert usage["daily"] == 0
    reserve_generation(user.id, mode="single", provider="template", now=now - timedelta(minutes=1))
    usage = get_usage(user.id, now=now)
    assert usage["daily"] == 1


def test_free_monthly_limit_is_enforced_across_days(user_factory):
    user = user_factory()
    month_start = utcnow().replace(day=1, hour=3, minute=0, second=0, microsecond=0)
    for day in range(5):
        _record_generations(
            user.id,
            8,
            start=month_start + timedelta(days=day),
        )
    with pytest.raises(UsageLimitError) as blocked:
        reserve_generation(
            user.id,
            mode="single",
            provider="template",
            now=month_start + timedelta(days=5, minutes=10),
        )
    assert blocked.value.code == "monthly_limit"


def test_llm_daily_cap_is_independent_of_template_usage(user_factory):
    user = user_factory()
    _record_generations(user.id, 4, provider="llm")
    with pytest.raises(UsageLimitError) as blocked:
        reserve_generation(
            user.id,
            mode="single",
            provider="llm",
            now=utcnow().replace(hour=2, minute=20, second=0, microsecond=0),
        )
    assert blocked.value.code == "llm_daily_limit"
    event_id, _ = reserve_generation(
        user.id,
        mode="single",
        provider="template",
        now=utcnow().replace(hour=2, minute=21, second=0, microsecond=0),
    )
    complete_generation(event_id, uuid.uuid4())


def test_starter_rate_limit_is_enforced(user_factory):
    user = user_factory(plan="starter")
    now = utcnow().replace(hour=5, minute=10, second=0, microsecond=0)
    for _index in range(30):
        event_id, _ = reserve_generation(
            user.id,
            mode="single",
            provider="template",
            now=now - timedelta(seconds=10),
        )
        complete_generation(event_id, uuid.uuid4())
    with pytest.raises(UsageLimitError) as blocked:
        reserve_generation(user.id, mode="single", provider="template", now=now)
    assert blocked.value.code == "rate_limit"


def test_bulk_row_cap_follows_effective_plan(user_factory):
    free_user = user_factory()
    pro_user = user_factory(plan="pro", email="pro-bulk@example.com")
    with pytest.raises(UsageLimitError) as blocked:
        assert_bulk_job_allowed(free_user.id, 6)
    assert blocked.value.code == "bulk_cap"
    assert assert_bulk_job_allowed(pro_user.id, 6) == "pro"


def test_usage_counters_are_isolated_between_users(user_factory):
    alice = user_factory(email="alice-usage@example.com")
    bob = user_factory(email="bob-usage@example.com")
    _record_generations(alice.id, 8)
    assert get_usage(alice.id)["can_generate"] is False
    assert get_usage(bob.id)["daily"] == 0
    assert get_usage(bob.id)["can_generate"] is True
    event_id, _ = reserve_generation(bob.id, mode="single", provider="template")
    complete_generation(event_id, uuid.uuid4())
    assert get_usage(alice.id)["daily"] == 8
    assert get_usage(bob.id)["daily"] == 1
