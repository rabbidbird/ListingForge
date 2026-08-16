from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from core.models import utcnow
from core.usage import UsageLimitError, complete_generation, get_usage, reserve_generation


def _record_generations(user_id, count: int) -> None:
    start = utcnow().replace(hour=2, minute=0, second=0, microsecond=0)
    for index in range(count):
        event_id, _ = reserve_generation(
            user_id,
            mode="single",
            provider="template",
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
