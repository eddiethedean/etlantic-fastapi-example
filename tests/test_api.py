from __future__ import annotations

import time

from etlantic.authoring import (
    contract_definition,
    edge,
    extract_node,
    field_spec,
    load_node,
    pipeline_definition,
    pipeline_to_dict,
)
from fastapi.testclient import TestClient
from sqlalchemy import select

from etlantic_runner.api import app
from etlantic_runner.database import SessionLocal
from etlantic_runner.models import ApiToken


def pipeline_document() -> dict:
    pipeline_id = "example:CopyPipeline"
    contract_id = "example:Row"
    definition = pipeline_definition(
        pipeline_id,
        "CopyPipeline",
        contracts=(
            contract_definition(
                contract_id,
                "Row",
                fields=(field_spec("value", "string"),),
            ),
        ),
        nodes=(
            extract_node(
                "source",
                asset="source",
                contract_id=contract_id,
                pipeline_id=pipeline_id,
            ),
            load_node(
                "sink",
                asset="sink",
                contract_id=contract_id,
                pipeline_id=pipeline_id,
            ),
        ),
        edges=(
            edge(
                "source",
                "result",
                "sink",
                "input",
                producer_contract_id=contract_id,
                consumer_contract_id=contract_id,
            ),
        ),
    )
    return pipeline_to_dict(definition)


def auth_headers(client: TestClient, email: str = "ada@example.com") -> dict[str, str]:
    response = client.post(
        "/users",
        json={
            "email": email,
            "display_name": "Ada",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 201, response.text
    response = client.post(
        "/auth/token",
        data={
            "username": email,
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_user_pipeline_run_and_schedule_lifecycle() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        assert client.get("/users/me", headers=headers).status_code == 200

        response = client.post(
            "/pipelines",
            headers=headers,
            json={
                "name": "copy",
                "description": "Copy in-memory rows",
                "document": pipeline_document(),
            },
        )
        assert response.status_code == 201, response.text
        pipeline = response.json()

        response = client.post(
            f"/pipelines/{pipeline['id']}/validate", headers=headers
        )
        assert response.status_code == 200, response.text
        assert "diagnostics" in response.json()

        response = client.post(
            f"/pipelines/{pipeline['id']}/runs", headers=headers
        )
        assert response.status_code == 202, response.text
        run_id = response.json()["id"]
        for _ in range(100):
            run = client.get(f"/runs/{run_id}", headers=headers).json()
            if run["status"] not in {"queued", "running"}:
                break
            time.sleep(0.02)
        assert run["status"] in {"succeeded", "partial", "failed"}

        response = client.post(
            f"/pipelines/{pipeline['id']}/schedules",
            headers=headers,
            json={
                "name": "hourly",
                "trigger_type": "interval",
                "trigger_args": {"hours": 1},
            },
        )
        assert response.status_code == 201, response.text
        schedule = response.json()
        assert schedule["next_run_at"] is not None

        response = client.patch(
            f"/schedules/{schedule['id']}",
            headers=headers,
            json={"enabled": False},
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is False
        assert response.json()["next_run_at"] is None


def test_pipeline_ownership_is_enforced() -> None:
    with TestClient(app) as client:
        owner = auth_headers(client, "owner@example.com")
        other = auth_headers(client, "other@example.com")
        pipeline = client.post(
            "/pipelines",
            headers=owner,
            json={"name": "private", "document": pipeline_document()},
        ).json()
        assert (
            client.get(f"/pipelines/{pipeline['id']}", headers=other).status_code
            == 404
        )


def test_rejects_unverified_pipeline_document() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client, "invalid@example.com")
        response = client.post(
            "/pipelines",
            headers=headers,
            json={"name": "bad", "document": {"schema": "etlantic.pipeline/1"}},
        )
        assert response.status_code == 422


def test_tokens_are_encrypted_scoped_and_used_by_pipeline() -> None:
    plaintext = "sk-example-super-secret-value"
    with TestClient(app) as client:
        owner = auth_headers(client, "token-owner@example.com")
        other = auth_headers(client, "token-other@example.com")
        response = client.post(
            "/tokens",
            headers=owner,
            json={
                "name": "source-api",
                "value": plaintext,
                "allow_read": True,
                "allow_write": False,
            },
        )
        assert response.status_code == 201, response.text
        token = response.json()
        assert "value" not in token
        assert "encrypted_value" not in token
        assert token["last_four"] == "alue"
        assert client.get(f"/tokens/{token['id']}", headers=other).status_code == 404

        with SessionLocal() as session:
            stored = session.scalar(select(ApiToken).where(ApiToken.id == token["id"]))
            assert stored is not None
            assert plaintext.encode() not in stored.encrypted_value

        pipeline = client.post(
            "/pipelines",
            headers=owner,
            json={
                "name": "credentialed",
                "document": pipeline_document(),
            },
        ).json()
        response = client.post(
            f"/pipelines/{pipeline['id']}/token-grants",
            headers=owner,
            json={
                "token_id": token["id"],
                "binding": "source",
                "provider": "memory",
                "operation": "read",
            },
        )
        assert response.status_code == 201, response.text
        reference = response.json()["secret_ref"]
        assert reference == {
            "provider": "user-tokens",
            "name": token["id"],
            "key": "value",
            "version": "current",
            "purpose": "read",
        }

        response = client.post(
            f"/pipelines/{pipeline['id']}/runs", headers=owner
        )
        run_id = response.json()["id"]
        for _ in range(100):
            run = client.get(f"/runs/{run_id}", headers=owner).json()
            if run["status"] not in {"queued", "running"}:
                break
            time.sleep(0.02)
        assert run["status"] in {"succeeded", "partial"}
        refreshed = client.get(f"/tokens/{token['id']}", headers=owner).json()
        assert refreshed["last_used_at"] is not None

        response = client.post(
            f"/pipelines/{pipeline['id']}/token-grants",
            headers=owner,
            json={
                "token_id": token["id"],
                "binding": "sink",
                "provider": "memory",
                "operation": "write",
            },
        )
        assert response.status_code == 422
