# Observability and Operations Plan

> **Roadmap:** 0.3  
> **Status:** Planned  
> **Depends on:** Stable problem details and request IDs from 0.2  
> **Goal:** Make execution, security-sensitive changes, and production health
> inspectable without exposing credentials or requiring direct database access.

The durable claim, attempt, lease, and retry state machine is defined in
[Durable Run Recovery](durable-run-recovery.md). This plan owns its observable
events, cancellation experience, audit trail, and operational recovery signals.

## Outcomes

- Users can follow and cancel runs from submission through a terminal state.
- Operators can correlate an API request, queued job, scheduler fire, worker
  attempt, and audit event.
- Pipeline revisions are durable, comparable, and restorable.
- Health signals distinguish “process alive” from “ready to accept work.”
- Logs, metrics, traces, and audit records share stable identifiers and
  redaction rules.

## Run lifecycle

Define an explicit state machine:

```text
queued → running → succeeded | partial | failed
   └────────────→ cancelling → cancelled
```

- Cancellation is idempotent.
- Cancelling a queued run prevents execution.
- Cancelling a running run signals the worker and records whether the backend
  acknowledged cooperative cancellation.
- A terminal run never returns to a non-terminal state.
- Timeout and worker-loss outcomes use stable failure codes.
- Store attempt number separately from logical run identity to support future
  retry without rewriting history.

Add:

- `POST /runs/{id}/cancel`
- `GET /runs/{id}/events` using SSE
- polling remains a documented fallback

SSE events carry monotonically increasing IDs so clients can reconnect with
`Last-Event-ID`. Events contain only redacted status, progress, diagnostic, and
metric payloads.

## Revision history

Persist an immutable revision for every successful pipeline create/update:

- pipeline ID and revision number;
- canonical document and fingerprint;
- author, timestamp, optional change summary;
- base revision/fingerprint;
- source operation (`create`, `edit`, `restore`, future `builder`);
- metadata needed for a structural diff.

Add list, get, compare, and restore endpoints. Restore always creates a new
revision and passes current optimistic-concurrency checks. Runs retain their
existing immutable document snapshot and point to the originating revision.

## Audit trail

Audit at minimum:

- authentication/session revocation security events;
- account profile/deactivation/deletion;
- pipeline create/update/delete/restore/share/unshare;
- token create/rotate/revoke and grant/revoke, never plaintext;
- run submit/cancel/terminal status;
- schedule create/update/enable/disable/delete/fire;
- group create/update/delete, invitation lifecycle, and membership changes.

Each event includes actor, action, target type/ID, outcome, timestamp, request
ID, correlation ID, safe structured changes, and source IP/user agent only
under a documented retention/privacy policy.

Audit writes for successful state changes occur in the same database
transaction where practical. Audit storage is append-only at the application
permission layer. Define retention, export, and access authorization before
exposing a general audit API.

## Telemetry

### Structured logs

JSON logs include timestamp, severity, service, environment, request ID,
correlation ID, route template, status, duration, user ID when authenticated,
pipeline/run/schedule IDs, and a stable error code.

Never log:

- passwords, JWTs, cookies, refresh/invitation/API-token values;
- decrypted ETLantic secrets;
- request bodies for credential endpoints;
- arbitrary pipeline payloads or row-level data by default.

### Metrics

- request rate/error/duration by route template;
- authentication and rate-limit outcomes;
- queue depth and oldest queued age;
- run starts, outcomes, duration, cancellation, and worker saturation;
- schedule fires, misses, duplicates prevented, and lag;
- database latency/lock errors and connection health;
- SSE connections, reconnects, and fallback polling;
- audit-write failures and redaction failures.

Avoid unbounded labels such as user, pipeline, run, email, or raw URL.

### Traces

Propagate trace/correlation context through API, scheduler, run queue, and
worker boundaries. Trace spans may describe node identity and duration but not
data payloads or secret-bearing parameters.

## Health and operational endpoints

- `/health/live`: event loop/process is alive; no database dependency.
- `/health/ready`: migrations current, database reachable, runner accepts work,
  and scheduler leadership is valid for the deployment mode.
- optional admin-only diagnostics expose version, queue, scheduler, and
  catalog state without secrets.

Shutdown stops accepting work, drains within a configured grace period, marks
or releases interrupted work deterministically, and closes SSE connections
with a retry hint.

## Failure handling

Document behavior for:

- database unavailable/locked;
- process restart with queued/running runs;
- scheduler misfire and clock movement;
- worker crash or timeout;
- client disconnect during SSE;
- audit sink unavailable;
- disk full and migration mismatch.

The single-process release may mark interrupted running jobs failed on restart,
but it must do so explicitly and audit the transition.

## UI work

- cancel control with state-aware confirmation;
- reconnecting live timeline with polling fallback;
- graph/list progress and first-failure focus;
- revision list, structural compare, and restore confirmation;
- user-visible request ID on unexpected errors;
- admin/authorized audit explorer only after access policy exists.

## Test and verification

- state-machine/property tests forbid invalid transitions;
- cancellation races at queued/start/running/terminal boundaries;
- SSE ordering, reconnect, authorization, backpressure, and redaction;
- restart recovery with queued and running fixtures;
- schedule misfire and duplicate-prevention behavior;
- audit completeness tests for every sensitive mutation;
- revision immutability, compare, restore, and run-snapshot integrity;
- log/trace snapshot scans for secret canaries;
- readiness failures for each dependency;
- load test event fan-out and polling fallback.

## Release gates

- Every run reaches one terminal state under cancellation/restart races.
- A user can reconnect without missing or reordering durable run events.
- Required sensitive operations emit an audit event with the same correlation
  chain as the API request.
- Restore creates a new revision and preserves all prior revisions/runs.
- Secret-canary tests find no plaintext in logs, events, metrics, or traces.
- Readiness fails closed when the service cannot safely accept work.
- Operations and incident runbooks cover restart, stuck run, schedule
  duplication, database restore, and key compromise.

## Risks

| Risk | Mitigation / trigger |
| --- | --- |
| Event streaming outgrows single-process memory | Durable event IDs now; shared event delivery moves to 0.7 |
| High-cardinality telemetry harms operations | Route-template metrics and enforced label review |
| Audit writes block primary workflows | Same-transaction minimal record plus measured indexing/retention |
| Cancellation implies guarantees a connector cannot honor | Report cooperative acknowledgement and document side-effect boundaries |

## Non-goals

- Full distributed tracing backend bundled with the example.
- User-authored arbitrary log statements.
- Exactly-once execution across multiple workers; that belongs to 0.7.
