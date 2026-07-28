# Groups and shared pipelines

## Create a group

`POST /groups` creates the group and an **owner** membership for the caller.

`GroupRead` includes `current_user_role`: `owner` or `member`.

## Membership

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/groups/{id}/members` | Members with nested user profiles |
| `DELETE` | `/groups/{id}/members/{user_id}` | Owner removes a member, or a member leaves |

The group owner cannot leave; they must delete the group instead.

## Invitations

Any current member may invite an email:

```http
POST /groups/{group_id}/invitations
{"email": "grace@example.com"}
```

Invitation acceptance tokens are:

- random and single-use
- stored only as SHA-256 hashes
- expired after seven days (`410` when stale)
- returned as `accept_token` **only** on create

This application does **not** send email. Deliver the token or acceptance link out-of-band.

Accept (must be signed in as the invited email):

```http
POST /group-invitations/accept
{"token": "the-one-time-acceptance-token"}
```

Wrong email → `403`. Unknown/used token → `404`. Expired → `410`.

List / revoke pending invites via `GET` / `DELETE` on `/groups/{id}/invitations`.

## Share pipelines

A user may add only a pipeline they **own** to a group they belong to:

```http
PUT /groups/{group_id}/pipelines/{pipeline_id}
```

Unshare (owner of the pipeline):

```http
DELETE /groups/{group_id}/pipelines/{pipeline_id}
```

Group members then see the pipeline in `GET /pipelines` with `access_source: "group"`. They may retrieve, edit, validate, plan, run, and schedule it. Ownership is unchanged: only the pipeline owner may delete it or remove it from a group.

`GET /groups/{id}/pipelines` lists pipelines shared with that group.

## Authorization summary

| Action | Who |
| --- | --- |
| Invite | Any member |
| Remove another member / delete group / rename | Owner |
| Leave group | Member (not owner) |
| Share / unshare pipeline | Pipeline owner who is a group member |
| Delete pipeline | Pipeline owner only |
