from __future__ import annotations

import importlib
import re

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from core.auth import AuthError, get_user_by_session_token
from core.billing import WebhookVerificationError
from core.config import reset_settings_cache
from core.database import session_scope
from core.models import User


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def _reload_web():
    import core.web

    return importlib.reload(core.web)


def test_public_signup_sets_httponly_session_cookie():
    web = _reload_web()
    with TestClient(web.app) as client:
        page = client.get("/auth/signup")
        assert page.status_code == 200
        assert "Fact-locked drafts from facts you supply" in page.text
        assert "does not publish to marketplaces" in page.text
        assert "TrueDraft" in page.text
        response = client.post(
            "/auth/signup",
            data={
                "csrf_token": _csrf(page.text),
                "name": "Web User",
                "email": "web@example.com",
                "password": "correct horse battery staple",
                "accepted_terms": "true",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "truedraft_session" in response.headers["set-cookie"]
        assert "HttpOnly" in response.headers["set-cookie"]
        assert client.get("/auth/login", follow_redirects=False).status_code == 303
    with session_scope() as session:
        assert session.query(User).filter_by(email="web@example.com").one().terms_accepted_at


def test_logout_revokes_session_and_clears_cookie():
    web = _reload_web()
    with TestClient(web.app) as client:
        page = client.get("/auth/signup")
        signup = client.post(
            "/auth/signup",
            data={
                "csrf_token": _csrf(page.text),
                "name": "Logout User",
                "email": "logout@example.com",
                "password": "correct horse battery staple",
                "accepted_terms": "true",
            },
            follow_redirects=False,
        )
        cookie_header = signup.headers["set-cookie"]
        token = re.search(r"truedraft_session=([^;]+)", cookie_header)
        assert token is not None
        raw_token = token.group(1)
        logout_page = client.get("/auth/logout")
        logout = client.post(
            "/auth/logout",
            data={"csrf_token": _csrf(logout_page.text)},
            follow_redirects=False,
        )
        assert logout.status_code == 303
        assert "truedraft_session=" in logout.headers.get("set-cookie", "")
    with session_scope() as session:
        assert get_user_by_session_token(session, raw_token) is None


def test_login_rejects_invalid_csrf():
    web = _reload_web()
    with TestClient(web.app) as client:
        client.get("/auth/login")
        response = client.post(
            "/auth/login",
            data={
                "csrf_token": "forged",
                "email": "web@example.com",
                "password": "correct horse battery staple",
            },
        )
        assert response.status_code == 400
        assert "expired" in response.text.lower()


def test_login_does_not_expose_internal_auth_errors(monkeypatch):
    web = _reload_web()

    def fail_authentication(*_args, **_kwargs):
        raise AuthError("sensitive-login-marker")

    monkeypatch.setattr(web, "authenticate_user", fail_authentication)
    with TestClient(web.app) as client:
        page = client.get("/auth/login")
        response = client.post(
            "/auth/login",
            data={
                "csrf_token": _csrf(page.text),
                "email": "person@example.com",
                "password": "correct horse battery staple",
            },
        )

    assert response.status_code == 400
    assert "Email or password is incorrect." in response.text
    assert "sensitive-login-marker" not in response.text


def test_signup_does_not_expose_internal_auth_errors(monkeypatch):
    web = _reload_web()

    def fail_registration(*_args, **_kwargs):
        raise AuthError("sensitive-signup-marker")

    monkeypatch.setattr(web, "register_user", fail_registration)
    with TestClient(web.app) as client:
        page = client.get("/auth/signup")
        response = client.post(
            "/auth/signup",
            data={
                "csrf_token": _csrf(page.text),
                "name": "Web User",
                "email": "person@example.com",
                "password": "correct horse battery staple",
                "accepted_terms": "true",
            },
        )

    assert response.status_code == 400
    assert "Account creation failed." in response.text
    assert "sensitive-signup-marker" not in response.text


def test_webhook_without_signature_is_rejected():
    web = _reload_web()
    with TestClient(web.app) as client:
        response = client.post("/webhooks/stripe", content=b'{"id":"evt_x"}')
        assert response.status_code == 400
        assert "signature" in response.json()["detail"].lower()


def test_webhook_invalid_signature_is_rejected(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
    from core.config import reset_settings_cache

    reset_settings_cache()
    web = _reload_web()
    with TestClient(web.app) as client:
        response = client.post(
            "/webhooks/stripe",
            content=b'{"id":"evt_x"}',
            headers={"stripe-signature": "t=1,v1=deadbeef"},
        )
        assert response.status_code == 400
        assert "signature" in response.json()["detail"].lower()


def test_webhook_does_not_expose_verification_errors(monkeypatch):
    web = _reload_web()

    def fail_verification(*_args, **_kwargs):
        raise WebhookVerificationError("sensitive-webhook-marker")

    monkeypatch.setattr(web, "handle_webhook", fail_verification)
    with TestClient(web.app) as client:
        response = client.post(
            "/webhooks/stripe",
            content=b'{"id":"evt_x"}',
            headers={"stripe-signature": "sensitive-signature"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Stripe webhook signature."}
    assert "sensitive-webhook-marker" not in response.text


def test_health_rejects_database_behind_migration_head(monkeypatch):
    web = _reload_web()
    monkeypatch.setattr(web, "database_at_migration_head", lambda _session: False)
    response = web.healthz()
    assert isinstance(response, JSONResponse)
    assert response.status_code == 503


def test_production_trusted_hosts_come_from_public_origin(monkeypatch):
    with monkeypatch.context() as production:
        production.setenv("ENV", "production")
        production.setenv("DATABASE_URL", "postgresql://user:pass@db/truedraft")
        production.setenv("PUBLIC_BASE_URL", "https://drafts.example.com")
        production.setenv("SESSION_SECRET", "a-unique-production-session-secret-2026")
        production.setenv("SESSION_COOKIE_SECURE", "true")
        reset_settings_cache()
        web = _reload_web()
        assert web._trusted_hosts() == ["drafts.example.com", "127.0.0.1", "localhost"]
        with TestClient(web.app) as client:
            rejected = client.get("/auth/login", headers={"host": "attacker.example"})
            assert rejected.status_code == 400

    reset_settings_cache()
    _reload_web()
