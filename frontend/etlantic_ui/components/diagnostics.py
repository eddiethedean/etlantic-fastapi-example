from __future__ import annotations

from typing import Any

import streamlit as st


def render_diagnostics(diagnostics: list[dict[str, Any]]) -> None:
    if not diagnostics:
        st.success("No diagnostics.")
        return
    by_severity: dict[str, list[dict[str, Any]]] = {}
    for item in diagnostics:
        severity = str(item.get("severity") or item.get("level") or "info").lower()
        by_severity.setdefault(severity, []).append(item)
    for severity in ("error", "warning", "info", "hint"):
        items = by_severity.pop(severity, [])
        if not items:
            continue
        st.markdown(f"**{severity.title()} ({len(items)})**")
        for item in items:
            code = item.get("code") or ""
            message = item.get("message") or item.get("msg") or str(item)
            path = item.get("path") or item.get("json_path") or ""
            line = f"`{code}` {message}" if code else message
            if path:
                line += f" — `{path}`"
            if severity == "error":
                st.error(line)
            elif severity == "warning":
                st.warning(line)
            else:
                st.info(line)
    for severity, items in by_severity.items():
        st.markdown(f"**{severity.title()} ({len(items)})**")
        for item in items:
            st.write(item)
