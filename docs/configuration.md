# Configuration

## API (`ETLANTIC_` prefix)

Loaded by `etlantic_runner.config.Settings` from the environment and optional `.env` file.

| Variable | Default | Notes |
| --- | --- | --- |
| `ETLANTIC_DATABASE_URL` | `sqlite:///./etlantic_runner.db` | SQLAlchemy URL |
| `ETLANTIC_JWT_SECRET` | development placeholder | ≥ 32 characters in real use |
| `ETLANTIC_JWT_ALGORITHM` | `HS256` | `HS256`, `HS384`, or `HS512` |
| `ETLANTIC_TOKEN_ENCRYPTION_KEY` | _(empty)_ | Required Fernet key for `/tokens` |
| `ETLANTIC_ACCESS_TOKEN_MINUTES` | `30` | JWT lifetime |
| `ETLANTIC_MAX_WORKERS` | `4` | In-process run pool size (1–64) |
| `ETLANTIC_PROFILE` | `development` | Passed into ETLantic policy context |
| `ETLANTIC_AUTO_MIGRATE` | `true` | Run Alembic `upgrade head` on startup |

Example (`.env.example`):

```dotenv
ETLANTIC_DATABASE_URL=sqlite:///./etlantic_runner.db
ETLANTIC_JWT_SECRET=replace-with-at-least-32-random-characters
ETLANTIC_TOKEN_ENCRYPTION_KEY=replace-with-a-fernet-key
ETLANTIC_ACCESS_TOKEN_MINUTES=30
ETLANTIC_MAX_WORKERS=4
ETLANTIC_PROFILE=development
ETLANTIC_AUTO_MIGRATE=true
```

Generate a Fernet key:

```bash
uv run python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Streamlit UI (`ETLANTIC_UI_` prefix)

Loaded by `etlantic_ui.config.UiSettings`. **Never** place JWT or Fernet secrets here.

| Variable | Default | Notes |
| --- | --- | --- |
| `ETLANTIC_UI_API_URL` | `http://127.0.0.1:8000` | FastAPI base URL |
| `ETLANTIC_UI_REQUEST_TIMEOUT_SECONDS` | `15` | httpx timeout |
| `ETLANTIC_UI_RUN_POLL_SECONDS` | `2` | Run status poll interval |

See also `frontend/.env.example`.

## Dependency pin

The API depends on a published ETLantic release from PyPI (see `pyproject.toml`, currently `etlantic==0.29.0`).
