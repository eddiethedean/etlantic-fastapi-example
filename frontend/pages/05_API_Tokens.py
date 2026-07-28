from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from etlantic_ui.components.token_form import (
    clear_token_form_widgets,
    render_token_create_form,
)
from etlantic_ui.errors import ApiError, render_error
from etlantic_ui.formatting import format_dt, mask_token
from etlantic_ui.navigation import page_guard
from etlantic_ui.state import get_api_client, require_auth

st.set_page_config(page_title="API tokens", layout="wide")
if not page_guard():
    st.stop()
require_auth()

st.title("API token vault")
st.warning(
    "Token values are write-only. After submission they are encrypted by the API and "
    "never returned. Losing the server encryption key makes stored tokens unrecoverable."
)

client = get_api_client()

st.subheader("Store a token")
payload = render_token_create_form("create")
if payload and st.button("Save token", type="primary"):
    try:
        created = client.create_token(
            name=str(payload["name"]),
            value=str(payload["value"]),
            allow_read=bool(payload["allow_read"]),
            allow_write=bool(payload["allow_write"]),
        )
        clear_token_form_widgets("create")
        st.success(
            f"Stored `{created.name}` ending in {mask_token(created.last_four)}"
        )
        st.rerun()
    except ApiError as exc:
        render_error(exc)

try:
    tokens = client.list_tokens()
except ApiError as exc:
    render_error(exc)
    client.close()
    st.stop()

st.subheader("Your tokens")
for token in tokens:
    cols = st.columns([3, 2, 1, 1, 1])
    cols[0].markdown(
        f"**{token.name}** `{mask_token(token.last_four)}`  \n"
        f"read={token.allow_read} write={token.allow_write} active={token.is_active}"
    )
    cols[1].caption(
        f"used {format_dt(token.last_used_at)} · created {format_dt(token.created_at)}"
    )
    if cols[2].button("Rotate", key=f"rot-{token.id}"):
        st.session_state["rotate_token_id"] = token.id
    if cols[3].button(
        "Disable" if token.is_active else "Enable", key=f"act-{token.id}"
    ):
        try:
            client.update_token(token.id, is_active=not token.is_active)
            st.rerun()
        except ApiError as exc:
            render_error(exc)
    if cols[4].button("Delete", key=f"del-{token.id}"):
        if st.session_state.get(f"confirm-del-{token.id}"):
            try:
                client.delete_token(token.id)
                st.rerun()
            except ApiError as exc:
                render_error(exc)
        else:
            st.session_state[f"confirm-del-{token.id}"] = True
            st.warning("Deleting removes related pipeline grants. Click delete again.")

rotate_id = st.session_state.get("rotate_token_id")
if rotate_id:
    st.divider()
    st.subheader("Rotate token")
    st.caption("Grants keep referencing the same token ID after rotation.")
    new_value = st.text_input("New token value", type="password", key="rotate-value")
    if st.button("Apply rotation"):
        try:
            client.update_token(rotate_id, value=new_value)
            st.session_state.pop("rotate_token_id", None)
            st.session_state.pop("rotate-value", None)
            st.success("Rotated.")
            st.rerun()
        except ApiError as exc:
            render_error(exc)

client.close()
