"""Print aggregate signups, users with a draft, and currently active paid users."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import session_scope
from core.events import PRODUCT_EVENTS, aggregate_product_events
from core.models import Listing, ProductMilestone, Subscription, UsageEvent, User, utcnow
from core.plans import ACTIVE_SUBSCRIPTION_STATUSES, PAID_PLANS


def _since(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use an ISO date such as 2026-08-27") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def build_report(
    session: Session, *, since: datetime | None = None, include_fixtures: bool = False
) -> list[dict[str, Any]]:
    activated = select(Listing.user_id).distinct().subquery()
    paid = (
        select(Subscription.user_id)
        .where(
            Subscription.plan.in_(PAID_PLANS),
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
        )
        .distinct()
        .subquery()
    )
    source = func.coalesce(User.acquisition_source, "direct")
    campaign = func.coalesce(User.acquisition_campaign, "unattributed")
    statement = (
        select(
            source.label("source"),
            campaign.label("campaign"),
            func.count(User.id).label("signups"),
            func.count(activated.c.user_id).label("users_with_draft"),
            func.count(paid.c.user_id).label("active_paid"),
        )
        .outerjoin(activated, activated.c.user_id == User.id)
        .outerjoin(paid, paid.c.user_id == User.id)
        .group_by(source, campaign)
        .order_by(func.count(User.id).desc(), source, campaign)
    )
    if since is not None:
        statement = statement.where(User.created_at >= since)
    if not include_fixtures:
        statement = statement.where(User.is_test_fixture.is_(False))
    return [dict(row._mapping) for row in session.execute(statement)]


def build_measurement_report(
    session: Session,
    *,
    since: datetime | None = None,
    now: datetime | None = None,
    include_fixtures: bool = False,
) -> dict[str, int]:
    """Unique account outcomes for the signup cohort; no content or identifiers."""
    now = now or utcnow()
    cohort = []
    if since is not None:
        cohort.append(User.created_at >= since)
    if not include_fixtures:
        cohort.append(User.is_test_fixture.is_(False))
    report = {"signups": int(session.scalar(select(func.count(User.id)).where(*cohort)) or 0)}
    for kind in (
        "first_draft_generated",
        "first_output_used",
        "second_activity_session",
        "first_paid_conversion",
    ):
        report[kind] = int(
            session.scalar(
                select(func.count())
                .select_from(ProductMilestone)
                .join(User, User.id == ProductMilestone.user_id)
                .where(ProductMilestone.kind == kind, *cohort)
            )
            or 0
        )
    # Only cohorts with a completed observation window belong in the D7 denominator.
    eligible = (
        select(ProductMilestone.user_id)
        .where(
            ProductMilestone.kind == "first_draft_generated",
            ProductMilestone.created_at <= now - timedelta(days=8),
            ProductMilestone.is_backfilled.is_(False),
        )
        .subquery()
    )
    report["day_7_eligible_users"] = int(
        session.scalar(
            select(func.count())
            .select_from(eligible)
            .join(User, User.id == eligible.c.user_id)
            .where(*cohort)
        )
        or 0
    )
    report["day_7_returned_users"] = int(
        session.scalar(
            select(func.count())
            .select_from(ProductMilestone)
            .join(eligible, eligible.c.user_id == ProductMilestone.user_id)
            .join(User, User.id == ProductMilestone.user_id)
            .where(ProductMilestone.kind == "day_7_return", *cohort)
        )
        or 0
    )
    errors = select(UsageEvent.user_id, func.count().label("errors")).where(
        UsageEvent.kind == "generation_failed", UsageEvent.status == "completed"
    )
    if since is not None:
        errors = errors.where(UsageEvent.created_at >= since)
    errors = errors.group_by(UsageEvent.user_id).subquery()
    report["users_with_generation_errors"] = int(
        session.scalar(
            select(func.count())
            .select_from(errors)
            .join(User, User.id == errors.c.user_id)
            .where(*cohort)
        )
        or 0
    )
    report["users_with_recurring_generation_errors"] = int(
        session.scalar(
            select(func.count())
            .select_from(errors)
            .join(User, User.id == errors.c.user_id)
            .where(errors.c.errors >= 2, *cohort)
        )
        or 0
    )
    unclassified = select(func.count(User.id)).where(User.is_test_fixture.is_(None))
    if since is not None:
        unclassified = unclassified.where(User.created_at >= since)
    report["unclassified_accounts_excluded"] = int(session.scalar(unclassified) or 0)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since", type=_since, help="Only include accounts created on/after ISO date"
    )
    parser.add_argument(
        "--include-fixtures",
        action="store_true",
        help="Include explicitly marked test accounts (diagnostic only)",
    )
    args = parser.parse_args()
    with session_scope() as session:
        rows = build_report(session, since=args.since, include_fixtures=args.include_fixtures)
    print("source\tcampaign\tsignups\tusers_with_draft\tactive_paid")
    for row in rows:
        print(
            f"{row['source']}\t{row['campaign']}\t{row['signups']}\t"
            f"{row['users_with_draft']}\t{row['active_paid']}"
        )
    with session_scope() as session:
        event_counts = aggregate_product_events(
            session, since=args.since, include_fixtures=args.include_fixtures
        )
        measures = build_measurement_report(
            session, since=args.since, include_fixtures=args.include_fixtures
        )
    print("\nunique_account_measure\tcount")
    for name, count in measures.items():
        print(f"{name}\t{count}")
    print("\nproduct_event\tcount")
    for event_name in sorted(PRODUCT_EVENTS):
        print(f"{event_name}\t{event_counts[event_name]}")


if __name__ == "__main__":
    main()
