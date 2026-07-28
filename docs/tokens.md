# Encrypted API tokens

User-stored secrets for pipeline sources/sinks — **not** the same as JWT access tokens.

## Prerequisites

Set a persistent Fernet key before storing tokens:

```bash
uv run python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

```dotenv
ETLANTIC_TOKEN_ENCRYPTION_KEY=<fernet-key>
```

Back the key up outside the database. Losing it makes ciphertext unrecoverable.

## Store a token

`POST /tokens`

```json
{
  "name": "source-api",
  "value": "sk-...",
  "allow_read": true,
  "allow_write": false
}
```

Rules:

- At least one of `allow_read` / `allow_write` is required.
- Value length 8–8192 characters.
- API responses never include `value` or `encrypted_value` — only metadata such as `last_four`, permissions, `is_active`, `last_used_at`.

## Manage tokens

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/tokens` | List metadata |
| `GET` / `PATCH` / `DELETE` | `/tokens/{id}` | Rotate value, rename, permissions, disable |

Rotation keeps the same token id (existing grants continue to reference it). Deletion cascades related grants.

## Pipeline grants

Bind a stored token to one asset in a pipeline document:

```http
POST /pipelines/{pipeline_id}/token-grants
```

```json
{
  "token_id": "the-token-uuid",
  "binding": "customer_source",
  "provider": "your-storage-provider",
  "location": "https://api.example.com/customers",
  "operation": "read"
}
```

- `binding` must match an asset on a pipeline node.
- `operation` must be allowed by the token (`allow_read` / `allow_write`).
- Inactive tokens cannot be granted.
- Duplicate binding on a pipeline → `409`.

Grant responses expose a computed `secret_ref` shaped like:

```json
{
  "provider": "user-tokens",
  "name": "the-token-uuid",
  "key": "value",
  "version": "current",
  "purpose": "read"
}
```

Only that reference enters the plan. At run time the owner-scoped provider decrypts just-in-time into an ETLantic `SecretValue` that refuses serialization into documents, reports, API responses, or logs.

List / revoke:

- `GET /pipelines/{id}/token-grants`
- `DELETE /pipelines/{id}/token-grants/{grant_id}`
