# DataBossX Security

## Immediate incident: rotate exposed credentials

`backend/.env` was committed to Git history. Removing it from the current tree does not revoke or erase those values. Treat every credential previously stored there as compromised and rotate it now.

Do not paste replacement values into issues, chats, logs, source files, or screenshots. Store them in a local ignored `.env` file or an approved secrets manager. History rewriting is optional defense in depth and does not replace key rotation.

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

## Reporting

Report security problems privately to the repository owner. Never open a public issue containing a key, token, client document, title evidence, cloud identifier, or private path.
