# Streamlit frontend

HTTP client for the ETLantic Runner API. Product docs:
[docs/streamlit-ui.md](../docs/streamlit-ui.md).

```bash
ETLANTIC_UI_API_URL=http://127.0.0.1:8000 \
  uv run streamlit run frontend/Home.py
```

Never put `ETLANTIC_JWT_SECRET` or `ETLANTIC_TOKEN_ENCRYPTION_KEY` in UI env.
See `frontend/.env.example` and [docs/configuration.md](../docs/configuration.md).
