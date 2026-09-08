"""User-scoped listing persistence, export, and input-cleaning helpers."""

from __future__ import annotations

import copy
import json
import math
import re
import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as BinasciiError
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from .database import session_scope
from .draft_review import recheck_edited_draft
from .models import Listing


def clean_optional_text(value: Any) -> str:
    """Turn null-like CSV values into empty text without leaking ``nan``."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "<na>", "none", "null"}:
        return ""
    return re.sub(r"\s+", " ", text)


def spreadsheet_safe_text(value: str) -> str:
    """Prevent user-supplied CSV cells from being interpreted as formulas."""

    text = str(value)
    stripped = text.lstrip()
    if text.startswith(("\t", "\r")) or (stripped and stripped[0] in "=+-@"):
        return "'" + text
    return text


def _new_listing(user_id: uuid.UUID, result: dict[str, Any]) -> Listing:
    overall = result["scores"]["overall"]
    return Listing(
        user_id=user_id,
        product_name=clean_optional_text(result["meta"]["product_name"]),
        primary_keyword=clean_optional_text(result["meta"]["primary_keyword"]),
        platform=clean_optional_text(result["platform"]),
        category=clean_optional_text(result["meta"]["category"]),
        best_title=clean_optional_text(result["best_title"]),
        description=str(result["description"]),
        tags_json=[clean_optional_text(tag) for tag in result["tags"]],
        overall_score=float(overall["overall"]),
        grade=str(overall["grade"]),
        full_json=result,
    )


def save_listing(
    user_id: uuid.UUID, result: dict[str, Any], *, session: Session | None = None
) -> uuid.UUID:
    """Save a listing for exactly one user."""
    if session is not None:
        listing = _new_listing(user_id, result)
        session.add(listing)
        session.flush()
        return listing.id
    with session_scope() as own_session:
        listing = _new_listing(user_id, result)
        own_session.add(listing)
        own_session.flush()
        return listing.id


HISTORY_PAGE_SIZE = 50
HISTORY_MAX_PAGE_SIZE = 100
_SOURCE_OMISSION_PREFIXES = (
    "Optional title phrase left out intact because ",
    "Tag phrase left out intact because ",
    "The supplied product phrase does not fit the platform title limit; ",
)


def _source_omission_notes(result: dict[str, Any]) -> list[str]:
    """Keep current generator omission notices while recalculating checklist state."""
    return [
        note
        for note in result.get("review_notes") or []
        if isinstance(note, str) and note.startswith(_SOURCE_OMISSION_PREFIXES)
    ]


def revalidate_saved_draft(result: dict[str, Any]) -> dict[str, Any]:
    """Rebuild saved checklist state in memory without altering the stored draft.

    Older rows can contain scores produced before a platform validator changed.
    Rechecking from their saved source facts makes read, export, and callback
    decisions use the same review path as an edited draft while preserving any
    saved warning and explicit verification decision.
    """
    stored = copy.deepcopy(result)
    omission_notes = _source_omission_notes(stored)
    title = str(stored.get("best_title") or "")
    description = str(stored.get("description") or "")
    tags = [str(tag) for tag in list(stored.get("tags") or [])]
    previous_review = stored.get("edit_review")
    previous_review = previous_review if isinstance(previous_review, dict) else {}
    previous_warnings = [
        warning
        for warning in list(previous_review.get("warnings") or [])
        if isinstance(warning, dict)
    ]
    explicitly_verified = bool(previous_review.get("explicitly_verified"))

    rechecked = recheck_edited_draft(
        stored,
        title=title,
        description=description,
        tags=tags,
        explicitly_verified=explicitly_verified,
    )
    review = rechecked.get("edit_review")
    assert isinstance(review, dict)
    current_warnings = [
        warning for warning in list(review.get("warnings") or []) if isinstance(warning, dict)
    ]
    seen = {json.dumps(warning, sort_keys=True, default=str) for warning in current_warnings}
    preserved_warnings = [
        warning
        for warning in previous_warnings
        if json.dumps(warning, sort_keys=True, default=str) not in seen
    ]
    warnings = [*current_warnings, *preserved_warnings]
    review["warnings"] = warnings
    review["explicitly_verified"] = explicitly_verified
    # A saved unverified warning remains a block until the owner verifies it.
    review["export_ready"] = bool(
        review.get("export_ready")
        and (not previous_warnings or explicitly_verified)
        and (previous_review.get("export_ready", True) or explicitly_verified)
    )
    if warnings and not explicitly_verified:
        rechecked["scores"]["overall"]["status"] = "Verify"
    elif omission_notes and rechecked["scores"]["overall"].get("status") == "Pass":
        # A whole supplied phrase was deliberately omitted, so it still needs review.
        rechecked["scores"]["overall"]["status"] = "Review"
    rechecked["review_notes"] = [
        *list(rechecked.get("review_notes") or []),
        *(warning.get("message", "") for warning in preserved_warnings),
        *omission_notes,
    ]
    rechecked["review_notes"] = list(dict.fromkeys(rechecked["review_notes"]))
    return rechecked


def _history_row(row: Listing) -> dict[str, Any]:
    result = revalidate_saved_draft(row.full_json)
    return {
        "id": str(row.id),
        "created_at": row.created_at.isoformat(),
        "product_name": row.product_name,
        "primary_keyword": row.primary_keyword,
        "platform": row.platform,
        "category": row.category,
        "best_title": row.best_title,
        "overall_score": row.overall_score,
        "grade": row.grade,
        "status": (
            result.get("scores", {}).get("overall", {}).get("status")
            if isinstance(result, dict)
            else None
        ),
    }


def _normalized_history_scope(search: str | None, platform: str | None) -> dict[str, str]:
    return {
        "search": clean_optional_text(search).casefold(),
        "platform": clean_optional_text(platform).casefold(),
    }


def _encode_history_cursor(
    *, created_at: datetime, listing_id: uuid.UUID, scope: dict[str, str]
) -> str:
    payload = {
        "v": 1,
        "created_at": created_at.isoformat(),
        "id": str(listing_id),
        "scope": scope,
    }
    return urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def _decode_history_cursor(
    cursor: str | None, scope: dict[str, str]
) -> tuple[datetime, uuid.UUID] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(urlsafe_b64decode(padded.encode()).decode())
        created_at = datetime.fromisoformat(payload["created_at"])
        listing_id = uuid.UUID(payload["id"])
    except (BinasciiError, KeyError, TypeError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Invalid history cursor.") from exc
    if payload.get("v") != 1 or payload.get("scope") != scope:
        raise ValueError("History cursor does not match the active search or filter.")
    return created_at, listing_id


def get_history_page(
    user_id: uuid.UUID,
    *,
    cursor: str | None = None,
    page_size: int = HISTORY_PAGE_SIZE,
    search: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    """Return one user-owned, keyset-paginated history page.

    A cursor is bound to its search and platform scope so a cursor from another
    filter cannot accidentally skip or expose records.  Fetching one extra row
    establishes whether a following page exists without counting all history.
    """
    page_size = max(1, min(int(page_size), HISTORY_MAX_PAGE_SIZE))
    scope = _normalized_history_scope(search, platform)
    position = _decode_history_cursor(cursor, scope)
    query = select(Listing).where(Listing.user_id == user_id)

    if scope["search"]:
        pattern = f"%{scope['search']}%"
        query = query.where(
            or_(
                func.lower(Listing.product_name).like(pattern),
                func.lower(Listing.primary_keyword).like(pattern),
                func.lower(Listing.platform).like(pattern),
                func.lower(Listing.category).like(pattern),
                func.lower(Listing.best_title).like(pattern),
            )
        )
    if scope["platform"]:
        query = query.where(func.lower(Listing.platform) == scope["platform"])
    if position is not None:
        created_at, listing_id = position
        query = query.where(
            or_(
                Listing.created_at < created_at,
                and_(Listing.created_at == created_at, Listing.id < listing_id),
            )
        )

    with session_scope() as session:
        rows = session.scalars(
            query.order_by(Listing.created_at.desc(), Listing.id.desc()).limit(page_size + 1)
        ).all()
    page_rows = rows[:page_size]
    next_cursor = (
        _encode_history_cursor(
            created_at=page_rows[-1].created_at,
            listing_id=page_rows[-1].id,
            scope=scope,
        )
        if len(rows) > page_size and page_rows
        else None
    )
    return {"rows": [_history_row(row) for row in page_rows], "next_cursor": next_cursor}


def get_history(user_id: uuid.UUID, limit: int = 50) -> list[dict[str, Any]]:
    """Compatibility helper for the first bounded history page."""
    limit = max(1, min(int(limit), 500))
    return get_history_page(user_id, page_size=limit)["rows"]


def get_listings_by_ids(
    user_id: uuid.UUID, listing_ids: list[str | uuid.UUID]
) -> dict[str, dict[str, Any]]:
    """Return at most one page of owned drafts keyed by their stable record IDs."""
    parsed_ids = [parsed for value in listing_ids if (parsed := _parse_listing_id(value))]
    if not parsed_ids:
        return {}
    parsed_ids = parsed_ids[:HISTORY_MAX_PAGE_SIZE]
    with session_scope() as session:
        rows = session.scalars(
            select(Listing).where(Listing.user_id == user_id, Listing.id.in_(parsed_ids))
        ).all()
    records = {row.id: revalidate_saved_draft(row.full_json) for row in rows}
    return {
        str(listing_id): records[listing_id] for listing_id in parsed_ids if listing_id in records
    }


def get_full_history(user_id: uuid.UUID, limit: int = 500) -> list[dict[str, Any]]:
    """Retrieve authorized full records in one bounded query for export."""
    limit = max(1, min(int(limit), 500))
    with session_scope() as session:
        return [
            revalidate_saved_draft(result)
            for result in session.scalars(
                select(Listing.full_json)
                .where(Listing.user_id == user_id)
                .order_by(Listing.created_at.desc())
                .limit(limit)
            ).all()
        ]


def _parse_listing_id(listing_id: str | uuid.UUID) -> uuid.UUID | None:
    if isinstance(listing_id, uuid.UUID):
        return listing_id
    try:
        return uuid.UUID(str(listing_id))
    except (ValueError, TypeError):
        return None


def get_listing_by_id(user_id: uuid.UUID, listing_id: str | uuid.UUID) -> dict[str, Any] | None:
    parsed = _parse_listing_id(listing_id)
    if parsed is None:
        return None
    with session_scope() as session:
        row = session.scalar(
            select(Listing).where(Listing.id == parsed, Listing.user_id == user_id)
        )
        return revalidate_saved_draft(row.full_json) if row is not None else None


def update_listing(
    user_id: uuid.UUID,
    listing_id: str | uuid.UUID,
    result: dict[str, Any],
    *,
    session: Session | None = None,
) -> bool:
    """Authorized update helper; never updates a row owned by another user."""
    parsed = _parse_listing_id(listing_id)
    if parsed is None:
        return False
    values = _new_listing(user_id, result)

    def execute(working_session: Session) -> bool:
        changed = working_session.execute(
            update(Listing)
            .where(Listing.id == parsed, Listing.user_id == user_id)
            .values(
                product_name=values.product_name,
                primary_keyword=values.primary_keyword,
                platform=values.platform,
                category=values.category,
                best_title=values.best_title,
                description=values.description,
                tags_json=values.tags_json,
                overall_score=values.overall_score,
                grade=values.grade,
                full_json=values.full_json,
            )
        )
        return bool(changed.rowcount)

    if session is not None:
        return execute(session)
    with session_scope() as own_session:
        return execute(own_session)


def delete_listing(user_id: uuid.UUID, listing_id: str | uuid.UUID) -> bool:
    parsed = _parse_listing_id(listing_id)
    if parsed is None:
        return False
    with session_scope() as session:
        result = session.execute(
            delete(Listing).where(Listing.id == parsed, Listing.user_id == user_id)
        )
        return bool(result.rowcount)


def export_to_dataframe(results: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for stored_result in results:
        result = revalidate_saved_draft(stored_result)
        row: dict[str, Any] = {
            "Product Name": clean_optional_text(result["meta"]["product_name"]),
            "Primary Keyword": clean_optional_text(result["meta"]["primary_keyword"]),
            "Platform": clean_optional_text(result["platform"]),
            "Best Title": clean_optional_text(result["best_title"]),
            "Title Drafts": " | ".join(clean_optional_text(title) for title in result["titles"]),
            "Description": str(result["description"]),
            "Tags": ", ".join(clean_optional_text(tag) for tag in result["tags"]),
            "Checklist Status": result["scores"]["overall"]["status"],
            "Title Status": result["scores"]["title"]["status"],
            "Description Status": result["scores"]["description"]["status"],
            "Tags Status": result["scores"]["tags"]["status"],
            "Review Notes": " | ".join(result.get("review_notes") or []),
            "Missing Fact Prompts": " | ".join(result.get("missing_fact_prompts") or []),
            "Draft Disclaimer": result["disclaimer"],
        }
        rows.append(
            {
                key: spreadsheet_safe_text(value) if isinstance(value, str) else value
                for key, value in row.items()
            }
        )
    return pd.DataFrame(rows)


def clean_keyword(text: str) -> str:
    text = clean_optional_text(text).lower()
    text = re.sub(r"[^\w\s\-]", "", text)
    return re.sub(r"\s+", " ", text).strip()
