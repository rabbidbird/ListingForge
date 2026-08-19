"""
ListingForge authentication using streamlit-authenticator.
Provides login, registration, and current-user helpers.
For production, replace the YAML credential store with a proper user database.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional, Tuple

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

CONFIG_PATH = Path(__file__).parent.parent / "config" / "credentials.yaml"
EXAMPLE_PATH = Path(__file__).parent.parent / "config" / "credentials.yaml.example"
AUTH_TRUE = {"1", "true", "yes", "on"}
ENV_USER_ID = "LISTINGFORGE_USER_ID"
ENV_REQUIRE_AUTH = "LISTINGFORGE_REQUIRE_AUTH"
ENV_SKIP_AUTH = ("LISTINGFORGE_SKIP_AUTH", "TRUEDRAFT_SKIP_AUTH")


def _is_truthy(value: str) -> bool:
    return bool(value and value.strip().lower() in AUTH_TRUE)


def _get_default_local_user_id() -> str:
    """Return a stable per-session local user id for demo/no-auth mode."""
    if not auth_required() and "listingforge_user" in st.session_state:
        return st.session_state["listingforge_user"]

    if not auth_required():
        configured = os.getenv(ENV_USER_ID, "").strip()
        if configured:
            return configured

    return f"guest-{uuid.uuid4().hex[:12]}"


def auth_required() -> bool:
    if any(_is_truthy(os.getenv(name)) for name in ENV_SKIP_AUTH):
        return False
    return _is_truthy(os.getenv(ENV_REQUIRE_AUTH, "false"))


def _ensure_config() -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        if EXAMPLE_PATH.exists():
            text = EXAMPLE_PATH.read_text()
            CONFIG_PATH.write_text(text)
        else:
            CONFIG_PATH.write_text(
                """
credentials:
  usernames:
    demo:
      email: demo@example.com
      name: Demo User
      password: $2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW
cookie:
  expiry_days: 30
  key: listingforge_cookie_key_change_me_in_production
  name: listingforge_auth
preauthorized:
  emails: []
""".strip()
            )
    with open(CONFIG_PATH) as f:
        return yaml.load(f, Loader=SafeLoader)


def get_authenticator() -> stauth.Authenticate:
    config = _ensure_config()
    return stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )


def require_login() -> Tuple[Optional[str], Optional[str]]:
    if any(_is_truthy(os.getenv(name)) for name in ENV_SKIP_AUTH):
        st.session_state["listingforge_user"] = "local"
        st.session_state["listingforge_name"] = "Local User"
        return "Local User", "local"

    authenticator = get_authenticator()
    try:
        authenticator.login(location="main")
    except Exception:
        authenticator.login("Login", "main")

    name = st.session_state.get("name")
    username = st.session_state.get("username")
    auth_status = st.session_state.get("authentication_status")

    if auth_status is False:
        st.error("Username or password is incorrect")
        st.stop()
    elif auth_status is None:
        st.info("Please log in. Default demo account: **demo** / **secret** (change in config/credentials.yaml)")
        st.stop()

    st.session_state["listingforge_user"] = username
    st.session_state["listingforge_name"] = name
    return name, username


def require_user_if_enabled() -> Tuple[Optional[str], Optional[str]]:
    if not auth_required():
        if "listingforge_user" not in st.session_state:
            st.session_state["listingforge_user"] = _get_default_local_user_id()
            st.session_state["listingforge_name"] = st.session_state["listingforge_user"]
        return st.session_state["listingforge_name"], st.session_state["listingforge_user"]
    return require_login()


def user_id(default: str = "anonymous") -> str:
    if auth_required():
        _, uid = require_login()
        return uid or default
    if "listingforge_user" not in st.session_state:
        st.session_state["listingforge_user"] = _get_default_local_user_id()
        st.session_state["listingforge_name"] = st.session_state["listingforge_user"]
    return (
        st.session_state.get("listingforge_user")
        or st.session_state.get("truedraft_user")
        or st.session_state.get("username")
        or os.getenv(ENV_USER_ID, default)
    )


def current_user() -> str:
    if auth_required():
        _, uid = require_login()
        return uid or "anonymous"
    if "listingforge_user" not in st.session_state:
        st.session_state["listingforge_user"] = _get_default_local_user_id()
        st.session_state["listingforge_name"] = st.session_state["listingforge_user"]
    return (
        st.session_state.get("listingforge_user")
        or st.session_state.get("truedraft_user")
        or st.session_state.get("username")
        or os.getenv(ENV_USER_ID, "anonymous")
    )


def logout_button():
    if any(_is_truthy(os.getenv(name)) for name in ENV_SKIP_AUTH):
        return
    try:
        authenticator = get_authenticator()
        authenticator.logout("Logout", "sidebar")
    except Exception:
        pass
