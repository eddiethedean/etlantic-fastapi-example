from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from etlantic_ui.components.run_status import render_run_status
from etlantic_ui.errors import ApiError, render_error
from etlantic_ui.formatting import format_dt, status_emoji
from etlantic_ui.navigation import page_guard
from etlantic_ui.polling import is_terminal
from etlantic_ui.state import SELECTED_RUN_ID_KEY, get_api_client, require_auth

st.set_page_config(page_title="Runs", layout="wide")
if not page_guard():
    st.stop()
require_auth()

st.title("Run history")
st.caption(
    "Runs are scoped to the user who initiated them. Group members do not automatically "
    "see each other's run records."
)

client = get_api_client()
try:
    pipelines = {p.id: p.name for p in client.list_pipelines()}
    runs = client.list_runs(limit=100)
except ApiError as exc:
    render_error(exc)
    client.close()
    st.stop()

status_filter = st.multiselect(
    "Status",
    ["queued", "running", "succeeded", "partial", "failed"],
    default=[],
)
pipeline_filter = st.selectbox(
    "Pipeline",
    ["all", *sorted(pipelines.values())],
)
auto_refresh = st.checkbox(
    "Auto-refresh while queued/running runs are visible", value=False
)

filtered = []
for run in runs:
    if status_filter and run.status not in status_filter:
        continue
    if pipeline_filter != "all" and pipelines.get(run.pipeline_id) != pipeline_filter:
        continue
    filtered.append(run)

active = [r for r in filtered if not is_terminal(r.status)]
if auto_refresh and active:
    st.info(f"{len(active)} active run(s) — refreshing…")
    import time

    time.sleep(2)
    st.rerun()

selected = st.session_state.get(SELECTED_RUN_ID_KEY)
for run in filtered:
    label = (
        f"{status_emoji(run.status)} `{run.status}` · "
        f"{pipelines.get(run.pipeline_id, run.pipeline_id)} · {format_dt(run.created_at)}"
    )
    if st.button(label, key=f"runrow-{run.id}"):
        st.session_state[SELECTED_RUN_ID_KEY] = run.id
        selected = run.id

if selected:
    try:
        detail = client.get_run(selected)
        st.divider()
        render_run_status(detail)
    except ApiError as exc:
        render_error(exc)

client.close()
