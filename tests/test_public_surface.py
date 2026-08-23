"""Public landing, pricing, and trust-copy invariants."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

import core.auth
import core.ui
from core.copy import (
    AUTH_PROMISE,
    CLAIM_CATEGORIES,
    DRAFT_BANNER,
    FEATURES,
    HOW_IT_WORKS,
    PLAN_BLURBS,
    PRODUCT_NAME,
    PROMISE,
    TAGLINE,
    TRUST_POINTS,
    forbidden_claims_in,
    plan_limit_lines,
    public_text_blob,
)
from core.plans import PLANS
from scripts.launch_check import remaining_legal_placeholders


def _visible_text(app: AppTest) -> str:
    parts: list[str] = []
    for attr in (
        "title",
        "header",
        "subheader",
        "markdown",
        "text",
        "caption",
        "info",
        "warning",
        "success",
        "error",
    ):
        block = getattr(app, attr, None)
        if not block:
            continue
        for item in block:
            value = getattr(item, "value", None)
            if value:
                parts.append(str(value))
    for attr in ("button", "link_button"):
        block = getattr(app, attr, None)
        if not block:
            continue
        for item in block:
            label = getattr(item, "label", None)
            if label:
                parts.append(str(label))
    expanders = getattr(app, "expander", None)
    if expanders:
        for item in expanders:
            label = getattr(item, "label", None)
            if label:
                parts.append(str(label))
    return "\n".join(parts)


def test_copy_module_contains_no_false_claims():
    blob = public_text_blob(
        PRODUCT_NAME,
        TAGLINE,
        PROMISE,
        DRAFT_BANNER,
        AUTH_PROMISE,
        *[body for _title, body in HOW_IT_WORKS],
        *[body for _title, body in FEATURES],
        *[body for _title, body in TRUST_POINTS],
        *[body for _title, body in CLAIM_CATEGORIES],
        *PLAN_BLURBS.values(),
    )
    assert forbidden_claims_in(blob) == []
    assert PRODUCT_NAME == "TrueDraft"


def test_plan_limit_lines_match_enforced_metadata():
    free = plan_limit_lines("free")
    assert "8 drafts / UTC day" in free
    assert "40 drafts / UTC month" in free
    assert PLANS["starter"].display_price == "$12/month"
    assert PLANS["pro"].display_price == "$29/month"
    assert PLANS["agency"].display_price == "$79/month"


def test_public_home_converts_a_cold_visitor():
    app = AppTest.from_file("app.py").run(timeout=15)
    assert not app.exception
    text = _visible_text(app)
    assert PRODUCT_NAME in text
    assert TAGLINE in text
    assert PROMISE in text
    assert "Create account" in text
    assert "Sign in" in text
    assert "How it works" in text
    assert "Supply facts" in text
    assert "No silent product facts" in text
    assert "What TrueDraft will not invent" in text
    assert "Starter" in text
    assert forbidden_claims_in(text) == []
    labels = [getattr(item, "label", "") for item in getattr(app, "link_button", [])]
    if labels:
        assert "Create account" in labels
        assert "Sign in" in labels


def test_logged_in_home_stays_a_product_home(monkeypatch, user_factory):
    user = user_factory()
    monkeypatch.setattr(core.auth, "streamlit_current_user", lambda: user)
    app = AppTest.from_file("app.py").run(timeout=15)
    assert not app.exception
    text = _visible_text(app)
    assert f"Welcome back, {user.name}." in text
    assert any(item.label == "Create one draft" for item in app.button)
    assert any(item.label == "Process a CSV" for item in app.button)
    public_cta_labels = [getattr(item, "label", "") for item in getattr(app, "link_button", [])]
    assert "Create account" not in public_cta_labels
    assert forbidden_claims_in(text) == []


def test_public_pricing_matches_backend_limits(monkeypatch):
    monkeypatch.setattr(core.ui, "render_sidebar", lambda _user=None: None)
    app = AppTest.from_file("pages/5_About_Pricing.py").run(timeout=15)
    assert not app.exception
    text = _visible_text(app)
    for key in ("free", "starter", "pro", "agency"):
        policy = PLANS[key]
        assert policy.name in text
        assert policy.display_price in text
        for line in plan_limit_lines(key):
            assert line in text
    assert "Create a Free account" in text
    assert "none are marketed as unlimited" in text
    assert forbidden_claims_in(text) == []


def test_legal_placeholders_remain_detectable(monkeypatch):
    remaining = remaining_legal_placeholders()
    assert "{{OPERATOR_LEGAL_NAME}}" in remaining
    assert "{{CONTACT_EMAIL}}" in remaining
    assert "{{JURISDICTION}}" in remaining
    monkeypatch.setattr(core.ui, "render_sidebar", lambda _user=None: None)
    app = AppTest.from_file("pages/6_Legal.py").run(timeout=15)
    assert not app.exception
    text = _visible_text(app)
    assert "{{OPERATOR_LEGAL_NAME}}" in text
    assert "starting drafts" in text.lower() or "starting draft" in text.lower()


def test_optimizer_shows_blocked_claim_categories(monkeypatch, user_factory):
    user = user_factory()
    monkeypatch.setattr(core.auth, "require_streamlit_user", lambda: user)
    monkeypatch.setattr(core.auth, "streamlit_current_user", lambda: user)
    monkeypatch.setattr(core.ui, "render_sidebar", lambda _user=None: None)
    app = AppTest.from_file("pages/1_Optimizer.py").run(timeout=15)
    assert not app.exception
    text = _visible_text(app)
    assert "will not invent" in text.lower() or "What TrueDraft will not invent" in text
    assert "nickel-free" in text
    assert "leaving a field blank" in text.lower()
    assert DRAFT_BANNER in text
    assert forbidden_claims_in(text) == []
