# Pipelines

## Sealed documents

Pipeline bodies must be sealed `etlantic.pipeline/1` documents with a valid fingerprint. That prevents saving a payload that changed after ETLantic validated it.

### Verify draft (recommended for editors)

```http
POST /pipelines/verify-draft
Authorization: Bearer <token>
Content-Type: application/json

{"document": { ... }}
```

Response (`PipelineDraftResult`):

- `ok` — whether sealing/validation succeeded
- `document` — canonical sealed document when successful
- `fingerprint`
- `diagnostics` — structured messages when `ok` is false (or warnings)

Use the sealed `document` in `POST /pipelines` or `PATCH /pipelines/{id}`.

For an existing pipeline id:

```http
POST /pipelines/{pipeline_id}/verify-draft
```

### Create / update

- `POST /pipelines` — name, optional description, document
- `PATCH /pipelines/{id}` — optional name, description, document, `expected_version`
- Optimistic concurrency: mismatched `expected_version` → `409 Pipeline version conflict`
- Duplicate names per owner → `409`

### Access metadata

List/get responses include:

| Field | Meaning |
| --- | --- |
| `access_source` | `owned` or `group` |
| `can_delete` | `true` only for the owner |
| `shared_group_ids` | Groups linking this pipeline that the current user belongs to |

Delete is owner-only. Group members may retrieve, edit, validate, plan, run, and schedule shared pipelines.

## Validate & plan

| Method | Path |
| --- | --- |
| `POST` | `/pipelines/{id}/validate` |
| `POST` | `/pipelines/{id}/plan` |

Returns ETLantic diagnostics / plan JSON. Plan output must not be assumed to contain secrets.

## Structured edits

`POST /pipelines/{id}/edits` applies ETLantic immutable edit commands with optional `expected_token` (fingerprint). Prefer verify-draft + PATCH for free-form JSON editing in the UI.

## Runs

```http
POST /pipelines/{id}/runs
→ 202 RunRead
```

Poll `GET /runs/{id}` until status leaves `queued` / `running`. Terminal statuses include `succeeded`, `partial`, and `failed`.

Each run stores a snapshot of pipeline document, version, and fingerprint.

`GET /runs` lists runs initiated by the current user (optional `pipeline_id` filter). Group members do **not** automatically see each other's runs.

## Schedules

Create via `POST /pipelines/{id}/schedules`. Manage via `/schedules`.

Trigger types: `cron`, `interval`, `date` (APScheduler args).

```json
{"name":"nightly","trigger_type":"cron","trigger_args":{"hour":2,"minute":0}}
```

```json
{"name":"frequent","trigger_type":"interval","trigger_args":{"minutes":15}}
```

```json
{"name":"once","trigger_type":"date","trigger_args":{"run_date":"2030-01-01T00:00:00Z"}}
```

Schedules are owned by their **creator**, even when the pipeline is group-shared. Enabled schedules are restored into APScheduler when the API process starts.
