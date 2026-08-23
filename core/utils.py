"""User-scoped listing persistence, export, and input-cleaning helpers."""

from __future__ import annotations

import math
import re
import uuid
from typing import Any

import pandas as pd
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .database import session_scope
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


def get_history(user_id: uuid.UUID, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    with session_scope() as session:
        rows = session.scalars(
            select(Listing)
            .where(Listing.user_id == user_id)
            .order_by(Listing.created_at.desc())
            .limit(limit)
        ).all()
        return [
            {
                "id": str(row.id),
                "created_at": row.created_at.isoformat(),
                "product_name": row.product_name,
                "primary_keyword": row.primary_keyword,
                "platform": row.platform,
                "category": row.category,
                "best_title": row.best_title,
                "overall_score": row.overall_score,
                "grade": row.grade,
            }
            for row in rows
        ]


def get_full_history(user_id: uuid.UUID, limit: int = 500) -> list[dict[str, Any]]:
    """Retrieve authorized full records in one bounded query for export."""
    limit = max(1, min(int(limit), 500))
    with session_scope() as session:
        return list(
            session.scalars(
                select(Listing.full_json)
                .where(Listing.user_id == user_id)
                .order_by(Listing.created_at.desc())
                .limit(limit)
            ).all()
        )


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
        return row.full_json if row is not None else None


def update_listing(user_id: uuid.UUID, listing_id: str | uuid.UUID, result: dict[str, Any]) -> bool:
    """Authorized update helper; never updates a row owned by another user."""
    parsed = _parse_listing_id(listing_id)
    if parsed is None:
        return False
    values = _new_listing(user_id, result)
    with session_scope() as session:
        changed = session.execute(
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
    for result in results:
        row: dict[str, Any] = {
            "Product Name": clean_optional_text(result["meta"]["product_name"]),
            "Primary Keyword": clean_optional_text(result["meta"]["primary_keyword"]),
            "Platform": clean_optional_text(result["platform"]),
            "Best Title": clean_optional_text(result["best_title"]),
            "Title Options": " | ".join(clean_optional_text(title) for title in result["titles"]),
            "Description": str(result["description"]),
            "Tags": ", ".join(clean_optional_text(tag) for tag in result["tags"]),
            "Overall Score": result["scores"]["overall"]["overall"],
            "Grade": result["scores"]["overall"]["grade"],
            "Title Score": result["scores"]["title"]["score"],
            "Description Score": result["scores"]["description"]["score"],
            "Tags Score": result["scores"]["tags"]["score"],
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
