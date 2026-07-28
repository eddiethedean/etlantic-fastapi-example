from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from etlantic_runner.database import SessionLocal
from etlantic_runner.models import ApiToken
from tests.helpers import create_pipeline, create_token, wait_for_run


def test_token_crud_never_exposes_secret(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    plaintext = "sk-example-super-secret-value"
    created = create_token(
        client,
        auth_headers,
        name="source-api",
        value=plaintext,
        allow_read=True,
        allow_write=False,
    )
    assert "value" not in created
    assert "encrypted_value" not in created
    assert created["last_four"] == plaintext[-4:]
    assert created["allow_read"] is True
    assert created["allow_write"] is False
    assert created["is_active"] is True

    with SessionLocal() as session:
        stored = session.scalar(select(ApiToken).where(ApiToken.id == created["id"]))
        assert stored is not None
        assert plaintext.encode() not in stored.encrypted_value

    listed = client.get("/tokens", headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["id"] == created["id"] for item in listed.json())
    assert all("value" not in item for item in listed.json())

    fetched = client.get(f"/tokens/{created['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert "value" not in fetched.json()

    rotated = client.patch(
        f"/tokens/{created['id']}",
        headers=auth_headers,
        json={
            "name": "source-api-v2",
            "value": "sk-rotated-secret-value",
            "allow_write": True,
        },
    )
    assert rotated.status_code == 200, rotated.text
    body = rotated.json()
    assert body["name"] == "source-api-v2"
    assert body["last_four"] == "alue"
    assert body["allow_write"] is True
    assert "value" not in body

    disabled = client.patch(
        f"/tokens/{created['id']}",
        headers=auth_headers,
        json={"is_active": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    deleted = client.delete(f"/tokens/{created['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    assert (
        client.get(f"/tokens/{created['id']}", headers=auth_headers).status_code == 404
    )


def test_token_duplicate_name_conflict(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    create_token(client, auth_headers, name="dup")
    response = client.post(
        "/tokens",
        headers=auth_headers,
        json={
            "name": "dup",
            "value": "another-secret-value",
            "allow_read": True,
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "A token with this name already exists"


def test_token_requires_at_least_one_permission(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    create_response = client.post(
        "/tokens",
        headers=auth_headers,
        json={
            "name": "none",
            "value": "secret-value-here",
            "allow_read": False,
            "allow_write": False,
        },
    )
    assert create_response.status_code == 422

    token = create_token(client, auth_headers, name="perms")
    update_response = client.patch(
        f"/tokens/{token['id']}",
        headers=auth_headers,
        json={"allow_read": False, "allow_write": False},
    )
    assert update_response.status_code == 422
    assert (
        update_response.json()["detail"]
        == "At least one of allow_read or allow_write is required"
    )


def test_token_ownership_is_enforced(
    client: TestClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    token = create_token(client, auth_headers)
    assert (
        client.get(f"/tokens/{token['id']}", headers=other_auth_headers).status_code
        == 404
    )
    assert (
        client.patch(
            f"/tokens/{token['id']}",
            headers=other_auth_headers,
            json={"name": "stolen"},
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/tokens/{token['id']}", headers=other_auth_headers).status_code
        == 404
    )


def test_token_grants_lifecycle_and_runtime_use(
    client: TestClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    plaintext = "sk-example-super-secret-value"
    token = create_token(
        client,
        auth_headers,
        value=plaintext,
        allow_read=True,
        allow_write=False,
    )
    pipeline = create_pipeline(client, auth_headers, name="credentialed")

    grant_response = client.post(
        f"/pipelines/{pipeline['id']}/token-grants",
        headers=auth_headers,
        json={
            "token_id": token["id"],
            "binding": "source",
            "provider": "memory",
            "operation": "read",
        },
    )
    assert grant_response.status_code == 201, grant_response.text
    grant = grant_response.json()
    assert grant["secret_ref"] == {
        "provider": "user-tokens",
        "name": token["id"],
        "key": "value",
        "version": "current",
        "purpose": "read",
    }

    listed = client.get(
        f"/pipelines/{pipeline['id']}/token-grants", headers=auth_headers
    )
    assert listed.status_code == 200
    assert any(item["id"] == grant["id"] for item in listed.json())

    assert (
        client.get(
            f"/pipelines/{pipeline['id']}/token-grants",
            headers=other_auth_headers,
        ).status_code
        == 404
    )

    run = client.post(f"/pipelines/{pipeline['id']}/runs", headers=auth_headers).json()
    finished = wait_for_run(client, auth_headers, run["id"])
    assert finished["status"] in {"succeeded", "partial"}

    refreshed = client.get(f"/tokens/{token['id']}", headers=auth_headers).json()
    assert refreshed["last_used_at"] is not None

    revoked = client.delete(
        f"/pipelines/{pipeline['id']}/token-grants/{grant['id']}",
        headers=auth_headers,
    )
    assert revoked.status_code == 204
    remaining = client.get(
        f"/pipelines/{pipeline['id']}/token-grants", headers=auth_headers
    ).json()
    assert remaining == []


def test_token_grant_validation_rules(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    read_only = create_token(
        client,
        auth_headers,
        name="read-only",
        allow_read=True,
        allow_write=False,
    )
    inactive = create_token(client, auth_headers, name="inactive")
    client.patch(
        f"/tokens/{inactive['id']}",
        headers=auth_headers,
        json={"is_active": False},
    )
    pipeline = create_pipeline(client, auth_headers)

    write_denied = client.post(
        f"/pipelines/{pipeline['id']}/token-grants",
        headers=auth_headers,
        json={
            "token_id": read_only["id"],
            "binding": "sink",
            "provider": "memory",
            "operation": "write",
        },
    )
    assert write_denied.status_code == 422
    assert write_denied.json()["detail"] == "Token does not allow writes"

    inactive_denied = client.post(
        f"/pipelines/{pipeline['id']}/token-grants",
        headers=auth_headers,
        json={
            "token_id": inactive["id"],
            "binding": "source",
            "provider": "memory",
            "operation": "read",
        },
    )
    assert inactive_denied.status_code == 422
    assert inactive_denied.json()["detail"] == "Token is inactive"

    bad_binding = client.post(
        f"/pipelines/{pipeline['id']}/token-grants",
        headers=auth_headers,
        json={
            "token_id": read_only["id"],
            "binding": "missing-asset",
            "provider": "memory",
            "operation": "read",
        },
    )
    assert bad_binding.status_code == 422
    assert (
        bad_binding.json()["detail"]
        == "Binding must match an asset in the pipeline document"
    )

    first = client.post(
        f"/pipelines/{pipeline['id']}/token-grants",
        headers=auth_headers,
        json={
            "token_id": read_only["id"],
            "binding": "source",
            "provider": "memory",
            "operation": "read",
        },
    )
    assert first.status_code == 201, first.text

    duplicate = client.post(
        f"/pipelines/{pipeline['id']}/token-grants",
        headers=auth_headers,
        json={
            "token_id": read_only["id"],
            "binding": "source",
            "provider": "memory",
            "operation": "read",
        },
    )
    assert duplicate.status_code == 409
    assert (
        duplicate.json()["detail"] == "This pipeline binding already has a token grant"
    )


def test_token_grant_ownership_is_enforced(
    client: TestClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    token = create_token(client, auth_headers)
    pipeline = create_pipeline(client, auth_headers)
    grant = client.post(
        f"/pipelines/{pipeline['id']}/token-grants",
        headers=auth_headers,
        json={
            "token_id": token["id"],
            "binding": "source",
            "provider": "memory",
            "operation": "read",
        },
    ).json()

    assert (
        client.delete(
            f"/pipelines/{pipeline['id']}/token-grants/{grant['id']}",
            headers=other_auth_headers,
        ).status_code
        == 404
    )

    other_pipeline = create_pipeline(client, other_auth_headers)
    assert (
        client.post(
            f"/pipelines/{other_pipeline['id']}/token-grants",
            headers=other_auth_headers,
            json={
                "token_id": token["id"],
                "binding": "source",
                "provider": "memory",
                "operation": "read",
            },
        ).status_code
        == 404
    )
