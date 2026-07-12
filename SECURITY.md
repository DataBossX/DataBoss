# DataBossX Security

## Immediate incident: rotate exposed credentials

`backend/.env` was committed to Git history. Removing it from the current tree does not revoke or erase those values. Treat every credential previously stored there as compromised and rotate it now.

Do not paste replacement values into issues, chats, logs, source files, or screenshots. Store them in a local ignored `.env` file or an approved secrets manager. History rewriting is optional defense in depth and does not replace key rotation.

Track rotation names-and-status only in
[docs/credential-rotation-evidence.md](docs/credential-rotation-evidence.md).
Provider rotation stays `BLOCKED_EXTERNAL` until an authorized human verifies it
at each provider; code changes never constitute rotation.

## Client-data incident containment

Client/project metadata was also present in the public repository. Public-record origin does not automatically make compiled client work product safe to publish.

Containment order:

1. Stop continuing exposure in the current tree.
2. Rotate any credentials or share links exposed with the metadata.
3. Move real project controls to an approved private repository/storage root.
4. Preserve an incident record and determine whether forks, caches, or Git history require coordinated cleanup.
5. Add policy tests so client paths, exact legal descriptions, cloud IDs, hashes, reports, and release artifacts cannot be reintroduced.

## Required controls

- Commit only `.env.example` templates with fake values.
- Treat every `REACT_APP_*` value as public.
- Give connectors read-only, folder/repository-scoped credentials by default.
- Never place secrets or client evidence in prompts, model memory, audit events, public artifacts, or screenshots.
- Require exact, expiring human approval for external writes.
- Bind workers to the minimum files, tools, and network destinations needed.
- Preserve immutable audit records for credential use and policy decisions.
- Keep public code/synthetic fixtures separate from private client operations.
- Run secret and publication-policy checks before every merge.

## Human-approval verifier

Promotions to `APPROVED` and `DELIVERED` require an authenticated, single-use,
expiring approval record bound to the exact asset content hash and exact target
state, signed with an Ed25519 key. Configure the trusted **public** verifier
keys via `DATABOSSX_APPROVAL_PUBKEYS` (see
[config/approval_authorities.example.json](config/approval_authorities.example.json)).
The private signing key never lives in the repository or the control database.
If no trusted verifier is configured, those promotions fail closed.

## Reporting

Report security problems privately to the repository owner. Never open a public issue containing a key, token, client document, title evidence, cloud identifier, or private path.
