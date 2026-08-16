from __future__ import annotations

import importlib
import re

from fastapi.testclient import TestClient

from core.database import session_scope
from core.models import User


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_public_signup_sets_httponly_session_cookie():
    import core.web

    web = importlib.reload(core.web)
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
