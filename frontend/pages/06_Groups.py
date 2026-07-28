from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from etlantic_ui.components.group_members import render_group_members
from etlantic_ui.errors import ApiError, render_error
from etlantic_ui.formatting import format_dt
from etlantic_ui.navigation import page_guard
from etlantic_ui.state import (
    LAST_ACCEPT_TOKEN_KEY,
    SELECTED_GROUP_ID_KEY,
    get_api_client,
    require_auth,
)

st.set_page_config(page_title="Groups", layout="wide")
if not page_guard():
    st.stop()
user = require_auth()
assert user is not None

st.title("Groups")
client = get_api_client()

try:
    groups = client.list_groups()
except ApiError as exc:
    render_error(exc)
    client.close()
    st.stop()

st.subheader("Your groups")
for group in groups:
    cols = st.columns([3, 1])
    cols[0].markdown(
        f"**{group.name}** · role `{group.current_user_role}`  \n"
        f"{group.description or ''}"
    )
    if cols[1].button("Open", key=f"open-g-{group.id}"):
        st.session_state[SELECTED_GROUP_ID_KEY] = group.id

st.divider()
st.subheader("Create group")
with st.form("create-group"):
    name = st.text_input("Name")
    description = st.text_input("Description")
    submitted = st.form_submit_button("Create")
if submitted:
    try:
        created = client.create_group(
            name=name.strip(), description=description.strip() or None
        )
        st.session_state[SELECTED_GROUP_ID_KEY] = created.id
        st.success(f"Created `{created.name}`")
        st.rerun()
    except ApiError as exc:
        render_error(exc)

group_id = st.session_state.get(SELECTED_GROUP_ID_KEY)
if not group_id:
    client.close()
    st.stop()

try:
    group = client.get_group(group_id)
except ApiError as exc:
    render_error(exc)
    client.close()
    st.stop()

st.divider()
st.header(f"Workspace: {group.name}")
st.caption(f"Your role: `{group.current_user_role}`")

tab_pipes, tab_members, tab_invites, tab_settings = st.tabs(
    ["Pipelines", "Members", "Invitations", "Settings"]
)

with tab_pipes:
    try:
        shared = client.list_group_pipelines(group.id)
        owned = [p for p in client.list_pipelines() if p.can_delete]
    except ApiError as exc:
        render_error(exc)
        shared, owned = [], []
    st.write("Shared with this group")
    for pipeline in shared:
        cols = st.columns([3, 1])
        cols[0].write(f"**{pipeline.name}** · owner `{pipeline.owner_id}`")
        if pipeline.owner_id == user.id and cols[1].button(
            "Unshare", key=f"un-{pipeline.id}"
        ):
            try:
                client.remove_pipeline_from_group(group.id, pipeline.id)
                st.rerun()
            except ApiError as exc:
                render_error(exc)
    addable = [p for p in owned if group.id not in p.shared_group_ids]
    if addable:
        labels = {p.name: p.id for p in addable}
        chosen = st.selectbox("Add one of my pipelines", list(labels.keys()))
        if st.button("Share pipeline"):
            try:
                client.add_pipeline_to_group(group.id, labels[chosen])
                st.rerun()
            except ApiError as exc:
                render_error(exc)
    else:
        st.caption("No additional owned pipelines to share.")

with tab_members:
    try:
        members = client.list_group_members(group.id)
    except ApiError as exc:
        render_error(exc)
        members = []

    def _remove(member_user_id: str) -> None:
        try:
            client.remove_group_member(group.id, member_user_id)
            st.rerun()
        except ApiError as exc:
            render_error(exc)

    render_group_members(
        members,
        current_user=user,
        current_role=group.current_user_role,
        on_remove=_remove,
    )

with tab_invites:
    st.info(
        "This application does not send email. Copy the acceptance link/token "
        "immediately — it is shown only once."
    )
    email = st.text_input("Invite email")
    if st.button("Send invitation") and email.strip():
        try:
            invitation = client.create_invitation(group.id, email=email.strip())
            st.session_state[LAST_ACCEPT_TOKEN_KEY] = invitation.accept_token
            st.success("Invitation created. Copy the token below now.")
        except ApiError as exc:
            render_error(exc)
    token = st.session_state.get(LAST_ACCEPT_TOKEN_KEY)
    if token:
        st.code(token)
        st.caption(
            "Acceptance URL pattern: Home page → Accept invitation tab, or "
            "`?invite=<token>` query parameter."
        )
        if st.button("Clear displayed token"):
            st.session_state.pop(LAST_ACCEPT_TOKEN_KEY, None)
            st.rerun()
    try:
        invitations = client.list_invitations(group.id)
    except ApiError as exc:
        render_error(exc)
        invitations = []
    for invite in invitations:
        cols = st.columns([3, 1, 1])
        cols[0].write(
            f"{invite.email} · `{invite.status}` · expires {format_dt(invite.expires_at)}"
        )
        if invite.status == "pending" and cols[1].button(
            "Revoke", key=f"rev-{invite.id}"
        ):
            try:
                client.revoke_invitation(group.id, invite.id)
                st.rerun()
            except ApiError as exc:
                render_error(exc)

with tab_settings:
    if group.current_user_role != "owner":
        st.caption("Only the group owner can edit settings or delete the group.")
        if st.button("Leave group"):
            try:
                client.remove_group_member(group.id, user.id)
                st.session_state.pop(SELECTED_GROUP_ID_KEY, None)
                st.rerun()
            except ApiError as exc:
                render_error(exc)
    else:
        new_name = st.text_input("Name", value=group.name)
        new_description = st.text_input("Description", value=group.description or "")
        if st.button("Save settings"):
            try:
                client.update_group(
                    group.id,
                    name=new_name.strip(),
                    description=new_description.strip() or None,
                    clear_description=not new_description.strip(),
                )
                st.success("Saved.")
                st.rerun()
            except ApiError as exc:
                render_error(exc)
        confirm = st.text_input("Type DELETE to confirm group deletion")
        if st.button("Delete group", type="primary") and confirm == "DELETE":
            try:
                client.delete_group(group.id)
                st.session_state.pop(SELECTED_GROUP_ID_KEY, None)
                st.success("Deleted.")
                st.rerun()
            except ApiError as exc:
                render_error(exc)

client.close()
