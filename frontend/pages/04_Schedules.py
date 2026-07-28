from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from etlantic_ui.components.schedule_form import render_schedule_form
from etlantic_ui.errors import ApiError, render_error
from etlantic_ui.formatting import format_dt
from etlantic_ui.navigation import page_guard
from etlantic_ui.state import get_api_client, require_auth

st.set_page_config(page_title="Schedules", layout="wide")
if not page_guard():
    st.stop()
require_auth()

st.title("Schedules")
st.caption(
    "Schedules are owned by their creator, even when attached to a group-shared pipeline."
)

client = get_api_client()
try:
    pipelines = client.list_pipelines()
    schedules = client.list_schedules()
except ApiError as exc:
    render_error(exc)
    client.close()
    st.stop()

pipeline_names = {p.id: p.name for p in pipelines}
enabled_filter = st.selectbox("Enabled", ["all", "yes", "no"])
type_filter = st.selectbox("Trigger type", ["all", "interval", "cron", "date"])

filtered = []
for schedule in schedules:
    if enabled_filter == "yes" and not schedule.enabled:
        continue
    if enabled_filter == "no" and schedule.enabled:
        continue
    if type_filter != "all" and schedule.trigger_type != type_filter:
        continue
    filtered.append(schedule)

for schedule in filtered:
    cols = st.columns([3, 1, 1, 1])
    cols[0].markdown(
        f"**{schedule.name}**  \n"
        f"{pipeline_names.get(schedule.pipeline_id, schedule.pipeline_id)} · "
        f"`{schedule.trigger_type}` · next {format_dt(schedule.next_run_at)}"
    )
    if cols[1].button("Disable" if schedule.enabled else "Enable", key=f"e-{schedule.id}"):
        try:
            client.update_schedule(schedule.id, enabled=not schedule.enabled)
            st.rerun()
        except ApiError as exc:
            render_error(exc)
    if cols[2].button("Delete", key=f"d-{schedule.id}"):
        confirm = st.session_state.get(f"confirm-{schedule.id}")
        if not confirm:
            st.session_state[f"confirm-{schedule.id}"] = True
            st.warning("Click delete again to confirm.")
        else:
            try:
                client.delete_schedule(schedule.id)
                st.session_state.pop(f"confirm-{schedule.id}", None)
                st.rerun()
            except ApiError as exc:
                render_error(exc)

st.divider()
st.subheader("Create schedule")
if not pipelines:
    st.info("Create a pipeline first.")
else:
    labels = {f"{p.name} ({p.id[:8]})": p.id for p in pipelines}
    chosen = st.selectbox("Pipeline", list(labels.keys()))
    form = render_schedule_form(key_prefix="global-sched")
    if form and st.button("Create", type="primary"):
        name, trigger_type, trigger_args, enabled = form
        try:
            client.create_schedule(
                labels[chosen],
                name=name,
                trigger_type=trigger_type,
                trigger_args=trigger_args,
                enabled=enabled,
            )
            st.success("Schedule created.")
            st.rerun()
        except ApiError as exc:
            render_error(exc)

client.close()
