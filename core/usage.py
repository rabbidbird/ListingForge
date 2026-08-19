"""Transactional per-user entitlements, quotas, and generation rate limits."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from .database import session_scope
from .models import Subscription, UsageEvent, User, utcnow
from .plans import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    FAILED_PAYMENT_STATUSES,
    PLANS,
    get_plan_policy,
    subscription_must_use_portal,
)

FREE_DAILY_LIMIT = PLANS["free"].daily_generations
FREE_MONTHLY_LIMIT = PLANS["free"].monthly_generations


class UsageLimitError(RuntimeError):
    def __init__(self, message: str, code: str = "limit_reached") -> None:
        super().__init__(message)
        self.code = code


def _period_starts(now: datetime) -> tuple[datetime, datetime, datetime]:
    day_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    minute_start = now - timedelta(seconds=60)
    return day_start, month_start, minute_start


def _countable(now: datetime):
    return or_(
        UsageEvent.status == "completed",
        and_(UsageEvent.status == "reserved", UsageEvent.created_at >= now - timedelta(minutes=5)),
    )


def _subscription_for(session, user_id: uuid.UUID) -> Subscription | None:
    return session.scalar(select(Subscription).where(Subscription.user_id == user_id))


def _effective_plan(session, user_id: uuid.UUID) -> str:
    subscription = _subscription_for(session, user_id)
    if (
        subscription is not None
        and subscription.plan in PLANS
        and subscription.plan != "free"
        and subscription.status in ACTIVE_SUBSCRIPTION_STATUSES
    ):
        return subscription.plan
    return "free"


def reserve_generation(
    user_id: uuid.UUID, *, mode: str, provider: str, now: datetime | None = None
) -> tuple[uuid.UUID, str]:
    now = now or utcnow()
    day_start, month_start, minute_start = _period_starts(now)
    with session_scope() as session:
        user = session.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None or not user.is_active:
            raise UsageLimitError("Active account required.", "unauthorized")

        plan = _effective_plan(session, user_id)
        policy = get_plan_policy(plan)
        base = [
            UsageEvent.user_id == user_id,
            UsageEvent.kind == "generation",
            _countable(now),
        ]
        daily = (
            session.scalar(
                select(func.count())
                .select_from(UsageEvent)
                .where(*base, UsageEvent.created_at >= day_start)
            )
            or 0
        )
        monthly = (
            session.scalar(
                select(func.count())
                .select_from(UsageEvent)
                .where(*base, UsageEvent.created_at >= month_start)
            )
            or 0
        )
        recent = (
            session.scalar(
                select(func.count())
                .select_from(UsageEvent)
                .where(*base, UsageEvent.created_at >= minute_start)
            )
            or 0
        )

        if daily >= policy.daily_generations:
            raise UsageLimitError(
                f"{policy.name} daily limit reached ({policy.daily_generations}, UTC).",
                "daily_limit",
            )
        if monthly >= policy.monthly_generations:
            raise UsageLimitError(
                f"{policy.name} monthly limit reached ({policy.monthly_generations}, UTC).",
                "monthly_limit",
            )
        if recent >= policy.per_minute_generations:
            raise UsageLimitError(
                "Generation rate limit reached. Wait a minute and try again.", "rate_limit"
            )
        if provider == "llm":
            llm_daily = (
                session.scalar(
                    select(func.count())
                    .select_from(UsageEvent)
                    .where(
                        *base,
                        UsageEvent.created_at >= day_start,
                        UsageEvent.provider == "llm",
                    )
                )
                or 0
            )
            if llm_daily >= policy.daily_llm_generations:
                raise UsageLimitError(
                    f"{policy.name} daily LLM limit reached ({policy.daily_llm_generations}, UTC). "
                    "Use template mode or try tomorrow.",
                    "llm_daily_limit",
                )

        event = UsageEvent(user_id=user_id, mode=mode, provider=provider, created_at=now)
        session.add(event)
        session.flush()
        return event.id, plan


def complete_generation(
    event_id: uuid.UUID, listing_id: uuid.UUID, *, session: Session | None = None
) -> None:
    statement = (
        update(UsageEvent)
        .where(UsageEvent.id == event_id, UsageEvent.status == "reserved")
        .values(
            status="completed",
            completed_at=utcnow(),
            details_json={"listing_id": str(listing_id)},
        )
    )
    if session is not None:
        session.execute(statement)
        return
    with session_scope() as own_session:
        own_session.execute(statement)


def fail_generation(event_id: uuid.UUID, reason: str = "generation_failed") -> None:
    with session_scope() as session:
        session.execute(
            update(UsageEvent)
            .where(UsageEvent.id == event_id, UsageEvent.status == "reserved")
            .values(status="failed", completed_at=utcnow(), details_json={"reason": reason[:120]})
        )


def get_usage(user_id: uuid.UUID, *, now: datetime | None = None) -> dict[str, object]:
    now = now or utcnow()
    day_start, month_start, _ = _period_starts(now)
    with session_scope() as session:
        subscription = _subscription_for(session, user_id)
        plan = _effective_plan(session, user_id)
        policy = get_plan_policy(plan)
        status = subscription.status if subscription is not None else "free"
        stored_plan = subscription.plan if subscription is not None else "free"
        period_end = (
            subscription.current_period_end.isoformat()
            if subscription is not None and subscription.current_period_end is not None
            else None
        )
        base = [
            UsageEvent.user_id == user_id,
            UsageEvent.kind == "generation",
            _countable(now),
        ]
        daily = (
            session.scalar(
                select(func.count())
                .select_from(UsageEvent)
                .where(*base, UsageEvent.created_at >= day_start)
            )
            or 0
        )
        monthly = (
            session.scalar(
                select(func.count())
                .select_from(UsageEvent)
                .where(*base, UsageEvent.created_at >= month_start)
            )
            or 0
        )
        return {
            "plan": plan,
            "stored_plan": stored_plan,
            "status": status,
            "period_end": period_end,
            "daily": daily,
            "monthly": monthly,
            "daily_limit": policy.daily_generations,
            "monthly_limit": policy.monthly_generations,
            "daily_remaining": max(0, policy.daily_generations - daily),
            "monthly_remaining": max(0, policy.monthly_generations - monthly),
            "can_generate": daily < policy.daily_generations
            and monthly < policy.monthly_generations,
            "bulk_rows_per_job": policy.bulk_rows_per_job,
            "daily_llm_limit": policy.daily_llm_generations,
            "has_stripe_customer": bool(
                subscription is not None and subscription.stripe_customer_id
            ),
            "manage_in_portal": subscription_must_use_portal(
                status,
                subscription.stripe_subscription_id if subscription is not None else None,
            ),
            "payment_failed": status in FAILED_PAYMENT_STATUSES,
        }


def assert_bulk_job_allowed(user_id: uuid.UUID, row_count: int) -> str:
    if row_count < 1:
        raise UsageLimitError("The CSV has no rows to process.", "empty_bulk")
    with session_scope() as session:
        plan = _effective_plan(session, user_id)
    cap = get_plan_policy(plan).bulk_rows_per_job
    if row_count > cap:
        raise UsageLimitError(
            f"{get_plan_policy(plan).name} bulk jobs are capped at {cap} rows.", "bulk_cap"
        )
    return plan
