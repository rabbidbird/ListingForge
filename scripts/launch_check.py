"""Operator-facing launch readiness report.

This never enables live payments or writes secrets. It only inspects the current
process environment and repository legal placeholders.
"""

from __future__ import annotations

import os
import sys
from typing import Any
from urllib.parse import urlparse

from core.config import (
    LOCAL_HOSTS,
    PROJECT_ROOT,
    get_settings,
    is_insecure_session_secret,
    reset_settings_cache,
)

LEGAL_PLACEHOLDERS = (
    "{{OPERATOR_LEGAL_NAME}}",
    "{{CONTACT_EMAIL}}",
    "{{JURISDICTION}}",
)
LEGACY_MAIN_VARS = (
    "LISTINGFORGE_SKIP_AUTH",
    "TRUEDRAFT_SKIP_AUTH",
    "LISTINGFORGE_REQUIRE_AUTH",
    "LISTINGFORGE_USER_ID",
    "STRIPE_SUCCESS_URL",
    "STRIPE_CANCEL_URL",
)
PLACEHOLDER_PRICE_IDS = frozenset(
    {
        "price_starter",
        "price_pro",
        "price_agency",
        "price_...",
        "price_xxx",
    }
)


def remaining_legal_placeholders() -> list[str]:
    text = (PROJECT_ROOT / "pages" / "6_Legal.py").read_text(encoding="utf-8")
    return [marker for marker in LEGAL_PLACEHOLDERS if marker in text]


def _database_dialect(url: str) -> str:
    if url.startswith("sqlite"):
        return "sqlite"
    if url.startswith("postgresql"):
        return "postgresql"
    parsed = urlparse(url)
    return parsed.scheme or "unknown"


def _stripe_key_kind(key: str) -> str:
    if not key:
        return "missing"
    if key.startswith("rk_live"):
        return "live_restricted"
    if key.startswith("sk_live"):
        return "live_secret"
    if key.startswith("rk_test"):
        return "test_restricted"
    if key.startswith("sk_test"):
        return "test_secret"
    return "unrecognized"


def _present(value: str) -> bool:
    return bool(value and value.strip())


def launch_report() -> dict[str, Any]:
    config_error: str | None = None
    try:
        reset_settings_cache()
        settings = get_settings()
    except RuntimeError as exc:
        environment = os.getenv("ENV", "development").strip().lower() or "development"
        remaining = remaining_legal_placeholders()
        blockers = [str(exc)]
        if remaining:
            blockers.append("Legal placeholders remain: " + ", ".join(remaining))
        return {
            "environment": environment,
            "production": environment == "production",
            "config_error": str(exc),
            "stripe_fully_configured": False,
            "llm_enabled": False,
            "legal_placeholders": remaining,
            "blockers": blockers,
            "warnings": [],
            "checks": {},
            "ready_for_public_traffic": False,
        }

    remaining = remaining_legal_placeholders()
    blockers: list[str] = []
    warnings: list[str] = []
    parsed = urlparse(settings.public_base_url)
    host = (parsed.hostname or "").lower()
    dialect = _database_dialect(settings.database_url)
    stripe_kind = _stripe_key_kind(settings.stripe_api_key)
    prices = {
        "starter": settings.stripe_price_starter,
        "pro": settings.stripe_price_pro,
        "agency": settings.stripe_price_agency,
    }
    missing_stripe = [
        name
        for name, ok in (
            ("STRIPE_API_KEY", _present(settings.stripe_api_key)),
            ("STRIPE_WEBHOOK_SECRET", _present(settings.stripe_webhook_secret)),
            ("STRIPE_PRICE_STARTER", _present(settings.stripe_price_starter)),
            ("STRIPE_PRICE_PRO", _present(settings.stripe_price_pro)),
            ("STRIPE_PRICE_AGENCY", _present(settings.stripe_price_agency)),
        )
        if not ok
    ]
    configured_prices = [value for value in prices.values() if _present(value)]
    duplicate_prices = sorted(
        {value for value in configured_prices if configured_prices.count(value) > 1}
    )
    placeholder_prices = [name for name, value in prices.items() if value in PLACEHOLDER_PRICE_IDS]
    legacy = [name for name in LEGACY_MAIN_VARS if os.getenv(name)]

    if not settings.is_production:
        blockers.append("ENV is not production")
    if dialect == "sqlite":
        blockers.append("DATABASE_URL is SQLite; production requires PostgreSQL")
    elif not settings.database_url.startswith("postgresql"):
        blockers.append("DATABASE_URL must point to PostgreSQL")
    if is_insecure_session_secret(settings.session_secret):
        blockers.append(
            "SESSION_SECRET must be a unique 32+ character value, not a documented default"
        )
    if parsed.scheme != "https" or not host:
        blockers.append("PUBLIC_BASE_URL must use https://")
    elif host in LOCAL_HOSTS:
        blockers.append("PUBLIC_BASE_URL must be the public https origin, not localhost")
    if not settings.cookie_secure:
        blockers.append("SESSION_COOKIE_SECURE must be true")
    if missing_stripe:
        blockers.append("Stripe is incomplete: " + ", ".join(missing_stripe))
    if duplicate_prices:
        blockers.append("Stripe Price IDs are not unique across plans")
    if placeholder_prices:
        blockers.append(
            "Stripe Price IDs still use documented placeholders: " + ", ".join(placeholder_prices)
        )
    if remaining:
        blockers.append("Legal placeholders remain: " + ", ".join(remaining))
    if legacy:
        message = (
            "Legacy main-branch variables are set and must not be used on the paid path: "
            + ", ".join(legacy)
        )
        if settings.is_production:
            blockers.append(message)
        else:
            warnings.append(message)

    if stripe_kind in {"test_restricted", "test_secret"} and settings.is_production:
        warnings.append("Stripe key is test-mode; live paid traffic needs a live key")
    if stripe_kind == "live_secret":
        warnings.append("Prefer a restricted live Stripe key (rk_live...) over sk_live")
    if stripe_kind == "unrecognized" and _present(settings.stripe_api_key):
        warnings.append("STRIPE_API_KEY does not use a recognized sk_/rk_ prefix")
    if settings.llm_enabled:
        has_llm_key = any(
            os.getenv(name) for name in ("OPENAI_API_KEY", "XAI_API_KEY", "GROK_API_KEY")
        )
        if not has_llm_key:
            warnings.append("LLM_ENABLED is true but no LLM provider API key is set")
        else:
            warnings.append(
                "LLM mode is enabled; confirm provider DPA, model, timeout, and token caps"
            )
    if settings.email_verification_required:
        warnings.append("EMAIL_VERIFICATION_REQUIRED is true, but v1 has no email delivery adapter")

    checks = {
        "environment": settings.environment,
        "database_dialect": dialect,
        "public_base_url": settings.public_base_url,
        "cookie_secure": settings.cookie_secure,
        "session_secret_hardened": not is_insecure_session_secret(settings.session_secret),
        "stripe_key_kind": stripe_kind,
        "stripe_webhook_secret_set": _present(settings.stripe_webhook_secret),
        "stripe_prices_set": {
            name: _present(value) and value not in PLACEHOLDER_PRICE_IDS
            for name, value in prices.items()
        },
        "stripe_fully_configured": settings.stripe_fully_configured
        and not duplicate_prices
        and not placeholder_prices,
        "webhook_url": f"{settings.public_base_url}/webhooks/stripe",
        "checkout_success_url": f"{settings.public_base_url}/About_Pricing?checkout=success",
        "checkout_cancel_url": f"{settings.public_base_url}/About_Pricing?checkout=cancelled",
        "portal_return_url": f"{settings.public_base_url}/About_Pricing?portal=return",
        "llm_enabled": settings.llm_enabled,
        "email_verification_required": settings.email_verification_required,
        "legacy_main_vars": legacy,
    }

    return {
        "environment": settings.environment,
        "production": settings.is_production,
        "config_error": config_error,
        "stripe_fully_configured": bool(checks["stripe_fully_configured"]),
        "llm_enabled": settings.llm_enabled,
        "legal_placeholders": remaining,
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
        "ready_for_public_traffic": not blockers,
    }


def render_report(report: dict[str, Any]) -> str:
    lines = [
        "TrueDraft launch check",
        f"  environment: {report['environment']}",
        f"  production: {report['production']}",
        f"  stripe fully configured: {report['stripe_fully_configured']}",
        f"  llm enabled: {report['llm_enabled']}",
    ]
    remaining = report["legal_placeholders"]
    lines.append(f"  legal placeholders: {', '.join(remaining) if remaining else 'none'}")
    checks = report.get("checks") or {}
    if checks:
        lines.append(f"  database dialect: {checks.get('database_dialect', 'unknown')}")
        lines.append(f"  public base url: {checks.get('public_base_url', '')}")
        lines.append(f"  cookie secure: {checks.get('cookie_secure', False)}")
        lines.append(f"  session secret hardened: {checks.get('session_secret_hardened', False)}")
        lines.append(f"  stripe key kind: {checks.get('stripe_key_kind', 'missing')}")
        lines.append(f"  webhook url: {checks.get('webhook_url', '')}")
        lines.append(f"  portal return url: {checks.get('portal_return_url', '')}")
    for blocker in report.get("blockers") or []:
        lines.append(f"  blocker: {blocker}")
    for warning in report.get("warnings") or []:
        lines.append(f"  warning: {warning}")
    if report.get("config_error"):
        lines.append(f"  config error: {report['config_error']}")
    if report["ready_for_public_traffic"]:
        lines.append("  public-traffic gate: pass")
    else:
        lines.append("  public-traffic gate: blocked")
        lines.append("  complete SHIP_CHECKLIST.md before accepting paid public traffic")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    strict = "--strict" in args
    report = launch_report()
    print(render_report(report))
    if report["ready_for_public_traffic"]:
        return 0
    if report["production"] or strict or report.get("config_error"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
