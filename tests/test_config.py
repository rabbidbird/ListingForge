from __future__ import annotations

import pytest

from core.config import get_settings, reset_settings_cache


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
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@db/truedraft")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://example.com")
    monkeypatch.setenv("SESSION_SECRET", "short")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    reset_settings_cache()
    with pytest.raises(RuntimeError, match="Invalid production configuration"):
        get_settings().validate_for_production()
