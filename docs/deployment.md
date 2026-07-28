# Deployment

## Local dual process

Run API and Streamlit as separate processes (see [Getting started](getting-started.md)).

## Production checklist

1. **Secrets** — Strong `ETLANTIC_JWT_SECRET` and a backed-up `ETLANTIC_TOKEN_ENCRYPTION_KEY`. Keep both only in the FastAPI environment.
2. **Database** — Replace SQLite with PostgreSQL (or similar) before multi-process use.
3. **Single scheduler** — This app restores enabled schedules in-process. Multiple API replicas would duplicate schedules; add leader election or move scheduling/execution to a dedicated worker before horizontal scale-out.
4. **Streamlit** — Configure only `ETLANTIC_UI_*`. Do not inject backend secrets into the UI container.
5. **TLS** — Terminate HTTPS in front of both services.
6. **CORS** — Not required for server-side Streamlit → API httpx calls. Add CORS only if browsers call the API directly.
7. **Logging** — Avoid logging `Authorization` headers, passwords, invitation tokens, or API-token payloads.
8. **Health** — Probe `GET /health` for the API; add a readiness check for Streamlit as appropriate.
9. **JWT rotation** — Changing `ETLANTIC_JWT_SECRET` invalidates outstanding access tokens.

## What this example is not

- A multi-tenant SaaS control plane
- A horizontally scaled runner/scheduler without extra design
- An email delivery system for group invitations
- A visual node-and-edge pipeline designer (see plan Phase 5)

## Related

- [Architecture](architecture.md)
- [Configuration](configuration.md)
