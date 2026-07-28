from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from etlantic_ui.errors import ApiError, ConflictError, render_error
from etlantic_ui.formatting import format_dt
from etlantic_ui.navigation import page_guard
from etlantic_ui.state import (
    SELECTED_PIPELINE_ID_KEY,
    get_api_client,
    require_auth,
)

st.set_page_config(page_title="Pipelines", layout="wide")
if not page_guard():
    st.stop()
user = require_auth()
assert user is not None

st.title("Pipelines")

client = get_api_client()
try:
    pipelines = client.list_pipelines()
except ApiError as exc:
    render_error(exc)
    client.close()
    st.stop()

access_filter = st.selectbox("Access", ["all", "owned", "shared"])
name_filter = st.text_input("Filter by name").strip().lower()
filtered = []
for pipeline in pipelines:
    if access_filter == "owned" and pipeline.access_source != "owned":
        continue
    if access_filter == "shared" and pipeline.access_source != "group":
        continue
    if name_filter and name_filter not in pipeline.name.lower():
        continue
    filtered.append(pipeline)

st.subheader(f"{len(filtered)} pipeline(s)")
for pipeline in filtered:
    cols = st.columns([3, 1, 1, 1, 2])
    cols[0].markdown(
        f"**{pipeline.name}**  \n"
        f"`{pipeline.access_source}` · v{pipeline.version} · "
        f"updated {format_dt(pipeline.updated_at)}"
    )
    if cols[1].button("Open", key=f"open-{pipeline.id}"):
        st.session_state[SELECTED_PIPELINE_ID_KEY] = pipeline.id
        st.switch_page("pages/02_Pipeline_Workspace.py")
    if cols[2].button("Validate", key=f"val-{pipeline.id}"):
        try:
            result = client.validate_pipeline(pipeline.id)
            st.toast(f"Validate ok={result.ok}")
        except ApiError as exc:
            render_error(exc)
    if cols[3].button("Run", key=f"run-{pipeline.id}"):
        try:
            run = client.submit_run(pipeline.id)
            st.session_state["selected_run_id"] = run.id
            st.success(f"Queued run `{run.id}`")
        except ApiError as exc:
            render_error(exc)
    with cols[4]:
        if pipeline.can_delete:
            if st.button("Delete", key=f"del-{pipeline.id}"):
                try:
                    client.delete_pipeline(pipeline.id)
                    st.rerun()
                except ApiError as exc:
                    render_error(exc)
        else:
            st.caption("Shared — cannot delete")

st.divider()
st.subheader("Create pipeline")
with st.form("create-pipeline"):
    name = st.text_input("Name")
    description = st.text_input("Description")
    document_text = st.text_area("Sealed ETLantic JSON document", height=240)
    submitted = st.form_submit_button("Create")
if submitted:
    try:
        document = json.loads(document_text)
    except json.JSONDecodeError as exc:
        st.error(f"Invalid JSON: {exc}")
    else:
        try:
            draft = client.verify_draft(document)
            if not draft.ok or draft.document is None:
                st.error("Draft verification failed.")
                st.write(draft.diagnostics)
            else:
                created = client.create_pipeline(
                    name=name.strip(),
                    description=description.strip() or None,
                    document=draft.document,
                )
                st.success(f"Created `{created.name}`")
                st.session_state[SELECTED_PIPELINE_ID_KEY] = created.id
                st.rerun()
        except ConflictError as exc:
            render_error(exc)
        except ApiError as exc:
            render_error(exc)

client.close()
