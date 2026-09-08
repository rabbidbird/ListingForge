from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from core.config import PROJECT_ROOT, reset_settings_cache
from core.database import reset_engine, session_scope
from core.models import Listing, ProductMilestone, UsageEvent, User
from scripts.acquisition_report import build_measurement_report
from scripts.classify_measurement_account import classify_account


def test_measurement_migration_preserves_0004_data_and_excludes_backfilled_d7(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "populated-0004.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("DATABASE_URL", database_url)
    reset_settings_cache()
    reset_engine()
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "20260827_0004")

    user_id = uuid.uuid4()
    listing_id = uuid.uuid4()
    first_draft_at = datetime(2025, 1, 1, tzinfo=UTC)
    second_draft_at = first_draft_at + timedelta(minutes=5)
    result = {
        "meta": {"product_name": "Historical mug", "primary_keyword": "mug", "category": "default"},
        "platform": "etsy",
        "best_title": "Historical mug",
        "description": "Historical draft",
        "tags": ["mug"],
        "scores": {"overall": {"overall": 90, "grade": "A", "status": "Pass"}},
    }
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (
                    id, email, name, password_hash, is_active, email_verified_at,
                    terms_accepted_at, terms_version, created_at, updated_at
                ) VALUES (
                    :id, :email, :name, :password_hash, :is_active, :verified_at,
                    :terms_at, :terms_version, :created_at, :updated_at
                )
                """
            ),
            {
                "id": user_id.hex,
                "email": "historical@example.com",
                "name": "Historical User",
                "password_hash": "historical-password-hash",
                "is_active": True,
                "verified_at": first_draft_at,
                "terms_at": first_draft_at,
                "terms_version": "2026-08-15",
                "created_at": first_draft_at,
                "updated_at": first_draft_at,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO listings (
                    id, user_id, product_name, primary_keyword, platform, category,
                    best_title, description, tags_json, overall_score, grade, full_json,
                    created_at, updated_at
                ) VALUES (
                    :id, :user_id, :product_name, :primary_keyword, :platform, :category,
                    :best_title, :description, :tags_json, :overall_score, :grade, :full_json,
                    :created_at, :updated_at
                )
                """
            ),
            {
                "id": listing_id.hex,
                "user_id": user_id.hex,
                "product_name": "Historical mug",
                "primary_keyword": "mug",
                "platform": "etsy",
                "category": "default",
                "best_title": "Historical mug",
                "description": "Historical draft",
                "tags_json": json.dumps(["mug"]),
                "overall_score": 90.0,
                "grade": "A",
                "full_json": json.dumps(result),
                "created_at": first_draft_at,
                "updated_at": first_draft_at,
            },
        )
        for event_id, created_at in (
            (uuid.uuid4(), first_draft_at),
            (uuid.uuid4(), second_draft_at),
        ):
            connection.execute(
                text(
                    """
                    INSERT INTO usage_events (
                        id, user_id, kind, status, mode, provider, details_json, created_at, completed_at
                    ) VALUES (
                        :id, :user_id, 'first_draft_generated', 'completed', 'single',
                        'template', '{}', :created_at, :completed_at
                    )
                    """
                ),
                {
                    "id": event_id.hex,
                    "user_id": user_id.hex,
                    "created_at": created_at,
                    "completed_at": created_at,
                },
            )
    engine.dispose()

    command.upgrade(config, "head")
    with session_scope() as session:
        migrated_user = session.get(User, user_id)
        assert migrated_user is not None
        assert migrated_user.is_test_fixture is None
        assert session.get(Listing, listing_id) is not None
        assert session.query(UsageEvent).filter_by(user_id=user_id).count() == 2
        milestone = session.get(ProductMilestone, (user_id, "first_draft_generated"))
        assert milestone is not None
        assert milestone.created_at == first_draft_at
        assert milestone.is_backfilled is True
        assert build_measurement_report(session, now=first_draft_at + timedelta(days=10)) == {
            "signups": 0,
            "first_draft_generated": 0,
            "first_output_used": 0,
            "second_activity_session": 0,
            "first_paid_conversion": 0,
            "day_7_eligible_users": 0,
            "day_7_returned_users": 0,
            "users_with_generation_errors": 0,
            "users_with_recurring_generation_errors": 0,
            "unclassified_accounts_excluded": 1,
        }
        assert classify_account(user_id, "customer", session=session) is True
        report = build_measurement_report(session, now=first_draft_at + timedelta(days=10))
        assert report["signups"] == report["first_draft_generated"] == 1
        assert report["day_7_eligible_users"] == report["day_7_returned_users"] == 0

    inspector = inspect(create_engine(database_url))
    assert inspector.get_pk_constraint("product_milestones")["constrained_columns"] == [
        "user_id",
        "kind",
    ]

    def insert_unique_milestone() -> int:
        concurrent_engine = create_engine(database_url)
        try:
            with concurrent_engine.begin() as connection:
                return int(
                    connection.execute(
                        text(
                            """
                            INSERT INTO product_milestones (user_id, kind, is_backfilled, created_at)
                            VALUES (:user_id, 'first_output_used', false, :created_at)
                            ON CONFLICT(user_id, kind) DO NOTHING
                            """
                        ),
                        {"user_id": user_id.hex, "created_at": first_draft_at},
                    ).rowcount
                )
        finally:
            concurrent_engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: insert_unique_milestone(), range(2))) == [0, 1]


def test_classify_account_sets_known_user_without_exposing_account_data(user_factory):
    user = user_factory(email="classify-measurement@example.com")
    with session_scope() as session:
        session.get(User, user.id).is_test_fixture = None
        assert classify_account(user.id, "fixture", session=session) is True
        assert session.get(User, user.id).is_test_fixture is True
        assert classify_account(user.id, "customer", session=session) is True
        assert session.get(User, user.id).is_test_fixture is False
        assert classify_account("not-a-uuid", "fixture", session=session) is False
