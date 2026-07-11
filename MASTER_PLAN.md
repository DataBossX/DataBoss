# DataBossX Master Plan — Top 100 Moves, Mapped to Reality

_Last updated: 2026-07-11. This document replaces guesswork with an audit of
what actually exists. Statuses:_

- ✅ **exists** — already working in this repo before this session
- 🔨 **built** — implemented this session (branch `claude/databossx-top-100-moves-dkbt75`)
- 🏠 **local/human** — requires the operator's machine, money, credentials, or judgment; the repo-side machinery is ready
- 📋 **next** — designed and unblocked; build in the 30-day window
- ⏸ **deferred** — intentionally not now (matches the "do not prioritize" list)

## The one-paragraph strategy

The repo already contains real engines: `horizon/` (exact-fraction interest
math, OGL↔runsheet chaining, validation, zero-destruction versioning, 66
tests), `grocery_report_pipeline.py` (stages A–I ingestion→report, 10 tests),
`automation/roger_mills_title_report_builder.py`, and `doto_image_commander/`
(OCR/county images). What was missing was the **control layer** that makes
every agent use the same evidence, rules, and approval gates. That layer now
exists as `core/land_title_os/` — manifests, asset inventory, evidence ledger
with authority ranking, hash-chained run receipts, staged promotion with
human gates, open-item management, and a deterministic QA engine.

## Section 32 Beckham status (Move #1) — mostly DONE, human-gated remainder

Discovered via Google Drive inventory (folder
`32-11N-25W Diversified Cursory - Beckham County - 2026-07`):

- A **FINAL_VERIFIED_2026-07-11** report exists and passed QA as a *qualified
  cursory with explicitly OPEN ownership conclusions* (see the Drive
  `FINAL_READINESS_STATEMENT_2026-07-11`). Client is **Diversified**.
- Six competing "final" workbooks sit in the Drive folder (BEST_AVAILABLE,
  MERGED_BEST, PERFECT, PERFECTED, 2026-07-10, NHE base). The manifest at
  `projects/OK-BECKHAM-32-11N-25W/manifest.json` names the authoritative one
  (SHA-256 recorded) and lists the rest as superseded — archive them.
- Remaining blockers are **human decisions**, now encoded in the manifest's
  `open_issues`: authorize the ~$8.80 / 22-instrument Tier 1 OKCR pull,
  resolve I-2011-001515 vs 1565, bridge 1988–2020, trace the ORRI/lien
  families, obtain Order 156126 + JOA 1580, and re-run searches at the
  2026-07-16 checkpoint.

## Move-by-move status

### Tier 1 — Critical

| # | Move | Status | Where / what's left |
|---|---|---|---|
| 1 | Finish & verify Section 32 | 🏠 | FINAL_VERIFIED report QA-passed; manifest `projects/OK-BECKHAM-32-11N-25W/` carries the open human-gated items above |
| 2 | One canonical repository | 🔨 | This repo (`DataBossX/DataBoss`) is canonical — see Governance below; CI now runs on every branch |
| 3 | Master asset inventory | 🔨 | `core/land_title_os/assets.py` (SQLite; stable IDs, SHA-256, duplicate groups, security class); run `scan_directory()` on local drives 🏠 |
| 4 | Evidence ledger | 🔨 | `core/land_title_os/evidence.py` — conclusions without evidence are rejected |
| 5 | Project control dashboard | 📋 | Data layer first (manifests + issues + receipts are queryable now); UI later |
| 6 | Canonical-file promotion | 🔨 | `core/land_title_os/promotion.py` — SOURCE→…→DELIVERED, checks gate every step, APPROVED/DELIVERED require a named human |
| 7 | Title-report QA engine | 🔨 | `core/land_title_os/qa_engine.py` (exact fractions) + `horizon/validation.py` (workbook gates) already ✅ |
| 8 | Secure & rotate credentials | 🏠🔨 | Committed keys **removed** from tracking, `.gitignore` hardened, gitleaks CI added — **you must rotate the keys per `SECURITY.md` NOW** |
| 9 | Verified backup & recovery | 📋🏠 | `horizon/foundation.py` snapshots + `versioning.py` exist ✅; restore-test automation is next; backup drives are local |
| 10 | Project manifest per section | 🔨 | `core/land_title_os/manifest.py` + real Beckham 32 manifest with Drive file IDs |

### Tier 2 — Production engine

| # | Move | Status | Notes |
|---|---|---|---|
| 11 | Universal intake engine | ✅ | `grocery_report_pipeline.py` stage A/B (inventory, hash, dedup, read-only originals); wire it to `assets.py` 📋 |
| 12 | Instrument classification | ✅ | pipeline stage D (deterministic keywords + confidence); LLM hook opt-in |
| 13 | Legal-description extraction | ✅/📋 | stage E extracts; normalization (aliquot parts, lots) 📋 |
| 14 | Chain-of-title graph | 📋 | `horizon/chaining.py` has the edges (instrument-keyed); graph model next |
| 15 | Ownership-math engine | ✅ | `horizon/interest.py` — Fraction/Decimal only, no floats |
| 16 | Runsheet generator | 📋 | reconciliation tables exist (stage F); dedicated generator next |
| 17 | Oklahoma report generation | ✅ | `horizon/pipeline.py --build-from` + `roger_mills_title_report_builder.py` |
| 18 | Wyoming abstract-index generation | 📋 | no Wyoming code yet; use verified Section 5/8 work as regression fixtures |
| 19 | Template-locking engine | 🔨/✅ | `qa_engine.check_template_sheets` + horizon validation gates |
| 20 | Independent final-review agents | 📋 | run as three roles (evidence/math/deliverable) over the QA engine outputs |

### Tier 3 — Reliability

21 🔨 (`evidence.AUTHORITY`) · 22 🔨 (per-axis confidence, enforced) ·
23 ✅/📋 (`conflicts_and_gaps` stage F; workbook-diff next) · 24 🔨
(`issues.py`) · 25 🔨 (`evidence.provenance()`) · 26 🔨 (human gates in
`promotion.py` + issue approval) · 27 ✅ (94+ tests; keep adding approved
projects as fixtures) · 28 📋 (coverage analysis) · 29 🔨/✅ (SHA-256 groups
in `assets.py`; perceptual hashing 📋) · 30 🔨 (`receipts.py`, hash-chained,
tamper-evident — tested).

### Tier 4 — Recover what exists

31–33 🏠 (local drives / Dropbox need the operator's machine; **Drive
inventory started** — Section 32 folder mapped into the manifest) ·
34 📋 (GitHub repo classification — this repo is canonical; list the rest via
the asset inventory) · 35 🏠 · 36 🔨 partially (duplicate groups) · 37 📋
(consolidate `lease---title-ai-suite-2-`, `penterra_engine`,
`ocr_to_spreadsheet` into `core/land_title_os/`) · 38 📋 · 39 ✅ partially
(`prompts/` exists; add metadata) · 40 📋 (generate status from receipts).

### Tier 5 — Orchestration

41 🔨 (a work order = manifest + required_checks + stop conditions; see
`RUNBOOK.md`) · 42–44 📋 · 45–46 ✅ partially (grocery pipeline isolates
per-file failures; horizon loop is bounded at 5 iterations) · 47 🔨 (receipt
`cost` field; aggregation 📋) · 48–50 📋 (supervisor must not bypass
`promotion.py` human gates — enforced in code).

### Tier 6 — Research automation

51–60 📋/🏠 — search-package generation can start from the manifest's open
issues (each Beckham open issue is already a research work order). County
portal access, OKCR pulls, and BLM lookups need credentials/payment 🏠.

### Tier 7 — Spreadsheet automation

61 ✅ (`horizon/repair.py` lxml repair preserves plats byte-for-byte;
zero-destruction versioning) · 62 📋 · 63 ✅ partially (horizon validation +
QA stale-string/formula scans) · 64 ✅ (`interest.py`) + 🔨
(`qa_engine.parse_interest` handles `UND 20/260`) · 65 🔨
(`qa_engine.check_total`) · 66 🔨 (external audit ledger = evidence ledger;
keeps client workbooks clean) · 67–70 📋.

### Tier 8 — Operating interface

71–80 📋/⏸ — build on the data layer (manifests, issues, receipts). The
"What needs me?" queue (#74) is already computable:
`IssueRegister.open_items()` + unverified conclusions + promotions awaiting
`human_approved=True`. A dashboard is worth building only after the data
layer is populated with real projects.

### Tier 9 — Business leverage

81–90 📋 — receipts carry cost/time fields (#81); client profiles = per-client
template + required_checks in manifests (#82); certification letters (#83)
must render only from `approved_facts` and require human signoff (enforced by
the DELIVERED gate).

### Tier 10 — Advanced evolution

91–100 ⏸/📋 — deliberately last, per the plan's own guidance. The promotion
human-gates and receipt chain are the prerequisites for any autonomous
improvement loop (#100), and they now exist.

## Repository governance (Move #2)

- **Canonical repo:** `DataBossX/DataBoss`. Everything else is `component
  source`, `experiment`, `duplicate`, `legacy`, or `archive` until promoted.
- **Branches:** `main` is production; feature branches (`claude/*`, short-lived)
  merge via PR. CI (tests + gitleaks secret scan) runs on **every push**.
- **Enable on GitHub (owner action, 5 minutes):** branch protection on `main`
  (require the `build` and `secret-scan` checks), secret scanning + push
  protection (Settings → Code security), and release tags on delivery.
- **No secrets in git** — see `SECURITY.md`. **No client documents in git** —
  documents live in Drive/local stores and are referenced by manifests/asset
  IDs; `output/` is gitignored.
- **Component classification:** `core/land_title_os` + `horizon` +
  `grocery_report_pipeline.py` = production; `automation/roger_mills_*` =
  verified project-specific; `doto_image_commander`, `mineral_deal_room`,
  `backend`/`frontend` = component source (not yet under the promotion
  system); `databossx.db` (committed sample DB) = legacy, candidate for
  removal once nothing references it.

## Execution order

### Next 72 hours (highest value, in order)

1. 🏠 **Rotate the exposed API keys** (`SECURITY.md`) — 30 minutes, blocks nothing else.
2. 🏠 **Authorize the $8.80 Tier 1 OKCR pull** for Section 32 and work the
   manifest's `open_issues` top-down; archive the five superseded "final"
   workbooks in Drive (keep `FINAL_VERIFIED_2026-07-11` + NHE base).
3. 🏠 Run `grocery_report_pipeline.py` / `horizon` against the real local
   folders (cloud can't see `D:\`), then `AssetInventory.scan_directory()`
   over `D:\Desktop\DataBossX`, `D:\Desktop\Horizon`, `D:\Desktop\Penterra`.
4. 📋 Wire the grocery pipeline's stage A/B output into `assets.py` so every
   inventory run lands in the master database.
5. 📋 Backfill the Beckham evidence register into `evidence.py` format so the
   FINAL_VERIFIED report's 51 runsheet rows each carry ledger entries.

### Next 30 days

Chain graph (#14) → runsheet generator (#16) → workbook diff (#23/#67) →
coverage analysis (#28) → Wyoming generator (#18) → review-agent roles
(#20/#49) → dashboard (#5/#74) — each lands as a `core/land_title_os` module
with tests, gated by the same CI.

### Explicitly not now (per the plan)

Fancy dashboards before data, another replacement repo, giant prompts,
unrestricted autonomous agents, blockchain, mobile apps, rebuilding what
works, and letting every AI mint its own "final" file — the promotion system
exists precisely to end that last one.
