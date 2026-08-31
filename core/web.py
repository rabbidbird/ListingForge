"""FastAPI edge for secure auth cookies, health checks, and Stripe webhooks."""

from __future__ import annotations

import hashlib
import html
import secrets
import threading
import time
from collections import OrderedDict, deque
from urllib.parse import urlencode, urlparse

import requests
from fastapi import FastAPI, Form, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy import func, select
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .attribution import (
    ATTRIBUTION_COOKIE_NAME,
    ATTRIBUTION_MAX_AGE_SECONDS,
    pack_attribution,
    unpack_attribution,
    user_attribution_fields,
)
from .auth import (
    AuthError,
    authenticate_user,
    create_user_session,
    get_or_create_google_user,
    get_user_by_session_token,
    link_google_identity,
    register_user,
    revoke_user_session,
)
from .billing import BillingError, WebhookVerificationError, handle_webhook
from .config import PROJECT_ROOT, get_settings
from .database import session_scope
from .events import PRODUCT_EVENTS, record_product_event
from .legal import TERMS_VERSION
from .marketing import (
    PUBLIC_PATHS,
    guide_page,
    guides_page,
    home_page,
    legal_page,
    pricing_page,
)
from .migrate import database_at_migration_head
from .models import User, utcnow
from .plans import PLANS

settings = get_settings()
settings.validate_for_production()
app = FastAPI(title="SellerDrafts edge", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/assets", StaticFiles(directory=PROJECT_ROOT / "static"), name="assets")


def _trusted_hosts() -> list[str]:
    if not settings.is_production:
        return ["*"]
    public_host = urlparse(settings.public_base_url).hostname
    return [host for host in (public_host, "127.0.0.1", "localhost") if host]


app.add_middleware(TrustedHostMiddleware, allowed_hosts=_trusted_hosts(), www_redirect=False)

_AUTH_WINDOW_SECONDS = 600
_AUTH_REQUESTS_PER_WINDOW = 40
_AUTH_IP_BUCKET_LIMIT = 10_000
_GOOGLE_OAUTH_MAX_AGE = 600
_GOOGLE_OAUTH_COOKIE = "sellerdrafts_google_oauth"
_PLAN_INTENTS = frozenset({"free", "starter", "pro", "agency"})
_BROWSER_PRODUCT_EVENTS = PRODUCT_EVENTS & {
    "title_copied",
    "description_copied",
    "tags_copied",
}
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
    if request.url.path.startswith(("/auth/", "/app/")):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'self'"
    )
    return response


def _public_page_response(request: Request, content: str) -> HTMLResponse:
    response = HTMLResponse(content, headers={"Cache-Control": "public, max-age=300"})
    existing = unpack_attribution(request.cookies.get(ATTRIBUTION_COOKIE_NAME))
    packed = (
        None if existing else pack_attribution(request.query_params, landing_path=request.url.path)
    )
    if packed:
        response.set_cookie(
            ATTRIBUTION_COOKIE_NAME,
            packed,
            max_age=ATTRIBUTION_MAX_AGE_SECONDS,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            path="/",
        )
    return response


def _plan_intent(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in _PLAN_INTENTS else ""


def _intent_query(plan: str) -> str:
    return {
        "free": "?plan=free",
        "starter": "?plan=starter",
        "pro": "?plan=pro",
        "agency": "?plan=agency",
    }.get(plan, "")


def _post_auth_target(user: User, plan: str = "", *, signup_origin: bool = False) -> str:
    default_target = (
        "/app/Optimizer" if signup_origin and plan not in {"starter", "pro", "agency"} else "/app/"
    )
    if user.terms_version != TERMS_VERSION:
        next_path = {
            "starter": "/app/About_Pricing",
            "pro": "/app/About_Pricing",
            "agency": "/app/About_Pricing",
        }.get(plan, default_target)
        query = (
            urlencode({"next": next_path, "plan": plan}) if plan else urlencode({"next": next_path})
        )
        return f"/auth/terms?{query}"
    return {
        "starter": "/app/About_Pricing?plan=starter",
        "pro": "/app/About_Pricing?plan=pro",
        "agency": "/app/About_Pricing?plan=agency",
    }.get(plan, default_target)


@app.get("/", response_class=HTMLResponse)
def public_home(request: Request):
    if user := _current_request_user(request):
        return RedirectResponse(_post_auth_target(user), status_code=303)
    return _public_page_response(request, home_page())


@app.get("/pricing", response_class=HTMLResponse)
def public_pricing(request: Request):
    if user := _current_request_user(request):
        return RedirectResponse(
            _post_auth_target(user, _plan_intent(request.query_params.get("plan"))), status_code=303
        )
    return _public_page_response(request, pricing_page())


@app.get("/legal", response_class=HTMLResponse)
def public_legal(request: Request):
    return _public_page_response(request, legal_page())


@app.get("/guides", response_class=HTMLResponse)
def public_guides(request: Request):
    return _public_page_response(request, guides_page())


@app.get("/guides/{slug}", response_class=HTMLResponse)
def public_guide(request: Request, slug: str):
    content = guide_page(slug)
    if content is None:
        return HTMLResponse(
            _page(
                "Guide not found",
                '<h1>Guide not found</h1><p class="note"><a href="/">Return to SellerDrafts</a>.</p>',
            ),
            status_code=404,
        )
    return _public_page_response(request, content)


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /app/\n"
        "Disallow: /auth/\n"
        "Disallow: /webhooks/\n"
        "Disallow: /_stcore/\n\n"
        "User-agent: OAI-SearchBot\n"
        "Allow: /\n"
        "Disallow: /app/\n"
        "Disallow: /auth/\n\n"
        "User-agent: GPTBot\n"
        "Disallow: /\n\n"
        f"Sitemap: {settings.public_base_url}/sitemap.xml\n"
    )
    return PlainTextResponse(body, headers={"Cache-Control": "public, max-age=3600"})


@app.post("/events/product")
async def product_event(request: Request):
    if not request.headers.get("content-type", "").startswith("application/json"):
        return JSONResponse({"detail": "Invalid event request."}, status_code=415)
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != settings.public_base_url.rstrip("/"):
        return JSONResponse({"detail": "Invalid event origin."}, status_code=403)
    user = _current_request_user(request)
    if user is None:
        return JSONResponse({"detail": "Authentication required."}, status_code=401)
    body = await request.body()
    if len(body) > 256:
        return JSONResponse({"detail": "Invalid event request."}, status_code=400)
    payload: object = None
    try:
        payload = await request.json()
        event_name = payload.get("event") if isinstance(payload, dict) else None
    except ValueError:
        event_name = None
    if (
        event_name not in _BROWSER_PRODUCT_EVENTS
        or not isinstance(payload, dict)
        or set(payload) != {"event"}
    ):
        return JSONResponse({"detail": "Invalid event request."}, status_code=400)
    record_product_event(user.id, event_name)
    return Response(status_code=204)


@app.get("/favicon.ico")
def favicon():
    return RedirectResponse("/assets/favicon.ico", status_code=307)


@app.get("/sitemap.xml")
def sitemap_xml():
    urls = "".join(
        f"<url><loc>{settings.public_base_url}{path}</loc></url>" for path in PUBLIC_PATHS
    )
    body = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return Response(
        body,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _legacy_streamlit_redirect(request: Request, public_path: str, app_path: str):
    target = app_path if _current_request_user(request) else public_path
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(target, status_code=308)


@app.get("/About_Pricing")
def legacy_pricing(request: Request):
    return _legacy_streamlit_redirect(request, "/pricing", "/app/About_Pricing")


@app.get("/Legal")
def legacy_legal(request: Request):
    return _legacy_streamlit_redirect(request, "/legal", "/app/Legal")


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} | SellerDrafts</title>
<meta name="robots" content="noindex,nofollow">
<link rel="icon" href="/assets/mark.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/public.css">
</head><body class="auth-page"><div class="auth-shell">
<header class="auth-header"><a class="wordmark" href="/"><img src="/assets/wordmark.svg" alt="SellerDrafts" width="188" height="36"></a><a href="/">Back to site</a></header>
<div class="auth-layout"><aside class="auth-note"><p class="ticket-label">ACCOUNT WORK TICKET</p><p class="auth-note-title">If you didn’t type it, it stays out.</p><dl class="auth-ticket"><div><dt>INPUT</dt><dd>Verified product facts</dd></div><div><dt>OUTPUT</dt><dd>Editable Etsy draft</dd></div><div><dt>FINAL CHECK</dt><dd>Yours</dd></div></dl></aside><main class="auth-card">{body}</main></div>
<footer class="auth-foot"><span class="draft-stamp">DRAFT</span> Check the item. You publish.</footer>
</div></body></html>"""


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


def _clear_attribution_cookie(response: Response) -> None:
    response.delete_cookie(ATTRIBUTION_COOKIE_NAME, path="/")


def _current_request_user(request: Request) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    with session_scope() as session:
        return get_user_by_session_token(session, token)


def _google_button(plan: str = "", *, signup_origin: bool = False) -> str:
    if not settings.google_configured:
        return ""
    query = urlencode({"origin": "signup", "plan": plan}) if signup_origin else _intent_query(plan)
    target = html.escape(f"/auth/google{query}", quote=True)
    label = "Create free account with Google" if signup_origin else "Continue with Google"
    return f"""
<a class="button google" href="{target}">{label}</a>
"""


def _google_state_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        settings.session_secret,
        salt="sellerdrafts-google-oauth-state-v1",
        signer_kwargs={"digest_method": hashlib.sha256},
    )


def _pack_google_oauth(
    state: str,
    nonce: str,
    *,
    mode: str = "login",
    user_id: str = "",
    plan: str = "",
    signup_origin: bool = False,
) -> str:
    return _google_state_serializer().dumps(
        {
            "state": state,
            "nonce": nonce,
            "mode": mode,
            "user_id": user_id,
            "plan": _plan_intent(plan),
            "signup_origin": signup_origin,
        }
    )


def _unpack_google_oauth(value: str | None) -> dict[str, str] | None:
    if not value or len(value) > 2048:
        return None
    try:
        payload = _google_state_serializer().loads(
            value,
            max_age=_GOOGLE_OAUTH_MAX_AGE,
        )
        state = payload["state"]
        nonce = payload["nonce"]
        mode = payload.get("mode", "login")
        user_id = payload.get("user_id", "")
        plan = _plan_intent(payload.get("plan"))
        signup_origin = payload.get("signup_origin", False)
    except (BadData, KeyError, TypeError, ValueError):
        return None
    if (
        not isinstance(state, str)
        or not isinstance(nonce, str)
        or mode not in {"login", "link"}
        or not isinstance(user_id, str)
        or not isinstance(signup_origin, bool)
    ):
        return None
    return {
        "state": state,
        "nonce": nonce,
        "mode": mode,
        "user_id": user_id,
        "plan": plan,
        "signup_origin": signup_origin,
    }


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
    return HTMLResponse(
        _page(
            "Google sign-in",
            f'<h1>Google sign-in</h1><p class="error">{html.escape(message)}</p>'
            '<p class="note"><a href="/auth/login">Return to sign in</a> or '
            '<a href="/auth/signup">return to account creation</a>.</p>',
        ),
        status_code=status_code,
    )


def _google_callback_error(message: str, *, status_code: int = 400) -> HTMLResponse:
    response = _google_error(message, status_code=status_code)
    response.delete_cookie(_GOOGLE_OAUTH_COOKIE, path="/auth/google")
    return response


LOGIN_FORM = """
<h1>Sign in</h1>
<p class="note">Open your private draft history and plan. SellerDrafts never publishes for you.</p>
{error}
{google_button}
<form method="post" action="/auth/login">
<input type="hidden" name="csrf_token" value="{{CSRF}}">
<input type="hidden" name="plan" value="{plan}">
<label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" required value="{email}">
<label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" maxlength="128" required>
<button type="submit">Sign in</button>
</form>
<p class="note">New here? <a href="/auth/signup">Create an account</a>.</p>
{google_terms}
"""

SIGNUP_FORM = """
<h1>Create your account</h1>
<p class="note">Start with product facts you can verify. Make an Etsy-first draft, edit it, and find it later in private History. SellerDrafts does not publish to marketplaces.</p>
{error}
{google_button}
<form method="post" action="/auth/signup">
<input type="hidden" name="csrf_token" value="{{CSRF}}">
<input type="hidden" name="plan" value="{plan}">
<label for="name">Name</label><input id="name" name="name" type="text" autocomplete="name" maxlength="120" required value="{name}">
<label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" required value="{email}">
<label for="password">Password</label><input id="password" name="password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required>
<div class="check"><input id="terms" name="accepted_terms" type="checkbox" value="true" required><label for="terms">I accept the <a href="/legal" target="_blank">Terms of Service and Privacy Policy</a>.</label></div>
<button type="submit">Create account</button>
</form>
<p class="note">Already registered? <a href="/auth/login">Sign in</a>.</p>
{google_terms}
"""


def _login_form(*, error: str = "", email: str = "", plan: str = "") -> str:
    google_terms = (
        '<p class="fine">If Google creates a new SellerDrafts account, continuing means you '
        'accept the <a href="/legal" target="_blank">Terms of Service and Privacy Policy</a>.</p>'
        if settings.google_configured
        else ""
    )
    return LOGIN_FORM.format(
        error=error,
        email=email,
        google_button=_google_button(plan),
        google_terms=google_terms,
        plan=html.escape(plan, quote=True),
    )


def _signup_form(*, error: str = "", name: str = "", email: str = "", plan: str = "") -> str:
    google_terms = (
        '<p class="fine">By continuing with Google, you accept the '
        '<a href="/legal" target="_blank">Terms of Service and Privacy Policy</a>.</p>'
        if settings.google_configured
        else ""
    )
    return SIGNUP_FORM.format(
        error=error,
        name=name,
        email=email,
        google_button=_google_button(plan, signup_origin=True),
        google_terms=google_terms,
        plan=html.escape(plan, quote=True),
    )


@app.get("/auth/login", response_class=HTMLResponse)
def login_page(request: Request):
    plan = _plan_intent(request.query_params.get("plan"))
    if user := _current_request_user(request):
        return RedirectResponse(_post_auth_target(user, plan), status_code=303)
    return _csrf_response("Sign in", _login_form(plan=plan))


@app.post("/auth/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    plan: str = Form(""),
):
    plan = _plan_intent(plan)
    if not _valid_csrf(request, csrf_token):
        return _csrf_response(
            "Sign in",
            _login_form(
                error='<p class="error">This form expired. Please try again.</p>',
                email=html.escape(email, quote=True),
                plan=plan,
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
                plan=plan,
            ),
            status_code=400,
        )
    response = RedirectResponse(_post_auth_target(user, plan), status_code=303)
    _set_session_cookie(response, token)
    _clear_attribution_cookie(response)
    return response


@app.get("/auth/google")
def google_login(request: Request):
    if not settings.google_configured:
        return _google_error("Google sign-in is not configured.", status_code=404)
    if user := _current_request_user(request):
        return RedirectResponse(_post_auth_target(user), status_code=303)
    plan = _plan_intent(request.query_params.get("plan"))
    signup_origin = request.query_params.get("origin") == "signup"
    return _start_google_oauth(request, mode="login", plan=plan, signup_origin=signup_origin)


def _start_google_oauth(
    request: Request,
    *,
    mode: str,
    plan: str = "",
    user: User | None = None,
    signup_origin: bool = False,
) -> RedirectResponse:
    del request
    nonce = secrets.token_urlsafe(32)
    browser_state = secrets.token_urlsafe(32)
    state = _pack_google_oauth(
        browser_state,
        nonce,
        mode=mode,
        user_id=str(user.id) if user else "",
        plan=plan,
        signup_origin=signup_origin,
    )
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
        browser_state,
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
        return _google_callback_error("Google sign-in is not configured.", status_code=404)
    returned_state = request.query_params.get("state", "")
    packed = _unpack_google_oauth(returned_state)
    browser_state = request.cookies.get(_GOOGLE_OAUTH_COOKIE, "")
    if (
        packed is None
        or not browser_state
        or not secrets.compare_digest(packed["state"], browser_state)
    ):
        return _google_callback_error("This Google sign-in request expired or is invalid.")
    if request.query_params.get("error"):
        return _google_callback_error("Google sign-in was cancelled or could not be completed.")
    code = request.query_params.get("code", "")
    if not code or len(code) > 4096:
        return _google_callback_error("Google sign-in did not return a valid authorization code.")

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
            or not secrets.compare_digest(packed["nonce"], returned_nonce)
        ):
            raise AuthError("Google sign-in could not be completed.")
        with session_scope() as session:
            if packed["mode"] == "link":
                current = get_user_by_session_token(
                    session, request.cookies.get(settings.session_cookie_name)
                )
                if current is None or not secrets.compare_digest(
                    str(current.id), packed["user_id"]
                ):
                    raise AuthError("Sign in again before linking Google.")
                user = link_google_identity(
                    session,
                    user=current,
                    subject=subject,
                    email=google_email,
                )
            else:
                user = get_or_create_google_user(
                    session,
                    subject=subject,
                    email=google_email,
                    name=google_name,
                    attribution=user_attribution_fields(
                        request.cookies.get(ATTRIBUTION_COOKIE_NAME)
                    ),
                )
            token = create_user_session(session, user.id)
    except AuthError:
        message = (
            "Google could not be linked. Use the Google account with the same email, "
            "or return to Account."
            if packed["mode"] == "link"
            else "Google sign-in could not be completed. If this email already has a "
            "password account, sign in with password and link Google from Account."
        )
        return _google_callback_error(message)
    except (GoogleAuthError, requests.RequestException, TypeError, ValueError):
        return _google_callback_error("Google sign-in could not be completed. Please try again.")

    target = (
        "/auth/account?linked=google"
        if packed["mode"] == "link"
        else _post_auth_target(
            user,
            packed["plan"],
            signup_origin=bool(packed["signup_origin"]),
        )
    )
    response = RedirectResponse(target, status_code=303)
    _set_session_cookie(response, token)
    _clear_attribution_cookie(response)
    response.delete_cookie(_GOOGLE_OAUTH_COOKIE, path="/auth/google")
    return response


@app.get("/auth/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    plan = _plan_intent(request.query_params.get("plan"))
    if user := _current_request_user(request):
        return RedirectResponse(_post_auth_target(user, plan), status_code=303)
    if not settings.password_signup_enabled:
        google = _google_button(plan, signup_origin=True)
        plan_note = (
            f'<p class="account"><strong>{html.escape(PLANS[plan].name)} selected.</strong> '
            f"You will review it before any charge; payment happens later in Stripe Checkout.</p>"
            if plan in {"starter", "pro", "agency"}
            else '<p class="fine">Free account creation requires no card.</p>'
        )
        body = (
            "<h1>Create a free draft account</h1>"
            '<p class="note">Bring product facts you can check. Leave with an editable Etsy draft. '
            "Existing password accounts can still sign in.</p>"
            f"{plan_note}"
            f"{google}"
            f'<p class="note"><a href="/auth/login{_intent_query(plan)}">Sign in to an existing account</a>.</p>'
            '<p class="fine">By continuing with Google, you accept the '
            '<a href="/legal" target="_blank">current Terms of Service and Privacy Policy</a>.</p>'
        )
        return HTMLResponse(_page("Create account", body), status_code=200)
    return _csrf_response("Create account", _signup_form(plan=plan))


@app.post("/auth/signup")
def signup(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    accepted_terms: str | None = Form(None),
    plan: str = Form(""),
):
    plan = _plan_intent(plan)
    if not settings.password_signup_enabled:
        signup_target = html.escape(f"/auth/signup{_intent_query(plan)}", quote=True)
        return HTMLResponse(
            _page(
                "Create account",
                '<h1>Create a free account with Google</h1><p class="error">This form is not '
                "available for new accounts.</p>"
                f'<p class="note"><a href="{signup_target}">Create a free account with Google</a> '
                'or <a href="/auth/login">sign in to an existing password account</a>.</p>',
            ),
            status_code=403,
        )
    safe_name = html.escape(name, quote=True)
    safe_email = html.escape(email, quote=True)
    if not _valid_csrf(request, csrf_token):
        return _csrf_response(
            "Create account",
            _signup_form(
                error='<p class="error">This form expired. Please try again.</p>',
                name=safe_name,
                email=safe_email,
                plan=plan,
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
                attribution=user_attribution_fields(request.cookies.get(ATTRIBUTION_COOKIE_NAME)),
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
                plan=plan,
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
    response = RedirectResponse(_post_auth_target(user, plan), status_code=303)
    _set_session_cookie(response, token)
    _clear_attribution_cookie(response)
    return response


@app.get("/auth/account", response_class=HTMLResponse)
def account_page(request: Request):
    user = _current_request_user(request)
    if user is None:
        return RedirectResponse("/auth/login", status_code=303)
    if user.terms_version != TERMS_VERSION:
        return RedirectResponse("/auth/terms?next=/auth/account", status_code=303)
    provider = "Google linked" if user.google_subject else "Google not linked"
    linked_notice = (
        '<p class="account">Google was linked successfully. Other active sessions were revoked.</p>'
        if request.query_params.get("linked") == "google" and user.google_subject
        else ""
    )
    link_action = (
        '<p class="note">Google is linked to this account.</p>'
        if user.google_subject
        else """
<form method="post" action="/auth/google/link">
<input type="hidden" name="csrf_token" value="{{CSRF}}">
<button type="submit" class="google">Link Google to this account</button>
</form>
<p class="fine">Linking requires a fresh sign-in and revokes other active sessions.</p>
"""
    )
    body = f"""
<h1>Account</h1>
<p class="note">Your drafts, usage, and billing entitlement stay attached to this account.</p>
{linked_notice}
<div class="account"><strong>{html.escape(user.name)}</strong><br>{html.escape(user.email)}<br><span class="note">Identity status: {provider}</span></div>
{link_action}
<a class="button" href="/">Return to SellerDrafts</a>
<p class="note"><a href="/app/About_Pricing">Plans and billing</a> · <a href="/auth/logout">Log out</a></p>
"""
    return _csrf_response("Account", body)


@app.post("/auth/google/link")
def google_link(request: Request, csrf_token: str = Form(...)):
    if not settings.google_configured:
        return _google_error("Google sign-in is not configured.", status_code=404)
    user = _current_request_user(request)
    if user is None:
        return RedirectResponse("/auth/login", status_code=303)
    if user.terms_version != TERMS_VERSION:
        return RedirectResponse("/auth/terms?next=/auth/account", status_code=303)
    if not _valid_csrf(request, csrf_token):
        return _google_error("This account-link form expired. Please try again.")
    return _start_google_oauth(request, mode="link", user=user)


def _safe_post_terms_target(value: str | None) -> str:
    return {
        "/app/": "/app/",
        "/app/Optimizer": "/app/Optimizer",
        "/app/About_Pricing": "/app/About_Pricing",
        "/auth/account": "/auth/account",
    }.get(value or "", "/app/")


def _accepted_terms_target(next_path: str, plan: str) -> str:
    if next_path != "/app/About_Pricing":
        return _safe_post_terms_target(next_path)
    return {
        "starter": "/app/About_Pricing?plan=starter",
        "pro": "/app/About_Pricing?plan=pro",
        "agency": "/app/About_Pricing?plan=agency",
    }.get(plan, "/app/About_Pricing")


@app.get("/auth/terms", response_class=HTMLResponse)
def terms_acceptance_page(request: Request):
    user = _current_request_user(request)
    if user is None:
        return RedirectResponse("/auth/login", status_code=303)
    next_path = _safe_post_terms_target(request.query_params.get("next"))
    plan = _plan_intent(request.query_params.get("plan"))
    if user.terms_version == TERMS_VERSION:
        return RedirectResponse(_accepted_terms_target(next_path, plan), status_code=303)
    body = f"""
<h1>Review updated Terms</h1>
<p class="note">SellerDrafts Terms version {html.escape(TERMS_VERSION)} applies before you continue to the workspace.</p>
<p><a href="/legal" target="_blank">Read the current Terms, Privacy Policy, and Acceptable Use Policy</a>.</p>
<form method="post" action="/auth/terms">
<input type="hidden" name="csrf_token" value="{{CSRF}}">
<input type="hidden" name="next" value="{html.escape(next_path, quote=True)}">
<input type="hidden" name="plan" value="{html.escape(plan, quote=True)}">
<div class="check"><input id="terms" name="accepted_terms" type="checkbox" value="true" required><label for="terms">I accept the current Terms of Service and Privacy Policy.</label></div>
<button type="submit">Accept and continue</button>
</form>
"""
    return _csrf_response("Review updated Terms", body)


@app.post("/auth/terms")
def accept_current_terms(
    request: Request,
    csrf_token: str = Form(...),
    accepted_terms: str | None = Form(None),
    next: str = Form("/app/"),
    plan: str = Form(""),
):
    user = _current_request_user(request)
    if user is None:
        return RedirectResponse("/auth/login", status_code=303)
    next_path = _safe_post_terms_target(next)
    plan = _plan_intent(plan)
    if not _valid_csrf(request, csrf_token) or accepted_terms != "true":
        return HTMLResponse(
            _page(
                "Review updated Terms",
                '<h1>Terms not accepted</h1><p class="error">Accept the current Terms before continuing.</p>'
                f'<p><a href="/auth/terms?{urlencode({"next": next_path, "plan": plan})}">Try again</a>.</p>',
            ),
            status_code=400,
        )
    with session_scope() as session:
        stored = session.get(User, user.id)
        if stored is None or not stored.is_active:
            return RedirectResponse("/auth/login", status_code=303)
        stored.terms_version = TERMS_VERSION
        stored.terms_accepted_at = utcnow()
    return RedirectResponse(_accepted_terms_target(next_path, plan), status_code=303)


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
