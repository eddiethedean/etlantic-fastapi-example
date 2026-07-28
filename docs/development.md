# Development

## Layout

```text
src/etlantic_runner/   FastAPI app (API, models, runner, scheduler, tokens)
frontend/              Streamlit UI (HTTP client only)
migrations/            Alembic revisions
tests/                 API TestClient suite + tests/ui/
docs/                  Project documentation
```

## Commands

```bash
uv sync
uv run pytest
uv run ruff check src frontend tests
uv run ruff format --check src frontend tests
```

Suggested format before commit:

```bash
uv run ruff format src frontend tests
```

## Testing

| Suite | Location | Focus |
| --- | --- | --- |
| API | `tests/test_*.py` | FastAPI `TestClient`, lifespan, ownership |
| UI client | `tests/ui/test_api_client.py` | httpx client against ASGI via sync transport |
| Contract | `tests/ui/test_openapi_coverage.py` | Client methods vs `app.openapi()` |
| Streamlit | `tests/ui/test_streamlit_apptest.py` | `streamlit.testing.v1.AppTest` |

API tests use a SQLite file under `tests/` configured in `tests/conftest.py`.

## Migrations

```bash
uv run alembic upgrade head
uv run alembic revision -m "description"
```

`ETLANTIC_AUTO_MIGRATE` runs upgrades on API startup by default.

## Lint notes

Ruff selects `E`, `F`, `I`, `B`, `UP`. Frontend pages ignore `E402` (path bootstrap before imports) and some `E501` lines.
