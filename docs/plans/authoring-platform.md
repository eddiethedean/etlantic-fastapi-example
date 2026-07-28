# Authoring Platform Plan

> **Roadmap:** 0.4  
> **Status:** Planned · prerequisite for visual builder  
> **Depends on:** 0.2 problem contracts; revision storage from 0.3 is strongly
> recommended  
> **Goal:** Expose ETLantic's authoring model as a stable, safe HTTP contract
> suitable for structured and visual clients.

## Outcomes

- Clients discover supported components and capabilities at runtime.
- A pipeline can be authored without submitting raw JSON.
- Draft edits are atomic, canonicalized, fingerprinted, and conflict-safe.
- Diagnostics point to stable graph and form locations.
- Upgrading the installed ETLantic package does not silently break saved drafts.

## Capability negotiation

Add `GET /authoring/capabilities` returning:

- installed ETLantic version;
- supported pipeline document/catalog schema versions;
- supported edit operations and lifecycle actions;
- enabled engines/providers and feature flags;
- server draft and compatibility limits.

Clients reject unsupported required schema versions before editing. Cache the
response with ETag and invalidate it when installed components/configuration
change.

## Catalog contract

Add `GET /authoring/catalog` with filters for kind, query, engine, capability,
and compatibility. Entries include:

- stable identity/version, kind, display name, description;
- typed input/output/parameter ports;
- required/default/choice/constraint/example metadata;
- contract/type compatibility;
- configuration JSON Schema plus curated UI hints;
- required credential capability (`read`, `write`, asset/provider);
- deprecation and replacement information;
- safe documentation link and application-controlled icon key.

Catalog output is UI-safe and inert: no callables, imports, secret defaults,
arbitrary HTML, or executable expressions. Paginate large third-party catalogs
and expose a catalog version/ETag.

## Draft resource

Use server-side drafts rather than repeatedly mutating persisted pipelines:

- `POST /pipeline-drafts`
- `GET /pipeline-drafts/{id}`
- `DELETE /pipeline-drafts/{id}`
- `POST /pipeline-drafts/{id}/edits`
- `POST /pipeline-drafts/{id}/verify`
- `POST /pipeline-drafts/{id}/plan`
- `POST /pipeline-drafts/{id}/commit`

A draft records owner, optional source pipeline/revision, canonical document,
draft fingerprint/concurrency token, catalog/document version, timestamps, and
expiry. Group access is evaluated against the source pipeline on every request;
draft possession is not authorization.

Draft creation supports blank, recipe, imported document, saved revision, and
clone. Imported content passes inert deserialization and resource limits before
storage.

## Edit contract

Expose discriminated OpenAPI models for:

- add/remove/update node;
- connect/disconnect ports;
- reorder nodes;
- clone document;
- atomic edit batch.

Do not claim rename, disable, layout, or field mapping as operations until
ETLantic provides explicit semantics. Never implement rename as delete/add
because it can destroy edges and identity.

Every mutation includes:

- expected draft concurrency token;
- idempotency key;
- one or more typed commands;
- optional client gesture label for undo/history.

The response contains the authoritative canonical document, new fingerprint
and token, localized diagnostics, and a structural change summary. An atomic
batch either fully applies or makes no change.

## Diagnostics

Normalize ETLantic diagnostics into:

- stable code and severity;
- user-safe message and optional suggestion;
- draft fingerprint;
- location path with node, port, field/parameter, edge identity, or document
  section;
- optional related locations;
- blocking/non-blocking classification.

Do not make clients parse message text. Preserve original safe diagnostic
metadata under a versioned extension field when useful.

## Compatibility and upgrades

- Pin ETLantic in the lockfile and test the exact installed release.
- Store document and catalog schema versions with every draft/revision.
- Provide an explicit preview/apply upgrade path for older documents.
- Upgrades show diagnostics and structural diff before commit.
- Unknown supported fields survive edits and graph/JSON round-trip.
- A missing/deprecated catalog component remains representable and never
  disappears silently.

## Structured Streamlit editor

Before the full canvas, ship a form/list authoring path that exercises the same
contracts:

- add node from searchable catalog;
- configure common and advanced fields;
- list ports and connect through compatible dropdowns;
- manage data mappings and credential grants;
- verify, plan, review changes, and commit.

This is both a useful accessible fallback and a proving ground for the visual
builder's backend contracts.

## Security and limits

- Authoring is inert until explicit plan/run; catalog discovery performs no
  user-controlled import.
- Apply maximum document, node, edge, nesting-depth, edit-batch, and diagnostic
  limits.
- Prevent SSRF/file access during verification and catalog rendering.
- Credentials remain database grants; drafts never contain plaintext.
- Sanitize descriptions/docs and allow-list outbound link schemes.
- Rate-limit expensive verification/planning separately from cheap edits.
- Expired drafts and orphaned resources are cleaned predictably.

## Test matrix

- catalog snapshots against the installed ETLantic public facade;
- OpenAPI discriminators for every edit;
- edit parity with ETLantic's public authoring API;
- batch atomicity and concurrency races;
- draft create/resume/expire/delete/commit authorization;
- invalid/malicious import and resource-limit cases;
- diagnostic location stability;
- old-document upgrade preview/apply;
- unknown-field preservation and property-based round-trip;
- group access changes while a draft is open;
- secret canaries across catalog, draft, diagnostics, and plan.

## Release gates

- A user creates and commits a valid sealed source-step-sink pipeline without
  raw JSON.
- Every supported edit is represented by typed OpenAPI and parity-tested
  against the installed ETLantic package.
- Stale draft edits return conflict without losing either document.
- Draft commit creates the correct immutable revision and respects persisted
  `expected_version`.
- Catalog and diagnostics contain no callable or secret-bearing values.
- Structured editor passes keyboard-only and screen-reader acceptance.
- Upgrade tests cover every supported document schema version.

## Risks

| Risk | Mitigation / trigger |
| --- | --- |
| Catalog schema cannot describe real plugins | Prove against representative source/step/sink fixtures before freezing v1 |
| UI and ETLantic edit semantics diverge | Public-API parity tests on the pinned PyPI version |
| Draft storage grows without bound | Quotas, expiry, cleanup metrics, and explicit resume policy |
| Verification performs unsafe I/O/imports | Inert parse first, strict resource policy, and adversarial fixtures |

## Non-goals

- Executing pipeline code in the frontend.
- Arbitrary plugin installation through the authoring API.
- Full graph canvas; delivered in 0.5.
- Live CRDT collaboration.
