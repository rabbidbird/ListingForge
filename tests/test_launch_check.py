from __future__ import annotations

import scripts.launch_check as launch_check
from core.config import PROJECT_ROOT, reset_settings_cache
from scripts.launch_check import (
    launch_report,
    main,
    next_operator_action,
    remaining_legal_placeholders,
    render_report,
)


def _configure_complete_production(monkeypatch, *, stripe_key: str = "rk_live_51RealKeyShape123"):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@db/truedraft")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.truedraft.test")
    monkeypatch.setenv("SESSION_SECRET", "unique-production-session-secret-value-32x")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("STRIPE_API_KEY", stripe_key)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_51RealSigningSecret123")
    monkeypatch.setenv("STRIPE_PRICE_STARTER", "price_1RealStarter")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_1RealPro")
    monkeypatch.setenv("STRIPE_PRICE_AGENCY", "price_1RealAgency")
    monkeypatch.setattr(launch_check, "remaining_legal_placeholders", lambda: [])
    reset_settings_cache()


def test_launch_check_reports_completed_legal_details():
    assert remaining_legal_placeholders() == []
    report = launch_report()
    assert report["environment"] == "test"
    assert report["ready_for_public_traffic"] is False
    assert report["stripe_fully_configured"] is False
    assert any("ENV is not production" in item for item in report["blockers"])
    assert any("SQLite" in item for item in report["blockers"])
    assert report["next_operator_action"] == "Set ENV=production on the production service."


def test_launch_check_does_not_print_secrets(monkeypatch):
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_this_must_not_be_printed")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_this_must_not_be_printed")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-with-at-least-32-characters")
    report = launch_report()
    rendered = render_report(report)
    assert "sk_test_this_must_not_be_printed" not in rendered
    assert "whsec_this_must_not_be_printed" not in rendered
    assert "test-session-secret-with-at-least-32-characters" not in rendered
    assert "session secret hardened" not in rendered
    assert "stripe key kind: test_secret" in rendered
    assert "next:" in rendered


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
    reset_settings_cache()
    report = launch_report()
    assert report["production"] is True
    assert report["ready_for_public_traffic"] is False
    assert any("STRIPE_PRICE_STARTER" in item for item in report["blockers"])
    assert report["legal_placeholders"] == []
    assert "Create Stripe Prices" in report["next_operator_action"]
    rendered = render_report(report)
    assert "verify:" in rendered
    assert "test-mode Checkout" in rendered
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
    reset_settings_cache()
    report = launch_report()
    joined = " ".join(report["blockers"])
    assert "not unique" in joined
    assert "placeholders" in joined
    assert report["ready_for_public_traffic"] is False


def test_launch_check_blocks_public_traffic_with_test_mode_stripe(monkeypatch):
    _configure_complete_production(monkeypatch, stripe_key="rk_test_51TestKeyShape123")

    report = launch_report()

    assert report["stripe_fully_configured"] is True
    assert report["checks"]["stripe_live_key"] is False
    assert report["ready_for_public_traffic"] is False
    assert any("Stripe key is test-mode" in item for item in report["blockers"])
    assert "switch all Stripe variables to live" in report["next_operator_action"]


def test_launch_check_passes_automated_gates_with_live_non_placeholder_values(monkeypatch):
    _configure_complete_production(monkeypatch)

    report = launch_report()

    assert report["ready_for_public_traffic"] is True
    assert report["checks"]["stripe_live_key"] is True
    assert report["checks"]["stripe_credentials_non_placeholder"] is True


def test_launch_check_blocks_email_verification_stub_in_production(monkeypatch):
    _configure_complete_production(monkeypatch)
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "true")
    reset_settings_cache()

    report = launch_report()

    assert report["ready_for_public_traffic"] is False
    assert any("Email verification is enabled" in item for item in report["blockers"])
    assert "EMAIL_VERIFICATION_REQUIRED=false" in report["next_operator_action"]


def test_launch_check_rejects_stripe_product_ids_used_as_prices(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@db/truedraft")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.truedraft.example")
    monkeypatch.setenv("SESSION_SECRET", "unique-production-session-secret-value-32x")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("STRIPE_API_KEY", "rk_live_example")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_example")
    monkeypatch.setenv("STRIPE_PRICE_STARTER", "prod_starter")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "prod_pro")
    monkeypatch.setenv("STRIPE_PRICE_AGENCY", "prod_agency")
    reset_settings_cache()
    report = launch_report()
    assert any("not Product IDs" in item for item in report["blockers"])
    assert "Price ID (price_" in report["next_operator_action"]
    assert report["ready_for_public_traffic"] is False


def test_launch_check_warns_about_legacy_main_vars(monkeypatch):
    monkeypatch.setenv("LISTINGFORGE_SKIP_AUTH", "true")
    monkeypatch.setenv("TRUEDRAFT_SKIP_AUTH", "1")
    report = launch_report()
    assert report["checks"]["legacy_main_vars"]
    assert any("Legacy main-branch" in item for item in report["warnings"])


def test_launch_check_surfaces_config_errors_instead_of_raising(monkeypatch, capsys):
    sensitive_marker = "postgresql://operator:sensitive-password@private-db/truedraft"

    def fail_settings():
        raise RuntimeError(sensitive_marker)

    monkeypatch.setenv("ENV", "production")
    monkeypatch.setattr(launch_check, "get_settings", fail_settings)
    report = launch_report()
    rendered = render_report(report)
    assert report["config_error"] == (
        "Application configuration is invalid. Review the required environment values."
    )
    assert sensitive_marker not in rendered
    assert report["ready_for_public_traffic"] is False
    assert "Fix the production configuration error" in report["next_operator_action"]
    assert main([]) == 1
    assert sensitive_marker not in capsys.readouterr().out


def test_non_production_launch_check_exits_zero_unless_strict(monkeypatch):
    report = launch_report()
    assert report["ready_for_public_traffic"] is False
    assert main([]) == 0
    assert main(["--strict"]) == 1


def test_next_operator_action_prefers_first_blocker():
    report = {
        "config_error": None,
        "blockers": ["ENV is not production", "Legal placeholders remain: {{CONTACT_EMAIL}}"],
        "warnings": [],
        "ready_for_public_traffic": False,
    }
    assert next_operator_action(report) == "Set ENV=production on the production service."


def test_next_operator_action_for_test_mode_warning():
    report = {
        "config_error": None,
        "blockers": [],
        "warnings": ["Stripe key is test-mode; live paid traffic needs a live key"],
        "ready_for_public_traffic": True,
    }
    assert "switch Stripe variables to live" in next_operator_action(report)


def test_container_defaults_fail_closed_to_production():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "ENV=production" in dockerfile
    assert "ENV: development" in compose


def test_streamlit_config_hides_dev_surfaces():
    config = (PROJECT_ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "gatherUsageStats = false" in config
    assert 'toolbarMode = "viewer"' in config
    assert "disableDataExport = true" in config
    assert "enableCORS = false" not in config
    supervisord = (PROJECT_ROOT / "deploy" / "supervisord.conf").read_text(encoding="utf-8")
    assert "--client.toolbarMode=viewer" in supervisord
    assert "--client.disableDataExport=true" in supervisord
    assert "--no-server-header" in supervisord
