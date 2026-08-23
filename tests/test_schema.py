from __future__ import annotations

from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command
from core.config import PROJECT_ROOT, reset_settings_cache
from core.database import get_engine, reset_engine, session_scope
from core.migrate import database_at_migration_head
from core.models import Base


def test_alembic_upgrade_creates_all_model_tables(tmp_path, monkeypatch):
    database_path = tmp_path / "alembic.db"
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    reset_settings_cache()
    reset_engine()

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names())
    assert set(Base.metadata.tables) <= tables
    assert "alembic_version" in tables
    assert {
        "users",
        "user_sessions",
        "listings",
        "usage_events",
        "subscriptions",
        "webhook_events",
    }.issubset(tables)
    subscription_columns = {column["name"] for column in inspector.get_columns("subscriptions")}
    assert {
        "pending_checkout_session_id",
        "pending_checkout_url",
        "pending_checkout_plan",
        "pending_checkout_expires_at",
    }.issubset(subscription_columns)

    with session_scope() as session:
        assert database_at_migration_head(session) is True
        session.execute(text("UPDATE alembic_version SET version_num = '20260815_0001'"))
    with session_scope() as session:
        assert database_at_migration_head(session) is False
