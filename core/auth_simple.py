"""
Very simple password gate for ListingForge demo / single-tenant use.
For production multi-user, replace with streamlit-authenticator + proper user DB.
"""

import streamlit as st
import os
from pathlib import Path

# Default password can be overridden by environment variable
DEFAULT_PASSWORD = os.getenv("LISTINGFORGE_PASSWORD", "listingforge")


def check_password() -> bool:
    """Returns True if the user has entered the correct password."""
    def password_entered():
        if st.session_state.get("password") == DEFAULT_PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.markdown("## 🔒 ListingForge")
    st.caption("Enter the access password to continue")
    st.text_input("Password", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("Incorrect password")
    st.info("Default password is `listingforge` (change via LISTINGFORGE_PASSWORD env var)")
    return False
