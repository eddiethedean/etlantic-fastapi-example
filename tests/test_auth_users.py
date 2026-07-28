from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import PASSWORD, login, register_user


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_and_login(client: TestClient, unique_email: str) -> None:
    user = register_user(client, unique_email, display_name="Ada Lovelace")
    assert user["email"] == unique_email.lower()
    assert user["display_name"] == "Ada Lovelace"
    assert user["is_active"] is True
    assert user["is_admin"] is False
    assert "password" not in user
    assert "password_hash" not in user

    token = login(client, unique_email)
    assert token["token_type"] == "bearer"
    assert token["expires_in"] > 0
    assert token["access_token"]

    me = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["id"] == user["id"]


def test_register_rejects_duplicate_email(
    client: TestClient, unique_email: str
) -> None:
    register_user(client, unique_email)
    response = client.post(
        "/users",
        json={
            "email": unique_email.upper(),
            "display_name": "Clone",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Email is already registered"


def test_register_rejects_short_password(client: TestClient, unique_email: str) -> None:
    response = client.post(
        "/users",
        json={
            "email": unique_email,
            "display_name": "Ada",
            "password": "too-short",
        },
    )
    assert response.status_code == 422


def test_login_rejects_bad_credentials(client: TestClient, unique_email: str) -> None:
    register_user(client, unique_email)
    response = client.post(
        "/auth/token",
        data={"username": unique_email, "password": "wrong password!!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_rejects_unknown_user(client: TestClient) -> None:
    response = client.post(
        "/auth/token",
        data={"username": "missing@example.com", "password": PASSWORD},
    )
    assert response.status_code == 401


def test_protected_routes_require_bearer(client: TestClient) -> None:
    assert client.get("/users/me").status_code == 401
    assert client.get("/pipelines").status_code == 401
    assert client.get("/tokens").status_code == 401
    assert client.get("/runs").status_code == 401
    assert client.get("/schedules").status_code == 401


def test_protected_routes_reject_invalid_token(client: TestClient) -> None:
    headers = {"Authorization": "Bearer not-a-real-jwt"}
    assert client.get("/users/me", headers=headers).status_code == 401


def test_update_profile_and_password(
    client: TestClient, auth_headers: dict[str, str], unique_email: str
) -> None:
    response = client.patch(
        "/users/me",
        headers=auth_headers,
        json={"display_name": "Augusta"},
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Augusta"

    new_password = "an even longer secure password"
    response = client.patch(
        "/users/me",
        headers=auth_headers,
        json={"password": new_password},
    )
    assert response.status_code == 200

    assert (
        client.post(
            "/auth/token",
            data={"username": unique_email, "password": PASSWORD},
        ).status_code
        == 401
    )
    token = login(client, unique_email, password=new_password)
    assert token["access_token"]


def test_deactivate_blocks_login(
    client: TestClient, auth_headers: dict[str, str], unique_email: str
) -> None:
    response = client.delete("/users/me", headers=auth_headers)
    assert response.status_code == 204

    assert client.get("/users/me", headers=auth_headers).status_code == 401
    assert (
        client.post(
            "/auth/token",
            data={"username": unique_email, "password": PASSWORD},
        ).status_code
        == 401
    )


def test_list_users_requires_admin(
    client: TestClient,
    auth_headers: dict[str, str],
    admin_auth_headers: dict[str, str],
) -> None:
    assert client.get("/users", headers=auth_headers).status_code == 403

    response = client.get("/users", headers=admin_auth_headers)
    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list)
    assert len(users) >= 1
    assert all("email" in user for user in users)
