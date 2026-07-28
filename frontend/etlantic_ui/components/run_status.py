from __future__ import annotations

import json

import streamlit as st

from etlantic_ui.formatting import format_dt, status_emoji
from etlantic_ui.models import RunRead


def render_run_status(run: RunRead) -> None:
    st.markdown(f"#### {status_emoji(run.status)} `{run.status}`")
    c1, c2, c3 = st.columns(3)
    c1.write(f"**Run ID:** `{run.id}`")
    c2.write(f"**Pipeline:** `{run.pipeline_id}`")
    c3.write(f"**Version:** `{run.pipeline_version}`")
    st.caption(
        f"Created {format_dt(run.created_at)} · started {format_dt(run.started_at)} · "
        f"finished {format_dt(run.finished_at)}"
    )
    if run.error:
        st.error(run.error)
    if run.report is not None:
        with st.expander("Run report JSON"):
            st.code(json.dumps(run.report, indent=2), language="json")
