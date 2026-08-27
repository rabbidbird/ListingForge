"""Public landing, pricing, and trust-copy invariants."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

import core.auth
import core.ui
from core.billing import STRIPE_API_VERSION
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


def test_legal_operator_details_are_complete(monkeypatch):
    assert remaining_legal_placeholders() == []
    monkeypatch.setattr(core.ui, "render_sidebar", lambda _user=None: None)
    app = AppTest.from_file("pages/6_Legal.py").run(timeout=15)
    assert not app.exception
    text = _visible_text(app)
    assert "Jaylen Johnson" in text
    assert "jaylen.johnson0@gmail.com" in text
    assert "Ohio, United States" in text
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


def test_readme_stripe_versions_match_the_pinned_integration():
    readme = Path("README.md").read_text(encoding="utf-8")
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    pinned_stripe = next(
        line.split("==", 1)[1] for line in requirements.splitlines() if line.startswith("stripe==")
    )
    assert STRIPE_API_VERSION in readme
    assert f"Stripe Python `{pinned_stripe}`" in readme


def test_nginx_applies_client_and_global_soft_limits_to_all_public_routes():
    config = Path("deploy/nginx.conf.template").read_text(encoding="utf-8")
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    server = config.split("server {", 1)[1]
    assert 'map "${RAILWAY_ENVIRONMENT_ID}:$http_x_railway_edge:$http_x_real_ip"' in config
    assert 'map "${RAILWAY_ENVIRONMENT_ID}:$http_x_railway_edge:$http_x_forwarded_proto"' in config
    assert "envsubst '$PORT $RAILWAY_ENVIRONMENT_ID'" in dockerfile
    assert "limit_req_zone $truedraft_client_ip zone=truedraft_client_requests" in config
    assert "limit_conn_zone $truedraft_client_ip zone=truedraft_client_connections" in config
    assert "limit_req_zone $server_name zone=truedraft_global_requests" in config
    assert "limit_conn_zone $server_name zone=truedraft_global_connections" in config
    assert "limit_req zone=truedraft_client_requests" in server
    assert "limit_req zone=truedraft_global_requests" in server
    assert "limit_conn truedraft_client_connections" in server
    assert "limit_conn truedraft_global_connections" in server
    assert "proxy_set_header X-Real-IP $truedraft_client_ip" in server
    assert "proxy_set_header X-Forwarded-Proto $truedraft_client_proto" in server
    assert "limit_req_status 429" in config
