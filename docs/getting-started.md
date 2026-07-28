# Getting started

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## 1. Clone and install

```bash
uv sync
cp .env.example .env
```

## 2. Configure secrets

Edit `.env` before the first run:

1. Set `ETLANTIC_JWT_SECRET` to at least 32 random characters.
2. Generate and set a Fernet key for token encryption:

```bash
uv run python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put the output in `ETLANTIC_TOKEN_ENCRYPTION_KEY`. **Back this key up.** Losing it makes stored API tokens unrecoverable.

See [Configuration](configuration.md) for the full variable list.

## 3. Migrate the database

```bash
uv run alembic upgrade head
```

With the default `ETLANTIC_AUTO_MIGRATE=true`, migrations also run when the API process starts.

## 4. Start the API

```bash
uv run uvicorn etlantic_runner.api:app --reload
# or: uv run python -m etlantic_runner
```

| URL | Purpose |
| --- | --- |
| http://127.0.0.1:8000/docs | Swagger UI |
| http://127.0.0.1:8000/redoc | ReDoc |
| http://127.0.0.1:8000/health | Liveness |

## 5. Start the Streamlit UI (optional)

In a second terminal — UI-only env vars, **no** JWT or Fernet secrets:

```bash
ETLANTIC_UI_API_URL=http://127.0.0.1:8000 \
  uv run streamlit run frontend/Home.py
# or: uv run etlantic-ui
```

Open http://127.0.0.1:8501.

## First API calls

```bash
curl -X POST http://127.0.0.1:8000/users \
  -H 'content-type: application/json' \
  -d '{"email":"ada@example.com","display_name":"Ada","password":"a long secure password"}'

curl -X POST http://127.0.0.1:8000/auth/token \
  -H 'content-type: application/x-www-form-urlencoded' \
  -d 'username=ada@example.com&password=a long secure password'
```

Use `Authorization: Bearer <access_token>` on subsequent requests. Details: [Authentication](authentication.md).

## Next steps

- [Streamlit UI](streamlit-ui.md) — browse pipelines without curl
- [Pipelines](pipelines.md) — sealed documents and runs
- [API tokens](tokens.md) — encrypted credentials
- [Groups](groups.md) — share pipelines with teammates
