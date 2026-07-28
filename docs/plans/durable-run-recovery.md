# Durable Run Recovery Plan

> **Roadmap:** Begins in 0.3; completes for multiple workers in 0.7  
> **Status:** Planned  
> **Depends on:** 0.2 idempotency/problem contracts; 0.3 run events and
> observability; PostgreSQL for multi-worker operation  
> **Goal:** Turn `PipelineRun` from a durable history row plus in-memory task
> into a recoverable database-backed job with explicit attempt and side-effect
> semantics.

## Current state

Submission currently:

1. inserts and commits a `PipelineRun(status="queued")`;
2. submits its ID to an in-process `ThreadPoolExecutor`;
3. changes the row to `running`;
4. stores the final report/error and terminal status.

The durable row and immutable pipeline snapshot are the correct starting
point, but the executor queue, claim ownership, and progress are process-local.
After a crash, nothing safely distinguishes:

- queued but never started;
- running in a dead process;
- completed externally but not committed locally;
- still running in another live process.

## Responsibility boundary

The platform owns:

- durable job admission and idempotent submission;
- queue ordering, worker claims, leases, heartbeats, attempts, and fencing;
- process restart recovery and scheduler occurrence deduplication;
- cancellation delivery, retry timing, and operational state transitions;
- PostgreSQL transactions and worker coordination.

ETLantic owns reusable pipeline-execution semantics:

- side-effect, determinism, idempotency, retry-safety, and write-intent
  declarations;
- checkpoint/state-provider contracts and safe advancement rules;
- attempt-aware execution context and normalized reports;
- classification of known failure versus unknown external commit outcome;
- replay/resume/repair planning and safe artifact reuse;
- execution-plugin conformance for cancellation, retries, and recovery.

ETLantic should not own this application's SQL queue, APScheduler leader,
FastAPI routes, or deployment topology.

## State and attempt model

Logical run states:

```text
queued → running → succeeded | partial | failed
   │         │
   │         ├→ cancelling → cancelled
   │         └→ recovery_required → queued | failed | manual_review
   └→ cancelled
```

Store execution attempts separately:

- attempt ID and monotonically increasing number;
- run ID;
- worker ID;
- claim/fencing token;
- claimed, started, heartbeat, lease-expiry, and finished timestamps;
- attempt status and normalized failure category;
- ETLantic report/reference;
- retry decision and reason;
- checkpoint/artifact references safe for a later attempt;
- whether external effect outcome is `none`, `known_committed`,
  `known_not_committed`, or `unknown`.

Never overwrite prior attempts. The logical run derives its visible status from
the active/latest valid attempt.

## Atomic claim and fencing

For PostgreSQL, claim queued or expired-recoverable work transactionally using
row locking such as `FOR UPDATE SKIP LOCKED`, or an equivalent compare-and-swap
update.

Claim returns a new fencing token and lease deadline. Every heartbeat, event,
checkpoint reference, and terminal write includes that token. A worker whose
lease expired cannot commit after a replacement worker has claimed the run.

A lease prevents two live workers from believing they own the same attempt; it
does not prevent duplicate external side effects. Side-effect safety remains a
separate retry decision.

## Recovery decisions

On startup and continuously:

- unclaimed `queued` runs are eligible for claim;
- `running` with a valid lease remains owned;
- expired lease with no side effects may retry automatically;
- expired lease with proven idempotent/transactional effects may retry under
  policy;
- known committed output proceeds only through safe post-commit recovery;
- unknown external commit outcome becomes `manual_review` unless the connector
  supplies reconciliation/deduplication proof;
- attempts over their retry/age limits terminate with a stable recovery code.

Do not reset every `running` row to `queued`.

## Retry policy

Resolve policy from platform limits plus ETLantic safety evidence:

- maximum attempts and total elapsed time;
- exponential backoff with jitter;
- retryable failure categories;
- required idempotency/transaction/checkpoint capability;
- per-node or whole-run recovery granularity;
- manual approval for destructive or ambiguous writes.

Platform policy may be stricter than ETLantic's declared maximum. It may never
weaken an ETLantic unsafe-retry decision.

## Checkpoints and resumability

Start with whole-run retry. Add step/region resume only when ETLantic reports:

- a durable artifact/checkpoint identity;
- the exact pipeline plan/revision and input snapshot it belongs to;
- successful publication boundary;
- security domain and credential-version compatibility;
- downstream invalidation/repair closure;
- atomic checkpoint advancement evidence.

A checkpoint is reusable evidence, not proof that arbitrary external effects
can be skipped.

## Database changes

Extend `pipeline_runs` with recovery-facing summary fields and add:

- `pipeline_run_attempts`;
- optional durable `pipeline_run_events`;
- queue/outbox metadata if admission and wake-up are separated;
- indexes for claimable state/availability/priority and expired leases;
- constraints preventing more than one active fenced attempt per run.

Migrate existing terminal rows as completed attempt zero or leave them as
legacy history through an explicit compatibility rule. Existing queued/running
rows at migration time require an operator-visible reconciliation step.

## Delivery slices

### Slice A — Honest restart handling (0.3)

- detect unfinished rows on single-process startup;
- mark previously `running` rows `recovery_required`;
- re-enqueue never-started `queued` rows;
- expose recovery status and operator/user action;
- do not automatically retry ambiguous external writes.

### Slice B — Durable single-worker claims (0.3)

- attempts, lease, heartbeat, fencing, cancellation intent;
- database polling/wakeup replaces correctness dependence on executor memory;
- whole-run retry only when policy says safe;
- restart and crash-injection tests.

### Slice C — Multiple workers (0.7)

- PostgreSQL concurrent claims;
- dedicated worker process;
- outbox/wakeup mechanism;
- scheduler occurrence deduplication;
- graceful drain, lease transfer, autoscaling, and load tests.

### Slice D — Checkpoint-aware resume (ETLantic integration)

- consume ETLantic attempt/checkpoint/retry-safety evidence;
- resume safe regions or build a repair/replay request;
- reconcile unknown outcomes where a provider supports it;
- preserve comparable normalized reports across attempts.

## API and UI

Add:

- attempt list/detail on a run;
- cancellation and permitted retry endpoints;
- `retryable`, `retry_reason`, `recovery_state`, and `active_attempt` metadata;
- admin/operator reconciliation action for ambiguous outcomes;
- event stream entries for claim, heartbeat loss, recovery, retry, and manual
  review without exposing worker secrets.

The UI distinguishes `failed`, `retrying`, `recovery required`, and `outcome
unknown`. A retry button appears only when the API authorizes and explains it.

## Test matrix

- crash after run insert, claim, start, checkpoint, external-write simulation,
  and terminal result;
- lease expiration before/after replacement claim;
- stale worker heartbeat/terminal write rejected by fencing;
- two workers claim the same queue concurrently;
- cancellation during queued/running/retrying states;
- idempotency-key replay at submission;
- safe-idempotent versus unsafe/unknown side-effect retry;
- max attempts/backoff and worker drain;
- migration with terminal, queued, and running legacy rows;
- event/report/secret redaction across every attempt;
- PostgreSQL failover and process restart in 0.7.

## Release gates

- Every accepted run is durably claimable or terminal; executor-memory loss
  cannot strand a never-started run.
- No two workers hold valid ownership of the same run.
- A stale worker cannot commit progress or terminal status.
- Unsafe or unknown external outcomes never retry automatically.
- Attempt history and the original pipeline snapshot remain immutable.
- Restart recovery and crash injection cover every persistence boundary.
- ETLantic retry/checkpoint evidence can restrict but never be overridden by
  platform policy.

## Non-goals

- Exactly-once external side effects for arbitrary systems.
- Treating a database lease as an idempotency guarantee.
- Embedding a specific FastAPI/PostgreSQL queue implementation in ETLantic.
- Step-level resume before durable artifact and checkpoint semantics exist.
