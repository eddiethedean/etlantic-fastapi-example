# Streamlit UI

The UI under `frontend/` is an HTTP-only client for the runner API.

## Principles

- FastAPI remains the only authority for auth, persistence, execution, and scheduling.
- Do not import `etlantic_runner` models/DB/runner/scheduler from Streamlit pages.
- Never store passwords, API-token plaintext, Fernet keys, or JWT signing secrets in Streamlit env or long-lived session state (beyond the short-lived access token).
- Token values are write-only; clear widgets after submit.
- Invitation `accept_token` values are shown once for manual copy — no email delivery.

## Run locally

```bash
# Terminal 1 — API
uv run uvicorn etlantic_runner.api:app --reload

# Terminal 2 — UI
ETLANTIC_UI_API_URL=http://127.0.0.1:8000 \
  uv run streamlit run frontend/Home.py
# or: uv run etlantic-ui
```

UI settings: [Configuration](configuration.md#streamlit-ui-etlantic_ui--prefix).

## Pages

| Page | Role |
| --- | --- |
| `Home.py` | Sign in / register / accept invitation / dashboard |
| `01_Pipelines` | Library, create, ownership badges |
| `02_Pipeline_Workspace` | Overview, JSON editor, validate, plan, runs, schedules, credentials, sharing |
| `03_Runs` | Run history and detail |
| `04_Schedules` | Global schedule management |
| `05_API_Tokens` | Encrypted token vault |
| `06_Groups` | Groups, members, invitations, shared pipelines |
| `07_Account` | Profile, password, deactivate; admin user list when `is_admin` |

## Editor workflow

1. Edit JSON in the workspace Definition tab (state preserved across Streamlit reruns).
2. **Verify & save** calls `POST /pipelines/{id}/verify-draft`, then `PATCH` with `expected_version`.
3. On `409` version conflict, keep local text or reload from the server — never silently overwrite.

## Package layout

```text
frontend/
├── Home.py
├── pages/
├── etlantic_ui/          # api_client, auth/state, components
└── .env.example
```

## Further reading

- Implementation plan (historical): [plans/streamlit-frontend.md](plans/streamlit-frontend.md)
- Testing with AppTest: [Development](development.md)
