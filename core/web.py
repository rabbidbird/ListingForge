"""FastAPI edge for secure auth cookies, health checks, and Stripe webhooks."""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import secrets
import threading
import time
from collections import OrderedDict, deque
from urllib.parse import urlencode, urlparse

import requests
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token
from sqlalchemy import func, select
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .auth import (
    AuthError,
    authenticate_user,
    create_user_session,
    get_or_create_google_user,
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
app = FastAPI(title="SellerDrafts edge", docs_url=None, redoc_url=None, openapi_url=None)


def _trusted_hosts() -> list[str]:
    if not settings.is_production:
        return ["*"]
    public_host = urlparse(settings.public_base_url).hostname
    return [host for host in (public_host, "127.0.0.1", "localhost") if host]


app.add_middleware(TrustedHostMiddleware, allowed_hosts=_trusted_hosts(), www_redirect=False)

_AUTH_WINDOW_SECONDS = 600
_AUTH_REQUESTS_PER_WINDOW = 40
_AUTH_IP_BUCKET_LIMIT = 10_000
_GOOGLE_OAUTH_COOKIE = "sellerdrafts_google_oauth"
_GOOGLE_OAUTH_MAX_AGE = 600
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
<title>{html.escape(title)} | SellerDrafts</title>
<style>
:root{{--ink:#f8fafc;--muted:#a9b7c9;--panel:#111c2e;--line:#26364c;--accent:#f4b860;--accent-dark:#152033}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;background:radial-gradient(circle at top,#162641 0,#0b1220 42%,#070c14 100%);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.55}}
.shell{{width:min(100% - 2rem,520px);margin:0 auto;padding:4vh 0 8vh}}.brand{{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.25rem;color:var(--ink);text-decoration:none;font-weight:800;letter-spacing:-.02em}}.brand span{{display:inline-grid;place-items:center;width:2rem;height:2rem;margin-right:.6rem;border-radius:.65rem;background:var(--accent);color:#182235}}
main{{padding:clamp(1.35rem,5vw,2.35rem);background:rgba(17,28,46,.96);border:1px solid var(--line);border-radius:1.25rem;box-shadow:0 24px 70px rgba(0,0,0,.32)}}
h1{{margin:.1rem 0 .5rem;font-size:clamp(1.85rem,6vw,2.45rem);line-height:1.08;letter-spacing:-.04em}}p{{margin:.7rem 0}}label{{display:block;margin:1rem 0 .4rem;font-size:.9rem;font-weight:700}}input[type=text],input[type=email],input[type=password]{{width:100%;padding:.78rem .85rem;border:1px solid #3a4b63;border-radius:.7rem;background:#0b1422;color:#fff;font:inherit;outline:none}}input:focus{{border-color:var(--accent);box-shadow:0 0 0 3px rgba(244,184,96,.15)}}
button,.button{{display:flex;align-items:center;justify-content:center;width:100%;min-height:46px;margin-top:1.1rem;padding:.72rem 1rem;border:1px solid transparent;border-radius:.72rem;background:var(--accent);color:#182235;font:inherit;font-weight:800;text-decoration:none;cursor:pointer}}button:hover,.button:hover{{filter:brightness(1.04)}}.google{{background:#fff;border-color:#747775;color:#1f1f1f;font-weight:700}}.divider{{display:flex;align-items:center;gap:.8rem;margin:1.25rem 0;color:#8494a9;font-size:.8rem;text-transform:uppercase;letter-spacing:.08em}}.divider:before,.divider:after{{content:"";height:1px;flex:1;background:var(--line)}}
a{{color:#91c8ff}}.error{{padding:.8rem 1rem;background:#511d27;border:1px solid #8b3443;border-radius:.72rem}}.note{{color:var(--muted);font-size:.9rem}}.check{{display:flex;gap:.65rem;align-items:flex-start;margin-top:1rem}}.check input{{margin-top:.25rem}}.check label{{margin:0;font-weight:500}}.fine{{margin-top:.85rem;color:#8fa0b6;font-size:.78rem;text-align:center}}.account{{padding:1rem;border:1px solid var(--line);border-radius:.8rem;background:#0c1625}}
@media (max-width:540px){{.shell{{width:min(100% - 1rem,520px);padding-top:.5rem}}main{{border-radius:1rem;padding:1.25rem}}}}
</style></head><body><div class="shell"><a class="brand" href="/"><strong><span>S</span>SellerDrafts</strong><small>Fact-locked drafts</small></a><main>{body}</main></div></body></html>"""


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


def _google_button() -> str:
    if not settings.google_configured:
        return ""
    return """
<a class="button google" href="/auth/google">Sign in with Google</a>
<div class="divider">or use email</div>
"""


def _pack_google_oauth(state: str, nonce: str) -> str:
    payload = json.dumps(
        {"state": state, "nonce": nonce, "issued_at": int(time.time())},
        separators=(",", ":"),
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    signature = hmac.new(
        settings.session_secret.encode("utf-8"),
        f"google-oauth:{encoded}".encode(),
        hashlib.sha256,
    ).digest()
    return f"{encoded}.{base64.urlsafe_b64encode(signature).decode('ascii').rstrip('=')}"


def _unpack_google_oauth(value: str | None) -> tuple[str, str] | None:
    if not value or len(value) > 2048:
        return None
    try:
        encoded, supplied_signature = value.split(".", 1)
        expected_signature = hmac.new(
            settings.session_secret.encode("utf-8"),
            f"google-oauth:{encoded}".encode(),
            hashlib.sha256,
        ).digest()
        decoded_signature = base64.urlsafe_b64decode(
            supplied_signature + "=" * (-len(supplied_signature) % 4)
        )
        if not hmac.compare_digest(decoded_signature, expected_signature):
            return None
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8")
        )
        state = payload["state"]
        nonce = payload["nonce"]
        issued_at = int(payload["issued_at"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    now = int(time.time())
    if not isinstance(state, str) or not isinstance(nonce, str):
        return None
    if issued_at > now + 60 or now - issued_at > _GOOGLE_OAUTH_MAX_AGE:
        return None
    return state, nonce


class _TimeoutSession(requests.Session):
    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", 10)
        return super().request(method, url, **kwargs)


def _google_token_claims(code: str) -> dict[str, object]:
    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    token_response.raise_for_status()
    token = token_response.json().get("id_token")
    if not isinstance(token, str) or not token:
        raise ValueError("Google did not return an ID token")
    return google_id_token.verify_oauth2_token(
        token,
        GoogleRequest(session=_TimeoutSession()),
        settings.google_client_id,
    )


def _google_error(message: str, *, status_code: int = 400) -> HTMLResponse:
    response = HTMLResponse(
        _page(
            "Google sign-in",
            f'<h1>Google sign-in</h1><p class="error">{html.escape(message)}</p>'
            '<p class="note"><a href="/auth/login">Return to sign in</a> or '
            '<a href="/auth/signup">create an account with email</a>.</p>',
        ),
        status_code=status_code,
    )
    response.delete_cookie(_GOOGLE_OAUTH_COOKIE, path="/auth/google")
    return response


LOGIN_FORM = """
<h1>Sign in</h1>
<p class="note">Fact-locked drafts from facts you supply. Return to your private History and plan usage; SellerDrafts never publishes on your behalf.</p>
{error}
{google_button}
<form method="post" action="/auth/login">
<input type="hidden" name="csrf_token" value="{{CSRF}}">
<label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" required value="{email}">
<label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" maxlength="128" required>
<button type="submit">Sign in</button>
</form>
<p class="note">New here? <a href="/auth/signup">Create an account</a>.</p>
{google_terms}
"""

SIGNUP_FORM = """
<h1>Create your account</h1>
<p class="note">Fact-locked drafts from facts you supply. SellerDrafts does not publish to marketplaces or promise rankings. Start Free, generate an Etsy-first draft, and find it later in private History.</p>
{error}
{google_button}
<form method="post" action="/auth/signup">
<input type="hidden" name="csrf_token" value="{{CSRF}}">
<label for="name">Name</label><input id="name" name="name" type="text" autocomplete="name" maxlength="120" required value="{name}">
<label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" required value="{email}">
<label for="password">Password</label><input id="password" name="password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required>
<div class="check"><input id="terms" name="accepted_terms" type="checkbox" value="true" required><label for="terms">I accept the <a href="/Legal" target="_blank">Terms of Service and Privacy Policy</a>.</label></div>
<button type="submit">Create account</button>
</form>
<p class="note">Already registered? <a href="/auth/login">Sign in</a>.</p>
{google_terms}
"""


def _login_form(*, error: str = "", email: str = "") -> str:
    google_terms = (
        '<p class="fine">If Google creates a new SellerDrafts account, continuing means you '
        'accept the <a href="/Legal" target="_blank">Terms of Service and Privacy Policy</a>.</p>'
        if settings.google_configured
        else ""
    )
    return LOGIN_FORM.format(
        error=error,
        email=email,
        google_button=_google_button(),
        google_terms=google_terms,
    )


def _signup_form(*, error: str = "", name: str = "", email: str = "") -> str:
    google_terms = (
        '<p class="fine">By continuing with Google, you accept the '
        '<a href="/Legal" target="_blank">Terms of Service and Privacy Policy</a>.</p>'
        if settings.google_configured
        else ""
    )
    return SIGNUP_FORM.format(
        error=error,
        name=name,
        email=email,
        google_button=_google_button(),
        google_terms=google_terms,
    )


@app.get("/auth/login", response_class=HTMLResponse)
def login_page(request: Request):
    if _current_request_user(request):
        return RedirectResponse("/", status_code=303)
    return _csrf_response("Sign in", _login_form())


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
            _login_form(
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
            _login_form(
                error='<p class="error">Email or password is incorrect.</p>',
                email=html.escape(email, quote=True),
            ),
            status_code=400,
        )
    response = RedirectResponse("/", status_code=303)
    _set_session_cookie(response, token)
    return response


@app.get("/auth/google")
def google_login(request: Request):
    if not settings.google_configured:
        return _google_error("Google sign-in is not configured.", status_code=404)
    if _current_request_user(request):
        return RedirectResponse("/", status_code=303)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    response = RedirectResponse(authorization_url, status_code=302)
    response.set_cookie(
        _GOOGLE_OAUTH_COOKIE,
        _pack_google_oauth(state, nonce),
        max_age=_GOOGLE_OAUTH_MAX_AGE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/auth/google",
    )
    return response


@app.get("/auth/google/callback")
def google_callback(request: Request):
    if not settings.google_configured:
        return _google_error("Google sign-in is not configured.", status_code=404)
    packed = _unpack_google_oauth(request.cookies.get(_GOOGLE_OAUTH_COOKIE))
    returned_state = request.query_params.get("state", "")
    if packed is None or not returned_state or not secrets.compare_digest(
        packed[0], returned_state
    ):
        return _google_error("This Google sign-in request expired or is invalid.")
    if request.query_params.get("error"):
        return _google_error("Google sign-in was cancelled or could not be completed.")
    code = request.query_params.get("code", "")
    if not code or len(code) > 4096:
        return _google_error("Google sign-in did not return a valid authorization code.")

    try:
        claims = _google_token_claims(code)
        subject = claims.get("sub")
        google_email = claims.get("email")
        google_name = claims.get("name") or ""
        returned_nonce = claims.get("nonce")
        if (
            not isinstance(subject, str)
            or not isinstance(google_email, str)
            or not isinstance(google_name, str)
            or claims.get("email_verified") is not True
            or not isinstance(returned_nonce, str)
            or not secrets.compare_digest(packed[1], returned_nonce)
        ):
            raise AuthError("Google sign-in could not be completed.")
        with session_scope() as session:
            user = get_or_create_google_user(
                session,
                subject=subject,
                email=google_email,
                name=google_name,
            )
            token = create_user_session(session, user.id)
    except (AuthError, GoogleAuthError, requests.RequestException, TypeError, ValueError):
        return _google_error("Google sign-in could not be completed. Please try again.")

    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(_GOOGLE_OAUTH_COOKIE, path="/auth/google")
    _set_session_cookie(response, token)
    return response


@app.get("/auth/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    if _current_request_user(request):
        return RedirectResponse("/", status_code=303)
    return _csrf_response("Create account", _signup_form())


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
            _signup_form(
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
            _signup_form(
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


@app.get("/auth/account", response_class=HTMLResponse)
def account_page(request: Request):
    user = _current_request_user(request)
    if user is None:
        return RedirectResponse("/auth/login", status_code=303)
    provider = "Email and Google" if user.google_subject else "Email and password"
    body = f"""
<h1>Account</h1>
<p class="note">Your drafts, usage, and billing entitlement stay attached to this account.</p>
<div class="account"><strong>{html.escape(user.name)}</strong><br>{html.escape(user.email)}<br><span class="note">Sign-in method: {provider}</span></div>
<a class="button" href="/">Return to SellerDrafts</a>
<p class="note"><a href="/About_Pricing">Plans and billing</a> · <a href="/auth/logout">Log out</a></p>
"""
    return HTMLResponse(_page("Account", body))


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
