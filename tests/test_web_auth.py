from __future__ import annotations

import importlib
import re
from urllib.parse import parse_qs, urlparse

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from core.auth import AuthError, get_user_by_session_token
from core.billing import WebhookVerificationError
from core.config import reset_settings_cache
from core.copy import forbidden_claims_in
from core.database import session_scope
from core.legal import CONTACT_EMAIL, OPERATOR_NAME, TERMS_VERSION
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
        assert "SellerDrafts" in page.text
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


def test_password_signup_preserves_allowlisted_plan_and_rejects_arbitrary_intent():
    web = _reload_web()
    with TestClient(web.app) as client:
        page = client.get("/auth/signup?plan=starter")
        assert 'name="plan" value="starter"' in page.text
        response = client.post(
            "/auth/signup",
            data={
                "csrf_token": _csrf(page.text),
                "name": "Starter Intent",
                "email": "starter-intent@example.com",
                "password": "correct horse battery staple",
                "accepted_terms": "true",
                "plan": "starter",
            },
            follow_redirects=False,
        )
        assert response.headers["location"] == "/app/About_Pricing?plan=starter"

    web = _reload_web()
    with TestClient(web.app) as client:
        arbitrary = client.get("/auth/signup?plan=https://attacker.example")
        assert 'name="plan" value=""' in arbitrary.text
        assert web._plan_intent("https://attacker.example") == ""


def test_public_marketing_routes_are_server_rendered_and_indexable():
    web = _reload_web()
    with TestClient(web.app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "<title>Etsy Listing Draft Generator | SellerDrafts</title>" in home.text
        assert '<link rel="canonical" href="http://localhost:8080/">' in home.text
        assert 'type="application/ld+json"' in home.text
        assert "Etsy listing drafts that stay inside the facts" in home.text
        assert "DRAFT — verify before publishing" in home.text
        assert "Streamlit" not in home.text
        assert forbidden_claims_in(home.text) == []

        for path in (
            "/pricing",
            "/legal",
            "/guides/etsy-listing-draft-checklist",
            "/guides/write-etsy-listings-without-inventing-facts",
            "/guides/etsy-title-description-and-tags-checklist",
        ):
            page = client.get(path)
            assert page.status_code == 200
            assert '<link rel="canonical"' in page.text
            assert "SellerDrafts" in page.text
            assert forbidden_claims_in(page.text) == []


def test_robots_and_sitemap_expose_only_public_canonical_routes():
    web = _reload_web()
    with TestClient(web.app) as client:
        robots = client.get("/robots.txt")
        assert robots.status_code == 200
        assert robots.headers["content-type"].startswith("text/plain")
        assert "User-agent: OAI-SearchBot" in robots.text
        assert "User-agent: GPTBot\nDisallow: /" in robots.text
        assert "Disallow: /app/" in robots.text
        assert "Sitemap: http://localhost:8080/sitemap.xml" in robots.text

        sitemap = client.get("/sitemap.xml")
        assert sitemap.status_code == 200
        assert sitemap.headers["content-type"].startswith("application/xml")
        assert "http://localhost:8080/pricing" in sitemap.text
        assert "/guides/etsy-listing-draft-checklist" in sitemap.text
        assert "/auth/" not in sitemap.text
        assert "/app/" not in sitemap.text
        assert "<lastmod>" not in sitemap.text


def test_first_touch_attribution_is_not_overwritten_by_later_campaign():
    web = _reload_web()
    with TestClient(web.app) as client:
        client.get("/?utm_source=first&utm_campaign=founding")
        first_cookie = client.cookies.get("sellerdrafts_attribution")
        assert first_cookie
        second = client.get("/?utm_source=second&utm_campaign=retargeting")
        assert "sellerdrafts_attribution" not in second.headers.get("set-cookie", "")
        assert client.cookies.get("sellerdrafts_attribution") == first_cookie


def test_tagged_signup_persists_signed_first_touch_attribution():
    web = _reload_web()
    with TestClient(web.app) as client:
        landing = client.get(
            "/?utm_source=x&utm_medium=paid-social&utm_campaign=launch&utm_content=truth-demo"
        )
        assert "sellerdrafts_attribution" in landing.headers["set-cookie"]
        assert "HttpOnly" in landing.headers["set-cookie"]
        signup_page = client.get("/auth/signup")
        response = client.post(
            "/auth/signup",
            data={
                "csrf_token": _csrf(signup_page.text),
                "name": "Campaign User",
                "email": "campaign@example.com",
                "password": "correct horse battery staple",
                "accepted_terms": "true",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    with session_scope() as session:
        user = session.query(User).filter_by(email="campaign@example.com").one()
        assert user.acquisition_source == "x"
        assert user.acquisition_medium == "paid-social"
        assert user.acquisition_campaign == "launch"
        assert user.acquisition_content == "truth-demo"
        assert user.acquisition_landing_path == "/"


def test_tampered_attribution_cookie_is_ignored():
    web = _reload_web()
    with TestClient(web.app) as client:
        client.cookies.set("sellerdrafts_attribution", "forged")
        signup_page = client.get("/auth/signup")
        response = client.post(
            "/auth/signup",
            data={
                "csrf_token": _csrf(signup_page.text),
                "name": "Unattributed User",
                "email": "unattributed@example.com",
                "password": "correct horse battery staple",
                "accepted_terms": "true",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    with session_scope() as session:
        user = session.query(User).filter_by(email="unattributed@example.com").one()
        assert user.acquisition_source is None


def test_password_login_still_sets_session_cookie(user_factory):
    user_factory(email="password-login@example.com")
    web = _reload_web()
    with TestClient(web.app) as client:
        page = client.get("/auth/login")
        response = client.post(
            "/auth/login",
            data={
                "csrf_token": _csrf(page.text),
                "email": "password-login@example.com",
                "password": "correct horse battery staple",
            },
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert "truedraft_session" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]


def test_google_button_is_hidden_without_configuration():
    web = _reload_web()
    with TestClient(web.app) as client:
        assert "Sign in with Google" not in client.get("/auth/login").text
        assert "Sign in with Google" not in client.get("/auth/signup").text
        assert client.get("/auth/google", follow_redirects=False).status_code == 404


def test_google_callback_rejects_missing_or_forged_state(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
    reset_settings_cache()
    web = _reload_web()
    with TestClient(web.app) as client:
        missing = client.get("/auth/google/callback?code=fake")
        assert missing.status_code == 400
        assert "expired or is invalid" in missing.text

        start = client.get("/auth/google", follow_redirects=False)
        assert start.status_code == 302
        forged = client.get("/auth/google/callback?state=forged&code=fake")
        assert forged.status_code == 400
        assert "fake" not in forged.text
        assert client.cookies.get("sellerdrafts_google_oauth") is None


def test_google_callback_rejects_mismatched_browser_state_cookie(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
    reset_settings_cache()
    web = _reload_web()

    with TestClient(web.app) as client:
        start = client.get("/auth/google", follow_redirects=False)
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
        client.cookies.set(
            "sellerdrafts_google_oauth",
            "different-browser-state",
            path="/auth/google",
        )
        callback = client.get(
            f"/auth/google/callback?state={state}&code=mock-code",
            follow_redirects=False,
        )
        assert callback.status_code == 400
        assert "sellerdrafts_google_oauth=" in callback.headers.get("set-cookie", "")
        assert "Max-Age=0" in callback.headers.get("set-cookie", "")


def test_google_login_does_not_auto_link_existing_email(monkeypatch, user_factory):
    existing = user_factory(email="linked@example.com")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
    reset_settings_cache()
    web = _reload_web()

    with TestClient(web.app) as client:
        start = client.get("/auth/google", follow_redirects=False)
        query = parse_qs(urlparse(start.headers["location"]).query)
        state = query["state"][0]
        nonce = query["nonce"][0]
        monkeypatch.setattr(
            web,
            "_google_token_claims",
            lambda _code: {
                "sub": "google-subject-123",
                "email": "linked@example.com",
                "email_verified": True,
                "name": "Linked User",
                "nonce": nonce,
            },
        )
        callback = client.get(
            f"/auth/google/callback?state={state}&code=mock-code",
            follow_redirects=False,
        )

    assert callback.status_code == 400
    assert "link Google from Account" in callback.text
    assert "truedraft_session" not in callback.headers.get("set-cookie", "")
    with session_scope() as session:
        users = session.query(User).filter_by(email="linked@example.com").all()
        assert len(users) == 1
        assert users[0].id == existing.id
        assert users[0].google_subject is None


def test_google_new_account_preserves_allowlisted_plan_and_current_terms(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
    reset_settings_cache()
    web = _reload_web()

    with TestClient(web.app) as client:
        start = client.get("/auth/google?plan=starter", follow_redirects=False)
        query = parse_qs(urlparse(start.headers["location"]).query)
        state = query["state"][0]
        nonce = query["nonce"][0]
        packed = web._unpack_google_oauth(state)
        assert packed is not None and packed["plan"] == "starter"
        monkeypatch.setattr(
            web,
            "_google_token_claims",
            lambda _code: {
                "sub": "new-google-subject",
                "email": "new-google@example.com",
                "email_verified": True,
                "name": "New Google User",
                "nonce": nonce,
            },
        )
        callback = client.get(
            f"/auth/google/callback?state={state}&code=mock-code",
            follow_redirects=False,
        )

    assert callback.status_code == 303
    assert callback.headers["location"] == "/app/About_Pricing?plan=starter"
    assert "truedraft_session" in callback.headers["set-cookie"]
    assert "sellerdrafts_google_oauth=" in callback.headers["set-cookie"]
    with session_scope() as session:
        user = session.query(User).filter_by(email="new-google@example.com").one()
        assert user.terms_version == TERMS_VERSION


def test_google_link_requires_auth_and_matching_account(monkeypatch, user_factory):
    user_factory(email="link-web@example.com")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
    reset_settings_cache()
    web = _reload_web()

    with TestClient(web.app) as anonymous:
        assert (
            anonymous.post(
                "/auth/google/link",
                data={"csrf_token": "x"},
                follow_redirects=False,
            ).status_code
            == 303
        )

    with TestClient(web.app) as client:
        login_page = client.get("/auth/login")
        login = client.post(
            "/auth/login",
            data={
                "csrf_token": _csrf(login_page.text),
                "email": "link-web@example.com",
                "password": "correct horse battery staple",
            },
            follow_redirects=False,
        )
        original_cookie = re.search(r"truedraft_session=([^;]+)", login.headers["set-cookie"])
        assert original_cookie is not None
        account = client.get("/auth/account")
        start = client.post(
            "/auth/google/link",
            data={"csrf_token": _csrf(account.text)},
            follow_redirects=False,
        )
        query = parse_qs(urlparse(start.headers["location"]).query)
        state = query["state"][0]
        nonce = query["nonce"][0]
        assert web._unpack_google_oauth(state)["mode"] == "link"
        monkeypatch.setattr(
            web,
            "_google_token_claims",
            lambda _code: {
                "sub": "linked-web-subject",
                "email": "link-web@example.com",
                "email_verified": True,
                "name": "Link Web",
                "nonce": nonce,
            },
        )
        callback = client.get(
            f"/auth/google/callback?state={state}&code=mock-code",
            follow_redirects=False,
        )
        assert callback.status_code == 303
        assert "truedraft_session" in callback.headers["set-cookie"]

    with session_scope() as session:
        linked = session.query(User).filter_by(email="link-web@example.com").one()
        assert linked.google_subject == "linked-web-subject"
        assert get_user_by_session_token(session, original_cookie.group(1)) is None


def test_production_password_signup_is_disabled(monkeypatch):
    with monkeypatch.context() as production:
        production.setenv("ENV", "production")
        production.setenv("DATABASE_URL", "postgresql://user:pass@db/sellerdrafts")
        production.setenv("PUBLIC_BASE_URL", "https://sellerdrafts.example")
        production.setenv("SESSION_SECRET", "unique-production-session-secret-2026-08-27")
        production.setenv("SESSION_COOKIE_SECURE", "true")
        production.setenv("GOOGLE_CLIENT_ID", "google-client-id.apps.googleusercontent.com")
        production.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
        reset_settings_cache()
        web = _reload_web()
        with TestClient(web.app) as client:
            request_headers = {"host": "sellerdrafts.example"}
            page = client.get("/auth/signup?plan=starter", headers=request_headers)
            assert page.status_code == 200
            assert 'name="password"' not in page.text
            assert "Sign in with Google" in page.text
            response = client.post(
                "/auth/signup",
                data={
                    "name": "Blocked",
                    "email": "blocked@example.com",
                    "password": "correct horse battery staple",
                    "csrf_token": "anything",
                    "accepted_terms": "true",
                    "plan": "starter",
                },
                headers=request_headers,
            )
            assert response.status_code == 403

    reset_settings_cache()
    _reload_web()


def test_stale_terms_block_and_reacceptance_updates_version(user_factory):
    user = user_factory(email="stale-terms@example.com")
    with session_scope() as session:
        session.get(User, user.id).terms_version = "2026-08-15"
    web = _reload_web()

    with TestClient(web.app) as client:
        login_page = client.get("/auth/login")
        login = client.post(
            "/auth/login",
            data={
                "csrf_token": _csrf(login_page.text),
                "email": "stale-terms@example.com",
                "password": "correct horse battery staple",
            },
            follow_redirects=False,
        )
        assert login.headers["location"].startswith("/auth/terms?")
        assert (
            client.get("/", follow_redirects=False).headers["location"].startswith("/auth/terms?")
        )
        terms = client.get("/auth/terms?next=/app/")
        accepted = client.post(
            "/auth/terms",
            data={
                "csrf_token": _csrf(terms.text),
                "accepted_terms": "true",
                "next": "/app/",
            },
            follow_redirects=False,
        )
        assert accepted.status_code == 303
        assert accepted.headers["location"] == "/app/"

    with session_scope() as session:
        stored = session.get(User, user.id)
        assert stored.terms_version == TERMS_VERSION
        assert stored.terms_accepted_at is not None


def test_public_and_authenticated_legal_use_canonical_identity_and_version():
    from core.marketing import legal_page

    rendered = legal_page()
    assert OPERATOR_NAME in rendered
    assert CONTACT_EMAIL in rendered
    assert "August 27, 2026" in rendered


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
