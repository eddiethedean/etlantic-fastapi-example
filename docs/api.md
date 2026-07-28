# API reference

Interactive schemas: `http://127.0.0.1:8000/docs` and `/redoc`.

Unless noted, endpoints require `Authorization: Bearer <token>`.

## System

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/health` | `{"status":"ok"}` (public) |

## Users & auth

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/users` | Register (public) |
| `POST` | `/auth/token` | Issue JWT (public) |
| `GET` / `PATCH` / `DELETE` | `/users/me` | Profile / deactivate |
| `GET` | `/users` | Admin-only listing |

See [Authentication](authentication.md).

## Pipelines

| Method | Path | Notes |
| --- | --- | --- |
| `POST` / `GET` | `/pipelines` | Create / list (owned + group-shared) |
| `POST` | `/pipelines/verify-draft` | Seal/verify a draft before save |
| `GET` / `PATCH` / `DELETE` | `/pipelines/{id}` | Read / update / delete (delete = owner) |
| `POST` | `/pipelines/{id}/verify-draft` | Seal draft against an existing pipeline id |
| `POST` | `/pipelines/{id}/edits` | ETLantic immutable edit commands |
| `POST` | `/pipelines/{id}/validate` | Validation diagnostics |
| `POST` | `/pipelines/{id}/plan` | Execution plan |
| `POST` | `/pipelines/{id}/runs` | Queue a run (`202`) |
| `POST` | `/pipelines/{id}/schedules` | Create schedule |
| `POST` / `GET` | `/pipelines/{id}/token-grants` | Credential grants |
| `DELETE` | `/pipelines/{id}/token-grants/{grant_id}` | Revoke grant |

`PipelineRead` includes `access_source`, `can_delete`, and `shared_group_ids`. See [Pipelines](pipelines.md).

## Runs & schedules

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/runs` | List (`pipeline_id`, `limit`, `offset`) |
| `GET` | `/runs/{id}` | Run detail + report |
| `GET` / `PATCH` / `DELETE` | `/schedules/{id}` | Manage schedules |
| `GET` | `/schedules` | List schedules you created |

## Encrypted API tokens

| Method | Path | Notes |
| --- | --- | --- |
| `POST` / `GET` | `/tokens` | Store / list metadata only |
| `GET` / `PATCH` / `DELETE` | `/tokens/{id}` | Rotate, scope, disable, delete |

See [API tokens](tokens.md).

## Groups

| Method | Path | Notes |
| --- | --- | --- |
| `POST` / `GET` | `/groups` | Create / list |
| `GET` / `PATCH` / `DELETE` | `/groups/{id}` | Manage (delete = owner) |
| `GET` | `/groups/{id}/members` | List members |
| `DELETE` | `/groups/{id}/members/{user_id}` | Remove / leave |
| `POST` / `GET` / `DELETE` | `/groups/{id}/invitations` | Invite lifecycle |
| `POST` | `/group-invitations/accept` | Accept with one-time token |
| `PUT` / `DELETE` | `/groups/{id}/pipelines/{pipeline_id}` | Share / unshare |
| `GET` | `/groups/{id}/pipelines` | Shared pipelines |

`GroupRead` includes `current_user_role`. See [Groups](groups.md).

## Common status codes

| Code | Meaning |
| --- | --- |
| `401` | Missing/invalid/expired credentials |
| `403` | Authenticated but not permitted (e.g. wrong invite email) |
| `404` | Missing or inaccessible resource (ownership hiding) |
| `409` | Conflict (duplicate name, version, membership) |
| `410` | Gone (expired invitation) |
| `422` | Validation / ETLantic authoring error |
