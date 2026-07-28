from __future__ import annotations

from datetime import datetime
from typing import Any


def format_dt(value: datetime | str | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if value.tzinfo is None:
        return value.isoformat(sep=" ", timespec="seconds") + " (naive)"
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def mask_token(last_four: str) -> str:
    return f"••••{last_four}"


def status_emoji(status: str) -> str:
    return {
        "queued": "⏳",
        "running": "🔄",
        "succeeded": "✅",
        "partial": "⚠️",
        "failed": "❌",
    }.get(status, "•")


def asset_bindings(document: dict[str, Any]) -> list[str]:
    assets: list[str] = []
    for node in document.get("nodes") or []:
        if isinstance(node, dict):
            asset = node.get("asset")
            if isinstance(asset, str) and asset not in assets:
                assets.append(asset)
    return assets


def node_counts(document: dict[str, Any]) -> dict[str, int]:
    counts = {"extract": 0, "transform": 0, "load": 0, "other": 0}
    for node in document.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        kind = str(node.get("kind") or node.get("type") or "other").lower()
        if "extract" in kind:
            counts["extract"] += 1
        elif "load" in kind:
            counts["load"] += 1
        elif "transform" in kind or "map" in kind:
            counts["transform"] += 1
        else:
            counts["other"] += 1
    return counts
