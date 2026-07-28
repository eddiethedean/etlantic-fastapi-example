# API Ergonomics and Sessions Plan

> **Roadmap:** 0.2  
> **Status:** Planned · next release  
> **Goal:** Make authenticated sessions and collection APIs reliable enough for
> long-running interactive clients without weakening the current security model.

## Outcomes

- A browser session survives access-token rotation without another password
  prompt.
- Every collection can be paged predictably and remains stable under concurrent
  inserts.
- Clients can retry eligible mutations without creating duplicates.
- Errors are machine-readable, safe to display, and traceable in server logs.
- Existing 0.1 clients receive a documented compatibility window.

## Decisions

### Session model

Use short-lived access JWTs and opaque, rotating refresh sessions.

- Store only a SHA-256 hash of each refresh token in SQL.
- Send refresh credentials to browser clients in `Secure`, `HttpOnly`,
  `SameSite=Lax`, path-scoped cookies when the browser calls FastAPI directly.
- For server-side clients such as Streamlit, return the refresh credential only
  through an explicit confidential-client response mode and keep it in a
  server-side session store.
- Rotate on every refresh. Reuse of an already-rotated token revokes the token
  family and emits a security audit event.
- Sessions record user, family, creation, last use, absolute expiry, idle
  expiry, revocation, client label, and a privacy-bounded device fingerprint.
- Password changes, account deactivation, and account deletion revoke every
  active session.
- Do not put refresh credentials in local storage, query parameters, logs, or
  JWT claims.

The current in-memory Streamlit refresh survival is an interim single-process
measure. Replace it with this durable session exchange before multi-process UI
deployment.

### Pagination

Prefer cursor pagination for runs, audit events, and revision history, where
records are append-heavy. Use limit/offset only for small administration lists
that require arbitrary page jumps.

Cursor envelopes:

```json
{
  "items": [],
  "next_cursor": null,
  "has_more": false
}
```

- Cursors are opaque, signed, versioned, and bind sort/filter fields.
- Default ordering has a stable unique tie-breaker such as `(created_at, id)`.
- Reject mismatched or expired cursors with a stable problem code.
- Enforce a documented default and maximum page size.

### Problem details

Adopt `application/problem+json` with:

- `type`, `title`, `status`, `detail`, and `instance`;
- stable application `code`;
- `request_id`;
- optional `errors[]` with `field`, `path`, `code`, and safe message;
- optional retry metadata.

Never include exception reprs, SQL, token material, pipeline secret values, or
stack traces. Keep the existing `detail` response readable during a transition,
then remove it only in a documented version boundary.

### Idempotency

Support `Idempotency-Key` on create pipeline/group/token metadata, invitation,
run submission, schedule creation, and other retryable POST operations.

- Scope keys to authenticated principal, method, route, and normalized payload
  hash.
- Store status and response for a bounded retention period.
- Concurrent duplicates wait for or replay the first completed response.
- Reusing a key with a different payload returns `409 idempotency_conflict`.
- Never store token plaintext in an idempotency record.

## API surface

Add:

- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/sessions`
- `DELETE /auth/sessions/{session_id}`
- `DELETE /auth/sessions` for “sign out everywhere”

Update collection endpoints to return envelopes and advertise cursor/filter
parameters in OpenAPI. Add standard request ID and problem response schemas to
every operation.

## Data model and migrations

Add tables for:

- refresh sessions/token families;
- idempotency records.

Migration requirements:

- additive first; no destructive 0.1 column changes;
- indexes for token hash, user/session status, expiry cleanup, and idempotency
  lookup;
- a bounded cleanup job for expired sessions and idempotency records;
- migrations exercised from an actual 0.1 database fixture;
- downgrade documented even if production policy is forward-fix.

## Streamlit work

- Replace the in-process bearer-session cache with a durable server-side
  Streamlit session that uses the refresh exchange.
- Refresh shortly before access expiry and retry one safe request after a
  successful rotation.
- Coordinate concurrent page calls so only one refresh occurs.
- On refresh failure, clear all user-scoped state and return to sign-in.
- Add paginated list controls that preserve filters and selection.
- Render field-level problem details next to the relevant widget.
- Generate a UUID idempotency key per user gesture and retain it across retry.

## Security and abuse controls

- Rate-limit login, refresh, session enumeration, and invitation acceptance.
- Use constant-time token-hash comparisons where applicable.
- Prevent session fixation by creating a new family at login.
- Enforce CSRF protection on cookie-authenticated mutation endpoints.
- Redact authorization, cookie, password, invitation, and token-value fields.
- Do not reveal account existence through login or refresh errors.
- Set conservative absolute/idle lifetimes and make them configurable.
- Cap active sessions per user with predictable eviction or rejection.

## Test matrix

- login → refresh → old refresh reuse → family revocation;
- concurrent refresh requests;
- logout one session and all sessions;
- disabled/deleted user;
- cookie flags and CSRF checks;
- expired, malformed, mismatched-filter, and tampered cursors;
- stable pagination during concurrent inserts;
- idempotent replay, conflict, in-flight duplicate, and expiry;
- problem details for validation/authz/conflict/rate limit/5xx;
- 0.1 compatibility and OpenAPI-client drift;
- multi-user cache/session isolation in Streamlit.

## Rollout

1. Ship new schemas and endpoints while retaining legacy list responses behind
   an explicit media type or API-version setting.
2. Update `EtlanticApiClient` and Streamlit.
3. Observe refresh, idempotency replay, pagination, and error-code metrics.
4. Publish the legacy removal milestone before changing defaults.

Rollback must not invalidate valid access JWTs. New tables are safe to leave in
place during an application rollback.

## Release gates

- Rotation/reuse tests prove stolen refresh-token replay revokes the family.
- No browser-readable storage contains access or refresh credentials.
- Collection contract tests cover empty, first, middle, last, and mutated pages.
- Every documented error path returns a stable problem code and request ID.
- Eligible mutation retries create exactly one durable side effect.
- Streamlit remains authenticated through access-token rotation and clears
  cleanly after revocation.
- Migration tests pass from a 0.1 snapshot.

## Risks

| Risk | Mitigation / trigger |
| --- | --- |
| Cookie refresh conflicts with server-side Streamlit HTTP calls | Complete a browser/proxy/session ADR before endpoint implementation |
| Rotation races revoke legitimate sessions | Serialize per-family refresh and test concurrent tabs |
| Pagination change breaks 0.1 clients | Additive version/media-type rollout with contract telemetry |
| Idempotency storage captures secret payloads | Route-specific normalized hashes and secret-canary tests |

## Non-goals

- Third-party OAuth/OIDC login.
- Organization-wide SSO.
- API keys as a replacement for user sessions.
- Arbitrary backward compatibility without an explicit version policy.
