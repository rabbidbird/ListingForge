from __future__ import annotations

import pytest

from core.config import (
    DEFAULT_DEV_SESSION_SECRET,
    get_settings,
    is_insecure_session_secret,
    reset_settings_cache,
)


def _production_env(monkeypatch, **overrides: str) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@db/truedraft")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.truedraft.example")
    monkeypatch.setenv("SESSION_SECRET", "unique-production-session-secret-value-32x")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    for key, value in overrides.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    reset_settings_cache()


def test_unknown_environment_is_rejected(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    reset_settings_cache()
    with pytest.raises(RuntimeError, match="ENV must be one of"):
        get_settings()


def test_production_rejects_sqlite(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///unsafe.db")
    reset_settings_cache()
    with pytest.raises(RuntimeError, match="SQLite"):
        get_settings()


def test_production_requires_https_secure_cookie_and_strong_secret(monkeypatch):
    _production_env(
        monkeypatch,
        PUBLIC_BASE_URL="http://example.com",
        SESSION_SECRET="short",
        SESSION_COOKIE_SECURE="false",
    )
    with pytest.raises(RuntimeError, match="Invalid production configuration"):
        get_settings()


def test_production_rejects_default_and_documented_session_secrets(monkeypatch):
    assert is_insecure_session_secret(DEFAULT_DEV_SESSION_SECRET)
    _production_env(monkeypatch, SESSION_SECRET=DEFAULT_DEV_SESSION_SECRET)
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        get_settings()


def test_production_rejects_localhost_public_url(monkeypatch):
    _production_env(monkeypatch, PUBLIC_BASE_URL="https://localhost:8080")
    with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
        get_settings()


def test_production_accepts_hardened_settings(monkeypatch):
    _production_env(monkeypatch)
    settings = get_settings()
    assert settings.is_production
    assert settings.cookie_secure is True
    assert settings.stripe_fully_configured is False
