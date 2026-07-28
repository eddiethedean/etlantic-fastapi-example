# Authentication

## Register

`POST /users`

```json
{
  "email": "ada@example.com",
  "display_name": "Ada",
  "password": "a long secure password"
}
```

- Passwords must be 12–128 characters.
- Emails are stored lowercased; duplicates return `409`.
- Passwords are hashed with Argon2 via pwdlib.
- Response never includes password material.

## Login

`POST /auth/token` — OAuth2 password flow (`application/x-www-form-urlencoded`).

| Field | Value |
| --- | --- |
| `username` | user email |
| `password` | plaintext password |

Response:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 1800
}
```

Tokens are signed with `ETLANTIC_JWT_SECRET` (default HS256). Claims include `sub` (user id), `type: "access"`, `iat`, and `exp`.

There is **no refresh-token endpoint**. Clients must re-authenticate when the access token expires or the API returns `401`.

## Authenticated requests

```http
Authorization: Bearer <access_token>
```

`GET /users/me` returns the current profile. Inactive users cannot log in or use bearer tokens.

## Profile

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/users/me` | Current user |
| `PATCH` | `/users/me` | Update `display_name` and/or `password` |
| `DELETE` | `/users/me` | Deactivate (`204`); further login fails |

## Administrators

`GET /users` lists users and requires `is_admin`. Ordinary registration creates non-admin accounts; promote via database for local demos.

## Public routes

No bearer token required:

- `GET /health`
- `POST /users`
- `POST /auth/token`
