"""
TrueDraft authentication using streamlit-authenticator.
Provides login, registration, and current-user helpers.
For production, replace the YAML credential store with a proper user database.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

CONFIG_PATH = Path(__file__).parent.parent / "config" / "credentials.yaml"
EXAMPLE_PATH = Path(__file__).parent.parent / "config" / "credentials.yaml.example"


def _ensure_config() -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        if EXAMPLE_PATH.exists():
            text = EXAMPLE_PATH.read_text()
            text = text.replace("listingforge", "truedraft").replace("ListingForge", "TrueDraft")
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
  key: truedraft_cookie_key_change_me_in_production
  name: truedraft_auth
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
    if os.getenv("TRUEDRAFT_SKIP_AUTH", "").lower() in ("1", "true", "yes"):
        st.session_state["truedraft_user"] = "local"
        st.session_state["truedraft_name"] = "Local User"
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

    st.session_state["truedraft_user"] = username
    st.session_state["truedraft_name"] = name
    return name, username


def current_user() -> str:
    return st.session_state.get("truedraft_user") or st.session_state.get("username") or "anonymous"


def logout_button():
    if os.getenv("TRUEDRAFT_SKIP_AUTH", "").lower() in ("1", "true", "yes"):
        return
    try:
        authenticator = get_authenticator()
        authenticator.logout("Logout", "sidebar")
    except Exception:
        pass
