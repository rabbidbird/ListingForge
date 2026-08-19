from __future__ import annotations

from scripts.launch_check import launch_report, main, remaining_legal_placeholders, render_report


def test_launch_check_reports_remaining_legal_placeholders():
    remaining = remaining_legal_placeholders()
    assert "{{OPERATOR_LEGAL_NAME}}" in remaining
    assert "{{CONTACT_EMAIL}}" in remaining
    assert "{{JURISDICTION}}" in remaining
    report = launch_report()
    assert report["environment"] == "test"
    assert report["ready_for_public_traffic"] is False
    assert report["stripe_fully_configured"] is False
    assert any("ENV is not production" in item for item in report["blockers"])
    assert any("SQLite" in item for item in report["blockers"])


def test_launch_check_does_not_print_secrets(monkeypatch):
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_this_must_not_be_printed")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_this_must_not_be_printed")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-with-at-least-32-characters")
    report = launch_report()
    rendered = render_report(report)
    assert "sk_test_this_must_not_be_printed" not in rendered
    assert "whsec_this_must_not_be_printed" not in rendered
    assert "test-session-secret-with-at-least-32-characters" not in rendered
    assert "stripe key kind: test_secret" in rendered


def test_launch_check_blocks_incomplete_production(monkeypatch, tmp_path):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@db/truedraft")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.truedraft.example")
    monkeypatch.setenv("SESSION_SECRET", "unique-production-session-secret-value-32x")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("STRIPE_API_KEY", "rk_live_example")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_example")
    monkeypatch.delenv("STRIPE_PRICE_STARTER", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_PRO", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_AGENCY", raising=False)
    from core.config import reset_settings_cache

    reset_settings_cache()
    report = launch_report()
    assert report["production"] is True
    assert report["ready_for_public_traffic"] is False
    assert any("STRIPE_PRICE_STARTER" in item for item in report["blockers"])
    assert any("Legal placeholders remain" in item for item in report["blockers"])
    assert main([]) == 1


def test_launch_check_flags_duplicate_and_placeholder_prices(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@db/truedraft")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.truedraft.example")
    monkeypatch.setenv("SESSION_SECRET", "unique-production-session-secret-value-32x")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("STRIPE_API_KEY", "rk_live_example")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_example")
    monkeypatch.setenv("STRIPE_PRICE_STARTER", "price_starter")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_starter")
    monkeypatch.setenv("STRIPE_PRICE_AGENCY", "price_starter")
    from core.config import reset_settings_cache

    reset_settings_cache()
    report = launch_report()
    joined = " ".join(report["blockers"])
    assert "not unique" in joined
    assert "placeholders" in joined
    assert report["ready_for_public_traffic"] is False


def test_launch_check_warns_about_legacy_main_vars(monkeypatch):
    monkeypatch.setenv("LISTINGFORGE_SKIP_AUTH", "true")
    monkeypatch.setenv("TRUEDRAFT_SKIP_AUTH", "1")
    report = launch_report()
    assert report["checks"]["legacy_main_vars"]
    assert any("Legacy main-branch" in item for item in report["warnings"])


def test_launch_check_surfaces_config_errors_instead_of_raising(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///unsafe.db")
    from core.config import reset_settings_cache

    reset_settings_cache()
    report = launch_report()
    assert report["config_error"]
    assert report["ready_for_public_traffic"] is False
    assert main([]) == 1


def test_non_production_launch_check_exits_zero_unless_strict(monkeypatch):
    report = launch_report()
    assert report["ready_for_public_traffic"] is False
    assert main([]) == 0
    assert main(["--strict"]) == 1
