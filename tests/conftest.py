from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator

import pytest

from core.auth import register_user
from core.config import reset_settings_cache
from core.database import reset_engine, session_scope
from core.models import Base, Subscription, User


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch) -> Iterator[None]:
    database_path = tmp_path / "test.db"
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-with-at-least-32-characters")
    monkeypatch.setenv("LLM_ENABLED", "false")
    reset_settings_cache()
    reset_engine()
    from core.database import get_engine

    Base.metadata.create_all(get_engine())
    yield
    reset_engine()
    reset_settings_cache()


@pytest.fixture
def user_factory() -> Callable[..., User]:
    sequence = 0

    def create(*, email: str | None = None, plan: str = "free") -> User:
        nonlocal sequence
        sequence += 1
        with session_scope() as session:
            user = register_user(
                session,
                email=email or f"user{sequence}@example.com",
                password="correct horse battery staple",
                name=f"Test User {sequence}",
                accepted_terms=True,
            )
            if plan != "free":
                subscription = session.query(Subscription).filter_by(user_id=user.id).one()
                subscription.plan = plan
                subscription.status = "active"
            session.flush()
            return user

    return create


@pytest.fixture
def random_listing_id() -> uuid.UUID:
    return uuid.uuid4()
