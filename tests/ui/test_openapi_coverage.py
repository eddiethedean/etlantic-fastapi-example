from __future__ import annotations

from datetime import UTC, datetime, timedelta

from etlantic_ui.api_client import EtlanticApiClient

from etlantic_runner.api import create_app


def test_openapi_client_coverage() -> None:
    app = create_app()
    schema = app.openapi()
    expected: set[tuple[str, str]] = set()
    for path, methods in schema.get("paths", {}).items():
        for method in methods:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                expected.add((method.upper(), path))

    missing = expected - set(EtlanticApiClient.COVERED_PATHS)
    assert not missing, f"API client missing coverage for: {sorted(missing)}"


def test_token_expiry_helper(monkeypatch) -> None:
    import etlantic_ui.state as state

    class FakeSession(dict):
        pass

    fake = FakeSession()
    monkeypatch.setattr(state.st, "session_state", fake)

    fake[state.TOKEN_EXPIRES_AT_KEY] = (
        datetime.now(UTC) - timedelta(seconds=1)
    ).isoformat()
    assert state.token_expired() is True

    fake[state.TOKEN_EXPIRES_AT_KEY] = (
        datetime.now(UTC) + timedelta(minutes=10)
    ).isoformat()
    assert state.token_expired() is False
