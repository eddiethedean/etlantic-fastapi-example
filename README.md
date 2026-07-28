# ETLantic FastAPI runner

A FastAPI application that stores users, ETLantic pipeline definitions, run
history, and schedules in SQL. SQLite and Alembic are the initial persistence
layer. The app itself runs pipelines in a bounded worker pool and restores
enabled schedules into APScheduler when it starts.

## Start it

This example uses the sibling `../etlantic` checkout as an editable dependency.

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

## Operational boundary

This is an in-process runner and scheduler, as requested. It is appropriate for
one application process. Running multiple API replicas would restore the same
schedules in every replica; before scaling horizontally, add leader election or
move scheduling/execution to a dedicated worker service. SQLite should likewise
be replaced with PostgreSQL before multi-process production deployment.

