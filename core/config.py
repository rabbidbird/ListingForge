"""Environment-backed application configuration.

Production intentionally fails closed when security-critical settings are absent
or still set to documented development defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Used only for local/dev. Production rejects these exact values.
DEFAULT_DEV_SESSION_SECRET = "development-only-session-secret-change-me"
INSECURE_SESSION_SECRETS = frozenset(
    {
        DEFAULT_DEV_SESSION_SECRET,
        "local-development-session-secret-change-before-use",
        "replace-with-at-least-32-random-characters",
        "test-session-secret-with-at-least-32-characters",
        "ci-session-secret-with-at-least-32-characters",
    }
)
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


def _as_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def _normalize_database_url(value: str) -> str:
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value.removeprefix("postgres://")
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value.removeprefix("postgresql://")
    return value


def is_insecure_session_secret(secret: str) -> bool:
    value = secret.strip()
    if value in INSECURE_SESSION_SECRETS:
        return True
    if len(value) < 32:
        return True
    if len(set(value)) == 1:
        return True
    lowered = value.lower()
    return any(marker in lowered for marker in ("change-me", "change-before-use", "replace-with"))


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    public_base_url: str
    session_secret: str
    session_cookie_name: str
    session_days: int
    cookie_secure: bool
    email_verification_required: bool
    llm_enabled: bool
    llm_timeout_seconds: int
    llm_max_tokens: int
    max_upload_bytes: int
    stripe_api_key: str
    stripe_webhook_secret: str
    stripe_price_starter: str
    stripe_price_pro: str
    stripe_price_agency: str

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def stripe_configured(self) -> bool:
        return bool(self.stripe_api_key and self.stripe_webhook_secret)

    @property
    def stripe_fully_configured(self) -> bool:
        return self.stripe_configured and len(self.stripe_price_to_plan) == 3

    @property
    def stripe_price_to_plan(self) -> dict[str, str]:
        return {
            price: plan
            for price, plan in (
                (self.stripe_price_starter, "starter"),
                (self.stripe_price_pro, "pro"),
                (self.stripe_price_agency, "agency"),
            )
            if price
        }

    def validate_for_production(self) -> None:
        if not self.is_production:
            return
        errors: list[str] = []
        if not self.database_url.startswith("postgresql+"):
            errors.append("DATABASE_URL must point to PostgreSQL")
        if is_insecure_session_secret(self.session_secret):
            errors.append(
                "SESSION_SECRET must be a unique 32+ character value, not a documented default"
            )
        parsed = urlparse(self.public_base_url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host:
            errors.append("PUBLIC_BASE_URL must use https://")
        elif host in LOCAL_HOSTS:
            errors.append("PUBLIC_BASE_URL must be the public https origin, not localhost")
        if not self.cookie_secure:
            errors.append("SESSION_COOKIE_SECURE must be true")
        if errors:
            raise RuntimeError("Invalid production configuration: " + "; ".join(errors))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = os.getenv("ENV", "development").strip().lower()
    if environment not in {"development", "test", "production"}:
        raise RuntimeError("ENV must be one of: development, test, production")
    default_db = f"sqlite:///{(PROJECT_ROOT / 'data' / 'truedraft_dev.db').as_posix()}"
    database_url = _normalize_database_url(os.getenv("DATABASE_URL", default_db).strip())
    if environment == "production" and database_url.startswith("sqlite"):
        raise RuntimeError("SQLite is allowed only when ENV=development or ENV=test")

    settings = Settings(
        environment=environment,
        database_url=database_url,
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/"),
        session_secret=os.getenv("SESSION_SECRET", DEFAULT_DEV_SESSION_SECRET),
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "truedraft_session"),
        session_days=_as_int("SESSION_DAYS", 30),
        cookie_secure=_as_bool("SESSION_COOKIE_SECURE", environment == "production"),
        email_verification_required=_as_bool("EMAIL_VERIFICATION_REQUIRED", False),
        llm_enabled=_as_bool("LLM_ENABLED", False) and not _as_bool("LLM_KILL_SWITCH", False),
        llm_timeout_seconds=_as_int("LLM_TIMEOUT_SECONDS", 25),
        llm_max_tokens=_as_int("LLM_MAX_TOKENS", 1200, minimum=100),
        max_upload_bytes=_as_int("MAX_UPLOAD_BYTES", 2_000_000, minimum=1_024),
        stripe_api_key=os.getenv("STRIPE_API_KEY", os.getenv("STRIPE_SECRET_KEY", "")),
        stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET", ""),
        stripe_price_starter=os.getenv("STRIPE_PRICE_STARTER", ""),
        stripe_price_pro=os.getenv("STRIPE_PRICE_PRO", ""),
        stripe_price_agency=os.getenv("STRIPE_PRICE_AGENCY", ""),
    )
    settings.validate_for_production()
    return settings


def reset_settings_cache() -> None:
    """Test helper for environment changes."""
    get_settings.cache_clear()
