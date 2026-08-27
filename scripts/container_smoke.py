"""Exercise the deployed nginx/Auth/Stripe/Streamlit edge inside Compose."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
import uuid

import httpx
from websockets.sync.client import connect

BASE_URL = os.getenv("CONTAINER_SMOKE_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _csrf(page: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', page)
    if match is None:
        raise AssertionError("Authentication page did not contain a CSRF token.")
    return match.group(1)


def _stripe_signature(payload: bytes, timestamp: int) -> str:
    _require(bool(WEBHOOK_SECRET), "STRIPE_WEBHOOK_SECRET is required for container smoke.")
    signed = f"{timestamp}.".encode() + payload
    digest = hmac.new(WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def _websocket_smoke(client: httpx.Client) -> None:
    websocket_url = re.sub(r"^http", "ws", BASE_URL) + "/_stcore/stream"
    cookie_header = "; ".join(f"{name}={value}" for name, value in client.cookies.items())
    with connect(
        websocket_url,
        origin=BASE_URL,
        subprotocols=["streamlit"],
        additional_headers={"Cookie": cookie_header},
        open_timeout=10,
        close_timeout=5,
        proxy=None,
    ) as websocket:
        _require(websocket.subprotocol == "streamlit", "Streamlit WebSocket was not upgraded.")


def main() -> None:
    with httpx.Client(base_url=BASE_URL, follow_redirects=False, timeout=15) as client:
        health = client.get("/healthz")
        _require(health.status_code == 200, "Migrated database health check failed.")
        _require(health.json() == {"status": "ok"}, "Unexpected health response.")

        signup_page = client.get("/auth/signup")
        _require(signup_page.status_code == 200, "Signup page is not reachable through nginx.")
        signup = client.post(
            "/auth/signup",
            data={
                "csrf_token": _csrf(signup_page.text),
                "name": "Container Smoke",
                "email": f"container-smoke-{uuid.uuid4().hex}@example.com",
                "password": "container smoke password 2026",
                "accepted_terms": "true",
            },
        )
        _require(signup.status_code == 303, "Signup did not create an authenticated session.")
        set_cookie = signup.headers.get("set-cookie", "")
        _require("truedraft_session=" in set_cookie, "Signup did not set a session cookie.")
        _require("HttpOnly" in set_cookie, "Session cookie is not HttpOnly.")

        authenticated_login = client.get("/auth/login")
        _require(authenticated_login.status_code == 303, "Session is not recognized after signup.")
        home = client.get("/")
        _require(home.status_code == 200, "Streamlit is not reachable through nginx.")
        _websocket_smoke(client)

        event_id = f"evt_container_smoke_{uuid.uuid4().hex}"
        payload = json.dumps(
            {
                "id": event_id,
                "object": "event",
                "type": "container.smoke",
                "created": int(time.time()),
                "data": {"object": {}},
            },
            separators=(",", ":"),
        ).encode()
        timestamp = int(time.time())
        headers = {
            "content-type": "application/json",
            "stripe-signature": _stripe_signature(payload, timestamp),
        }
        webhook = client.post("/webhooks/stripe", content=payload, headers=headers)
        _require(
            webhook.status_code == 200,
            f"Signed webhook was rejected through nginx: {webhook.status_code} {webhook.text[:200]}",
        )
        _require(webhook.json().get("duplicate") is False, "New webhook was not processed.")
        duplicate = client.post("/webhooks/stripe", content=payload, headers=headers)
        _require(duplicate.status_code == 200, "Webhook retry was rejected.")
        _require(duplicate.json().get("duplicate") is True, "Webhook retry was not idempotent.")

        logout_page = client.get("/auth/logout")
        logout = client.post("/auth/logout", data={"csrf_token": _csrf(logout_page.text)})
        _require(logout.status_code == 303, "Logout failed through nginx.")
        _require(
            client.get("/auth/login").status_code == 200, "Session remained active after logout."
        )

    print("SellerDrafts container edge smoke passed")


if __name__ == "__main__":
    main()
