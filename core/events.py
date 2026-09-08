"""Privacy-conscious first-party product events.

Event rows intentionally contain no listing text, draft text, email address, or
arbitrary caller-supplied payload.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import session_scope
from .models import Listing, ProductMilestone, UsageEvent, User, UserSession, utcnow

PRODUCT_EVENTS = frozenset(
    {
        "signup_completed",
        "first_draft_generated",
        "generation_failed",
        "draft_edited_saved",
        "title_copied",
        "description_copied",
        "tags_copied",
        "export_completed",
        "bulk_sample_downloaded",
        "bulk_job_started",
        "bulk_job_completed",
        "pricing_viewed",
        "checkout_initiated",
        "first_output_used",
        "second_activity_session",
        "day_7_return",
        "first_paid_conversion",
        "test_paid_conversion",
    }
)


def _new_event(user_id: uuid.UUID, event_name: str) -> UsageEvent:
    if event_name not in PRODUCT_EVENTS:
        raise ValueError("Unknown product event.")
    now = utcnow()
    return UsageEvent(
        user_id=user_id,
        kind=event_name,
        status="completed",
        mode="product",
        provider="first_party",
        details_json={},
        created_at=now,
        completed_at=now,
    )


def record_product_event(
    user_id: uuid.UUID, event_name: str, *, session: Session | None = None
) -> None:
    event = _new_event(user_id, event_name)
    if session is not None:
        session.add(event)
        if event_name in {"title_copied", "description_copied", "tags_copied", "export_completed"}:
            record_product_event_once(user_id, "first_output_used", session=session)
        session.flush()
        return
    with session_scope() as own_session:
        record_product_event(user_id, event_name, session=own_session)


def record_product_event_once(
    user_id: uuid.UUID, event_name: str, *, session: Session | None = None
) -> bool:
    if event_name not in PRODUCT_EVENTS:
        raise ValueError("Unknown product event.")

    def record(working_session: Session) -> bool:
        # A database uniqueness constraint makes simultaneous first events safe.
        if working_session.get_bind().dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        statement = (
            insert(ProductMilestone)
            .values(user_id=user_id, kind=event_name, created_at=utcnow())
            .on_conflict_do_nothing(index_elements=["user_id", "kind"])
        )
        if working_session.execute(statement).rowcount == 0:
            return False
        working_session.add(_new_event(user_id, event_name))
        working_session.flush()
        return True

    if session is not None:
        return record(session)
    with session_scope() as own_session:
        return record(own_session)


def aggregate_product_events(
    session: Session, *, since: datetime | None = None, include_fixtures: bool = False
) -> dict[str, int]:
    statement = (
        select(UsageEvent.kind, func.count(UsageEvent.id))
        .join(User, User.id == UsageEvent.user_id)
        .where(
            UsageEvent.kind.in_(PRODUCT_EVENTS),
            UsageEvent.status == "completed",
        )
        .group_by(UsageEvent.kind)
    )
    if since is not None:
        statement = statement.where(UsageEvent.created_at >= since)
    if not include_fixtures:
        statement = statement.where(User.is_test_fixture.is_(False))
    counts = {event_name: 0 for event_name in PRODUCT_EVENTS}
    counts.update({str(name): int(count) for name, count in session.execute(statement)})
    return counts


def record_return_activity(user_id: uuid.UUID, *, session: Session, now: datetime) -> None:
    """Authenticated workspace activity after 30 idle minutes; day 7 is [7, 8) days."""
    previous = session.scalar(
        select(func.max(UserSession.last_seen_at)).where(UserSession.user_id == user_id)
    )
    if previous is not None:
        previous = previous.replace(tzinfo=UTC) if previous.tzinfo is None else previous
        if now - previous >= timedelta(minutes=30):
            record_product_event_once(user_id, "second_activity_session", session=session)
    first = session.get(ProductMilestone, (user_id, "first_draft_generated"))
    if first is not None and not first.is_backfilled:
        activated = first.created_at
        activated = activated.replace(tzinfo=UTC) if activated.tzinfo is None else activated
        if timedelta(days=7) <= now - activated < timedelta(days=8):
            record_product_event_once(user_id, "day_7_return", session=session)


def _copy_serializer():
    from itsdangerous import URLSafeTimedSerializer

    from .config import get_settings

    return URLSafeTimedSerializer(get_settings().session_secret, salt="sellerdrafts-copy-v1")


def copy_event_ticket(user_id: uuid.UUID, listing_id: str, event_name: str) -> str:
    """Issue a short-lived action capability without any product or draft content."""
    if event_name not in {"title_copied", "description_copied", "tags_copied"}:
        raise ValueError("Unknown copy action.")
    with session_scope() as session:
        listing = session.get(Listing, uuid.UUID(str(listing_id)))
        if listing is None or listing.user_id != user_id:
            raise ValueError("Draft unavailable.")
    return _copy_serializer().dumps([str(user_id), str(listing_id), event_name])


def record_copy_acknowledgment(user_id: uuid.UUID, event_name: str, ticket: str) -> bool:
    from itsdangerous import BadData

    try:
        payload = _copy_serializer().loads(ticket, max_age=3600)
        if not isinstance(payload, list) or len(payload) != 3:
            return False
        owner, listing_id, action = payload
        if owner != str(user_id) or action != event_name:
            return False
        with session_scope() as session:
            listing = session.get(Listing, uuid.UUID(listing_id))
            if listing is None or listing.user_id != user_id:
                return False
            record_product_event(user_id, event_name, session=session)
        return True
    except (BadData, ValueError, TypeError):
        return False


def record_export_action(user_id: uuid.UUID, listing_ids: list[str]) -> None:
    """Verify the bounded saved records behind a server download callback."""
    from .draft_review import draft_export_ready
    from .utils import revalidate_saved_draft

    if not listing_ids or len(listing_ids) > 500:
        return
    try:
        ids = {uuid.UUID(str(value)) for value in listing_ids}
    except (ValueError, TypeError, AttributeError):
        return
    with session_scope() as session:
        rows = session.scalars(
            select(Listing).where(Listing.user_id == user_id, Listing.id.in_(ids))
        ).all()
        if len(rows) != len(ids) or not all(
            draft_export_ready(revalidate_saved_draft(row.full_json)) for row in rows
        ):
            return
        record_product_event(user_id, "export_completed", session=session)
