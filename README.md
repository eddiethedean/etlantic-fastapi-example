# ETLantic FastAPI runner

Example FastAPI service for authoring, running, and scheduling [ETLantic](https://pypi.org/project/etlantic/) pipelines.

It persists users, sealed pipeline documents, run history, schedules, encrypted API tokens, and collaboration groups in SQL (SQLite + Alembic by default). Pipelines execute in a bounded in-process worker pool; enabled schedules are restored into APScheduler on startup.

## Features

- JWT auth (PyJWT) with Argon2 password hashing (pwdlib)
- Sealed `etlantic.pipeline/1` documents with fingerprint checks and optimistic versioning
- Validate, plan, edit, run, and schedule pipelines
- Encrypted user API tokens with per-pipeline asset grants (`SecretValue` at runtime)
- Groups with hashed one-time invitations and shared pipeline access
- Interactive OpenAPI docs at `/docs`

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Quick start

```bash
cp .env.example .env
```

Edit `.env` and set strong secrets before the first run:

```bash
# JWT signing secret (≥ 32 characters)
# TOKEN_ENCRYPTION_KEY — generate with:
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then install, migrate, and start:

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn etlantic_runner.api:app --reload
# or: uv run python -m etlantic_runner
```

| URL | Purpose |
| --- | --- |
| http://127.0.0.1:8000/docs | Swagger UI |
| http://127.0.0.1:8000/redoc | ReDoc |
| http://127.0.0.1:8000/health | Liveness check |

Migrations also run automatically on startup when `ETLANTIC_AUTO_MIGRATE` is left at its default (`true`).

## Configuration

Environment variables use the `ETLANTIC_` prefix (see `.env.example`):

| Variable | Default | Notes |
| --- | --- | --- |
| `ETLANTIC_DATABASE_URL` | `sqlite:///./etlantic_runner.db` | SQLAlchemy URL |
| `ETLANTIC_JWT_SECRET` | development placeholder | Must be ≥ 32 characters in real use |
| `ETLANTIC_TOKEN_ENCRYPTION_KEY` | _(empty)_ | Required Fernet key; losing it makes stored tokens unrecoverable |
| `ETLANTIC_ACCESS_TOKEN_MINUTES` | `30` | JWT lifetime |
| `ETLANTIC_MAX_WORKERS` | `4` | In-process run pool size |
| `ETLANTIC_PROFILE` | `development` | Passed into ETLantic policy context |
| `ETLANTIC_AUTO_MIGRATE` | `true` | Run Alembic `upgrade head` on app startup |

The pinned ETLantic release comes from PyPI (`etlantic==0.29.0` in `pyproject.toml`).

## Authentication

1. Register with `POST /users`.
2. Exchange credentials at `POST /auth/token` (OAuth2 password flow; use email as `username`).
3. Send `Authorization: Bearer <access_token>` on subsequent requests.

```bash
curl -X POST http://127.0.0.1:8000/users \
  -H 'content-type: application/json' \
  -d '{"email":"ada@example.com","display_name":"Ada","password":"a long secure password"}'

curl -X POST http://127.0.0.1:8000/auth/token \
  -H 'content-type: application/x-www-form-urlencoded' \
  -d 'username=ada@example.com&password=a long secure password'
```

`GET /users` is restricted to administrators (`is_admin`). `DELETE /users/me` deactivates the account and invalidates further logins.

## API overview

Interactive docs are the source of truth for request/response schemas. High-level surface:

### Users & auth

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/users` | Register |
| `POST` | `/auth/token` | Issue JWT |
| `GET` / `PATCH` / `DELETE` | `/users/me` | Profile, password, deactivate |
| `GET` | `/users` | Admin-only listing |

### Pipelines

| Method | Path | Notes |
| --- | --- | --- |
| `POST` / `GET` | `/pipelines` | Create / list (owned + group-shared) |
| `GET` / `PATCH` / `DELETE` | `/pipelines/{id}` | Read / update / delete (delete = owner only) |
| `POST` | `/pipelines/{id}/edits` | ETLantic immutable edit commands |
| `POST` | `/pipelines/{id}/validate` | Validation diagnostics |
| `POST` | `/pipelines/{id}/plan` | Execution plan |
| `POST` | `/pipelines/{id}/runs` | Queue a run (`202`) |

Documents must be sealed `etlantic.pipeline/1` payloads with a valid fingerprint. That blocks saving a document that changed after ETLantic validated it. Each run stores a snapshot of the document, version, and fingerprint so later edits cannot rewrite history. Updates support `expected_version` for optimistic concurrency.

### Runs & schedules

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/runs` | List (optional `pipeline_id` filter) |
| `GET` | `/runs/{id}` | Run detail + report |
| `POST` | `/pipelines/{id}/schedules` | Attach a schedule |
| `GET` / `PATCH` / `DELETE` | `/schedules/{id}` | Manage schedules |
| `GET` | `/schedules` | List your schedules |

Trigger examples (APScheduler args):

```json
{"name":"nightly","trigger_type":"cron","trigger_args":{"hour":2,"minute":0}}
```

```json
{"name":"frequent","trigger_type":"interval","trigger_args":{"minutes":15}}
```

```json
{"name":"once","trigger_type":"date","trigger_args":{"run_date":"2030-01-01T00:00:00Z"}}
```

### Encrypted API tokens

| Method | Path | Notes |
| --- | --- | --- |
| `POST` / `GET` | `/tokens` | Store / list metadata only |
| `GET` / `PATCH` / `DELETE` | `/tokens/{id}` | Rotate, scope, disable, delete |
| `POST` / `GET` | `/pipelines/{id}/token-grants` | Bind a token to a pipeline asset |
| `DELETE` | `/pipelines/{id}/token-grants/{grant_id}` | Revoke a grant |

Generate a persistent Fernet key and set `ETLANTIC_TOKEN_ENCRYPTION_KEY` before storing tokens:

```bash
uv run python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Users submit a secret once via `POST /tokens`. Values are authenticated-encrypted at rest and **never** returned by the API (only `last_four` and permissions). Tokens can be rotated, disabled, or deleted, and independently allow read, write, or both.

Grant a stored token to one pipeline asset:

```json
{
  "token_id": "the-token-uuid",
  "binding": "customer_source",
  "provider": "your-storage-provider",
  "location": "https://api.example.com/customers",
  "operation": "read"
}
```

The grant exposes an ETLantic secret reference (not the plaintext):

```json
{
  "provider": "user-tokens",
  "name": "the-token-uuid",
  "key": "value",
  "version": "current",
  "purpose": "read"
}
```

Only that reference enters the plan. At run time, an owner-scoped provider checks the operation, decrypts just-in-time, and supplies an ETLantic `SecretValue`. Secret values refuse serialization and do not appear in documents, reports, API responses, or logs. Keep the encryption key outside the database and back it up; losing it makes stored tokens unrecoverable.

### Groups & shared pipelines

| Method | Path | Notes |
| --- | --- | --- |
| `POST` / `GET` | `/groups` | Create / list memberships |
| `GET` / `PATCH` / `DELETE` | `/groups/{id}` | Manage group (delete = owner) |
| `GET` | `/groups/{id}/members` | List members |
| `DELETE` | `/groups/{id}/members/{user_id}` | Remove member / leave |
| `POST` / `GET` / `DELETE` | `/groups/{id}/invitations` | Invite by email |
| `POST` | `/group-invitations/accept` | Accept with one-time token |
| `PUT` / `DELETE` | `/groups/{id}/pipelines/{pipeline_id}` | Share / unshare owned pipeline |
| `GET` | `/groups/{id}/pipelines` | Pipelines shared with the group |

Creating a group also creates the owner membership. Any current member may invite an email address. Invitation acceptance tokens are random, single-use, stored only as SHA-256 hashes, and expire after seven days. The raw token is returned **only** when the invitation is created so your app can deliver it out-of-band (email, chat, etc.).

```json
POST /groups/{group_id}/invitations
{"email": "grace@example.com"}
```

```json
POST /group-invitations/accept
{"token": "the-one-time-acceptance-token"}
```

Share a pipeline you own with a group you belong to:

```http
PUT /groups/{group_id}/pipelines/{pipeline_id}
```

Group members then see it in `GET /pipelines` and may retrieve, edit, validate, plan, run, and schedule it. Ownership is unchanged: only the pipeline owner may delete it or remove it from a group. Group owners may remove members or delete the group; ordinary members may leave and invite others.

## Project layout

```text
src/etlantic_runner/   Application package (API, models, runner, scheduler, tokens)
migrations/            Alembic revisions
tests/                 FastAPI TestClient suite
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
```

Tests use FastAPI’s `TestClient` (lifespan, migrations, runner, and scheduler) with a dedicated SQLite file under `tests/`.

## Operational boundary

This is an **in-process** runner and scheduler, suitable for a single application process.

- Multiple API replicas would each restore the same schedules — add leader election or move scheduling/execution to a dedicated worker before horizontal scale-out.
- Replace SQLite with PostgreSQL (or similar) before multi-process production use.
- Treat `ETLANTIC_JWT_SECRET` and `ETLANTIC_TOKEN_ENCRYPTION_KEY` as production secrets; rotate JWT secret carefully (existing tokens become invalid).
