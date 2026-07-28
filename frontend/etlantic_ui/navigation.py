from __future__ import annotations

import streamlit as st

from etlantic_ui.state import current_user, is_authenticated, logout


def render_sidebar() -> None:
    user = current_user()
    with st.sidebar:
        st.markdown("### ETLantic Runner")
        if user:
            st.caption(f"Signed in as **{user.display_name}**")
            st.caption(user.email)
            if st.button("Sign out", use_container_width=True):
                logout()
                st.switch_page("Home.py")
        else:
            st.caption("Not signed in")


def page_guard() -> bool:
    """Return True when the page may continue for an authenticated user."""
    from etlantic_ui.state import require_auth

    render_sidebar()
    if not is_authenticated():
        require_auth()
        return False
    return require_auth() is not None
