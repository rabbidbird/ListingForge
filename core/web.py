"""FastAPI edge for secure auth cookies, health checks, and Stripe webhooks."""

from __future__ import annotations

import html
import secrets
import threading
import time
from collections import OrderedDict, deque
from urllib.parse import urlparse

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .auth import (
    AuthError,
    authenticate_user,
    create_user_session,
    get_user_by_session_token,
    register_user,
    revoke_user_session,
)
from .billing import BillingError, WebhookVerificationError, handle_webhook
from .config import get_settings
from .database import session_scope
from .migrate import database_at_migration_head
from .models import User

settings = get_settings()
settings.validate_for_production()
app = FastAPI(title="TrueDraft edge", docs_url=None, redoc_url=None, openapi_url=None)


def _trusted_hosts() -> list[str]:
    if not settings.is_production:
        return ["*"]
    public_host = urlparse(settings.public_base_url).hostname
    return [host for host in (public_host, "127.0.0.1", "localhost") if host]


app.add_middleware(TrustedHostMiddleware, allowed_hosts=_trusted_hosts(), www_redirect=False)

_AUTH_WINDOW_SECONDS = 600
_AUTH_REQUESTS_PER_WINDOW = 40
_AUTH_IP_BUCKET_LIMIT = 10_000
_ip_requests: OrderedDict[str, deque[float]] = OrderedDict()
_ip_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    # nginx overwrites X-Real-IP, so clients cannot choose this value in production.
    return request.headers.get("x-real-ip") or (
        request.client.host if request.client else "unknown"
    )


@app.middleware("http")
async def security_and_soft_limit(request: Request, call_next):
    if request.url.path.startswith("/auth/"):
        now = time.monotonic()
        key = _client_ip(request)
        with _ip_lock:
            requests = _ip_requests.setdefault(key, deque())
            _ip_requests.move_to_end(key)
            while requests and requests[0] <= now - _AUTH_WINDOW_SECONDS:
                requests.popleft()
            if len(requests) >= _AUTH_REQUESTS_PER_WINDOW:
                return JSONResponse(
                    {"detail": "Too many authentication requests. Try again later."},
                    status_code=429,
                    headers={"Retry-After": str(_AUTH_WINDOW_SECONDS)},
                )
            requests.append(now)
            while len(_ip_requests) > _AUTH_IP_BUCKET_LIMIT:
                _ip_requests.popitem(last=False)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'self'"
    )
    return response


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} | TrueDraft</title>
<style>
body{{margin:0;background:#0f172a;color:#f1f5f9;font-family:system-ui,sans-serif}}
main{{max-width:440px;margin:7vh auto;padding:2rem;background:#1e293b;border:1px solid #334155;border-radius:14px}}
h1{{margin-top:0}}label{{display:block;margin:.9rem 0 .35rem}}input[type=text],input[type=email],input[type=password]{{box-sizing:border-box;width:100%;padding:.75rem;border:1px solid #64748b;border-radius:8px;background:#0f172a;color:#fff}}
button{{width:100%;margin-top:1.2rem;padding:.8rem;border:0;border-radius:8px;background:#818cf8;color:#0f172a;font-weight:700;cursor:pointer}}
a{{color:#a5b4fc}}.error{{padding:.75rem;background:#7f1d1d;border-radius:8px}}.note{{color:#cbd5e1;font-size:.9rem}}.check{{display:flex;gap:.6rem;align-items:flex-start;margin-top:1rem}}.check label{{margin:0}}
</style></head><body><main><p><a href="/">← TrueDraft</a></p>{body}</main></body></html>"""


def _csrf_response(title: str, body_template: str, *, status_code: int = 200) -> HTMLResponse:
    token = secrets.token_urlsafe(32)
    escaped_token = html.escape(token, quote=True)
    body = body_template.replace("{{CSRF}}", escaped_token).replace("{CSRF}", escaped_token)
    response = HTMLResponse(
        _page(title, body),
        status_code=status_code,
    )
    response.set_cookie(
        "truedraft_csrf",
        token,
        max_age=3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/auth",
    )
    return response


def _valid_csrf(request: Request, form_token: str) -> bool:
    cookie_token = request.cookies.get("truedraft_csrf", "")
    return bool(cookie_token and form_token and secrets.compare_digest(cookie_token, form_token))


def _set_session_cookie(response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_days * 86_400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _current_request_user(request: Request) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    with session_scope() as session:
        return get_user_by_session_token(session, token)


LOGIN_FORM = """
<h1>Sign in</h1>
<p class="note">Fact-locked drafts from facts you supply. TrueDraft does not publish to marketplaces or promise ranking.</p>
{error}
<form method="post" action="/auth/login">
<input type="hidden" name="csrf_token" value="{{CSRF}}">
<label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" required value="{email}">
<label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" maxlength="128" required>
<button type="submit">Sign in</button>
</form>
<p class="note">New here? <a href="/auth/signup">Create an account</a>. <a href="/">Back to home</a>.</p>
"""

SIGNUP_FORM = """
<h1>Create your account</h1>
<p class="note">Fact-locked drafts from facts you supply. TrueDraft does not publish to marketplaces or promise ranking.</p>
{error}
<form method="post" action="/auth/signup">
<input type="hidden" name="csrf_token" value="{{CSRF}}">
<label for="name">Name</label><input id="name" name="name" type="text" autocomplete="name" maxlength="120" required value="{name}">
<label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" required value="{email}">
<label for="password">Password</label><input id="password" name="password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required>
<div class="check"><input id="terms" name="accepted_terms" type="checkbox" value="true" required><label for="terms">I accept the <a href="/Legal" target="_blank">Terms of Service and Privacy Policy</a>.</label></div>
<button type="submit">Create account</button>
</form>
<p class="note">Already registered? <a href="/auth/login">Sign in</a>. <a href="/">Back to home</a>.</p>
"""


@app.get("/auth/login", response_class=HTMLResponse)
def login_page(request: Request):
    if _current_request_user(request):
        return RedirectResponse("/", status_code=303)
    return _csrf_response("Sign in", LOGIN_FORM.format(error="", email=""))


@app.post("/auth/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    if not _valid_csrf(request, csrf_token):
        return _csrf_response(
            "Sign in",
            LOGIN_FORM.format(
                error='<p class="error">This form expired. Please try again.</p>',
                email=html.escape(email, quote=True),
            ),
            status_code=400,
        )
    try:
        with session_scope() as session:
            user = authenticate_user(session, email=email, password=password)
            if user is None:
                raise AuthError("Email or password is incorrect.")
            token = create_user_session(session, user.id)
    except AuthError:
        return _csrf_response(
            "Sign in",
            LOGIN_FORM.format(
                error='<p class="error">Email or password is incorrect.</p>',
                email=html.escape(email, quote=True),
            ),
            status_code=400,
        )
    response = RedirectResponse("/", status_code=303)
    _set_session_cookie(response, token)
    return response


@app.get("/auth/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    if _current_request_user(request):
        return RedirectResponse("/", status_code=303)
    return _csrf_response("Create account", SIGNUP_FORM.format(error="", name="", email=""))


@app.post("/auth/signup")
def signup(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    accepted_terms: str | None = Form(None),
):
    safe_name = html.escape(name, quote=True)
    safe_email = html.escape(email, quote=True)
    if not _valid_csrf(request, csrf_token):
        return _csrf_response(
            "Create account",
            SIGNUP_FORM.format(
                error='<p class="error">This form expired. Please try again.</p>',
                name=safe_name,
                email=safe_email,
            ),
            status_code=400,
        )
    try:
        with session_scope() as session:
            user = register_user(
                session,
                email=email,
                password=password,
                name=name,
                accepted_terms=accepted_terms == "true",
            )
            token = None
            if not settings.email_verification_required:
                token = create_user_session(session, user.id)
    except AuthError:
        return _csrf_response(
            "Create account",
            SIGNUP_FORM.format(
                error=(
                    '<p class="error">Account creation failed. Check the supplied '
                    "details or use a different email.</p>"
                ),
                name=safe_name,
                email=safe_email,
            ),
            status_code=400,
        )
    if token is None:
        return HTMLResponse(
            _page(
                "Verify email",
                "<h1>Check your email</h1><p>Email verification is enabled. "
                "Delivery is an operator-configured v1 stub; contact support if no link arrives.</p>",
            ),
            status_code=202,
        )
    response = RedirectResponse("/", status_code=303)
    _set_session_cookie(response, token)
    return response


@app.get("/auth/logout", response_class=HTMLResponse)
def logout_page():
    body = """
<h1>Log out?</h1><form method="post" action="/auth/logout"><input type="hidden" name="csrf_token" value="{{CSRF}}"><button type="submit">Log out</button></form>
"""
    return _csrf_response("Log out", body)


@app.post("/auth/logout")
def logout(request: Request, csrf_token: str = Form(...)):
    if not _valid_csrf(request, csrf_token):
        return JSONResponse({"detail": "Invalid CSRF token."}, status_code=400)
    token = request.cookies.get(settings.session_cookie_name)
    with session_scope() as session:
        revoke_user_session(session, token)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie("truedraft_csrf", path="/auth")
    return response


@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        result = handle_webhook(payload, signature)
    except WebhookVerificationError:
        return JSONResponse({"detail": "Invalid Stripe webhook signature."}, status_code=400)
    except BillingError:
        return JSONResponse({"detail": "Webhook could not be processed."}, status_code=400)
    return JSONResponse(result)


@app.get("/healthz")
def healthz():
    try:
        with session_scope() as session:
            session.scalar(select(func.count()).select_from(User))
            if not database_at_migration_head(session):
                raise RuntimeError("Database schema is not at the expected migration head.")
    except Exception:
        return JSONResponse({"status": "unhealthy"}, status_code=503)
    return {"status": "ok"}
