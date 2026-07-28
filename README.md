# ETLantic FastAPI runner

Example FastAPI service for authoring, running, and scheduling
[ETLantic](https://pypi.org/project/etlantic/) pipelines, plus an optional
Streamlit UI.

It persists users, sealed pipeline documents, run history, schedules, encrypted
API tokens, and collaboration groups in SQL (SQLite + Alembic by default).
Pipelines execute in a bounded in-process worker pool; enabled schedules are
restored into APScheduler on startup.

## Features

- JWT auth (PyJWT) with Argon2 password hashing (pwdlib)
- Sealed `etlantic.pipeline/1` documents with fingerprint checks and optimistic versioning
- Validate, plan, edit, run, and schedule pipelines
- Encrypted user API tokens with per-pipeline asset grants (`SecretValue` at runtime)
- Groups with hashed one-time invitations and shared pipeline access
- Interactive OpenAPI at `/docs`
- Streamlit web UI for the full non-admin workflow

## Quick start

```bash
cp .env.example .env
# Set ETLANTIC_JWT_SECRET (≥ 32 chars) and ETLANTIC_TOKEN_ENCRYPTION_KEY (Fernet).
uv sync
uv run alembic upgrade head
uv run uvicorn etlantic_runner.api:app --reload
```

Streamlit UI (second terminal, no backend secrets):

```bash
ETLANTIC_UI_API_URL=http://127.0.0.1:8000 \
  uv run streamlit run frontend/Home.py
```

| URL | Purpose |
| --- | --- |
| http://127.0.0.1:8000/docs | Swagger UI |
| http://127.0.0.1:8000/health | Liveness |
| http://127.0.0.1:8501 | Streamlit UI |

Full walkthrough: **[docs/getting-started.md](docs/getting-started.md)**

## Documentation

| Topic | Link |
| --- | --- |
| Docs index | [docs/README.md](docs/README.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| Configuration | [docs/configuration.md](docs/configuration.md) |
| Authentication | [docs/authentication.md](docs/authentication.md) |
| API reference | [docs/api.md](docs/api.md) |
| Pipelines | [docs/pipelines.md](docs/pipelines.md) |
| API tokens | [docs/tokens.md](docs/tokens.md) |
| Groups | [docs/groups.md](docs/groups.md) |
| Streamlit UI | [docs/streamlit-ui.md](docs/streamlit-ui.md) |
| Development | [docs/development.md](docs/development.md) |
| Deployment | [docs/deployment.md](docs/deployment.md) |
| Roadmap | [docs/plans/ROADMAP.md](docs/plans/ROADMAP.md) |

## Project layout

```text
src/etlantic_runner/   FastAPI application
frontend/              Streamlit UI (HTTP client only)
migrations/            Alembic revisions
tests/                 API + Streamlit AppTest suites
docs/                  Guides and plans
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check src frontend tests
```

## Operational boundary

In-process runner and scheduler for a **single** API process. Use PostgreSQL and
a dedicated worker/leader design before horizontal scale-out. Keep JWT and Fernet
keys only in the API environment. Details: [docs/deployment.md](docs/deployment.md).
