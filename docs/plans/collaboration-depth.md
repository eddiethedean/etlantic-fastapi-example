# Collaboration Depth Plan

> **Roadmap:** 0.6  
> **Status:** Planned after visual-builder foundations  
> **Depends on:** Sessions, audit events, revisions, and conflict-safe drafts  
> **Goal:** Turn groups into understandable, auditable team workspaces with
> useful roles and safe collaboration—without moving authorization into the UI.

## Outcomes

- Invitations arrive through a normal delivery flow instead of copied tokens.
- Owners can grant view, edit, run, schedule, and manage permissions explicitly.
- Shared-pipeline activity and revisions have clear authorship.
- Concurrent work is detected early and resolved without data loss.
- Removing access takes effect promptly across drafts, sessions, schedules, and
  future operations.

## Authorization model

Adopt a small permission model before adding more roles:

| Permission | Viewer | Editor | Operator | Group admin | Owner |
| --- | ---: | ---: | ---: | ---: | ---: |
| View pipeline/history | ✓ | ✓ | ✓ | ✓ | ✓ |
| Edit/commit pipeline |  | ✓ |  | ✓ | ✓ |
| Run pipeline | optional | ✓ | ✓ | ✓ | ✓ |
| Create own schedule |  | optional | ✓ | ✓ | ✓ |
| Share owned pipeline |  |  |  | ✓ | ✓ |
| Invite/remove members |  |  |  | ✓ | ✓ |
| Change roles/group |  |  |  | limited | ✓ |
| Delete group |  |  |  |  | ✓ |

Exact grants are represented as permissions in API responses. The frontend
must render `can_*` capabilities rather than infer them from role names.

Decide whether roles are group-wide or pipeline-specific before migration. For
0.6, prefer group-wide base roles plus per-pipeline sharing; avoid arbitrary
custom roles until real use cases justify them.

## Invitation delivery

- Introduce an email delivery interface with a development console/file sink
  and one production provider adapter.
- Store only hashed, single-use acceptance tokens.
- Acceptance links expire, are email-bound, and reveal no group data before
  authentication.
- Resend rotates the old token and is rate-limited.
- Owners/admins see invitation status, expiry, inviter, resend, and revoke.
- Stop returning raw acceptance tokens from general production API responses;
  allow them only in an explicit development delivery mode.
- Templates include inviter, group, expiry, expected recipient, and a safe
  application link without sensitive query logging.

## Sharing and ownership

- A pipeline has one immutable owner unless a deliberate transfer operation is
  added.
- Sharing grants group access; it does not copy the pipeline.
- Owners see all groups a pipeline is shared with and can bulk share/unshare.
- Group workspaces distinguish group-shared pipelines from personal items.
- Unsharing/revoking membership blocks new operations immediately while
  preserving immutable revisions, audit events, and historical run snapshots.
- Define what happens to schedules created by a member who loses access:
  disable them by default and audit the reason.
- Token grants remain owned/revocable credentials and do not become visible to
  other group members beyond safe readiness metadata.

## Collaboration experience

- Show current revision author/time and draft ownership.
- Provide soft presence (`editing`, `viewing`) with a short TTL; presence is a
  hint, never an authorization or locking mechanism.
- Saving requires the expected revision/fingerprint.
- Conflict UI compares node, edge, configuration, and metadata changes and
  offers latest, copy, or manual resolution.
- Change summaries are optional but encouraged for group commits.
- Comments/review requests are a later subphase only after revisions and
  notification preferences are stable.

## API and data changes

Add or update:

- role/permission fields on group membership;
- invitation resend/delivery status;
- bulk pipeline share/unshare with per-item result;
- membership role update and ownership transfer safeguards;
- current-user `can_*` capabilities on groups and pipelines;
- ephemeral presence endpoint/channel if enabled;
- activity/revision feeds backed by audit data.

Migrations backfill existing owners as Owner and members as Editor to preserve
0.1 behavior unless product policy chooses a more restrictive default.

## Security and abuse controls

- Reauthorize every request; never trust cached membership.
- Rate-limit invites by actor, group, recipient, and source network.
- Prevent last-owner removal and require verified transfer before owner exit.
- Require recent authentication for ownership transfer and destructive group
  actions.
- Normalize invitation emails and avoid account-existence disclosure.
- Audit role, owner, invite, share, schedule-disable, and credential-grant
  changes.
- Delivery webhooks use signed requests and idempotent processing.
- Apply retention/privacy policy to presence and email-delivery metadata.

## Test matrix

- full role/permission matrix at every pipeline/group/run/schedule endpoint;
- migration from owner/member records;
- invite send/resend/revoke/expire/accept and provider retries;
- wrong-email and replayed-token acceptance;
- last-owner and ownership-transfer races;
- access removal during open draft, run submission, and schedule fire;
- bulk share partial failure/idempotent retry;
- concurrent editor conflicts and revision authorship;
- presence expiry and cross-group isolation;
- token metadata/plaintext isolation between members;
- audit completeness for all collaboration mutations.

## Rollout

1. Add permissions and backfill roles without changing existing effective
   access.
2. Update API/UI to consume capabilities.
3. Enable invitation delivery in development/staging and verify redaction.
4. Switch production invitation responses from raw token to delivery receipt.
5. Add presence only after conflict/revision workflows are proven.

## Release gates

- Endpoint-level permission tests cover every role and sensitive operation.
- Existing groups retain intended access after migration.
- Default invitation flow never exposes acceptance tokens in UI/API logs.
- Removing a member prevents new edits/runs and disables affected schedules
  within the documented bound.
- Concurrent edits cannot silently overwrite and remain attributable.
- Last-owner and transfer invariants hold under race tests.
- Group UI clearly explains ownership, role, and effective capabilities.

## Risks

| Risk | Mitigation / trigger |
| --- | --- |
| Role matrix becomes difficult to explain or audit | Keep fixed roles and expose effective `can_*` permissions |
| Email delivery leaks acceptance links | Redacted provider adapter, signed webhooks, development-only raw-token mode |
| Revocation leaves active schedules/drafts usable | Central authorization plus revocation race tests |
| Presence is mistaken for a lock | Label it advisory and retain revision/fingerprint enforcement |

## Non-goals

- Arbitrary organization hierarchy or custom RBAC policy language.
- Billing/seat management.
- Full CRDT live co-editing.
- Making group members co-owners of stored credentials.
