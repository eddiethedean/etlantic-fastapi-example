from __future__ import annotations

import json
from typing import Any

import streamlit as st

from etlantic_ui.state import get_editor_state, set_editor_state


def render_pipeline_editor(
    pipeline_id: str,
    document: dict[str, Any],
    *,
    version: int,
    fingerprint: str,
) -> str:
    existing = get_editor_state(pipeline_id)
    if existing is None:
        text = json.dumps(document, indent=2, sort_keys=True)
        set_editor_state(pipeline_id, text, version=version, fingerprint=fingerprint)
    else:
        text = existing["text"]

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Format JSON", key=f"fmt-{pipeline_id}"):
            try:
                parsed = json.loads(st.session_state.get(f"editor-{pipeline_id}", text))
                text = json.dumps(parsed, indent=2, sort_keys=True)
                set_editor_state(
                    pipeline_id,
                    text,
                    version=st.session_state.get("pipeline_editor_version", version),
                    fingerprint=st.session_state.get(
                        "pipeline_editor_fingerprint", fingerprint
                    ),
                )
            except json.JSONDecodeError as exc:
                st.error(f"Cannot format: {exc}")
    with col2:
        st.download_button(
            "Export JSON",
            data=text,
            file_name=f"pipeline-{pipeline_id}.json",
            mime="application/json",
            key=f"export-{pipeline_id}",
        )
    with col3:
        uploaded = st.file_uploader(
            "Import JSON", type=["json"], key=f"import-{pipeline_id}"
        )
        if uploaded is not None:
            imported = uploaded.read().decode("utf-8")
            text = imported
            set_editor_state(
                pipeline_id,
                text,
                version=st.session_state.get("pipeline_editor_version", version),
                fingerprint=st.session_state.get(
                    "pipeline_editor_fingerprint", fingerprint
                ),
            )

    edited = st.text_area(
        "Pipeline document",
        value=text,
        height=420,
        key=f"editor-{pipeline_id}",
    )
    set_editor_state(
        pipeline_id,
        edited,
        version=st.session_state.get("pipeline_editor_version", version),
        fingerprint=st.session_state.get("pipeline_editor_fingerprint", fingerprint),
    )
    st.caption(
        f"Base version `{st.session_state.get('pipeline_editor_version', version)}` · "
        f"fingerprint `{st.session_state.get('pipeline_editor_fingerprint', fingerprint)[:16]}…`"
    )
    return edited
