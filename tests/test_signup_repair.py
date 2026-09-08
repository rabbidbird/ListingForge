"""Production-signup Google path regressions through the real OAuth boundaries."""

from __future__ import annotations

import html
import importlib
import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
import streamlit as st
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

import core.ui
from core.auth import get_user_by_session_token
from core.config import reset_settings_cache
from core.database import session_scope
from core.models import User
from core.utils import get_history


def _reload_web():
    import core.web

    return importlib.reload(core.web)


def _configure_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
    reset_settings_cache()
    return _reload_web()


def _signup_google_href(page: str) -> str:
    match = re.search(r'<a class="button google" href="([^"]+)">', page)
    assert match is not None
    return html.unescape(match.group(1))


def _oauth_start(client: TestClient, href: str) -> tuple[str, str]:
    start = client.get(href, follow_redirects=False)
    assert start.status_code == 302
    query = parse_qs(urlparse(start.headers["location"]).query)
    assert query["client_id"] == ["google-client-id.apps.googleusercontent.com"]
    return query["state"][0], query["nonce"][0]


def _mock_google_token_boundaries(monkeypatch, web, claims: dict[str, object]) -> dict[str, object]:
    captured: dict[str, object] = {}

    class TokenResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id_token": "signed-id-token-from-google"}

    def post(url, *, data, timeout):
        captured.update({"url": url, "data": data, "timeout": timeout})
        return TokenResponse()

    def verify(token, request, audience):
        captured.update({"id_token": token, "request": request, "audience": audience})
        return claims

    monkeypatch.setattr(web.requests, "post", post)
    monkeypatch.setattr(web.google_id_token, "verify_oauth2_token", verify)
    return captured


@pytest.mark.parametrize(
    ("requested_plan", "expected_plan"),
    [
        ("", ""),
        ("free", "free"),
        ("starter", "starter"),
        ("pro", "pro"),
        ("agency", "agency"),
        ("attacker", ""),
    ],
)
def test_rendered_production_signup_google_href_is_followable_for_each_intent(
    monkeypatch, requested_plan, expected_plan
):
    """Assert the exact rendered href, then follow that href through the OAuth start route."""

    with monkeypatch.context() as production:
        production.setenv("ENV", "production")
        production.setenv("DATABASE_URL", "postgresql://user:pass@db/sellerdrafts")
        production.setenv("PUBLIC_BASE_URL", "https://sellerdrafts.example")
        production.setenv("SESSION_SECRET", "unique-production-session-secret-2026-08-27")
        production.setenv("SESSION_COOKIE_SECURE", "true")
        production.setenv("GOOGLE_CLIENT_ID", "google-client-id.apps.googleusercontent.com")
        production.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
        reset_settings_cache()
        production_web = _reload_web()
        path = "/auth/signup" + (f"?plan={requested_plan}" if requested_plan else "")
        with TestClient(production_web.app) as client:
            href = _signup_google_href(
                client.get(path, headers={"host": "sellerdrafts.example"}).text
            )

    reset_settings_cache()
    web = _configure_google(monkeypatch)
    with TestClient(web.app) as client:
        state, _nonce = _oauth_start(client, href)
        packed = web._unpack_google_oauth(state)

    assert parse_qs(urlparse(href).query, keep_blank_values=True) == {
        "origin": ["signup"],
        "plan": [expected_plan],
    }
    assert packed is not None
    assert packed["plan"] == expected_plan
    assert packed["signup_origin"] is True


@pytest.mark.parametrize("plan", ["", "free", "starter", "pro", "agency"])
def test_google_signup_callback_uses_token_and_id_token_verification_boundaries(monkeypatch, plan):
    web = _configure_google(monkeypatch)
    with TestClient(web.app) as client:
        signup_href = _signup_google_href(client.get(f"/auth/signup?plan={plan}").text)
        state, nonce = _oauth_start(client, signup_href)
        captured = _mock_google_token_boundaries(
            monkeypatch,
            web,
            {
                "sub": "signup-boundary-subject",
                "email": "signup-boundary@example.com",
                "email_verified": True,
                "name": "Signup Boundary",
                "nonce": nonce,
            },
        )
        callback = client.get(
            f"/auth/google/callback?state={state}&code=authorization-code",
            follow_redirects=False,
        )
        session_token = client.cookies.get(web.settings.session_cookie_name)

    assert callback.status_code == 303
    expected = (
        f"/app/About_Pricing?plan={plan}"
        if plan in {"starter", "pro", "agency"}
        else "/app/Optimizer"
    )
    assert callback.headers["location"] == expected
    assert captured["url"] == "https://oauth2.googleapis.com/token"
    assert captured["data"] == {
        "code": "authorization-code",
        "client_id": "google-client-id.apps.googleusercontent.com",
        "client_secret": "google-client-secret",
        "redirect_uri": "http://localhost:8080/auth/google/callback",
        "grant_type": "authorization_code",
    }
    assert captured["timeout"] == 10
    assert captured["id_token"] == "signed-id-token-from-google"
    assert captured["audience"] == "google-client-id.apps.googleusercontent.com"
    if plan == "free":
        with session_scope() as session:
            user = get_user_by_session_token(session, session_token)
            assert user is not None
        monkeypatch.setattr(
            st,
            "context",
            SimpleNamespace(cookies={web.settings.session_cookie_name: session_token}),
        )
        app = AppTest.from_file("app.py").run(timeout=15)
        app.switch_page("pages/1_Optimizer.py").run(timeout=15)
        next(item for item in app.text_input if item.label == "Product name *").set_value(
            "5 x 5 inch print"
        )
        next(item for item in app.button if item.label == "Generate fact-locked draft").click()
        app.run(timeout=15)
        assert not app.exception
        assert get_history(user.id)[0]["best_title"] == "5 X 5 Inch Print"
        history = app.switch_page("pages/4_History.py").run(timeout=15)
        assert not history.exception
        assert any("5 X 5 Inch Print" in str(item.value) for item in history.markdown)


def test_google_callback_rejects_state_and_nonce_before_account_mutation(monkeypatch):
    web = _configure_google(monkeypatch)
    with TestClient(web.app) as client:
        calls = _mock_google_token_boundaries(monkeypatch, web, {})
        forged = client.get("/auth/google/callback?state=forged&code=code", follow_redirects=False)
        assert forged.status_code == 400
        assert calls == {}

        state, nonce = _oauth_start(client, "/auth/google?origin=signup&plan=free")
        _mock_google_token_boundaries(
            monkeypatch,
            web,
            {
                "sub": "bad-nonce-subject",
                "email": "bad-nonce@example.com",
                "email_verified": True,
                "name": "Bad Nonce",
                "nonce": nonce + "wrong",
            },
        )
        callback = client.get(
            f"/auth/google/callback?state={state}&code=authorization-code",
            follow_redirects=False,
        )

    assert callback.status_code == 400
    with session_scope() as session:
        assert session.query(User).filter_by(email="bad-nonce@example.com").count() == 0


def test_google_subject_reuse_never_auto_links_password_accounts(monkeypatch, user_factory):
    web = _configure_google(monkeypatch)
    with TestClient(web.app) as first_client:
        state, nonce = _oauth_start(first_client, "/auth/google?origin=signup")
        _mock_google_token_boundaries(
            monkeypatch,
            web,
            {
                "sub": "reused-subject",
                "email": "reused-google@example.com",
                "email_verified": True,
                "name": "First Google User",
                "nonce": nonce,
            },
        )
        assert (
            first_client.get(
                f"/auth/google/callback?state={state}&code=first-code", follow_redirects=False
            ).status_code
            == 303
        )

    with TestClient(web.app) as second_client:
        state, nonce = _oauth_start(second_client, "/auth/google?origin=signup")
        _mock_google_token_boundaries(
            monkeypatch,
            web,
            {
                "sub": "reused-subject",
                "email": "changed-google-email@example.com",
                "email_verified": True,
                "name": "Returning Google User",
                "nonce": nonce,
            },
        )
        assert (
            second_client.get(
                f"/auth/google/callback?state={state}&code=second-code", follow_redirects=False
            ).status_code
            == 303
        )

    password_user = user_factory(email="password-only@example.com")
    with TestClient(web.app) as password_client:
        state, nonce = _oauth_start(password_client, "/auth/google?origin=signup")
        _mock_google_token_boundaries(
            monkeypatch,
            web,
            {
                "sub": "password-account-subject",
                "email": password_user.email,
                "email_verified": True,
                "name": "Password Account",
                "nonce": nonce,
            },
        )
        rejected = password_client.get(
            f"/auth/google/callback?state={state}&code=password-code", follow_redirects=False
        )

    assert rejected.status_code == 400
    with session_scope() as session:
        reused = session.query(User).filter_by(google_subject="reused-subject").one()
        assert reused.email == "reused-google@example.com"
        assert session.get(User, password_user.id).google_subject is None


def test_authenticated_matching_email_google_link_and_streamlit_generation_use_session_cookie(
    monkeypatch, user_factory
):
    """Keep auth real: the Streamlit page resolves the opaque cookie, not a user bypass."""

    user = user_factory(email="streamlit-cookie@example.com")
    web = _configure_google(monkeypatch)
    with TestClient(web.app) as client:
        login_page = client.get("/auth/login")
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', login_page.text)
        assert csrf is not None
        login = client.post(
            "/auth/login",
            data={
                "csrf_token": csrf.group(1),
                "email": user.email,
                "password": "correct horse battery staple",
            },
            follow_redirects=False,
        )
        token_match = re.search(r"truedraft_session=([^;]+)", login.headers["set-cookie"])
        assert token_match is not None
        original_token = token_match.group(1)

        account = client.get("/auth/account")
        account_csrf = re.search(r'name="csrf_token" value="([^"]+)"', account.text)
        assert account_csrf is not None
        start = client.post(
            "/auth/google/link",
            data={"csrf_token": account_csrf.group(1)},
            follow_redirects=False,
        )
        query = parse_qs(urlparse(start.headers["location"]).query)
        state, nonce = query["state"][0], query["nonce"][0]
        _mock_google_token_boundaries(
            monkeypatch,
            web,
            {
                "sub": "streamlit-linked-subject",
                "email": user.email,
                "email_verified": True,
                "name": "Streamlit Cookie",
                "nonce": nonce,
            },
        )
        linked = client.get(
            f"/auth/google/callback?state={state}&code=link-code", follow_redirects=False
        )
        new_token_match = re.search(r"truedraft_session=([^;]+)", linked.headers["set-cookie"])
        assert linked.status_code == 303
        assert new_token_match is not None
        session_token = new_token_match.group(1)

    with session_scope() as session:
        assert get_user_by_session_token(session, original_token) is None
        current = get_user_by_session_token(session, session_token)
        assert current is not None and current.id == user.id

    # AppTest cannot own an HTTP cookie jar. Supplying the actual opaque token to
    # Streamlit's request context exercises require_streamlit_user unchanged.
    monkeypatch.setattr(
        st, "context", SimpleNamespace(cookies={"truedraft_session": session_token})
    )
    monkeypatch.setattr(core.ui.st, "page_link", lambda *_args, **_kwargs: None)
    app = AppTest.from_file("pages/1_Optimizer.py").run(timeout=15)
    assert not app.exception
    next(item for item in app.text_input if item.label == "Product name *").set_value("Cookie mug")
    next(item for item in app.button if item.label == "Generate fact-locked draft").click()
    app.run(timeout=15)

    assert not app.exception
    assert get_history(user.id, limit=10)[0]["product_name"] == "Cookie mug"
