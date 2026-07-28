from __future__ import annotations

import time
import uuid
from typing import Any

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

PASSWORD = "correct horse battery staple"


def register_user(
    client: TestClient,
    email: str,
    *,
    display_name: str = "Ada",
    password: str = PASSWORD,
) -> dict[str, Any]:
    response = client.post(
        "/users",
        json={
            "email": email,
            "display_name": display_name,
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, Any]:
    response = client.post(
        "/auth/token",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers_for(
    client: TestClient,
    email: str,
    *,
    password: str = PASSWORD,
    display_name: str = "Ada",
) -> dict[str, str]:
    register_user(client, email, display_name=display_name, password=password)
    token = login(client, email, password=password)
    return {"Authorization": f"Bearer {token['access_token']}"}


def pipeline_document() -> dict[str, Any]:
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


def create_pipeline(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str | None = None,
    description: str | None = "Copy in-memory rows",
    document: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.post(
        "/pipelines",
        headers=headers,
        json={
            "name": name or f"pipeline-{uuid.uuid4().hex[:8]}",
            "description": description,
            "document": document or pipeline_document(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_token(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str | None = None,
    value: str = "sk-example-super-secret-value",
    allow_read: bool = True,
    allow_write: bool = False,
) -> dict[str, Any]:
    response = client.post(
        "/tokens",
        headers=headers,
        json={
            "name": name or f"token-{uuid.uuid4().hex[:8]}",
            "value": value,
            "allow_read": allow_read,
            "allow_write": allow_write,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def wait_for_run(
    client: TestClient,
    headers: dict[str, str],
    run_id: str,
    *,
    timeout_s: float = 5.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    run: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = client.get(f"/runs/{run_id}", headers=headers)
        assert response.status_code == 200, response.text
        run = response.json()
        if run["status"] not in {"queued", "running"}:
            return run
        time.sleep(0.02)
    raise AssertionError(f"Run {run_id} did not finish: {run}")
