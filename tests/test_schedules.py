from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_pipeline


def test_schedule_lifecycle(client: TestClient, auth_headers: dict[str, str]) -> None:
    pipeline = create_pipeline(client, auth_headers)

    created = client.post(
        f"/pipelines/{pipeline['id']}/schedules",
        headers=auth_headers,
        json={
            "name": "hourly",
            "trigger_type": "interval",
            "trigger_args": {"hours": 1},
        },
    )
    assert created.status_code == 201, created.text
    schedule = created.json()
    assert schedule["enabled"] is True
    assert schedule["next_run_at"] is not None
    assert schedule["pipeline_id"] == pipeline["id"]

    listed = client.get("/schedules", headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["id"] == schedule["id"] for item in listed.json())

    fetched = client.get(f"/schedules/{schedule['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == schedule["id"]

    disabled = client.patch(
        f"/schedules/{schedule['id']}",
        headers=auth_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert disabled.json()["next_run_at"] is None

    renamed = client.patch(
        f"/schedules/{schedule['id']}",
        headers=auth_headers,
        json={
            "name": "daily",
            "trigger_type": "cron",
            "trigger_args": {"hour": 9, "minute": 0},
            "enabled": True,
        },
    )
    assert renamed.status_code == 200, renamed.text
    body = renamed.json()
    assert body["name"] == "daily"
    assert body["trigger_type"] == "cron"
    assert body["enabled"] is True
    assert body["next_run_at"] is not None

    deleted = client.delete(f"/schedules/{schedule['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    assert (
        client.get(f"/schedules/{schedule['id']}", headers=auth_headers).status_code
        == 404
    )


def test_schedule_date_trigger(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    pipeline = create_pipeline(client, auth_headers)
    response = client.post(
        f"/pipelines/{pipeline['id']}/schedules",
        headers=auth_headers,
        json={
            "name": "once",
            "trigger_type": "date",
            "trigger_args": {"run_date": "2030-01-01T00:00:00Z"},
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["next_run_at"] is not None


def test_schedule_rejects_invalid_triggers(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    pipeline = create_pipeline(client, auth_headers)

    empty_args = client.post(
        f"/pipelines/{pipeline['id']}/schedules",
        headers=auth_headers,
        json={
            "name": "bad-empty",
            "trigger_type": "interval",
            "trigger_args": {},
        },
    )
    assert empty_args.status_code == 422

    missing_interval = client.post(
        f"/pipelines/{pipeline['id']}/schedules",
        headers=auth_headers,
        json={
            "name": "bad-interval",
            "trigger_type": "interval",
            "trigger_args": {"timezone": "UTC"},
        },
    )
    assert missing_interval.status_code == 422

    missing_date = client.post(
        f"/pipelines/{pipeline['id']}/schedules",
        headers=auth_headers,
        json={
            "name": "bad-date",
            "trigger_type": "date",
            "trigger_args": {"timezone": "UTC"},
        },
    )
    assert missing_date.status_code == 422

    invalid_cron = client.post(
        f"/pipelines/{pipeline['id']}/schedules",
        headers=auth_headers,
        json={
            "name": "bad-cron",
            "trigger_type": "cron",
            "trigger_args": {"hour": "not-an-hour"},
        },
    )
    assert invalid_cron.status_code == 422


def test_schedule_ownership_is_enforced(
    client: TestClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    pipeline = create_pipeline(client, auth_headers)
    schedule = client.post(
        f"/pipelines/{pipeline['id']}/schedules",
        headers=auth_headers,
        json={
            "name": "private",
            "trigger_type": "interval",
            "trigger_args": {"minutes": 30},
        },
    ).json()

    assert (
        client.get(
            f"/schedules/{schedule['id']}", headers=other_auth_headers
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/schedules/{schedule['id']}",
            headers=other_auth_headers,
            json={"enabled": False},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/schedules/{schedule['id']}", headers=other_auth_headers
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/pipelines/{pipeline['id']}/schedules",
            headers=other_auth_headers,
            json={
                "name": "hijack",
                "trigger_type": "interval",
                "trigger_args": {"hours": 2},
            },
        ).status_code
        == 404
    )
