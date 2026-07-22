# Legacy Backend Security Quarantine — 2026-07-22

**Component:** `backend/server.py` and its legacy development launch path  
**Classification:** `LEGACY_DEMO_QUARANTINE`  
**Ruling:** **DO NOT DEPLOY, EXPOSE, OR TREAT AS THE CANONICAL API**

This record is governance only. It changes no runtime code, deployment, port, credential, database, or process. A private Windows truth gate and deployment inventory must identify whether this component is running anywhere before a remediation slice is selected.

## Direct current-tree evidence

The current public baseline contains all of the following:

1. `backend/server.py` configures credentialed CORS with `allow_origins=["*"]`, `allow_credentials=True`, and all methods/headers allowed.
2. The API has no visible authentication or authorization dependency on document upload, document listing/detail, logs, or analytics endpoints.
3. `/api/documents/upload` reads the complete upload into memory without a declared byte limit, page limit, MIME allowlist, extension allowlist, timeout, or decompression bound.
4. Document text is interpolated directly into provider prompts without a prompt-injection trust boundary.
5. OCR text and LLM analysis are stored and returned through unauthenticated endpoints.
6. Error responses can include raw exception text.
7. The module's direct runner binds Uvicorn to `0.0.0.0:8001`.
8. `.devcontainer/supervisord_without_vscode.conf` autostarts the backend on `0.0.0.0:8001` with `--reload`, autostarts the frontend on `0.0.0.0:3000`, and starts MongoDB with `--bind_ip_all`.
9. `entrypoint.sh` also starts the backend on `0.0.0.0:8001`, while `nginx.conf` publishes `/api` through a server listening on port `8080`.
10. `scripts/update-and-start.sh` stops and restarts these legacy backend/frontend services, proving the path is operationally launchable rather than dead documentation.

## Security impact

If this stack is exposed outside a strictly isolated trusted environment, an unauthenticated caller could potentially:

- upload arbitrary or oversized content;
- cause provider calls and spend;
- enumerate document metadata;
- retrieve OCR text and model outputs;
- retrieve system logs and analytics;
- exploit permissive network and browser-origin assumptions;
- inject hostile document instructions into model prompts;
- consume memory, storage, worker capacity, or provider quota.

Passing current secret scans does not mitigate these runtime controls.

## Current disposition

- Treat `backend/server.py`, the matching frontend, devcontainer launcher, Nginx path, and update script as a single **legacy demo deployment unit**.
- Do not deploy it, forward its ports publicly, place it behind a public domain, or use it for client evidence.
- Do not patch it piecemeal on `main` while local deployment and process ownership remain unproved.
- Do not allow this legacy API to become a second command center or persistence source.
- Prefer the canonical release-train architecture and bounded capabilities from PR #52, with PR #54 considered only as an additive port after contract reconciliation.

## Minimum gate for any future rehabilitation

A bounded replacement or rehabilitation slice must prove, with focused tests:

1. authenticated sessions or scoped service credentials;
2. project/document authorization on every read and write;
3. loopback/private binding by default and explicit deployment-mode configuration;
4. exact CORS allowlists, never wildcard credentialed CORS;
5. upload byte, MIME, extension, page, decompression, recursion, redirect, and timeout limits;
6. streamed or bounded file handling rather than unbounded `await file.read()`;
7. rate limits, provider budgets, idempotency, cancellation, and duplicate suppression;
8. prompt-injection isolation and evidence-vs-command separation;
9. safe error responses and redacted structured logs;
10. private runtime storage, retention, deletion, encryption/access, and backup policy;
11. replay, restart, crash-recovery, and audit-chain tests;
12. a synthetic public test and a private Windows canary with exact receipts.

## Immediate next proof

The private Windows truth gate must determine:

- whether any process, service, container, task, launcher, proxy, or deployment currently runs this backend;
- which repository and commit produced that runtime;
- network binding and exposure;
- active database and log paths;
- whether real client data or live credentials ever entered it;
- the smallest safe containment or replacement action.

Until that proof exists, this component remains **QUARANTINED / HOLD / NO DEPLOY**.
