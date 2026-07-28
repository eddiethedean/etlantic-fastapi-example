from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.helpers import auth_headers_for, create_pipeline


def test_group_invitation_and_shared_pipeline_collaboration(
    client: TestClient,
) -> None:
    suffix = uuid.uuid4().hex
    owner_email = f"group-owner-{suffix}@example.com"
    member_email = f"group-member-{suffix}@example.com"
    outsider_email = f"group-outsider-{suffix}@example.com"
    owner = auth_headers_for(client, owner_email)
    member = auth_headers_for(client, member_email)
    outsider = auth_headers_for(client, outsider_email)

    response = client.post(
        "/groups",
        headers=owner,
        json={"name": "Data team", "description": "Shared pipelines"},
    )
    assert response.status_code == 201, response.text
    group = response.json()
    assert group["current_user_role"] == "owner"

    response = client.post(
        f"/groups/{group['id']}/invitations",
        headers=owner,
        json={"email": member_email},
    )
    assert response.status_code == 201, response.text
    invitation = response.json()
    assert invitation["accept_token"]

    assert (
        client.post(
            "/group-invitations/accept",
            headers=outsider,
            json={"token": invitation["accept_token"]},
        ).status_code
        == 403
    )
    response = client.post(
        "/group-invitations/accept",
        headers=member,
        json={"token": invitation["accept_token"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["current_user_role"] == "member"

    members = client.get(f"/groups/{group['id']}/members", headers=member).json()
    assert {item["user"]["email"] for item in members} == {
        owner_email,
        member_email,
    }

    # Ordinary members can invite others.
    response = client.post(
        f"/groups/{group['id']}/invitations",
        headers=member,
        json={"email": outsider_email},
    )
    assert response.status_code == 201, response.text

    owner_pipeline = create_pipeline(client, owner, name=f"owner-{suffix}")
    response = client.put(
        f"/groups/{group['id']}/pipelines/{owner_pipeline['id']}",
        headers=owner,
    )
    assert response.status_code == 201, response.text

    visible = client.get("/pipelines", headers=member).json()
    shared = next(p for p in visible if p["id"] == owner_pipeline["id"])
    assert shared["access_source"] == "group"
    assert shared["can_delete"] is False
    assert group["id"] in shared["shared_group_ids"]
    response = client.patch(
        f"/pipelines/{owner_pipeline['id']}",
        headers=member,
        json={
            "description": "Edited by a group member",
            "expected_version": owner_pipeline["version"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["description"] == "Edited by a group member"
    assert (
        client.delete(
            f"/pipelines/{owner_pipeline['id']}", headers=member
        ).status_code
        == 404
    )

    # Members can add pipelines they own to any group they belong to.
    member_pipeline = create_pipeline(client, member, name=f"member-{suffix}")
    response = client.put(
        f"/groups/{group['id']}/pipelines/{member_pipeline['id']}",
        headers=member,
    )
    assert response.status_code == 201, response.text
    group_pipelines = client.get(
        f"/groups/{group['id']}/pipelines", headers=owner
    ).json()
    assert {pipeline["id"] for pipeline in group_pipelines} == {
        owner_pipeline["id"],
        member_pipeline["id"],
    }


def test_group_access_and_ownership_boundaries(
    client: TestClient,
) -> None:
    suffix = uuid.uuid4().hex
    owner = auth_headers_for(client, f"bounds-owner-{suffix}@example.com")
    outsider = auth_headers_for(client, f"bounds-outsider-{suffix}@example.com")
    group = client.post(
        "/groups",
        headers=owner,
        json={"name": f"private-{suffix}"},
    ).json()
    pipeline = create_pipeline(client, owner, name=f"private-pipe-{suffix}")

    assert client.get(f"/groups/{group['id']}", headers=outsider).status_code == 404
    assert (
        client.put(
            f"/groups/{group['id']}/pipelines/{pipeline['id']}",
            headers=outsider,
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/groups/{group['id']}/pipelines/{pipeline['id']}",
            headers=owner,
        ).status_code
        == 201
    )
    assert (
        client.delete(
            f"/groups/{group['id']}/members/{group['owner_id']}",
            headers=owner,
        ).status_code
        == 409
    )
