from __future__ import annotations

import uuid

import pytest
from etlantic_ui.api_client import EtlanticApiClient
from etlantic_ui.config import UiSettings
from etlantic_ui.errors import AuthenticationError, ConflictError, NotFoundError
from fastapi.testclient import TestClient

from etlantic_runner.api import app
from tests.helpers import PASSWORD, pipeline_document
from tests.ui.http_transport import SyncTestClientTransport


@pytest.fixture
def live_client():
    with TestClient(app) as test_client:
        settings = UiSettings(api_url="http://testserver")
        client = EtlanticApiClient(
            settings=settings,
            transport=SyncTestClientTransport(test_client),
        )
        try:
            yield client
        finally:
            try:
                client.close()
            except Exception:
                pass


def _login(client: EtlanticApiClient, email: str) -> None:
    token = client.login(email=email, password=PASSWORD)
    client.with_token(token.access_token)


def _register_login(client: EtlanticApiClient, email: str) -> None:
    client.register_user(email=email, display_name="UI", password=PASSWORD)
    _login(client, email)


def test_health(live_client: EtlanticApiClient) -> None:
    assert live_client.health()["status"] == "ok"


def test_register_login_me(live_client: EtlanticApiClient) -> None:
    email = f"ui-{uuid.uuid4().hex}@example.com"
    _register_login(live_client, email)
    me = live_client.get_me()
    assert me.email == email


def test_auth_error_mapping(live_client: EtlanticApiClient) -> None:
    with pytest.raises(AuthenticationError):
        live_client.login(email="missing@example.com", password="nope-nope-nope")


def test_pipeline_workflow(live_client: EtlanticApiClient) -> None:
    _register_login(live_client, f"pipe-{uuid.uuid4().hex}@example.com")
    draft = live_client.verify_draft(pipeline_document())
    assert draft.ok and draft.document is not None
    pipeline = live_client.create_pipeline(name="ui-pipe", document=draft.document)
    assert pipeline.access_source == "owned"
    assert pipeline.can_delete is True
    assert "ok" in live_client.validate_pipeline(pipeline.id).model_dump()
    assert "ok" in live_client.plan_pipeline(pipeline.id).model_dump()
    run = live_client.submit_run(pipeline.id)
    assert run.pipeline_id == pipeline.id


def test_version_conflict(live_client: EtlanticApiClient) -> None:
    _register_login(live_client, f"conflict-{uuid.uuid4().hex}@example.com")
    pipeline = live_client.create_pipeline(
        name="conflict-pipe", document=pipeline_document()
    )
    with pytest.raises(ConflictError):
        live_client.update_pipeline(pipeline.id, name="stale", expected_version=99)


def test_token_vault_never_returns_secret(live_client: EtlanticApiClient) -> None:
    _register_login(live_client, f"vault-{uuid.uuid4().hex}@example.com")
    secret = "sk-super-secret-value"
    created = live_client.create_token(name="src", value=secret)
    assert created.last_four == secret[-4:]
    dumped = created.model_dump()
    assert "value" not in dumped
    assert secret not in str(dumped)


def test_group_invite_accept_share(live_client: EtlanticApiClient) -> None:
    suffix = uuid.uuid4().hex
    owner_email = f"g-owner-{suffix}@example.com"
    member_email = f"g-member-{suffix}@example.com"
    _register_login(live_client, owner_email)
    group = live_client.create_group(name="Team")
    assert group.current_user_role == "owner"
    invitation = live_client.create_invitation(group.id, email=member_email)
    pipeline = live_client.create_pipeline(
        name="shared-pipe", document=pipeline_document()
    )

    _register_login(live_client, member_email)
    joined = live_client.accept_invitation(invitation.accept_token)
    assert joined.current_user_role == "member"

    _login(live_client, owner_email)
    live_client.add_pipeline_to_group(group.id, pipeline.id)

    _login(live_client, member_email)
    shared = next(p for p in live_client.list_pipelines() if p.id == pipeline.id)
    assert shared.access_source == "group"
    assert shared.can_delete is False


def test_not_found(live_client: EtlanticApiClient) -> None:
    _register_login(live_client, f"err-{uuid.uuid4().hex}@example.com")
    with pytest.raises(NotFoundError):
        live_client.get_pipeline("00000000-0000-0000-0000-000000000000")
