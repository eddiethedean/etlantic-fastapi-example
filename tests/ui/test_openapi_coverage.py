from __future__ import annotations

from datetime import UTC, datetime, timedelta

from etlantic_ui.api_client import EtlanticApiClient
from etlantic_ui.models import UserRead

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


def test_auth_session_restores_after_streamlit_state_reset(monkeypatch) -> None:
    import etlantic_ui.state as state

    class FakeSession(dict):
        pass

    fake = FakeSession()
    monkeypatch.setattr(state.st, "session_state", fake)
    monkeypatch.setattr(state, "_browser_session_key", lambda: "browser-key")
    state._AUTH_SESSIONS.clear()
    user = UserRead(
        id="00000000-0000-0000-0000-000000000001",
        email="refresh@example.com",
        display_name="Refresh User",
        is_active=True,
        is_admin=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    state.set_auth_session("server-memory-bearer", 600, user)
    fake.clear()  # Simulate a new Streamlit websocket/session after refresh.

    assert state.restore_auth_session() is True
    assert state.access_token() == "server-memory-bearer"
    assert state.current_user() == user

    state.logout()
    fake.clear()
    assert state.restore_auth_session() is False
