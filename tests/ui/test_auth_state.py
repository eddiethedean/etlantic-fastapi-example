from __future__ import annotations

from datetime import UTC, datetime

from etlantic_ui.formatting import asset_bindings, format_dt, mask_token, node_counts
from etlantic_ui.polling import is_terminal


def test_formatting_helpers() -> None:
    assert mask_token("abcd") == "••••abcd"
    doc = {
        "nodes": [
            {"asset": "source", "kind": "source"},
            {"kind": "step"},
            {"asset": "sink", "kind": "sink"},
            {"kind": "subpipeline"},
        ]
    }
    assert asset_bindings(doc) == ["source", "sink"]
    counts = node_counts(doc)
    assert counts["extract"] == 1
    assert counts["transform"] == 1
    assert counts["load"] == 1
    assert counts["other"] == 1


def test_naive_timestamp_is_interpreted_as_utc() -> None:
    value = datetime(2026, 7, 28, 19, 54, 37)
    expected = value.replace(tzinfo=UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    assert format_dt(value) == expected
    assert "(naive)" not in format_dt(value)


def test_terminal_statuses() -> None:
    assert is_terminal("succeeded")
    assert is_terminal("failed")
    assert not is_terminal("queued")
    assert not is_terminal("running")
