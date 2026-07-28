# Planning and Delivery Standards

> **Applies to:** Every roadmap phase and detailed plan  
> **Purpose:** Keep releases small, secure, testable, observable, and
> reversible while the example grows into a production-capable runner.

## Plan states

- **Proposed:** Product/technical direction exists but dependencies or an ADR
  remain open.
- **Planned:** Scope, contracts, owner, dependencies, and release gates are
  agreed.
- **In progress:** At least one delivery slice is actively implemented.
- **Shipped:** Release gates passed and product/operations docs match behavior.
- **Deferred:** Intentionally paused with the reason and revisit condition.

A status describes repository reality, not optimism. Update it in the same
change that starts or ships the phase.

## Required content

Every implementation plan identifies:

- user/operational outcomes and explicit non-goals;
- dependencies and sequencing;
- important architecture decisions and security boundaries;
- API/data migrations and compatibility strategy;
- UI/client work where relevant;
- test matrix, observability, rollout, and rollback;
- measurable release gates;
- unresolved decisions with an owner/date before implementation.

## Delivery slices

- Prefer vertical slices that deliver one safe end-to-end capability.
- Keep database, API, client, UI, tests, and docs synchronized.
- Land additive schema/API changes before switching consumers.
- Use feature flags only with an owner and removal condition.
- Do not mark a phase shipped with critical behavior hidden behind an
  undocumented flag.

## Cross-cutting invariants

These apply to every phase:

1. FastAPI is the authority for authentication, authorization, persistence,
   scheduling, and execution.
2. Streamlit communicates only through supported HTTP contracts.
3. Pipeline documents are canonical, sealed, fingerprinted, and
   optimistic-concurrency protected.
4. Credential plaintext is write-only at API boundaries and never appears in
   stored pipeline documents, UI state, logs, events, reports, or telemetry.
5. Group access is checked server-side for every operation.
6. Mutations that can be retried are idempotent.
7. Migrations preserve user data and are tested from the last shipped release.
8. Failures return stable safe codes and include a request/correlation ID.
9. Accessibility and keyboard use are acceptance criteria, not polish.
10. Current public ETLantic APIs are used from the pinned PyPI release; this
    example does not vendor or import a neighboring checkout.

## Definition of ready

Implementation starts when:

- prerequisites and open ADRs are resolved;
- API schemas and state transitions are sketched;
- data migration and rollback approach is credible;
- abuse/secret/privacy review is complete;
- representative test fixtures and performance target exist;
- release gate metrics can actually be measured.

## Definition of shipped

- scoped behavior is implemented end to end;
- unit, contract, integration, UI, security, and migration tests pass;
- OpenAPI/client drift is clean;
- logs/events/metrics are redaction-tested;
- accessibility checks appropriate to the surface pass;
- operational docs, configuration, and upgrade notes are current;
- rollback or forward-fix procedure has been rehearsed proportionally to risk;
- roadmap, detailed plan, package version, and changelog agree.

## Verification commands

The exact CI workflow may evolve, but a release should include equivalents of:

```bash
uv sync --locked
uv run ruff check .
uv run pytest
alembic upgrade head
```

Phases that add PostgreSQL, browser components, migrations, or deployment roles
must add their own required jobs rather than relying only on the base suite.

## Risk tracking

Plans keep a short risk register for issues that could change architecture or
release scope. Each risk has a mitigation and trigger. Routine coding tasks do
not belong in the risk register.

Shared high-impact risks:

- Streamlit limitations force insecure browser credential storage;
- ETLantic public authoring contracts change across upgrades;
- SQLite semantics hide PostgreSQL concurrency problems;
- scheduler/worker coupling produces duplicate work during scale-out;
- visual-builder dependencies regress accessibility or maintenance posture;
- collaboration roles become too complex to explain or audit.

## Change control

- An ADR is required for auth/session storage, graph component, queue/lease,
  scheduler leadership, email provider, and incompatible API versioning.
- Scope may move between phases, but update dependencies and release gates in
  the same change.
- A deferred item records why, what evidence would restart it, and which
  shipped assumption remains valid meanwhile.
