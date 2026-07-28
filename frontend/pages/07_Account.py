from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from etlantic_ui.errors import ApiError, render_error
from etlantic_ui.navigation import page_guard
from etlantic_ui.state import get_api_client, logout, require_auth

st.set_page_config(page_title="Account", layout="wide")
if not page_guard():
    st.stop()
user = require_auth()
assert user is not None

st.title("Account")
st.write(f"**Email:** {user.email}")
st.write(f"**User ID:** `{user.id}`")
st.caption("Email and user ID are immutable in this release.")

client = get_api_client()

st.subheader("Display name")
new_name = st.text_input("Display name", value=user.display_name)
if st.button("Update display name"):
    try:
        updated = client.update_me(display_name=new_name.strip())
        st.session_state["current_user"] = updated.model_dump(mode="json")
        st.success("Updated.")
        st.rerun()
    except ApiError as exc:
        render_error(exc)

st.subheader("Change password")
with st.form("password"):
    password = st.text_input("New password (min 12 chars)", type="password")
    confirm = st.text_input("Confirm password", type="password")
    submitted = st.form_submit_button("Change password")
if submitted:
    if len(password) < 12:
        st.error("Password must be at least 12 characters.")
    elif password != confirm:
        st.error("Passwords do not match.")
    else:
        try:
            client.update_me(password=password)
            st.success("Password updated.")
        except ApiError as exc:
            render_error(exc)

st.subheader("Session")
if st.button("Sign out"):
    logout()
    st.switch_page("Home.py")

st.subheader("Deactivate account")
st.warning("Deactivation blocks further logins. Type DEACTIVATE to confirm.")
confirm = st.text_input("Confirmation")
if st.button("Deactivate") and confirm == "DEACTIVATE":
    try:
        client.deactivate_me()
        logout()
        st.switch_page("Home.py")
    except ApiError as exc:
        render_error(exc)

if user.is_admin:
    st.divider()
    st.subheader("Administrators — users")
    try:
        users = client.list_users()
        for item in users:
            st.write(
                f"{item.display_name} · {item.email} · "
                f"admin={item.is_admin} active={item.is_active}"
            )
    except ApiError as exc:
        render_error(exc)

client.close()
