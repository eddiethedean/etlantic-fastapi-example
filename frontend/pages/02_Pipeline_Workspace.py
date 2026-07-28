from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from etlantic_ui.components.diagnostics import render_diagnostics
from etlantic_ui.components.pipeline_editor import render_pipeline_editor
from etlantic_ui.components.pipeline_summary import render_pipeline_summary
from etlantic_ui.components.run_status import render_run_status
from etlantic_ui.components.schedule_form import render_schedule_form
from etlantic_ui.errors import ApiError, ConflictError, render_error
from etlantic_ui.formatting import asset_bindings, format_dt, mask_token
from etlantic_ui.navigation import page_guard
from etlantic_ui.polling import is_terminal, poll_run
from etlantic_ui.state import (
    SELECTED_PIPELINE_ID_KEY,
    get_api_client,
    get_editor_state,
    require_auth,
    set_editor_state,
)

st.set_page_config(page_title="Pipeline workspace", layout="wide")
if not page_guard():
    st.stop()
user = require_auth()
assert user is not None

client = get_api_client()
try:
    pipelines = client.list_pipelines()
except ApiError as exc:
    render_error(exc)
    client.close()
    st.stop()

options = {f"{p.name} ({p.access_source})": p.id for p in pipelines}
if not options:
    st.info("No pipelines yet. Create one on the Pipelines page.")
    client.close()
    st.stop()

default_id = st.session_state.get(SELECTED_PIPELINE_ID_KEY)
labels = list(options.keys())
default_index = 0
if default_id:
    for i, label in enumerate(labels):
        if options[label] == default_id:
            default_index = i
            break
selected_label = st.selectbox("Pipeline", labels, index=default_index)
pipeline_id = options[selected_label]
st.session_state[SELECTED_PIPELINE_ID_KEY] = pipeline_id

try:
    pipeline = client.get_pipeline(pipeline_id)
except ApiError as exc:
    render_error(exc)
    client.close()
    st.stop()

tabs = st.tabs(
    [
        "Overview",
        "Definition",
        "Diagnostics",
        "Plan",
        "Runs",
        "Schedules",
        "Credentials",
        "Sharing",
    ]
)

with tabs[0]:
    render_pipeline_summary(pipeline)
    c1, c2, c3 = st.columns(3)
    if c1.button("Validate now"):
        try:
            result = client.validate_pipeline(pipeline.id)
            st.session_state["last_validation"] = result.model_dump(mode="json")
            st.success(f"ok={result.ok}")
        except ApiError as exc:
            render_error(exc)
    if c2.button("Plan now"):
        try:
            result = client.plan_pipeline(pipeline.id)
            st.session_state["last_plan"] = result.model_dump(mode="json")
            st.success(f"ok={result.ok}")
        except ApiError as exc:
            render_error(exc)
    if c3.button("Run now", type="primary"):
        try:
            run = client.submit_run(pipeline.id)
            st.session_state["workspace_active_run"] = run.id
            st.success(f"Queued `{run.id}`")
        except ApiError as exc:
            render_error(exc)

with tabs[1]:
    st.write(
        "Edit JSON, then **Verify & save**. Unsaved text is kept across Streamlit reruns."
    )
    edited_text = render_pipeline_editor(
        pipeline.id,
        pipeline.document,
        version=pipeline.version,
        fingerprint=pipeline.fingerprint,
    )
    name = st.text_input("Name", value=pipeline.name)
    description = st.text_input("Description", value=pipeline.description or "")
    if st.button("Verify & save", type="primary"):
        try:
            document = json.loads(edited_text)
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            try:
                draft = client.verify_draft(document, pipeline_id=pipeline.id)
                if not draft.ok or draft.document is None:
                    st.error("Verification failed.")
                    render_diagnostics(draft.diagnostics)
                else:
                    editor = get_editor_state(pipeline.id) or {}
                    expected = editor.get("version") or pipeline.version
                    updated = client.update_pipeline(
                        pipeline.id,
                        name=name.strip(),
                        description=description.strip() or None,
                        document=draft.document,
                        expected_version=expected,
                        clear_description=not description.strip(),
                    )
                    set_editor_state(
                        pipeline.id,
                        json.dumps(updated.document, indent=2, sort_keys=True),
                        version=updated.version,
                        fingerprint=updated.fingerprint,
                    )
                    st.success(f"Saved version {updated.version}")
                    st.rerun()
            except ConflictError:
                st.warning(
                    "Version conflict. Reload from server or keep your local text."
                )
                if st.button("Reload from server"):
                    fresh = client.get_pipeline(pipeline.id)
                    set_editor_state(
                        pipeline.id,
                        json.dumps(fresh.document, indent=2, sort_keys=True),
                        version=fresh.version,
                        fingerprint=fresh.fingerprint,
                    )
                    st.rerun()
            except ApiError as exc:
                render_error(exc)

with tabs[2]:
    if st.button("Run validation"):
        try:
            result = client.validate_pipeline(pipeline.id)
            st.session_state["last_validation"] = result.model_dump(mode="json")
        except ApiError as exc:
            render_error(exc)
    payload = st.session_state.get("last_validation")
    if payload:
        st.write(f"ok={payload.get('ok')} · fingerprint `{payload.get('fingerprint')}`")
        render_diagnostics(list(payload.get("diagnostics") or []))
        if not payload.get("ok"):
            st.warning("Validation reported errors — fix before running.")

with tabs[3]:
    if st.button("Build plan"):
        try:
            result = client.plan_pipeline(pipeline.id)
            st.session_state["last_plan"] = result.model_dump(mode="json")
        except ApiError as exc:
            render_error(exc)
    plan_payload = st.session_state.get("last_plan")
    if plan_payload:
        st.write(f"ok={plan_payload.get('ok')}")
        render_diagnostics(list(plan_payload.get("diagnostics") or []))
        plan = plan_payload.get("plan")
        if plan:
            st.subheader("Plan summary")
            for key in ("nodes", "bindings", "implementations", "regions"):
                if key in plan:
                    st.write(f"**{key}**")
                    st.write(plan[key])
            with st.expander("Raw plan JSON"):
                st.code(json.dumps(plan, indent=2), language="json")

with tabs[4]:
    if st.button("Submit run"):
        try:
            run = client.submit_run(pipeline.id)
            st.session_state["workspace_active_run"] = run.id
        except ApiError as exc:
            render_error(exc)
    active_id = st.session_state.get("workspace_active_run")
    if active_id:
        try:
            run = client.get_run(active_id)
            render_run_status(run)
            if not is_terminal(run.status):
                st.info("Polling for completion…")
                finished = poll_run(client, active_id, timeout_s=30)
                render_run_status(finished)
        except ApiError as exc:
            render_error(exc)
    try:
        runs = client.list_runs(pipeline_id=pipeline.id, limit=20)
    except ApiError as exc:
        render_error(exc)
        runs = []
    st.subheader("Recent runs for this pipeline")
    for run in runs:
        st.write(
            f"`{run.status}` · `{run.id}` · {format_dt(run.created_at)}"
        )

with tabs[5]:
    st.caption(
        "Schedules are owned by their creator, even when the pipeline is shared."
    )
    form = render_schedule_form(key_prefix=f"ws-{pipeline.id}")
    if form and st.button("Create schedule"):
        name, trigger_type, trigger_args, enabled = form
        try:
            created = client.create_schedule(
                pipeline.id,
                name=name,
                trigger_type=trigger_type,
                trigger_args=trigger_args,
                enabled=enabled,
            )
            st.success(f"Created schedule `{created.name}`")
        except ApiError as exc:
            render_error(exc)
    try:
        schedules = [
            s for s in client.list_schedules() if s.pipeline_id == pipeline.id
        ]
    except ApiError as exc:
        render_error(exc)
        schedules = []
    for schedule in schedules:
        cols = st.columns([3, 1, 1, 1])
        cols[0].write(
            f"**{schedule.name}** · {schedule.trigger_type} · "
            f"next {format_dt(schedule.next_run_at)}"
        )
        if cols[1].button(
            "Disable" if schedule.enabled else "Enable",
            key=f"tog-{schedule.id}",
        ):
            try:
                client.update_schedule(schedule.id, enabled=not schedule.enabled)
                st.rerun()
            except ApiError as exc:
                render_error(exc)
        if cols[2].button("Delete", key=f"ds-{schedule.id}"):
            try:
                client.delete_schedule(schedule.id)
                st.rerun()
            except ApiError as exc:
                render_error(exc)

with tabs[6]:
    st.caption("Token values are never shown. Grants bind metadata-only tokens to assets.")
    bindings = asset_bindings(pipeline.document)
    try:
        tokens = client.list_tokens()
        grants = client.list_token_grants(pipeline.id)
    except ApiError as exc:
        render_error(exc)
        tokens, grants = [], []
    st.write("Existing grants")
    for grant in grants:
        cols = st.columns([4, 1])
        cols[0].write(
            f"`{grant.binding}` · {grant.operation} · provider `{grant.provider}` · "
            f"token `{grant.token_id}`"
        )
        if cols[1].button("Revoke", key=f"rg-{grant.id}"):
            try:
                client.delete_token_grant(pipeline.id, grant.id)
                st.rerun()
            except ApiError as exc:
                render_error(exc)
    st.subheader("Add grant")
    if not bindings:
        st.warning("No asset bindings found in the pipeline document.")
    else:
        binding = st.selectbox("Binding", bindings)
        operation = st.selectbox("Operation", ["read", "write"])
        provider = st.text_input("Provider", value="memory")
        location = st.text_input("Location (optional)")
        eligible = [
            t
            for t in tokens
            if t.is_active
            and ((operation == "read" and t.allow_read) or (operation == "write" and t.allow_write))
        ]
        if not eligible:
            st.warning("No active tokens allow this operation.")
        else:
            label_to_id = {
                f"{t.name} ({mask_token(t.last_four)})": t.id for t in eligible
            }
            chosen = st.selectbox("Token", list(label_to_id.keys()))
            if st.button("Grant token"):
                try:
                    client.create_token_grant(
                        pipeline.id,
                        token_id=label_to_id[chosen],
                        binding=binding,
                        provider=provider.strip(),
                        operation=operation,
                        location=location.strip() or None,
                    )
                    st.success("Grant created.")
                    st.rerun()
                except ApiError as exc:
                    render_error(exc)

with tabs[7]:
    st.write(
        "Group members may edit and run a shared pipeline. Ownership stays with the creator. "
        "Only the owner can unshare or delete."
    )
    try:
        groups = client.list_groups()
    except ApiError as exc:
        render_error(exc)
        groups = []
    linked = set(pipeline.shared_group_ids)
    for group in groups:
        cols = st.columns([3, 1])
        cols[0].write(
            f"**{group.name}** · role `{group.current_user_role}` · "
            f"{'shared here' if group.id in linked else 'not shared'}"
        )
        with cols[1]:
            if pipeline.owner_id != user.id:
                st.caption("Owner only")
            elif group.id in linked:
                if st.button("Unshare", key=f"unshare-{group.id}"):
                    try:
                        client.remove_pipeline_from_group(group.id, pipeline.id)
                        st.rerun()
                    except ApiError as exc:
                        render_error(exc)
            else:
                if st.button("Share", key=f"share-{group.id}"):
                    try:
                        client.add_pipeline_to_group(group.id, pipeline.id)
                        st.rerun()
                    except ApiError as exc:
                        render_error(exc)

client.close()
