from __future__ import annotations

from scripts.launch_check import launch_report, remaining_legal_placeholders


def test_launch_check_reports_remaining_legal_placeholders():
    remaining = remaining_legal_placeholders()
    assert "{{OPERATOR_LEGAL_NAME}}" in remaining
    report = launch_report()
    assert report["environment"] == "test"
    assert report["ready_for_public_traffic"] is False
    assert report["stripe_fully_configured"] is False
