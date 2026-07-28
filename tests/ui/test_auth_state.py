from __future__ import annotations

from etlantic_ui.formatting import asset_bindings, mask_token, node_counts
from etlantic_ui.polling import is_terminal


def test_formatting_helpers() -> None:
    assert mask_token("abcd") == "••••abcd"
    doc = {
        "nodes": [
            {"asset": "source", "kind": "extract"},
            {"asset": "sink", "kind": "load"},
        ]
    }
    assert asset_bindings(doc) == ["source", "sink"]
    counts = node_counts(doc)
    assert counts["extract"] == 1
    assert counts["load"] == 1


def test_terminal_statuses() -> None:
    assert is_terminal("succeeded")
    assert is_terminal("failed")
    assert not is_terminal("queued")
    assert not is_terminal("running")
