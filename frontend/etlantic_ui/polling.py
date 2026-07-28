from __future__ import annotations

import time
from collections.abc import Callable

from etlantic_ui.api_client import EtlanticApiClient
from etlantic_ui.config import get_ui_settings
from etlantic_ui.models import RunRead

TERMINAL_STATUSES = frozenset({"succeeded", "partial", "failed", "cancelled"})


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def poll_run(
    client: EtlanticApiClient,
    run_id: str,
    *,
    timeout_s: float = 60.0,
    on_update: Callable[[RunRead], None] | None = None,
) -> RunRead:
    interval = get_ui_settings().run_poll_seconds
    deadline = time.monotonic() + timeout_s
    run = client.get_run(run_id)
    if on_update:
        on_update(run)
    while not is_terminal(run.status) and time.monotonic() < deadline:
        time.sleep(interval)
        run = client.get_run(run_id)
        if on_update:
            on_update(run)
    return run
