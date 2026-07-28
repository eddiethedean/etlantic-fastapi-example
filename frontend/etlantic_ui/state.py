from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import streamlit as st

from etlantic_ui.api_client import EtlanticApiClient
from etlantic_ui.errors import AuthenticationError
from etlantic_ui.models import UserRead

ACCESS_TOKEN_KEY = "access_token"
TOKEN_EXPIRES_AT_KEY = "token_expires_at"
USER_KEY = "current_user"
PENDING_INVITE_TOKEN_KEY = "pending_invite_token"
SELECTED_PIPELINE_ID_KEY = "selected_pipeline_id"
SELECTED_GROUP_ID_KEY = "selected_group_id"
SELECTED_RUN_ID_KEY = "selected_run_id"
SELECTED_SCHEDULE_ID_KEY = "selected_schedule_id"
EDITOR_TEXT_KEY = "pipeline_editor_text"
EDITOR_PIPELINE_ID_KEY = "pipeline_editor_pipeline_id"
EDITOR_VERSION_KEY = "pipeline_editor_version"
EDITOR_FINGERPRINT_KEY = "pipeline_editor_fingerprint"
LAST_ACCEPT_TOKEN_KEY = "last_accept_token_display"

USER_SCOPED_KEYS = (
    ACCESS_TOKEN_KEY,
    TOKEN_EXPIRES_AT_KEY,
    USER_KEY,
    SELECTED_PIPELINE_ID_KEY,
    SELECTED_GROUP_ID_KEY,
    SELECTED_RUN_ID_KEY,
    SELECTED_SCHEDULE_ID_KEY,
    EDITOR_TEXT_KEY,
    EDITOR_PIPELINE_ID_KEY,
    EDITOR_VERSION_KEY,
    EDITOR_FINGERPRINT_KEY,
    LAST_ACCEPT_TOKEN_KEY,
)


def clear_auth_state() -> None:
    for key in USER_SCOPED_KEYS:
        st.session_state.pop(key, None)


def set_auth_session(access_token: str, expires_in: int, user: UserRead) -> None:
    st.session_state[ACCESS_TOKEN_KEY] = access_token
    st.session_state[TOKEN_EXPIRES_AT_KEY] = (
        datetime.now(UTC) + timedelta(seconds=expires_in)
    ).isoformat()
    st.session_state[USER_KEY] = user.model_dump(mode="json")


def token_expired() -> bool:
    raw = st.session_state.get(TOKEN_EXPIRES_AT_KEY)
    if not raw:
        return True
    expires_at = datetime.fromisoformat(raw)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return datetime.now(UTC) >= expires_at


def current_user() -> UserRead | None:
    data = st.session_state.get(USER_KEY)
    if not data:
        return None
    return UserRead.model_validate(data)


def access_token() -> str | None:
    return st.session_state.get(ACCESS_TOKEN_KEY)


def get_api_client() -> EtlanticApiClient:
    return EtlanticApiClient(access_token=access_token())


def is_authenticated() -> bool:
    return bool(access_token()) and not token_expired()


def require_auth() -> UserRead | None:
    """Return the current user or stop the page after redirecting to login."""
    if not access_token() or token_expired():
        clear_auth_state()
        st.warning("Please sign in to continue.")
        st.switch_page("Home.py")
        return None
    user = current_user()
    if user is not None:
        return user
    client = get_api_client()
    try:
        user = client.get_me()
    except AuthenticationError:
        clear_auth_state()
        st.warning("Your session expired. Please sign in again.")
        st.switch_page("Home.py")
        return None
    finally:
        client.close()
    st.session_state[USER_KEY] = user.model_dump(mode="json")
    return user


def login_and_store(email: str, password: str) -> UserRead:
    client = get_api_client()
    try:
        token = client.login(email=email, password=password)
        client.with_token(token.access_token)
        user = client.get_me()
        set_auth_session(token.access_token, token.expires_in, user)
        return user
    finally:
        client.close()


def register_and_login(
    *, email: str, display_name: str, password: str
) -> UserRead:
    client = get_api_client()
    try:
        client.register_user(
            email=email, display_name=display_name, password=password
        )
    finally:
        client.close()
    return login_and_store(email, password)


def logout() -> None:
    clear_auth_state()


def capture_invite_query_param() -> None:
    params = st.query_params
    token = params.get("invite")
    if token:
        st.session_state[PENDING_INVITE_TOKEN_KEY] = token
        try:
            del st.query_params["invite"]
        except (KeyError, TypeError, AttributeError):
            pass


def pending_invite_token() -> str | None:
    return st.session_state.get(PENDING_INVITE_TOKEN_KEY)


def clear_pending_invite_token() -> None:
    st.session_state.pop(PENDING_INVITE_TOKEN_KEY, None)


def set_editor_state(
    pipeline_id: str,
    text: str,
    *,
    version: int,
    fingerprint: str,
) -> None:
    st.session_state[EDITOR_PIPELINE_ID_KEY] = pipeline_id
    st.session_state[EDITOR_TEXT_KEY] = text
    st.session_state[EDITOR_VERSION_KEY] = version
    st.session_state[EDITOR_FINGERPRINT_KEY] = fingerprint


def get_editor_state(pipeline_id: str) -> dict[str, Any] | None:
    if st.session_state.get(EDITOR_PIPELINE_ID_KEY) != pipeline_id:
        return None
    text = st.session_state.get(EDITOR_TEXT_KEY)
    if text is None:
        return None
    return {
        "text": text,
        "version": st.session_state.get(EDITOR_VERSION_KEY),
        "fingerprint": st.session_state.get(EDITOR_FINGERPRINT_KEY),
    }
