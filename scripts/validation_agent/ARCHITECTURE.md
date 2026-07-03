# DataBossX — Validation & Repair Agent
## System Architecture & Phased Build Plan (Blueprint)

**Architect deliverable — no implementation code. This is the contract Claude (Lead Python Developer) builds against.**

Target data: Section 31-12N-24W, Roger Mills County, OK. Prospect 25-004. 637.42 gross acres across ten tracts. Alexander 1-31 well.
Home: **all modules live under `D:/Desktop/DataBossX/scripts/validation_agent/`**. Nothing is written to the desktop or repo root. Runtime artifacts go to a git-ignored `output/` under the module.

---

### 0. Golden Law → enforced as system invariants

| # | Principle | Where enforced in the architecture |
|---|-----------|-----------------------------------|
| 1 | AI does the labor; the Examiner approves risk | Every `Fix` carries a `risk_class`; anything above `SAFE` is routed to the Escalation Matrix, never auto-applied. |
| 2 | Every action leaves proof | `audit_log` (append-only) + `evidence_cache` (source provenance). No validator or fixer may run without writing a row. |
| 3 | No fabricated legal facts | The `SafeFixRegistry` physically contains **no** strategy that writes a party name, date, or interest fraction not already present in a verified source. Such needs raise `EscalationRequired`. |
| 4 | Immutability / no overwrites | Every mutation produces `report_vN+1.xlsx`; prior versions are frozen. The DB is append-only (no UPDATE/DELETE on log tables). |
| 5 | Production-grade code | This doc specifies full typing, ABCs, dataclasses/pydantic models, and per-phase test gates. No stubs, no placeholders, no `TODO`s in delivered phases. |

---

## 1. System Overview & Full Module List

```
D:/Desktop/DataBossX/scripts/validation_agent/
├── __init__.py
├── app.py                       # C1  Streamlit dashboard (entrypoint: `streamlit run app.py`)
├── config.py                    #     Constants: TRACTS, GROSS_ACRES=637.42, EPSILON, ACRE_TOL,
│                                #     API_SPEND_CAP_USD=100.00, paths, LibreOffice path
├── models.py                    #     Typed core models (pydantic v2): see §3.0
├── orchestrator.py              # C8  PerfectionLoop state machine
├── memory/
│   ├── db.py                    # C2  SQLite engine, schema, migrations, connection factory
│   ├── audit_log.py             # C2  Append-only AuditLog writer/reader
│   └── spend_ledger.py          # C5  Append-only API spend ledger + $100 hard cap guard
├── ingestion/
│   ├── workbook_map.py          # C3  WorkbookMapper → categorizes every sheet
│   └── sheet_models.py          # C3  TractGrid, OGLRegister, Runsheet, WISheet, WellTab views
├── validation/
│   ├── base.py                  # C4  Validator ABC + ValidationResult contract
│   ├── interest_conservation.py # C4  Gate G1
│   ├── pro_rata_footing.py      # C4  Gate G2
│   ├── chain_of_title.py        # C4  Gate G3
│   ├── instrument_line_audit.py # C4  Gate G4
│   └── ogl_register_audit.py    # C4  Gate G5
├── source_verification/
│   ├── okcr_client.py           # C5  OKCountyRecords via curl-subprocess (Basic Auth)
│   └── evidence_cache.py        # C5  Local doc cache + provenance index (immutable)
├── repair/
│   ├── xml_surgery.py           # C6  zip+lxml cell/style writer (drawing-preserving)
│   ├── safe_fixes.py            # C6  SafeFixRegistry (SAFE strategies only)
│   └── recalc_engine.py         # C7  LibreOffice headless forced-recalc runner
├── reporting/
│   ├── audit_report.py          # C9  Exhaustive per-run action report (MD)
│   └── certification.py         # C9  Certified workbook stamp + final title-picture summary
├── output/                      #     (git-ignored) versioned .xlsx, reports, evidence, run DBs
└── tests/                       #     Mirrors package; each phase ships its own suite
```

**Third-party surface (pin in `requirements.txt`):** `streamlit`, `pydantic>=2`, `lxml`, `openpyxl` (READ-ONLY use — see §3.C6 hard rule), `python-dateutil`. LibreOffice (`soffice`) and `curl` are external binaries invoked via `subprocess`, never as Python libs.

---

## 2. Data Flow Mapping

```
                    ┌─────────────────────────── PerfectionLoop (orchestrator) ───────────────────────────┐
                    │                                                                                       │
 report_v0.xlsx ──► INGEST ──► WorkbookModel ──► VALIDATE (5 gates, read-only) ──► GateScorecard ──┐        │
   (client copy)    (map)      (typed views)      │                                                │        │
                    │                             └──► Failures ──► FailureTaxonomy.classify() ──► Router    │
                    │                                                                               │        │
                    │   ┌──────────────── SAFE ────────────────┐   ┌─── NEEDS-SOURCE ───┐   ┌── UNSAFE ──┐  │
                    │   │ SafeFixRegistry.plan()                │   │ okcr_client.fetch  │   │ Escalation │  │
                    │   │ → xml_surgery.apply() → report_vN+1   │   │ (spend-capped)     │   │ Matrix →   │  │
                    │   │ → recalc_engine.recalc(single-sheet)  │   │ → evidence_cache   │   │ HALT +     │  │
                    │   └───────────────┬───────────────────────┘   └─────────┬──────────┘   │ examiner   │  │
                    │                   │                                     │              └─────┬──────┘  │
                    │                   └───────────── re-VALIDATE (loop) ◄───┘                    │         │
                    │                                                                              │         │
                    └──────── all gates PASS ──► CERTIFY ──► report_vFINAL.xlsx + audit_report.md ─┘         │
                                                                                                             │
 Every arrow writes: audit_log(row) + (if source touched) evidence_cache(provenance) + spend_ledger(if paid) │
```

Data is **append-forward only**: ingestion snapshots `v0`; each repair emits `vN+1`; certification stamps `vFINAL`. No stage mutates an existing file in place. The Streamlit dashboard is a pure **reader** of the SQLite DB and the `output/` version tree — it never drives mutation except by enqueuing a run.

---

## 3. Class & Function Responsibilities

> Signatures below are **interface contracts** (names, inputs, return types, invariants) — not implementations. Claude writes the bodies.

### 3.0 `models.py` — shared typed vocabulary
- `Coord(sheet: str, cell: str)` — a fully-qualified cell address.
- `Severity(Enum)` = `INFO | WARN | FAIL`.
- `RiskClass(Enum)` = `SAFE | NEEDS_SOURCE | UNSAFE`.
- `GateId(Enum)` = `G1_CONSERVATION | G2_FOOTING | G3_CHAIN | G4_INSTRUMENT | G5_OGL`.
- `ValidationResult(gate: GateId, severity, passed: bool, message: str, locations: list[Coord], metric: float | None, expected: float | None)`.
- `Failure(id: str, gate, category: FailureCategory, coord: Coord | None, detail: str, proposed_fix: "FixPlan | None")`.
- `FixPlan(strategy_id: str, risk: RiskClass, target: Coord, before: Any, after: Any, justification: str, source_refs: list[SourceRef])`.
- `SourceRef(kind: Literal["rawdata","okcr_image","index_page","formula","prior_version"], locator: str, hash: str | None)`.
- `GateScore(gate, passed: bool, failures: int, worst: Severity)` and `Scorecard(scores: dict[GateId, GateScore], all_pass: bool)`.
- `LoopState(Enum)` = `INGESTED | VALIDATING | ROUTING | REPAIRING | RECALC | ESCALATED | CERTIFIED | HALTED`.
- `RunContext(run_id, source_path, workdir, version: int, spend_used: Decimal)`.

### 3.C1 `app.py` — Streamlit dashboard
- `render_dashboard()` — top-level layout. Reads `RunContext` + latest `Scorecard` from DB.
- `panel_loop_status()` — current `LoopState`, iteration count, version pointer.
- `panel_gate_scorecard()` — 5-gate PASS/FAIL grid with metric vs expected per gate.
- `panel_live_results(run_id)` — streaming table of `ValidationResult` + applied `FixPlan` rows from the audit log (auto-refresh).
- `panel_escalations()` — queue of `EscalationTicket`s awaiting examiner decision, with approve/reject controls that write a decision row (never auto-mutate).
- `action_start_run(path)` — enqueues an orchestrator run; disabled while a run is `REPAIRING`.

### 3.C2 `memory/` — SQLite shared memory + append-only audit
- `db.get_connection(run_id) -> Connection` — WAL mode, one DB file per run under `output/<run_id>/run.db`.
- `db.init_schema(conn)` — creates tables (all log tables enforce append-only via triggers rejecting UPDATE/DELETE):
  - `runs`, `versions(version, path, sha256, created_ts, parent_version)`,
  - `audit_log(id, ts, run_id, actor, action, gate, coord, before, after, risk, source_refs_json, result)`,
  - `validation_results`, `fixes`, `escalations`, `spend_ledger`, `evidence(hash, kind, locator, path, fetched_ts, cost_usd)`.
- `audit_log.AuditLog.record(entry: AuditEntry) -> None` — the **only** write path; every component calls it. Idempotent on `(run_id, action_hash)`.
- `audit_log.AuditLog.trail(run_id) -> Iterator[AuditEntry]`.
- `spend_ledger.SpendLedger.remaining() -> Decimal`, `.charge(cost, evidence_hash) -> None` (raises `SpendCapExceeded` if it would cross `API_SPEND_CAP_USD`).

### 3.C3 `ingestion/` — workbook mapping layer
- `workbook_map.WorkbookMapper.load(path) -> WorkbookModel` — opens the `.xlsx` **read-only** (openpyxl read is safe; writes are forbidden here). Classifies each sheet by name + shape heuristics into a `SheetKind`.
- `SheetKind(Enum)` = `TRACT_GRID | OGL_REGISTER | RUNSHEET | WI | WELL | OVERVIEW | PLAT | RAWDATA | OTHER`.
- `sheet_models.TractGrid` — view over one tract: `.tract_no`, `.acreage`, `.instrument_columns() -> list[InstrumentColumn]`, `.owner_rows() -> list[OwnerRow]`, `.report_total_cell`, `.subtotal_guard_cells()`.
- `sheet_models.OGLRegister` — `.leases() -> list[OGLRecord]` (ogl_no, book_page, grantor, grantee, legal, gross_ac, term, royalty, base_or_top, tract_refs).
- `sheet_models.Runsheet` — `.instruments() -> list[RunsheetRow]` (instr_no, doc_type, book_page, grantor, grantee, legal, tract_refs, classification).
- `sheet_models.WISheet`, `sheet_models.WellTab` — analogous typed views.
- `WorkbookModel.sheet(kind)`, `.tracts() -> list[TractGrid]`, `.checksum()`.
- **Invariant:** ingestion is pure/read-only and never imports `repair`.

### 3.C4 `validation/` — five gates
- `base.Validator(ABC)` — `.gate: GateId`; `.validate(model: WorkbookModel, recalc: RecalcValues) -> list[ValidationResult]`. Read-only; must be deterministic; must not touch the network.
- `base.RecalcValues` — cached computed values from the last LibreOffice recalc (so validators compare against *evaluated* formulas, not stale cached values).
- Concrete validators (one per §5 gate): `InterestConservationValidator`, `ProRataFootingValidator`, `ChainOfTitleValidator`, `InstrumentLineAuditValidator`, `OGLRegisterAuditValidator`.
- `ValidatorSuite.run_all(model, recalc) -> tuple[list[ValidationResult], Scorecard]` — fixed execution order G1→G5; aggregates to a `Scorecard`.

### 3.C5 `source_verification/` — OKCountyRecords
- `okcr_client.OKCRClient(api_key, ledger: SpendLedger)`:
  - **Auth:** HTTP Basic, API key as username, empty password.
  - **Transport:** `subprocess.run(["curl", "-u", f"{key}:", ...])` — deliberately **not** `requests`; curl clears Cloudflare where the Python stack gets 403. (Verified this session: the Python/WebFetch path is blocked; curl-with-key is the supported channel on the DataBossX host.)
  - `.counties() -> list[str]` → `GET /api/v1/counties`.
  - `.lookup(county, number) -> InstrumentMeta` — returns metadata incl. the **`free_to_view` flag**.
  - `.fetch_image(county, number) -> EvidencePath` — **guard: only proceeds if `free_to_view` is true OR `ledger.remaining()` covers the quoted cost; otherwise returns `SourceUnavailable`, never a silent charge.** On paid fetch: `ledger.charge()` then cache.
  - Every call writes `audit_log` + (on fetch) `evidence` rows. Endpoint shape: `GET /api/v1/images?county=<c>&number=<n>&action=view` → `application/pdf` bytes.
- `evidence_cache.EvidenceCache.put(bytes, kind, locator) -> SourceRef` (content-addressed by sha256; immutable), `.get(hash)`, `.provenance(instr_no) -> list[SourceRef]`.

### 3.C6 `repair/xml_surgery.py` — drawing-preserving writer
- **HARD RULE (proven this session): never write the workbook with openpyxl.** openpyxl drops embedded drawings, the SVG map layer, and threaded comments on save. All writes go through zip+lxml surgery.
- `XmlWorkbook.open(path)` — loads the OOXML zip into memory; indexes `sheetN.xml`, `styles.xml`, `workbook.xml`, `[Content_Types].xml`, rels.
- `.set_cell(sheet, cell, value: CellValue)` — writes inline string / number / formula; **unshares** any shared-formula group intersecting the edit (expands the host formula and translates relative refs for each member) so the edit can't corrupt a `t="shared"` range.
- `.set_fill(sheet, cell, style_ref)` — clones the cell's `xf` with a new `fillId` (append-only styles) to add/remove a highlight without disturbing other cells.
- `.drop_calc_chain()` — removes `xl/calcChain.xml`, its content-type override, and its rel.
- `.force_full_calc()` — sets `calcPr/@fullCalcOnLoad="1"` and clears `@calcId`.
- `.save_as(version_path)` — repackages the zip byte-for-byte except modified parts; asserts media/drawings/comments parts are byte-identical to the source (regression guard).
- `safe_fixes.SafeFixRegistry` — an ordered registry of `SafeFix` strategies. Each `SafeFix` declares `.can_handle(failure) -> bool`, `.risk == SAFE` (enforced), and `.plan(failure, model) -> FixPlan`. **The registry admits only fixes whose `after` value is fully derivable from the model or a verified `SourceRef`** (formula-range extension, `calcChain` rebuild, `fullCalcOnLoad`, number-format normalization, style-only highlight add/remove, bijective book/page↔OGL renumber, name normalization *only when the normalized string exactly equals a verified source spelling*). No strategy may synthesize a legal fact.

### 3.C7 `repair/recalc_engine.py` — LibreOffice validation recalc
- `RecalcEngine(soffice_path, profile_dir)`:
  - `.ensure_force_recalc_profile()` — writes `registrymodifications.xcu` with `OOXMLRecalcMode=0` (**always recalc**). Without this, `--convert-to` keeps stale cached values (verified this session).
  - `.recalc(path) -> RecalcValues` — headless `--convert-to xlsx` into a temp dir with an isolated `-env:UserInstallation`; reads back evaluated values; surfaces any `#REF!/#VALUE!/#DIV0!/#NAME?/#N/A/#NUM!/#NULL!` as `FormulaError` failures.
  - `.recalc_sheet(path, sheet)` — **OOM mitigation:** for large books, materialize a single-sheet slice (copy target sheet + its formula dependencies into a throwaway workbook), recalc that, and map values back — avoids loading all ten dense grids at once.

### 3.C8 `orchestrator.py` — the Perfection Loop (see §4).

### 3.C9 `reporting/`
- `audit_report.AuditReportBuilder.build(run_id) -> Path` — renders the full append-only trail into an exhaustive human MD: every validation result, every fix (before→after→source), every escalation, every API charge, per-iteration scorecards. Lives **beside** the workbook, never inside it.
- `certification.Certifier.certify(final_version) -> CertifiedArtifact` — stamps a version tag + sha256 into `versions`, emits `report_vFINAL.xlsx` (untouched bytes, just recorded as certified) and a one-page **final title-picture summary** (ownership by tract, OGL/HBP posture, open escalations). Certification is only reachable from `LoopState.CERTIFIED` (all gates green).

---

## 4. The Perfection Loop — Control Logic (state machine)

```
INGESTED
   │  map workbook, snapshot v0, checksum
   ▼
VALIDATING ──────────────────────────────────────────────┐
   │  RecalcEngine.recalc(current_version)                │  (re-entry after each repair)
   │  ValidatorSuite.run_all → Scorecard                  │
   ▼                                                       │
ROUTING                                                    │
   │  FailureTaxonomy.classify(all failures)               │
   │  partition → {SAFE, NEEDS_SOURCE, UNSAFE}             │
   ├── all gates pass ───────────────► CERTIFIED ──► (exit)│
   ├── UNSAFE non-empty ─────────────► ESCALATED ──► HALT  │
   │       (open ticket, freeze, await examiner)           │
   ├── NEEDS_SOURCE non-empty ──► fetch via OKCRClient     │
   │       success → convert to SAFE fix                   │
   │       unavailable / cap hit → ESCALATED               │
   ▼                                                       │
REPAIRING                                                  │
   │  for each SAFE FixPlan (deterministic order):         │
   │    xml_surgery.apply → emit report_v(N+1)             │
   │    audit_log.record(before, after, source_refs)       │
   ▼                                                       │
RECALC ── RecalcEngine.recalc(v(N+1)) ────────────────────┘
   │  (formula errors introduced? → treat as new failures)
   │  convergence guard: if iteration budget hit OR a gate's
   │  failure set is unchanged across 2 passes → ESCALATED
   ▼  loop back to VALIDATING
```

**Termination guarantees:** (a) monotonic version counter with a hard `MAX_ITERATIONS`; (b) a **no-progress detector** — if the multiset of failures for any gate is identical across two consecutive iterations, the loop stops fabricating attempts and escalates; (c) the loop can **only** exit via `CERTIFIED` (all green) or `ESCALATED/HALTED` (never silently "good enough"). The loop **never** fabricates title data — a gate that cannot go green with SAFE fixes + verified sources always escalates.

---

## 5. Quality Gates — exact definitions

Let `ε = 1e-9` (dimensionless interest), `τ = 0.01` acres (footing tolerance).

- **G1 — Interest Conservation.** For every instrument column `c` in every `TractGrid`: `|Σ_r cells[r,c]| ≤ ε`. (Pure conveyances net to zero: grantors negative, grantees positive.) Equivalent live check: each per-column `SUBTOTAL` guard cell in grid rows 6–7 evaluates to `""` (not `"RECHECK"`). PASS ⇔ all columns conserve **and** no guard shows `RECHECK`.

- **G2 — Pro-Rata Net-Acre Footing.** (a) Per tract: `|REPORT_TOTAL − tract_acreage| ≤ τ`. (b) Per owner row with positive interest: `|net_ac − fraction × tract_acreage| ≤ τ`. (c) Global: `|Σ_tract tract_acreage − 637.42| ≤ τ`. PASS ⇔ (a)∧(b)∧(c). (Reference footings from this section: 80/160/40/80/38.28/51/40/32.8/75.34/40.)

- **G3 — Chain-of-Title Continuity.** Order each tract's instruments by effective date. Maintain a running per-party ownership ledger. For each conveyance, the grantor's pre-conveyance balance must be `≥` the interest conveyed (within `ε`); cumulative tract ownership must stay in `[0, tract_acreage]`. A grantor who conveys with **no prior vesting and no locatable source** is an **orphan** → G3 fail routed to source-verification, and if still unresolved, to the highlight/escalation path (this is exactly the "highlight unresolved grantors" rule). PASS ⇔ no gaps, no orphans, no negative balances.

- **G4 — Instrument-Line Audit.** Coverage `= resolved_lines / total_lines`. A line is *resolved* iff its instrument number maps to at least one `SourceRef` (rawdata row, OKCR image, or index page). PASS ⇔ coverage `== 1.0`. Unresolved lines enumerate into G4 failures with their missing locators.

- **G5 — OGL Register Audit.** (a) Every OGL number referenced on Title/WI exists exactly once in the OGL register (no phantom numbers). (b) book/page ↔ OGL number is a bijection. (c) Every base/top-lease pairing is internally consistent (top lease's "prior lease" points to a real base OGL; royalties/legals reconcile with the covered tracts). PASS ⇔ (a)∧(b)∧(c).

---

## 6. Failure Taxonomy & routing

| Category | Example | Detected by | Default route |
|---|---|---|---|
| `COMPUTATION_CONSERVATION` | column sums to −2 not 0 | G1 | SAFE only if caused by a formula-range/`SUBTOTAL` defect; else NEEDS_SOURCE→UNSAFE (missing interest) |
| `COMPUTATION_FOOTING` | tract total 1838 ≠ 40 | G2 | SAFE (SUMIF range extension / ROUND) |
| `FORMULA_ERROR` | `#REF!`, `#VALUE!` after edit | G-recalc | SAFE (rebuild ref / unshare) or UNSAFE if structural |
| `XML_DAMAGE` | orphaned shared-formula, lost style | recalc/surgery self-check | SAFE (re-emit) or UNSAFE (halt) |
| `TITLE_GAP_ORPHAN` | grantor conveys, no vesting | G3 | NEEDS_SOURCE (okcr) → highlight → UNSAFE/escalate |
| `TITLE_GAP_CHAIN` | ownership > tract acreage | G3 | UNSAFE (never auto-invent) |
| `PROVENANCE_MISSING` | instrument line, no source | G4 | NEEDS_SOURCE → escalate if unfetchable |
| `REGISTER_PHANTOM_OGL` | Title cites OGL 110, not in register | G5 | SAFE only if a bijective, unambiguous renumber exists; else UNSAFE |
| `REGISTER_MISMATCH` | book/page ↔ OGL not 1:1 | G5 | UNSAFE |
| `SPEND_CAP` | $100 reached | ledger | ESCALATE (freeze source fetches) |

`FailureTaxonomy.classify(failure) -> (FailureCategory, RiskClass)` is the single routing authority; the orchestrator never hard-codes routing.

---

## 7. Human-in-the-Loop Escalation Matrix

| Trigger | Why it halts | Handoff artifact |
|---|---|---|
| Any fix that would **write a legal fact** (party, date, interest) not in a verified source | Golden Law #3 | `EscalationTicket` w/ the failing gate, the *would-be* value, and the empty source set |
| G3 orphan grantor unresolved after OKCR lookup | Cannot vest without inventing chain | Ticket + full name-variant search trail + highlight coordinates |
| G1 conservation gap resolvable only by inventing an interest | Same | Ticket + the column, the imbalance, candidate instruments |
| G5 non-bijective register / ambiguous renumber | Multiple valid mappings = examiner judgment | Ticket + the conflicting mappings |
| `XML_DAMAGE` not repairable by re-emit | Integrity risk | Ticket + failing part + last-good version pointer |
| Spend cap reached with open `NEEDS_SOURCE` | Budget governance | Ticket + remaining unresolved lines + spend ledger |
| No-progress detector fires (2 identical passes) | Loop would spin | Ticket + the stuck failure set |

Escalation = **freeze at current version, write ticket, surface in dashboard `panel_escalations()`, exit loop as `HALTED`.** The examiner's approve/reject writes a decision row; only an explicit approval can promote a `NEEDS_SOURCE`/`UNSAFE` fix to applied — the system never self-approves.

---

## 8. Strict Phased Build Plan (one component per phase, each independently testable to perfection)

| Phase | Delivers | Depends on | "Perfect" exit test |
|---|---|---|---|
| **P0 — Skeleton** | `config.py`, `models.py`, `memory/` (schema + append-only triggers, audit log, spend ledger) | — | Unit: append-only triggers reject UPDATE/DELETE; ledger enforces $100 cap; models round-trip. |
| **P1 — Ingestion** | `ingestion/` mapper + typed sheet views | P0 | Against the real 31-12N-24W workbook: all 19 sheets classified correctly; 10 tract grids, OGL, runsheet, WI, well parsed with exact acreages. |
| **P2 — Validators (read-only)** | `validation/` all 5 gates + `ValidatorSuite` + `Scorecard` | P1, (P7 recalc stub ok) | On the known workbook, emits the *expected* failure set (seed known-bad fixtures; assert each gate's metric vs expected). No writes anywhere. |
| **P3 — Recalc engine** | `repair/recalc_engine.py` incl. forced-recalc profile + single-sheet slice | P0 | Recalc a known workbook → zero formula errors; forced-recalc actually recomputes a seeded stale cell; single-sheet path matches full recalc within `ε`. |
| **P4 — XML surgery** | `repair/xml_surgery.py` | P0 | Round-trip edit → media/drawings/comments parts **byte-identical**; shared-formula unshared correctly; `calcChain` dropped + `fullCalcOnLoad` set; opens clean in Excel + LibreOffice. |
| **P5 — Safe-fix loop** | `repair/safe_fixes.py` + `orchestrator.py` (SAFE path, no network) | P2,P3,P4 | Seed footing/formula defects → loop converges to all-green in ≤ N iters, every fix has an audit row, no-progress detector trips on an unfixable seed. |
| **P6 — Source verification** | `source_verification/` + NEEDS_SOURCE routing | P0,P5 | Mock curl: `free_to_view` honored, paid fetch charges ledger, cap blocks over-spend; live smoke test on the DataBossX host resolves one real instrument. |
| **P7 — Reporting + certification** | `reporting/` + certified output | P5 | End-to-end on real workbook → `report_vFINAL.xlsx` + exhaustive audit MD + title-picture summary; certification only reachable when all gates green. |
| **P8 — Dashboard + hardening** | `app.py` Streamlit + OOM/idempotency/resume | all | Dashboard shows live scorecard/escalations from DB; kill-and-resume mid-loop reproduces state from append-only log; large-book recalc stays within memory budget. |

Each phase ships its own `tests/` suite and is signed off before the next begins. No phase may import a later phase; `ingestion` and `validation` never import `repair` (enforced by an import-linter test in P0).

---

### Appendix A — Non-negotiable implementation notes for Claude (hard-won this session)
1. **Writes = XML surgery only.** openpyxl save destroys the Overview SVG map, drawings, and threaded comments. Use it for *reading* exclusively.
2. **LibreOffice won't recalc without `OOXMLRecalcMode=0`** in the user-profile `registrymodifications.xcu`; otherwise `--convert-to` preserves stale cached values and validation is meaningless.
3. **Unshare shared formulas before editing inside their range**, translating relative refs per member cell, or Excel repairs/renders `#REF!`.
4. **Drop `calcChain.xml` + its content-type override + rel** and set `fullCalcOnLoad` on every emitted version.
5. **OKCountyRecords needs curl (Basic Auth, key as username), not `requests`/WebFetch** — Cloudflare/policy blocks the Python path; check `free_to_view` before any spend; endpoints `/api/v1/counties` and `/api/v1/images?county=&number=&action=view` (PDF bytes).
6. **This module assumes it runs on the DataBossX host** (`D:/Desktop/DataBossX`) where OKCR + OCC are reachable; in a locked-down/cloud runner those hosts 403 at the egress proxy — the loop must degrade to `NEEDS_SOURCE → escalate`, never fake the data.
