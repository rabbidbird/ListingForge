from __future__ import annotations

import pytest

from core.config import (
    DEFAULT_DEV_SESSION_SECRET,
    INSECURE_SESSION_SECRETS,
    get_settings,
    is_insecure_session_secret,
    reset_settings_cache,
)


def _production_env(monkeypatch, **overrides: str | None) -> None:
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


def test_development_allows_sqlite(monkeypatch, tmp_path):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'dev.db').as_posix()}")
    reset_settings_cache()
    settings = get_settings()
    assert settings.is_production is False
    assert settings.database_url.startswith("sqlite:///")


def test_postgres_urls_are_normalized_to_psycopg(monkeypatch):
    _production_env(monkeypatch, DATABASE_URL="postgres://user:password@db/truedraft")
    settings = get_settings()
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_production_requires_https_secure_cookie_and_strong_secret(monkeypatch):
    _production_env(
        monkeypatch,
        PUBLIC_BASE_URL="http://example.com",
        SESSION_SECRET="short",
        SESSION_COOKIE_SECURE="false",
    )
    with pytest.raises(RuntimeError, match="Invalid production configuration"):
        get_settings()


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "0.0.0.0"])
def test_production_rejects_loopback_public_urls(monkeypatch, host):
    _production_env(monkeypatch, PUBLIC_BASE_URL=f"https://{host}:8080")
    with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
        get_settings()


@pytest.mark.parametrize(
    "public_url",
    [
        "https://app.truedraft.example/subpath",
        "https://app.truedraft.example?mode=prod",
        "https://user:password@app.truedraft.example",
    ],
)
def test_production_requires_public_base_url_to_be_an_origin(monkeypatch, public_url):
    _production_env(monkeypatch, PUBLIC_BASE_URL=public_url)
    with pytest.raises(RuntimeError, match="origin without path"):
        get_settings()


def test_production_rejects_default_and_documented_session_secrets(monkeypatch):
    assert is_insecure_session_secret(DEFAULT_DEV_SESSION_SECRET)
    for secret in INSECURE_SESSION_SECRETS:
        assert is_insecure_session_secret(secret)
    _production_env(monkeypatch, SESSION_SECRET=DEFAULT_DEV_SESSION_SECRET)
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        get_settings()


def test_production_rejects_repeated_and_placeholder_secrets(monkeypatch):
    assert is_insecure_session_secret("a" * 40)
    assert is_insecure_session_secret("please-change-me-this-is-long-enough-ok")
    _production_env(monkeypatch, SESSION_SECRET="a" * 40)
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        get_settings()


def test_production_accepts_hardened_settings(monkeypatch):
    _production_env(monkeypatch)
    settings = get_settings()
    assert settings.is_production
    assert settings.cookie_secure is True
    assert settings.stripe_fully_configured is False


def test_stripe_fully_configured_requires_three_distinct_prices(monkeypatch):
    _production_env(
        monkeypatch,
        STRIPE_API_KEY="rk_live_example",
        STRIPE_WEBHOOK_SECRET="whsec_example",
        STRIPE_PRICE_STARTER="price_aaa",
        STRIPE_PRICE_PRO="price_bbb",
        STRIPE_PRICE_AGENCY="price_ccc",
    )
    settings = get_settings()
    assert settings.stripe_fully_configured is True
    assert settings.stripe_price_to_plan["price_bbb"] == "pro"


def test_llm_kill_switch_disables_llm(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_KILL_SWITCH", "true")
    reset_settings_cache()
    assert get_settings().llm_enabled is False
