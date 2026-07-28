from __future__ import annotations

import streamlit as st

from etlantic_ui.formatting import format_dt, node_counts
from etlantic_ui.models import PipelineRead


def render_pipeline_summary(pipeline: PipelineRead) -> None:
    badge = "Owned" if pipeline.access_source == "owned" else "Shared"
    st.markdown(f"### {pipeline.name} · `{badge}`")
    if pipeline.description:
        st.write(pipeline.description)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Version", pipeline.version)
    c2.metric("Access", pipeline.access_source)
    counts = node_counts(pipeline.document)
    c3.metric("Sources", counts["extract"])
    c4.metric("Sinks", counts["load"])
    st.caption(
        f"Owner `{pipeline.owner_id}` · fingerprint `{pipeline.fingerprint[:20]}…` · "
        f"updated {format_dt(pipeline.updated_at)}"
    )
    if pipeline.shared_group_ids:
        st.caption("Shared via groups: " + ", ".join(pipeline.shared_group_ids))
