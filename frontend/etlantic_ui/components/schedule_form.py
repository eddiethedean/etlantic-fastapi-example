from __future__ import annotations

from typing import Any

import streamlit as st


def build_trigger_args(
    trigger_type: str,
    *,
    key_prefix: str = "sched",
) -> dict[str, Any] | None:
    if trigger_type == "interval":
        unit = st.selectbox(
            "Interval unit",
            ["minutes", "hours", "days", "weeks", "seconds"],
            key=f"{key_prefix}-unit",
        )
        amount = st.number_input(
            "Amount", min_value=1, value=15, key=f"{key_prefix}-amount"
        )
        return {unit: int(amount)}
    if trigger_type == "cron":
        hour = st.number_input(
            "Hour (0-23)", min_value=0, max_value=23, value=2, key=f"{key_prefix}-hour"
        )
        minute = st.number_input(
            "Minute (0-59)",
            min_value=0,
            max_value=59,
            value=0,
            key=f"{key_prefix}-minute",
        )
        return {"hour": int(hour), "minute": int(minute)}
    if trigger_type == "date":
        run_date = st.text_input(
            "Run date (ISO-8601)",
            value="2030-01-01T00:00:00Z",
            key=f"{key_prefix}-date",
        )
        if not run_date.strip():
            return None
        return {"run_date": run_date.strip()}
    return None


def render_schedule_form(
    key_prefix: str = "sched",
) -> tuple[str, str, dict[str, Any], bool] | None:
    name = st.text_input("Schedule name", key=f"{key_prefix}-name")
    trigger_type = st.selectbox(
        "Trigger type",
        ["interval", "cron", "date"],
        key=f"{key_prefix}-type",
    )
    enabled = st.checkbox("Enabled", value=True, key=f"{key_prefix}-enabled")
    trigger_args = build_trigger_args(trigger_type, key_prefix=key_prefix)
    if trigger_args is not None:
        st.code(trigger_args, language="json")
    if not name or trigger_args is None:
        return None
    return name, trigger_type, trigger_args, enabled
