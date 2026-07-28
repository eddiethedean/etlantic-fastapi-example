from __future__ import annotations

import streamlit as st


def render_token_create_form(key_prefix: str = "token") -> dict[str, object] | None:
    name = st.text_input("Token name", key=f"{key_prefix}-name")
    value = st.text_input(
        "Token value",
        type="password",
        key=f"{key_prefix}-value",
        help="This value cannot be retrieved later.",
    )
    allow_read = st.checkbox("Allow read", value=True, key=f"{key_prefix}-read")
    allow_write = st.checkbox("Allow write", value=False, key=f"{key_prefix}-write")
    st.info("After save, the plaintext value is cleared and never shown again.")
    if not name or not value:
        return None
    if not allow_read and not allow_write:
        st.warning("Select at least one permission.")
        return None
    return {
        "name": name,
        "value": value,
        "allow_read": allow_read,
        "allow_write": allow_write,
    }


def clear_token_form_widgets(key_prefix: str = "token") -> None:
    for suffix in ("name", "value", "read", "write"):
        st.session_state.pop(f"{key_prefix}-{suffix}", None)
