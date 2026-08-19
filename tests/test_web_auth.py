from __future__ import annotations

import importlib
import re

from fastapi.testclient import TestClient

from core.auth import get_user_by_session_token
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
