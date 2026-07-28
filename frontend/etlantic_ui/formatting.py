from __future__ import annotations

from datetime import UTC, datetime
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
        # SQLAlchemy's SQLite dialect returns DateTime columns without tzinfo.
        # The runner persists application timestamps in UTC, so restore that
        # contract before converting to the viewer's local timezone.
        value = value.replace(tzinfo=UTC)
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
    kind_groups = {
        "extract": {"extract", "source"},
        "transform": {"transform", "transformation", "map", "step"},
        "load": {"load", "sink"},
    }
    for node in document.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        kind = str(node.get("kind") or node.get("type") or "other").lower()
        bucket = next(
            (name for name, aliases in kind_groups.items() if kind in aliases),
            "other",
        )
        counts[bucket] += 1
    return counts
