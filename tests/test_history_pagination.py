from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from core.database import session_scope
from core.events import record_export_action
from core.generator import ListingGenerator
from core.models import Listing, UsageEvent
from core.utils import (
    delete_listing,
    export_to_dataframe,
    get_full_history,
    get_history_page,
    get_listing_by_id,
    save_listing,
    update_listing,
)


def _result(number: int) -> dict:
    return ListingGenerator(use_llm=False).generate_full_listing(
        product_name=f"Saved product {number}",
        primary_keyword=f"keyword {number}",
        platform="etsy" if number % 2 else "shopify",
    )


def _save_at(user_id, number: int, created_at: datetime) -> str:
    listing_id = save_listing(user_id, _result(number))
    with session_scope() as session:
        session.execute(
            update(Listing).where(Listing.id == listing_id).values(created_at=created_at)
        )
    return str(listing_id)


def _all_pages(user_id, **filters) -> list[dict]:
    cursor = None
    rows: list[dict] = []
    while True:
        page = get_history_page(user_id, cursor=cursor, page_size=80, **filters)
        rows.extend(page["rows"])
        cursor = page["next_cursor"]
        if cursor is None:
            return rows


def test_keyset_history_retrieves_more_than_500_equal_timestamps_without_duplicates(user_factory):
    user = user_factory(email="many-history@example.com")
    same_time = datetime(2026, 9, 8, tzinfo=UTC)
    expected_ids = {_save_at(user.id, number, same_time) for number in range(501)}

    rows = _all_pages(user.id)

    assert len(rows) == 501
    assert {row["id"] for row in rows} == expected_ids
    assert len({row["id"] for row in rows}) == 501
    assert [(row["created_at"], row["id"]) for row in rows] == sorted(
        [(row["created_at"], row["id"]) for row in rows], reverse=True
    )


def test_history_cursor_is_scoped_and_empty_pages_are_safe(user_factory):
    user = user_factory(email="empty-history@example.com")
    assert get_history_page(user.id) == {"rows": [], "next_cursor": None}

    timestamp = datetime(2026, 9, 8, tzinfo=UTC)
    _save_at(user.id, 1, timestamp)
    _save_at(user.id, 2, timestamp - timedelta(seconds=1))
    first = get_history_page(user.id, page_size=1, search="saved")
    assert first["next_cursor"]
    with pytest.raises(ValueError, match="search or filter"):
        get_history_page(user.id, cursor=first["next_cursor"], page_size=1, platform="etsy")

    last = get_history_page(user.id, cursor=first["next_cursor"], page_size=1, search="saved")
    assert len(last["rows"]) == 1
    assert last["next_cursor"] is None


def test_history_page_ignores_concurrent_newer_insert_and_other_users(user_factory):
    owner = user_factory(email="owner-history@example.com")
    stranger = user_factory(email="stranger-history@example.com")
    base = datetime(2026, 9, 8, tzinfo=UTC)
    original_ids = [
        _save_at(owner.id, number, base - timedelta(seconds=number)) for number in range(3)
    ]
    _save_at(stranger.id, 99, base + timedelta(days=1))

    first = get_history_page(owner.id, page_size=2)
    _save_at(owner.id, 100, base + timedelta(days=1))
    second = get_history_page(owner.id, cursor=first["next_cursor"], page_size=2)

    seen_ids = [row["id"] for row in first["rows"] + second["rows"]]
    assert set(seen_ids) == set(original_ids)
    assert len(seen_ids) == len(set(seen_ids))
    assert all(row["product_name"] != "Saved product 99" for row in first["rows"] + second["rows"])
    assert get_history_page(owner.id, page_size=1)["rows"][0]["product_name"] == "Saved product 100"


def test_history_search_and_platform_filter_preserve_old_records(user_factory):
    user = user_factory(email="filtered-history@example.com")
    base = datetime(2026, 9, 8, tzinfo=UTC)
    _save_at(user.id, 1, base)
    _save_at(user.id, 2, base - timedelta(days=365))
    _save_at(user.id, 3, base - timedelta(days=730))

    filtered = _all_pages(user.id, search="product", platform="etsy")

    assert [row["product_name"] for row in filtered] == ["Saved product 1", "Saved product 3"]


def test_old_record_remains_available_to_inspect_edit_export_and_delete(user_factory):
    user = user_factory(email="old-record-history@example.com")
    old_id = _save_at(user.id, 1, datetime(2022, 1, 1, tzinfo=UTC))
    original = get_listing_by_id(user.id, old_id)
    assert original is not None

    edited = _result(2)
    assert update_listing(user.id, old_id, edited) is True
    assert get_listing_by_id(user.id, old_id)["best_title"] == edited["best_title"]

    record_export_action(user.id, [old_id])
    with session_scope() as session:
        assert (
            session.query(UsageEvent).filter_by(user_id=user.id, kind="export_completed").count()
            == 1
        )

    assert delete_listing(user.id, old_id) is True
    assert get_listing_by_id(user.id, old_id) is None


def test_history_page_renders_an_old_record_for_normal_inspection(monkeypatch, user_factory):
    from streamlit.testing.v1 import AppTest

    import core.auth
    import core.ui

    user = user_factory(email="old-record-ui@example.com")
    _save_at(user.id, 1, datetime(2022, 1, 1, tzinfo=UTC))
    monkeypatch.setattr(core.auth, "require_streamlit_user", lambda: user)
    monkeypatch.setattr(core.auth, "streamlit_current_user", lambda: user)
    monkeypatch.setattr(core.ui, "render_sidebar", lambda _user=None: None)

    app = AppTest.from_file("pages/4_History.py").run(timeout=15)

    assert not app.exception
    assert len(app.selectbox) == 1


def test_legacy_stale_scores_are_rechecked_before_reading_or_exporting(user_factory):
    user = user_factory(email="stale-history@example.com")
    listing_id = _save_at(user.id, 1, datetime(2022, 1, 1, tzinfo=UTC))
    with session_scope() as session:
        listing = session.get(Listing, uuid.UUID(listing_id))
        stored = copy.deepcopy(listing.full_json)
        stored["tags"] = ["x" * 21]
        stored["scores"]["tags"]["status"] = "Pass"
        stored["scores"]["overall"]["status"] = "Pass"
        listing.full_json = stored

    inspected = get_listing_by_id(user.id, listing_id)
    reloaded = get_full_history(user.id)

    assert inspected["scores"]["tags"]["status"] == "Verify"
    assert inspected["scores"]["overall"]["status"] == "Verify"
    assert reloaded[0]["scores"]["overall"]["status"] == "Verify"
    assert export_to_dataframe([inspected]).iloc[0]["Checklist Status"] == "Verify"


def test_source_omission_review_survives_save_reload_and_export(user_factory):
    user = user_factory(email="omission-history@example.com")
    original = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Simple charm",
        features=["20 cm chain with 10 cm extension"],
        platform="etsy",
    )
    omission = next(
        note for note in original["review_notes"] if note.startswith("Tag phrase left out")
    )
    listing_id = save_listing(user.id, original)

    reloaded = get_listing_by_id(user.id, listing_id)
    exported = export_to_dataframe([reloaded]).iloc[0]

    assert omission in reloaded["review_notes"]
    assert reloaded["scores"]["overall"]["status"] == "Review"
    assert omission in exported["Review Notes"]
    assert exported["Checklist Status"] == "Review"
