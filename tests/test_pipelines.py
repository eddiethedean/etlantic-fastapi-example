from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_pipeline, pipeline_document, wait_for_run


def test_pipeline_crud_and_list(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = create_pipeline(
        client, auth_headers, name="alpha", description="first"
    )
    assert created["name"] == "alpha"
    assert created["description"] == "first"
    assert created["version"] == 1
    assert created["fingerprint"]
    assert created["document"]["schema"] == "etlantic.pipeline/1"
    assert created["access_source"] == "owned"
    assert created["can_delete"] is True
    assert created["shared_group_ids"] == []

    listed = client.get("/pipelines", headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["id"] == created["id"] for item in listed.json())

    fetched = client.get(f"/pipelines/{created['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]
    assert fetched.json()["access_source"] == "owned"

    updated = client.patch(
        f"/pipelines/{created['id']}",
        headers=auth_headers,
        json={
            "name": "beta",
            "description": None,
            "expected_version": 1,
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "beta"
    assert body["description"] is None
    assert body["version"] == 2

    deleted = client.delete(f"/pipelines/{created['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    assert (
        client.get(f"/pipelines/{created['id']}", headers=auth_headers).status_code
        == 404
    )


def test_verify_draft_seals_document(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/pipelines/verify-draft",
        headers=auth_headers,
        json={"document": pipeline_document()},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["fingerprint"]
    assert body["document"]["schema"] == "etlantic.pipeline/1"

    bad = client.post(
        "/pipelines/verify-draft",
        headers=auth_headers,
        json={"document": {"schema": "etlantic.pipeline/1"}},
    )
    assert bad.status_code == 200
    assert bad.json()["ok"] is False
    assert bad.json()["diagnostics"]


def test_pipeline_duplicate_name_conflict(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    create_pipeline(client, auth_headers, name="same-name")
    response = client.post(
        "/pipelines",
        headers=auth_headers,
        json={"name": "same-name", "document": pipeline_document()},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "A pipeline with this name already exists"


def test_pipeline_version_conflict(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    pipeline = create_pipeline(client, auth_headers)
    response = client.patch(
        f"/pipelines/{pipeline['id']}",
        headers=auth_headers,
        json={"name": "stale", "expected_version": 99},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Pipeline version conflict"


def test_rejects_unverified_pipeline_document(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/pipelines",
        headers=auth_headers,
        json={"name": "bad", "document": {"schema": "etlantic.pipeline/1"}},
    )
    assert response.status_code == 422


def test_pipeline_ownership_is_enforced(
    client: TestClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    pipeline = create_pipeline(client, auth_headers, name="private")
    assert (
        client.get(
            f"/pipelines/{pipeline['id']}", headers=other_auth_headers
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/pipelines/{pipeline['id']}",
            headers=other_auth_headers,
            json={"name": "stolen"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/pipelines/{pipeline['id']}", headers=other_auth_headers
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/pipelines/{pipeline['id']}/runs", headers=other_auth_headers
        ).status_code
        == 404
    )


def test_validate_and_plan_pipeline(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    pipeline = create_pipeline(client, auth_headers)

    validated = client.post(
        f"/pipelines/{pipeline['id']}/validate", headers=auth_headers
    )
    assert validated.status_code == 200, validated.text
    body = validated.json()
    assert "ok" in body
    assert "diagnostics" in body
    assert "fingerprint" in body

    planned = client.post(f"/pipelines/{pipeline['id']}/plan", headers=auth_headers)
    assert planned.status_code == 200, planned.text
    plan_body = planned.json()
    assert "ok" in plan_body
    assert "diagnostics" in plan_body


def test_run_pipeline_and_list_runs(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    pipeline = create_pipeline(client, auth_headers)
    response = client.post(
        f"/pipelines/{pipeline['id']}/runs", headers=auth_headers
    )
    assert response.status_code == 202, response.text
    run = response.json()
    assert run["pipeline_id"] == pipeline["id"]
    assert run["status"] in {"queued", "running", "succeeded", "partial", "failed"}
    assert run["pipeline_version"] == pipeline["version"]
    assert run["pipeline_fingerprint"] == pipeline["fingerprint"]

    finished = wait_for_run(client, auth_headers, run["id"])
    assert finished["status"] in {"succeeded", "partial", "failed"}
    assert finished["finished_at"] is not None

    listed = client.get("/runs", headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["id"] == run["id"] for item in listed.json())

    filtered = client.get(
        "/runs",
        headers=auth_headers,
        params={"pipeline_id": pipeline["id"]},
    )
    assert filtered.status_code == 200
    assert all(item["pipeline_id"] == pipeline["id"] for item in filtered.json())
    assert any(item["id"] == run["id"] for item in filtered.json())


def test_run_ownership_is_enforced(
    client: TestClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    pipeline = create_pipeline(client, auth_headers)
    run = client.post(
        f"/pipelines/{pipeline['id']}/runs", headers=auth_headers
    ).json()
    assert (
        client.get(f"/runs/{run['id']}", headers=other_auth_headers).status_code
        == 404
    )


def test_pipeline_list_is_owner_scoped(
    client: TestClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    mine = create_pipeline(client, auth_headers, name="mine-only")
    create_pipeline(client, other_auth_headers, name="theirs-only")

    listed = client.get("/pipelines", headers=auth_headers).json()
    ids = {item["id"] for item in listed}
    assert mine["id"] in ids
    assert all(item["owner_id"] == mine["owner_id"] for item in listed)
