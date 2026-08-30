"""Privacy-conscious first-party product events.

Event rows intentionally contain no listing text, draft text, email address, or
arbitrary caller-supplied payload.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import session_scope
from .models import UsageEvent, utcnow

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
        session.flush()
        return
    with session_scope() as own_session:
        own_session.add(event)


def record_product_event_once(
    user_id: uuid.UUID, event_name: str, *, session: Session | None = None
) -> bool:
    if event_name not in PRODUCT_EVENTS:
        raise ValueError("Unknown product event.")

    def record(working_session: Session) -> bool:
        exists = working_session.scalar(
            select(UsageEvent.id).where(
                UsageEvent.user_id == user_id,
                UsageEvent.kind == event_name,
                UsageEvent.status == "completed",
            )
        )
        if exists is not None:
            return False
        working_session.add(_new_event(user_id, event_name))
        working_session.flush()
        return True

    if session is not None:
        return record(session)
    with session_scope() as own_session:
        return record(own_session)


def aggregate_product_events(session: Session, *, since: datetime | None = None) -> dict[str, int]:
    statement = (
        select(UsageEvent.kind, func.count(UsageEvent.id))
        .where(
            UsageEvent.kind.in_(PRODUCT_EVENTS),
            UsageEvent.status == "completed",
        )
        .group_by(UsageEvent.kind)
    )
    if since is not None:
        statement = statement.where(UsageEvent.created_at >= since)
    counts = {event_name: 0 for event_name in PRODUCT_EVENTS}
    counts.update({str(name): int(count) for name, count in session.execute(statement)})
    return counts
