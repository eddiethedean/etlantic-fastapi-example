# ETLantic FastAPI runner

A FastAPI application that stores users, ETLantic pipeline definitions, run
history, and schedules in SQL. SQLite and Alembic are the initial persistence
layer. The app itself runs pipelines in a bounded worker pool and restores
enabled schedules into APScheduler when it starts.

## Start it

The app installs the latest published ETLantic release from PyPI.

```bash
cp .env.example .env
# Set a strong ETLANTIC_JWT_SECRET in .env.
uv sync
uv run alembic upgrade head
uv run uvicorn etlantic_runner.api:app --reload
```

Open `http://127.0.0.1:8000/docs` for the generated API documentation.

## Authentication

Register with `POST /users`, then send the email as the OAuth2 `username` to
`POST /auth/token`. Tokens use PyJWT; passwords use Argon2 through pwdlib.

```bash
curl -X POST http://127.0.0.1:8000/users \
  -H 'content-type: application/json' \
  -d '{"email":"ada@example.com","display_name":"Ada","password":"a long secure password"}'

curl -X POST http://127.0.0.1:8000/auth/token \
  -H 'content-type: application/x-www-form-urlencoded' \
  -d 'username=ada@example.com&password=a long secure password'
```

Use the returned token as `Authorization: Bearer <token>`.

## API surface

- `POST /users`, `POST /auth/token`, `GET/PATCH/DELETE /users/me`
- `GET /users` (administrators)
- `POST/GET /pipelines`, `GET/PATCH/DELETE /pipelines/{id}`
- `POST /pipelines/{id}/edits` for ETLantic immutable edit commands
- `POST /pipelines/{id}/validate` and `/plan`
- `POST /pipelines/{id}/runs`, `GET /runs`, `GET /runs/{id}`
- `POST /pipelines/{id}/schedules`
- `GET/PATCH/DELETE /schedules/{id}`
- `POST/GET/PATCH/DELETE /tokens` for encrypted user API tokens
- `POST/GET/DELETE /pipelines/{id}/token-grants`
- `POST/GET/PATCH/DELETE /groups`
- `POST/GET/DELETE /groups/{id}/invitations`
- `POST /group-invitations/accept`
- `PUT/GET/DELETE /groups/{id}/pipelines/{pipeline_id}`

Pipeline documents must be sealed `etlantic.pipeline/1` documents with a valid
fingerprint. This prevents saving a payload that was changed after ETLantic
validated it. Each run stores a snapshot of the pipeline document, version, and
fingerprint so editing a pipeline cannot change the meaning of earlier runs.

Schedules accept APScheduler trigger arguments:

```json
{"name":"nightly","trigger_type":"cron","trigger_args":{"hour":2,"minute":0}}
```

```json
{"name":"frequent","trigger_type":"interval","trigger_args":{"minutes":15}}
```

```json
{"name":"once","trigger_type":"date","trigger_args":{"run_date":"2030-01-01T00:00:00Z"}}
```

## Secure API tokens

Set `ETLANTIC_TOKEN_ENCRYPTION_KEY` to a persistent Fernet key before startup:

```bash
uv run python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Users submit a token once through `POST /tokens`. Values are authenticated-
encrypted in the database and are never returned by the API. Tokens can be
rotated, disabled, or deleted, and independently restricted to reads, writes,
or both.

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

The grant creates an ETLantic reference shaped like:

```json
{
  "provider": "user-tokens",
  "name": "the-token-uuid",
  "key": "value",
  "version": "current",
  "purpose": "read"
}
```

Only that reference enters the pipeline plan. During a run, the owner-scoped
provider verifies the requested operation, decrypts the value just in time,
and supplies an ETLantic `SecretValue` to the configured storage provider.
Secret values refuse serialization and do not enter pipeline documents,
reports, API responses, or application logs. Keep the encryption key outside
the database and back it up securely; losing it makes stored tokens
unrecoverable.

## Groups and shared pipelines

Creating a group also creates its owner membership. Any current member may
invite another email address. Invitation acceptance tokens are random,
single-use, stored only as SHA-256 hashes, and expire after seven days. The raw
acceptance token is returned only in the invitation-creation response so the
application can deliver it through its chosen email or messaging service.

```json
POST /groups/{group_id}/invitations
{"email": "grace@example.com"}
```

```json
POST /group-invitations/accept
{"token": "the-one-time-acceptance-token"}
```

A user may add only a pipeline they own to a group they belong to:

```text
PUT /groups/{group_id}/pipelines/{pipeline_id}
```

Group members then see the pipeline in `GET /pipelines` and may retrieve, edit,
validate, plan, run, and schedule it. Ownership remains unchanged: only the
pipeline owner may delete it or remove it from a group. Group owners may remove
members or delete the group; ordinary members may leave and may invite others.

## Operational boundary

This is an in-process runner and scheduler, as requested. It is appropriate for
one application process. Running multiple API replicas would restore the same
schedules in every replica; before scaling horizontally, add leader election or
move scheduling/execution to a dedicated worker service. SQLite should likewise
be replaced with PostgreSQL before multi-process production deployment.
