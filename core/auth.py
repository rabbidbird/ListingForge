"""Database-backed identity, password, and opaque session-token services."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Subscription, User, UserSession, utcnow

TERMS_VERSION = "2026-08-15"
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65_536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash("not-a-real-user-password")


class AuthError(ValueError):
    """Safe validation error that may be shown to an end user."""


def normalize_email(email: str) -> str:
    try:
        result = validate_email(email.strip(), check_deliverability=False)
    except EmailNotValidError as exc:
        raise AuthError("Enter a valid email address.") from exc
    return result.normalized.lower()


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise AuthError(f"Password must be no more than {MAX_PASSWORD_LENGTH} characters.")


def hash_password(password: str) -> str:
    validate_password(password)
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


def register_user(
    session: Session,
    *,
    email: str,
    password: str,
    name: str,
    accepted_terms: bool,
) -> User:
    if not accepted_terms:
        raise AuthError("You must accept the Terms of Service and Privacy Policy.")
    clean_name = " ".join(name.split())
    if not clean_name or len(clean_name) > 120:
        raise AuthError("Name is required and must be 120 characters or fewer.")
    normalized_email = normalize_email(email)
    password_hash = hash_password(password)
    now = utcnow()
    user = User(
        email=normalized_email,
        name=clean_name,
        password_hash=password_hash,
        email_verified_at=None if get_settings().email_verification_required else now,
        terms_accepted_at=now,
        terms_version=TERMS_VERSION,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise AuthError("An account with that email already exists.") from exc
    session.add(Subscription(user_id=user.id, plan="free", status="free"))
    session.flush()
    return user


def authenticate_user(session: Session, *, email: str, password: str) -> User | None:
    try:
        normalized_email = normalize_email(email)
    except AuthError:
        normalized_email = "invalid@example.invalid"
    user = session.scalar(select(User).where(User.email == normalized_email))
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    valid = verify_password(password_hash, password)
    if user is None or not valid or not user.is_active:
        return None
    if get_settings().email_verification_required and user.email_verified_at is None:
        raise AuthError("Verify your email before signing in.")
    if _PASSWORD_HASHER.check_needs_rehash(user.password_hash):
        user.password_hash = _PASSWORD_HASHER.hash(password)
    return user


def _token_hash(token: str) -> str:
    secret = get_settings().session_secret.encode("utf-8")
    return hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()


def create_user_session(session: Session, user_id: uuid.UUID) -> str:
    token = secrets.token_urlsafe(48)
    now = utcnow()
    session.add(
        UserSession(
            user_id=user_id,
            token_hash=_token_hash(token),
            expires_at=now + timedelta(days=get_settings().session_days),
            last_seen_at=now,
        )
    )
    session.flush()
    return token


def get_user_by_session_token(
    session: Session, token: str | None, *, touch: bool = False
) -> User | None:
    if not isinstance(token, str) or not token or len(token) > 512:
        return None
    now = utcnow()
    auth_session = session.scalar(
        select(UserSession).where(
            UserSession.token_hash == _token_hash(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    )
    if auth_session is None:
        return None
    user = session.get(User, auth_session.user_id)
    if user is None or not user.is_active:
        return None
    last_seen = auth_session.last_seen_at
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)
    if touch and (now - last_seen).total_seconds() >= 3600:
        auth_session.last_seen_at = now
    return user


def revoke_user_session(session: Session, token: str | None) -> None:
    if not token:
        return
    auth_session = session.scalar(
        select(UserSession).where(UserSession.token_hash == _token_hash(token))
    )
    if auth_session is not None and auth_session.revoked_at is None:
        auth_session.revoked_at = utcnow()


def streamlit_current_user() -> User | None:
    """Resolve the HttpOnly cookie received by Streamlit's server connection."""
    import streamlit as st

    token = st.context.cookies.get(get_settings().session_cookie_name)
    if not token:
        return None
    from .database import session_scope

    with session_scope() as session:
        return get_user_by_session_token(session, token, touch=True)


def require_streamlit_user() -> User:
    import streamlit as st

    user = streamlit_current_user()
    if user is None:
        st.warning("Sign in to use TrueDraft.")
        st.markdown("[Sign in](/auth/login) · [Create an account](/auth/signup)")
        st.stop()
    return user


def render_account_sidebar(user: User) -> None:
    import streamlit as st

    st.sidebar.caption(f"Signed in as {user.email}")
    st.sidebar.markdown("[Log out](/auth/logout)")
