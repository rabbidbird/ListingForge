"""Operator-facing launch readiness report.

This never enables live payments or writes secrets. It only inspects the current
process environment and repository legal placeholders.
"""

from __future__ import annotations

from core.config import PROJECT_ROOT, get_settings

LEGAL_PLACEHOLDERS = (
    "{{OPERATOR_LEGAL_NAME}}",
    "{{CONTACT_EMAIL}}",
    "{{JURISDICTION}}",
)


def remaining_legal_placeholders() -> list[str]:
    text = (PROJECT_ROOT / "pages" / "6_Legal.py").read_text(encoding="utf-8")
    return [marker for marker in LEGAL_PLACEHOLDERS if marker in text]


def launch_report() -> dict[str, object]:
    settings = get_settings()
    remaining = remaining_legal_placeholders()
    return {
        "environment": settings.environment,
        "production": settings.is_production,
        "stripe_fully_configured": settings.stripe_fully_configured,
        "llm_enabled": settings.llm_enabled,
        "legal_placeholders": remaining,
        "ready_for_public_traffic": settings.is_production
        and settings.stripe_fully_configured
        and not remaining,
    }


def main() -> None:
    report = launch_report()
    print("TrueDraft launch check")
    print(f"  environment: {report['environment']}")
    print(f"  stripe fully configured: {report['stripe_fully_configured']}")
    print(f"  llm enabled: {report['llm_enabled']}")
    remaining = report["legal_placeholders"]
    print(f"  legal placeholders: {', '.join(remaining) if remaining else 'none'}")
    if report["ready_for_public_traffic"]:
        print("  public-traffic gate: pass")
        return
    print("  public-traffic gate: blocked")
    print("  complete SHIP_CHECKLIST.md before accepting paid public traffic")


if __name__ == "__main__":
    main()
