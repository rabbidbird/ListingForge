from __future__ import annotations

from alembic.config import Config
from sqlalchemy import inspect

from alembic import command
from core.config import PROJECT_ROOT, reset_settings_cache
from core.database import get_engine, reset_engine
from core.models import Base


def test_alembic_upgrade_creates_all_model_tables(tmp_path, monkeypatch):
    database_path = tmp_path / "alembic.db"
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    reset_settings_cache()
    reset_engine()

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    tables = set(inspect(get_engine()).get_table_names())
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
