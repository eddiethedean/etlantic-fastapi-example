from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

FRONTEND_ROOT = Path(__file__).resolve().parent
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from etlantic_ui.errors import ApiError, AuthenticationError, render_error
from etlantic_ui.formatting import format_dt, status_emoji
from etlantic_ui.navigation import render_sidebar
from etlantic_ui.state import (
    PENDING_INVITE_TOKEN_KEY,
    access_token,
    capture_invite_query_param,
    clear_auth_state,
    clear_pending_invite_token,
    get_api_client,
    is_authenticated,
    login_and_store,
    pending_invite_token,
    register_and_login,
    require_auth,
    token_expired,
)

st.set_page_config(page_title="ETLantic Runner", page_icon="⚙️", layout="wide")
capture_invite_query_param()
render_sidebar()


def render_auth() -> None:
    st.title("ETLantic Runner")
    st.write("Sign in to manage pipelines, runs, credentials, and groups.")

    tab_signin, tab_register, tab_invite = st.tabs(
        ["Sign in", "Create account", "Accept invitation"]
    )

    with tab_signin:
        with st.form("signin"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")
        if submitted:
            try:
                login_and_store(email.strip(), password)
                st.success("Signed in.")
                st.rerun()
            except AuthenticationError:
                st.error("Incorrect email or password.")
            except ApiError as exc:
                render_error(exc)

    with tab_register:
        with st.form("register"):
            email = st.text_input("Email", key="reg-email")
            display_name = st.text_input("Display name", key="reg-name")
            password = st.text_input("Password (min 12 chars)", type="password", key="reg-pass")
            confirm = st.text_input("Confirm password", type="password", key="reg-confirm")
            submitted = st.form_submit_button("Create account")
        if submitted:
            if len(password) < 12:
                st.error("Password must be at least 12 characters.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                try:
                    register_and_login(
                        email=email.strip(),
                        display_name=display_name.strip(),
                        password=password,
                    )
                    st.success("Account created and signed in.")
                    st.rerun()
                except ApiError as exc:
                    render_error(exc)

    with tab_invite:
        st.info(
            "This app does not send email. Paste the one-time acceptance token "
            "from the invitation creator, then sign in with the invited email."
        )
        default_token = pending_invite_token() or ""
        token = st.text_input("Invitation token", value=default_token, type="password")
        if token and token != pending_invite_token():
            st.session_state[PENDING_INVITE_TOKEN_KEY] = token
        if not is_authenticated():
            st.warning("Sign in first with the invited email address.")
        elif st.button("Accept invitation", type="primary"):
            client = get_api_client()
            try:
                group = client.accept_invitation(token.strip())
                clear_pending_invite_token()
                st.success(f"Joined group **{group.name}**.")
            except ApiError as exc:
                render_error(exc)
            finally:
                client.close()


def render_dashboard() -> None:
    user = require_auth()
    if user is None:
        return
    st.title(f"Welcome, {user.display_name}")
    client = get_api_client()
    health_ok = False
    pipelines = []
    runs = []
    schedules = []
    groups = []
    try:
        health = client.health()
        health_ok = health.get("status") == "ok"
    except ApiError as exc:
        st.warning(f"API health check failed: {exc.message}")
    try:
        pipelines = client.list_pipelines()
    except ApiError as exc:
        st.warning(f"Could not load pipelines: {exc.message}")
    try:
        runs = client.list_runs(limit=20)
    except ApiError as exc:
        st.warning(f"Could not load runs: {exc.message}")
    try:
        schedules = client.list_schedules()
    except ApiError as exc:
        st.warning(f"Could not load schedules: {exc.message}")
    try:
        groups = client.list_groups()
    except ApiError as exc:
        st.warning(f"Could not load groups: {exc.message}")
    finally:
        client.close()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("API", "ok" if health_ok else "down")
    owned = sum(1 for p in pipelines if p.access_source == "owned")
    shared = sum(1 for p in pipelines if p.access_source == "group")
    c2.metric("Pipelines", f"{owned} owned / {shared} shared")
    c3.metric("Recent runs", len(runs))
    enabled = [s for s in schedules if s.enabled]
    nearest = min((s.next_run_at for s in enabled if s.next_run_at), default=None)
    c4.metric("Enabled schedules", len(enabled))
    c5.metric("Groups", len(groups))
    if nearest:
        st.caption(f"Nearest next run: {format_dt(nearest)}")

    st.subheader("Quick actions")
    a1, a2, a3, a4 = st.columns(4)
    if a1.button("Pipelines", use_container_width=True):
        st.switch_page("pages/01_Pipelines.py")
    if a2.button("Run history", use_container_width=True):
        st.switch_page("pages/03_Runs.py")
    if a3.button("New token", use_container_width=True):
        st.switch_page("pages/05_API_Tokens.py")
    if a4.button("New group", use_container_width=True):
        st.switch_page("pages/06_Groups.py")

    if pending_invite_token():
        st.info("You have a pending group invitation token. Open the Accept invitation tab on refresh or use Groups.")

    st.subheader("Recent runs")
    if not runs:
        st.write("No runs yet.")
    else:
        for run in runs[:10]:
            st.write(
                f"{status_emoji(run.status)} `{run.status}` · pipeline `{run.pipeline_id}` · "
                f"{format_dt(run.created_at)}"
            )


if is_authenticated():
    render_dashboard()
else:
    if access_token() and token_expired():
        clear_auth_state()
    render_auth()
