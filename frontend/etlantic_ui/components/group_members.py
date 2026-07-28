from __future__ import annotations

import streamlit as st

from etlantic_ui.formatting import format_dt
from etlantic_ui.models import GroupMemberRead, UserRead


def render_group_members(
    members: list[GroupMemberRead],
    *,
    current_user: UserRead,
    current_role: str,
    on_remove,
) -> None:
    for member in members:
        cols = st.columns([3, 2, 2, 2])
        cols[0].write(f"**{member.user.display_name}** ({member.user.email})")
        cols[1].write(member.role)
        cols[2].write(format_dt(member.created_at))
        with cols[3]:
            if member.user_id == current_user.id and current_role == "member":
                if st.button("Leave", key=f"leave-{member.id}"):
                    on_remove(member.user_id)
            elif current_role == "owner" and member.role != "owner":
                if st.button("Remove", key=f"remove-{member.id}"):
                    on_remove(member.user_id)
