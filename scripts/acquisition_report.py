"""Print aggregate signups, users with a draft, and currently active paid users."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import session_scope
from core.events import PRODUCT_EVENTS, aggregate_product_events
from core.models import Listing, Subscription, User
from core.plans import ACTIVE_SUBSCRIPTION_STATUSES, PAID_PLANS


def _since(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use an ISO date such as 2026-08-27") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def build_report(session: Session, *, since: datetime | None = None) -> list[dict[str, Any]]:
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
    return [dict(row._mapping) for row in session.execute(statement)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since", type=_since, help="Only include accounts created on/after ISO date"
    )
    args = parser.parse_args()
    with session_scope() as session:
        rows = build_report(session, since=args.since)
    print("source\tcampaign\tsignups\tusers_with_draft\tactive_paid")
    for row in rows:
        print(
            f"{row['source']}\t{row['campaign']}\t{row['signups']}\t"
            f"{row['users_with_draft']}\t{row['active_paid']}"
        )
    with session_scope() as session:
        event_counts = aggregate_product_events(session, since=args.since)
    print("\nproduct_event\tcount")
    for event_name in sorted(PRODUCT_EVENTS):
        print(f"{event_name}\t{event_counts[event_name]}")


if __name__ == "__main__":
    main()
