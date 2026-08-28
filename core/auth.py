"""Database-backed identity, password, and opaque session-token services."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .legal import TERMS_VERSION
from .models import Subscription, User, UserSession, utcnow

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
    if len(email) > 320:
        raise AuthError("Enter a valid email address.")
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
    attribution: dict[str, Any] | None = None,
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
        **(attribution or {}),
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


def _normalize_google_subject(subject: str) -> str:
    clean_subject = subject.strip()
    if not clean_subject or len(clean_subject) > 255:
        raise AuthError("Google sign-in could not be completed.")
    return clean_subject


def find_user_by_google_subject(session: Session, subject: str) -> User | None:
    """Return the account linked to a Google subject, if one exists."""
    clean_subject = _normalize_google_subject(subject)
    return session.scalar(select(User).where(User.google_subject == clean_subject))


def create_google_user(
    session: Session,
    *,
    subject: str,
    email: str,
    name: str,
    attribution: dict[str, Any] | None = None,
) -> User:
    """Create a Google-backed account without linking an existing email account."""
    clean_subject = _normalize_google_subject(subject)
    normalized_email = normalize_email(email)
    clean_name = " ".join(name.split())[:120] or normalized_email.split("@", 1)[0][:120]
    now = utcnow()

    if find_user_by_google_subject(session, clean_subject) is not None:
        raise AuthError("This Google account is already linked to an account.")
    if session.scalar(select(User).where(User.email == normalized_email)) is not None:
        raise AuthError(
            "An account with this email already exists. Sign in with your password, "
            "then link Google from your account settings."
        )

    user = User(
        email=normalized_email,
        name=clean_name,
        # Google-only accounts do not have a usable local password. Store an
        # unguessable hash so the existing non-null schema remains compatible.
        password_hash=hash_password(secrets.token_urlsafe(48)),
        google_subject=clean_subject,
        google_email=normalized_email,
        email_verified_at=now,
        terms_accepted_at=now,
        terms_version=TERMS_VERSION,
        **(attribution or {}),
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise AuthError("Google sign-in could not be completed.") from exc
    session.add(Subscription(user_id=user.id, plan="free", status="free"))
    session.flush()
    return user


def revoke_all_user_sessions(session: Session, user_id: uuid.UUID) -> None:
    """Revoke every active session belonging to a user."""
    now = utcnow()
    auth_sessions = session.scalars(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
    )
    changed = False
    for auth_session in auth_sessions:
        auth_session.revoked_at = now
        changed = True
    if changed:
        session.flush()


def link_google_identity(
    session: Session,
    *,
    user: User,
    subject: str,
    email: str,
) -> User:
    """Link Google to an already-authenticated user and revoke existing sessions."""
    clean_subject = _normalize_google_subject(subject)
    normalized_email = normalize_email(email)
    if not user.is_active:
        raise AuthError("Google linking could not be completed for this account.")
    if normalized_email != user.email:
        raise AuthError(
            "Choose the Google account with the same email as this SellerDrafts account."
        )

    linked_user = find_user_by_google_subject(session, clean_subject)
    if linked_user is not None and linked_user.id != user.id:
        raise AuthError("This Google account is already linked to another account.")
    if user.google_subject is not None and user.google_subject != clean_subject:
        raise AuthError("This account is already linked to a different Google account.")

    user.google_subject = clean_subject
    user.google_email = normalized_email
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    session.flush()
    revoke_all_user_sessions(session, user.id)
    return user


def get_or_create_google_user(
    session: Session,
    *,
    subject: str,
    email: str,
    name: str,
    attribution: dict[str, Any] | None = None,
) -> User:
    """Resolve Google by immutable subject, or create a genuinely new account."""
    user = find_user_by_google_subject(session, subject)
    if user is not None:
        if not user.is_active:
            raise AuthError("Google sign-in could not be completed.")
        user.google_email = normalize_email(email)
        if user.email_verified_at is None:
            user.email_verified_at = utcnow()
        session.flush()
        return user
    return create_google_user(
        session,
        subject=subject,
        email=email,
        name=name,
        attribution=attribution,
    )


def authenticate_user(session: Session, *, email: str, password: str) -> User | None:
    try:
        normalized_email = normalize_email(email)
    except AuthError:
        normalized_email = "invalid@example.invalid"
    user = session.scalar(select(User).where(User.email == normalized_email))
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    # Bound attacker-controlled input before the deliberately expensive Argon2 call.
    candidate = password if 0 < len(password) <= MAX_PASSWORD_LENGTH else "invalid-password-length"
    valid = verify_password(password_hash, candidate)
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
        session.flush()


def streamlit_current_user() -> User | None:
    """Resolve the HttpOnly cookie received by Streamlit's server connection."""
    import streamlit as st

    token = st.context.cookies.get(get_settings().session_cookie_name)
    if not token:
        return None
    from .database import session_scope

    with session_scope() as session:
        user = get_user_by_session_token(session, token, touch=True)
    if user is not None and user.terms_version != TERMS_VERSION:
        st.warning("Review and accept the current Terms before continuing.")
        st.markdown("[Review current Terms](/auth/terms)")
        st.stop()
    return user


def require_streamlit_user() -> User:
    import streamlit as st

    user = streamlit_current_user()
    if user is None:
        st.warning("Sign in to use SellerDrafts.")
        st.markdown("[Sign in](/auth/login) · [Create an account](/auth/signup)")
        st.stop()
    return user


def render_account_sidebar(user: User) -> None:
    import streamlit as st

    st.caption(f"Signed in as {user.email}")
