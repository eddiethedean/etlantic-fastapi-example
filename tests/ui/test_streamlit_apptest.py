from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from etlantic_ui.api_client import EtlanticApiClient
from etlantic_ui.config import UiSettings
from etlantic_ui.models import UserRead
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from etlantic_runner.api import app
from tests.helpers import PASSWORD
from tests.ui.http_transport import SyncTestClientTransport

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
HOME = FRONTEND / "Home.py"
PIPELINES = FRONTEND / "pages" / "01_Pipelines.py"
TOKENS = FRONTEND / "pages" / "05_API_Tokens.py"
ACCOUNT = FRONTEND / "pages" / "07_Account.py"


@pytest.fixture
def backend(monkeypatch):
    """Live FastAPI lifespan + patch Streamlit UI to call it in-process."""
    with TestClient(app) as test_client:
        settings = UiSettings(api_url="http://testserver")
        transport = SyncTestClientTransport(test_client)

        def get_api_client() -> EtlanticApiClient:
            import etlantic_ui.state as state

            return EtlanticApiClient(
                settings=settings,
                transport=transport,
                access_token=state.access_token(),
            )

        monkeypatch.setattr("etlantic_ui.state.get_api_client", get_api_client)
        monkeypatch.setattr(
            "streamlit.switch_page",
            lambda *_args, **_kwargs: None,
            raising=False,
        )
        yield {"test_client": test_client, "settings": settings, "transport": transport}


def _register_user(
    backend: dict, email: str, *, display_name: str = "Ada"
) -> tuple[UserRead, object]:
    client = EtlanticApiClient(
        settings=backend["settings"],
        transport=backend["transport"],
    )
    client.register_user(
        email=email, display_name=display_name, password=PASSWORD
    )
    token = client.login(email=email, password=PASSWORD)
    client.with_token(token.access_token)
    return client.get_me(), token


def _auth_session(at: AppTest, user: UserRead, access_token: str, expires_in: int = 1800) -> None:
    at.session_state["access_token"] = access_token
    at.session_state["token_expires_at"] = (
        datetime.now(UTC) + timedelta(seconds=expires_in)
    ).isoformat()
    at.session_state["current_user"] = user.model_dump(mode="json")


def _home() -> AppTest:
    return AppTest.from_file(str(HOME), default_timeout=15)


def _assert_no_exception(at: AppTest) -> None:
    assert not at.exception, f"App raised: {at.exception}"


def test_unauthenticated_home_shows_auth_tabs(backend: dict) -> None:
    at = _home().run()
    _assert_no_exception(at)
    assert at.title[0].value == "ETLantic Runner"
    assert len(at.tabs) == 3
    labels = [tab.label for tab in at.tabs]
    assert labels == ["Sign in", "Create account", "Accept invitation"]
    assert any(b.label == "Sign in" for b in at.button)
    assert any(b.label == "Create account" for b in at.button)
    assert "access_token" not in at.session_state


def test_register_rejects_short_password_client_side(backend: dict) -> None:
    at = _home().run()
    # Register tab widgets follow sign-in fields in declaration order.
    # Sign-in: email, password; Register: email, display_name, password, confirm;
    # Invite: token.
    email_box = next(t for t in at.text_input if t.label == "Email" and t.key == "reg-email")
    name_box = next(t for t in at.text_input if t.key == "reg-name")
    pass_box = next(t for t in at.text_input if t.key == "reg-pass")
    confirm_box = next(t for t in at.text_input if t.key == "reg-confirm")
    email_box.input(f"short-{uuid.uuid4().hex}@example.com")
    name_box.input("Short")
    pass_box.input("too-short")
    confirm_box.input("too-short")
    submit = next(b for b in at.button if b.label == "Create account")
    submit.click().run()
    _assert_no_exception(at)
    assert any("at least 12 characters" in e.value for e in at.error)
    assert "access_token" not in at.session_state


def test_register_rejects_password_mismatch(backend: dict) -> None:
    at = _home().run()
    next(t for t in at.text_input if t.key == "reg-email").input(
        f"mismatch-{uuid.uuid4().hex}@example.com"
    )
    next(t for t in at.text_input if t.key == "reg-name").input("Mismatch")
    next(t for t in at.text_input if t.key == "reg-pass").input(PASSWORD)
    next(t for t in at.text_input if t.key == "reg-confirm").input(PASSWORD + "x")
    next(b for b in at.button if b.label == "Create account").click().run()
    _assert_no_exception(at)
    assert any("do not match" in e.value for e in at.error)


def test_failed_login_shows_generic_error(backend: dict) -> None:
    at = _home().run()
    email_inputs = [t for t in at.text_input if t.label == "Email"]
    password_inputs = [t for t in at.text_input if t.label == "Password"]
    email_inputs[0].input("nobody@example.com")
    password_inputs[0].input("wrong password!!")
    next(b for b in at.button if b.label == "Sign in").click().run()
    _assert_no_exception(at)
    assert any("Incorrect email or password" in e.value for e in at.error)
    assert "access_token" not in at.session_state


def test_register_and_login_reaches_dashboard(backend: dict) -> None:
    email = f"dash-{uuid.uuid4().hex}@example.com"
    at = _home().run()
    next(t for t in at.text_input if t.key == "reg-email").input(email)
    next(t for t in at.text_input if t.key == "reg-name").input("Dashboard User")
    next(t for t in at.text_input if t.key == "reg-pass").input(PASSWORD)
    next(t for t in at.text_input if t.key == "reg-confirm").input(PASSWORD)
    next(b for b in at.button if b.label == "Create account").click().run()
    _assert_no_exception(at)
    # Successful register triggers st.rerun into authenticated dashboard.
    assert "access_token" in at.session_state
    assert at.session_state["current_user"]["email"] == email
    assert any(t.value.startswith("Welcome,") for t in at.title)
    assert any(m.label == "API" for m in at.metric)
    assert any(b.label == "Sign out" for b in at.button)


def test_authenticated_dashboard_loads_metrics(backend: dict) -> None:
    email = f"metrics-{uuid.uuid4().hex}@example.com"
    user, token = _register_user(backend, email)
    at = _home()
    _auth_session(at, user, token.access_token, token.expires_in)
    at.run()
    _assert_no_exception(at)
    assert any(t.value == f"Welcome, {user.display_name}" for t in at.title)
    labels = {m.label for m in at.metric}
    assert {"API", "Pipelines", "Recent runs", "Enabled schedules", "Groups"} <= labels
    assert any(b.label == "Pipelines" for b in at.button)
    assert any(b.label == "Sign out" for b in at.button)


def test_sign_out_clears_auth_state(backend: dict) -> None:
    email = f"logout-{uuid.uuid4().hex}@example.com"
    user, token = _register_user(backend, email)
    at = _home()
    _auth_session(at, user, token.access_token, token.expires_in)
    at.run()
    next(b for b in at.button if b.label == "Sign out").click().run()
    _assert_no_exception(at)
    assert "access_token" not in at.session_state
    assert "current_user" not in at.session_state
    assert at.title[0].value == "ETLantic Runner"
    assert len(at.tabs) == 3


def test_expired_token_forces_login(backend: dict) -> None:
    email = f"expired-{uuid.uuid4().hex}@example.com"
    user, token = _register_user(backend, email)
    at = _home()
    at.session_state["access_token"] = token.access_token
    at.session_state["token_expires_at"] = (
        datetime.now(UTC) - timedelta(minutes=1)
    ).isoformat()
    at.session_state["current_user"] = user.model_dump(mode="json")
    at.run()
    _assert_no_exception(at)
    # Expired session should present auth UI, not dashboard.
    assert len(at.tabs) == 3
    assert "access_token" not in at.session_state


def test_invite_query_param_captured_into_session(backend: dict) -> None:
    at = _home()
    at.query_params["invite"] = "one-time-invite-token-value-1234567890"
    at.run()
    _assert_no_exception(at)
    assert "pending_invite_token" in at.session_state
    assert (
        at.session_state["pending_invite_token"]
        == "one-time-invite-token-value-1234567890"
    )
    assert "invite" not in dict(at.query_params)


def test_pipelines_page_requires_auth(backend: dict) -> None:
    at = AppTest.from_file(str(PIPELINES), default_timeout=15).run()
    # Unauthenticated: page_guard warns and stops before pipeline chrome.
    _assert_no_exception(at)
    assert any("sign in" in w.value.lower() for w in at.warning) or len(at.title) == 0


def test_pipelines_page_lists_owned_pipeline(backend: dict) -> None:
    email = f"pipes-{uuid.uuid4().hex}@example.com"
    user, token = _register_user(backend, email)
    client = EtlanticApiClient(
        settings=backend["settings"],
        transport=backend["transport"],
        access_token=token.access_token,
    )
    from tests.helpers import pipeline_document

    client.create_pipeline(name="listed-pipe", document=pipeline_document())

    at = AppTest.from_file(str(PIPELINES), default_timeout=15)
    _auth_session(at, user, token.access_token, token.expires_in)
    at.run()
    _assert_no_exception(at)
    assert any(t.value == "Pipelines" for t in at.title)
    assert any("listed-pipe" in m.value for m in at.markdown)


def test_account_page_shows_profile(backend: dict) -> None:
    email = f"acct-{uuid.uuid4().hex}@example.com"
    user, token = _register_user(backend, email, display_name="Account Ada")
    at = AppTest.from_file(str(ACCOUNT), default_timeout=15)
    _auth_session(at, user, token.access_token, token.expires_in)
    at.run()
    _assert_no_exception(at)
    assert any(t.value == "Account" for t in at.title)
    assert any(email in w.value for w in at.markdown) or any(
        email in c.value for c in at.caption
    )
    assert any(b.label == "Sign out" for b in at.button)
    assert any(b.label == "Update display name" for b in at.button)


def test_token_vault_clears_secret_after_save(backend: dict) -> None:
    email = f"tokui-{uuid.uuid4().hex}@example.com"
    user, token = _register_user(backend, email)
    at = AppTest.from_file(str(TOKENS), default_timeout=15)
    _auth_session(at, user, token.access_token, token.expires_in)
    at.run()
    _assert_no_exception(at)
    assert any(t.value == "API token vault" for t in at.title)
    assert any("write-only" in w.value.lower() for w in at.warning)

    secret = "sk-streamlit-secret-value"
    next(t for t in at.text_input if t.key == "create-name").input("ui-source")
    next(t for t in at.text_input if t.key == "create-value").input(secret)
    # Button is gated on a non-empty form payload; rerun after filling fields.
    at.run()
    save = next(b for b in at.button if b.label == "Save token")
    save.click().run()
    _assert_no_exception(at)

    # After save + rerun, password widgets must be empty (never retain plaintext).
    if "create-value" in at.session_state:
        assert at.session_state["create-value"] in {"", None}
    value_widgets = [t for t in at.text_input if t.key == "create-value"]
    assert value_widgets, "expected create-value password input to remain on page"
    assert value_widgets[0].value in {"", None}
    assert value_widgets[0].value != secret
    visible = " ".join(
        str(getattr(item, "value", ""))
        for item in [*at.success, *at.markdown, *at.warning, *at.caption]
    )
    assert secret not in visible
    # Token metadata should be listed after save.
    assert any(b.label in {"Rotate", "Disable", "Delete"} for b in at.button)
