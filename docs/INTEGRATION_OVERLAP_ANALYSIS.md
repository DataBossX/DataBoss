# Integration overlap & reconciliation analysis (#52 vs #51 / #54)

> Bounded groundwork for the canonical release train (issue **#56**). This
> document **merges nothing, changes no schema, and contains no client data**.
> It is the schema / API / economics diff the ruling requires *before* any
> selective port. Precise line-level diffs of #51 and #54 still require checking
> out those branches; where that is needed it is called out explicitly, and the
> claims below are grounded in the canonical `main` schema (read in full) plus
> the #51/#54 PR descriptions.

## 0. Baseline and disposition (from #56)

- **Canonical baseline:** `main` at #50 — `src/databossx` foundation: immutable
  SHA-256 vault, per-project SQLite (`migrations/001_initial_schema.sql`,
  20 tables incl. `assets`/`asset_versions`, `runs`/`tasks`/`task_attempts`,
  `derived_artifacts`/`artifact_lineage`, append-only `audit_events` + FTS,
  `approvals`, `workbook_templates`/`writable_ranges`).
- **#52 (this PR):** primary functional candidate — *initial* candidate, **not**
  automatic merge authority.
- **#54 Landman Helper:** additive candidate — port onto the integration branch
  after #52-level tests pass; do not merge as a second platform.
- **#51 Trusted local evidence kernel:** donor-only — competing migration/schema
  line; adopt patterns (exact economics, provenance invalidation, review gating,
  security) selectively, with a schema/API diff first; no wholesale merge.
- **Integration target:** `integration/canonical-release-train-20260719`
  (not this branch; not touched here).

## 1. #52 compliance against the #56 rulings

| #56 requirement | #52 status |
| --- | --- |
| One persistence architecture (no dual source of truth, no competing migration) | ✅ Uses the #50 schema **as-is**. The audit bridge calls the existing `create_project` / `db.audit` and `migrations/001` via `CREATE TABLE IF NOT EXISTS`; it adds **no** table, migration, or alternative store. |
| One control kernel (no parallel command centers / duplicate job DBs) | ✅ `command_center.run_project` is the single orchestration entry #56 designates primary. Run/deliverable events are recorded through the foundation `audit_events`, not a new job DB. |
| No raw-document-as-command execution | ✅ Documents are read as data only (openpyxl/text); injection-hardened (Excel formula guard, PDF/HTML escaping). |
| Publication boundary (synthetic only) | ✅ Only the labeled synthetic golden project; generated `**/databossx_output/`, `runtime/`, `.dbxvenv/` are git-ignored. |
| Human release gate; no auto client release | ✅ Every deliverable states technical verification ≠ release; no merge/auto-release performed. |
| Exact-rational economics (no floats) | ✅ `ownership.py` is exact `Fraction` throughout; undetermined ⇒ blank + review. |

**Conclusion:** #52 does not create any of the forbidden conflicts. It is a clean
consumer of the canonical foundation.

## 2. Overlap map by dimension

| Dimension | #52 (this PR) | #51 (donor) | #54 (additive) | Reconciliation |
| --- | --- | --- | --- | --- |
| **Persistence / schema** | Uses #50 schema unchanged | Introduces a **competing** migration/schema line | Uses #50 schema (`runs`/`tasks`/`audit_events`, `derived_artifacts`) | Keep **#50 schema** as the single baseline. #51 schema is **not** adopted wholesale; port its *logic* onto #50 tables. Any #51 table needs an explicit migration + rollback + compat report (#56 step 2). |
| **Control / orchestration kernel** | `command_center.run_project` (CLI) | Authenticated loopback Command Center + CLI | `title_intelligence.analyze_project` + `/api/landman/*` | **One** kernel: #52's. #54's `analyze_project` becomes a **module invoked by** #52 (or #52 absorbs its ingestion), exposed through one API. Do not ship two command centers. |
| **Exact economics** | `ownership.py`: mineral/WI/NRI/ORRI, Σ=8/8 checks, over-conveyance | Lease units/events, assignment burden carry, revenue conservation, `EXPLICIT_EVENT_ALLOCATION`, evidence-bound | (consumes horizon interest math) | Keep #52 `ownership.py` as the base; **port #51's additional validation rules** (over-assignment, unbalanced WI/leasehold, burden conservation, ambiguous-burden blocking) as tested additions — **not** its schema. |
| **Document ingestion / OCR** | grocery stages (txt/csv/xlsx/docx/pdf; OCR optional, degrades) | deterministic extraction bound to evidence spans | `extract_conveyance`, real PDF/DOCX/OCR, legal-desc normalization | Port #54's **format ingestion + legal parsing** into the #52 pipeline as one extraction module; keep #52's "no-text ⇒ missing-evidence" flagging. |
| **API / UI** | none (CLI + launchers) | authenticated loopback | `backend/landman_api.py` + `frontend/src/App.js` | No file-level conflict today. Mount #54's API/UI **over the unified #52 kernel** once orchestration is single-sourced; resolve API/DB/UI/workflow contracts first (#56 step 4). |
| **Audit / provenance** | audit log + manifest + `--audit` → `audit_events` (+ deliverable sha256) | hash-chained audit, provenance invalidation, credentialed hash approval | run/task/attempt + `audit_events` + lineage | Converge on **one** recording path through `audit_events`. Port #51's **hash-chaining + provenance invalidation** and #54's **run/task/attempt lineage** onto that single path. |
| **Templates** | `--template` → media-preserving `horizon.report_io` | approved-template fidelity (private) | canonical Roger-Mills xlsx | Align on the `workbook_templates`/`writable_ranges` tables (already in #50) for approved-template registration + writable-range contracts. |
| **Security** | formula-injection guard, XML/HTML escaping, read-only sources, backups | credentialed approval, provenance invalidation, path validation | binary-safe upload preview | Union of all three as gates (§4); none conflict. |

## 3. Recommended bounded port slices (ordered, each reversible + independently testable)

Each slice starts from `integration/canonical-release-train-20260719`, ports the
**smallest coherent unit**, and must be green in public CI (synthetic fixtures)
before the next. This ordering keeps one schema and one kernel throughout.

1. **S1 — #52 core kernel** (this PR's `command_center` + `ownership` + reports +
   `abstract`/`curative` + `selfcheck`/`backup`). Pure consumer of #50; lowest
   risk. Gate: full pytest + flake8 + formula-injection/escaping tests.
2. **S2 — #54 document ingestion** (`extract_conveyance`, PDF/DOCX/OCR, legal
   normalization) as an extraction module the S1 kernel calls. Gate: #54's
   document-format tests, OCR-ambiguous ⇒ flagged (not guessed).
3. **S3 — unified run/task/audit recording** (merge #52 `audit_bridge` +
   #54 run/task/attempt + lineage into one path). Gate: audit-immutability +
   lineage tests; one recording path only.
4. **S4 — #51 economics validation rules** (over-assignment, burden conservation,
   `EXPLICIT_EVENT_ALLOCATION`, ambiguous-burden blocking) added to `ownership.py`.
   Gate: exact-fraction identity tests; **no** #51 schema pulled in.
5. **S5 — #51 provenance/approval patterns** (hash-chained audit, provenance
   invalidation, credentialed hash approval) onto `audit_events`/`approvals`.
   Gate: replay/duplicate protection, approval-secrecy, provenance-invalidation.
6. **S6 — #54 API/UI** mounted over the unified kernel. Gate: API/DB/UI/workflow
   contract tests; publication-policy gate.

Any slice that would require a schema change ships an explicit migration **and**
a rollback + a schema/migration compatibility report (#56 step 2).

### Status update (implemented natively in #52, not ported from #51/#54)

To de-risk the S2/S4 slices, the *capabilities* (not the other branches' code)
were built directly in the canonical package from the described boundaries, so
they arrive already tested and on the #50 schema:

- **S2 (mostly done):** `legal.py` — PLSS Section/Township/Range normalization
  across abbreviated / spelled-out / compact-hyphenated forms → one canonical
  tract key (`dbx.py legal`), used for chain-of-title grouping.
  `title_extraction.py` — cursory conveyance extraction (grantor/grantee,
  instrument, interest, legal, acres) from raw document text, wired as the chain
  fallback so a folder of loose **deeds/assignments** (no OGL workbook) still
  yields a reconciled chain; text comes from the grocery extractor (PDF/DOCX/OCR
  when backends are installed). Remaining: richer real-world deed parsing and
  #54's HTTP/UI surface.
- **S4 (partial):** `ownership.py` — duplicate-owner detection and
  excessive-burden (royalty+ORRI ≥ 8/8) checks added to the exact-fraction
  engine. Remaining S4 work: #51's lease-unit/event model, assignment burden
  carry with `EXPLICIT_EVENT_ALLOCATION`, and provenance invalidation.

## 4. Gates every slice must pass (from #56 §5)

Secret scan · publication-policy gate · dependency review · path-traversal /
reparse tests · **formula-injection tests (already in #52)** · prompt-injection
boundaries · duplicate/replay protection · approval secrecy · atomic writes ·
timeout/cancel/restart recovery · immutable-audit verification · schema/backward
compatibility (or explicit migration + rollback).

## 5. Out of scope here (honest limits)

- **No merge, no port is performed by this document.** It is analysis only.
- **Branch-level diffs of #51/#54** (exact DDL, endpoint signatures) require
  checking those branches out on the integration branch; do that as the first
  action of S2/S4/S5.
- **The private Windows truth gate (#56 step 1)** — repository/worktree lineage,
  active writers, DB/WAL/refs preservation, local test receipts, recovery, and
  the end-to-end returned-receipt canary — runs on the operator's machine and is
  a precondition to any integration. It cannot be executed from this public
  cloud session.
- **No client evidence, private runtime state, workbooks, private hashes,
  credentials, or release receipts** are referenced or introduced.
