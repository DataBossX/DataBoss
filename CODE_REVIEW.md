# DataBossX — Independent Code Review

_Reviewer: Claude Code (independent QA / verifier). Date: 2026-07-24._
_Branch: `claude/databossx-code-review-rdez54` • Baseline: `main` @ 582d951_

> Posture: **read-only review**. This report does not modify production title logic
> (Codex/Cursor are the writers). Every finding below is traced to an exact
> `file:line` with a concrete failure scenario and a proposed fix, so it can be
> picked up by the owning writer without re-investigation.

---

## Current task
Independent, evidence-first review of the DataBossX repository: title-math core,
the controlled workbook QA/repair loop, the grocery report pipeline, and the
backend/infra surface. Goal: find anything that could put a **fabricated,
silently-changed, or unflagged title fact** into a deliverable, plus security and
hygiene defects.

## Evidence reviewed
- `horizon/` core: `interest.py`, `chaining.py`, `validation.py`, `models.py`,
  `versioning.py`, `project_manifest.py`, `report_io.py`, `repair.py`,
  `workbook_qa.py`, `controlled_loop.py`, `orchestrator.py`, `foundation.py`,
  `pipeline.py`.
- `grocery_report_pipeline.py` (1711 lines) + `tests/test_grocery_pipeline.py`.
- Backend/infra: `backend/server.py`, `doto_image_commander/core/database.py`,
  `Dockerfile`, `entrypoint.sh`, `nginx.conf`, `.env.example`, `.gitleaks.toml`,
  `SECURITY.md`, `.github/workflows/*`, `requirements.txt`.
- Test baseline: **146 passed, 10 skipped** (after installing
  `openpyxl`, `pydantic`, `lxml`).
- Runtime verification of the interest/chaining primitives (see Appendix A).

## What is solid (verified, no action needed)
- **Exact interest math.** `interest.py` uses `fractions.Fraction` end-to-end;
  `0.1 → 1/10`, `1/3 × 160 → 53.3333`, `12.5% of 8/8 → 1/8`. No floats enter the
  chain. Over-conveyance and unknown-grantor return `over_conveyance` /
  `examiner_review` instead of a fabricated balance.
- **Legal-description tie-out** is token-boundary, not substring: `"Sec 3"` does
  **not** tie to `"Sec 31"` (verified). Chain-of-title continuity and legal-tie
  failures "poison" the downstream holder so later rows flag review rather than
  show a false balance (`chaining.py:274-290`).
- **Zero-destruction versioning** (`versioning.py`) and the human-gate control
  files (`project_manifest.py`) enforce `approved_hash_required`,
  `technical_verification_is_not_release`, and `require_human_approval` — a work
  order literally cannot disable human approval or edit originals.
- **Public-repo boundary holds:** no owner PII, chains, or data files
  (`.xlsx/.pdf/.csv`) are committed; only public county names and a template
  filename appear.

---

## Findings (most severe first)

Severity key: **CRITICAL** = can emit a fabricated/unflagged title fact as clean ·
**HIGH** = data integrity / security exposure · **MEDIUM** = incorrect output in
plausible cases · **LOW** = hygiene / robustness.

### F1 — CRITICAL — Repair converts an errored cell into an unflagged literal
- **File / source:** `horizon/repair.py:65-71` (default fixer of `repair_workbook`,
  invoked by `Orchestrator.repair`, `orchestrator.py:82`).
- **Current behavior:** For `<c t="e"><f>…</f><v>#REF!</v></c>` the code removes
  `<f>` **and** `del cell.attrib["t"]` while keeping `<v>#REF!`. Empirically the
  cell becomes `<c r="A1"><v>#REF!</v></c>` — a default-typed cell whose value is
  the literal string `#REF!`, with nothing left marking it as an error.
- **Correct behavior:** An error formula must escalate to examiner review (or be
  restored from the template authority + recalculated), never be silently
  downgraded to a plain value.
- **Reason / scenario:** A grantee/legal/interest cell driven by `=VLOOKUP(...)`
  errors to `#REF!`. Repair strips the marker; re-ingest (`read_report`,
  `data_only=True`) reads `#REF!` as an ordinary field; `validation.py` has no
  Excel-error check, so at most a `review` (often nothing) results and
  `emit_version` writes a "converged" `_vNNN`. A broken title fact ships as clean
  data. This defeats the headline "never fabricate / never advance a broken chain"
  guarantee.
- **Fix:** Do not treat error-formula removal as a repair. Flag the cell for
  review, or use `restore_formula_from_template` and require an approved
  recalculation. At minimum, never remove `t="e"` while leaving a `#…` cached `<v>`.
- **Confidence:** High (mechanism empirically reproduced — Appendix A).

### F2 — HIGH — Grocery pipeline fabricates `recording_date` and never flags it
- **File / source:** `grocery_report_pipeline.py:903-904`; flag list at `:953-955`.
- **Current behavior:** When no "Recorded/Filed/recording date" label is found,
  `setv("recording_date", parse_date(text), 0.4)` grabs the **first date anywhere
  in the document** (effective date, execution date, a stray case-number year).
  `recording_date` is **absent** from the low-confidence review list, so the 0.4
  value is never flagged, and it suppresses the `missing-recording-data` yellow
  flag (`:1137` fires only if book/page AND recording_date are both absent).
- **Correct behavior:** Missing recording data must be blank and flagged, per the
  pipeline's own Non-negotiable #1.
- **Scenario:** A deed with only `Effective Date: 2019-03-15` and no recording
  info is emitted with `recording_date = 2019-03-15`, presented as verified.
- **Fix:** Drop the blind fallback, or store as `unlabeled_date_candidate` and
  always attach a REVIEW flag; never let it satisfy the missing-recording check.
- **Confidence:** High (verified in source).

### F3 — HIGH — No authentication on any backend `/api/*` endpoint
- **File / source:** `backend/server.py` — upload (`:270`), list (`:377`), get by
  id (`:396`), logs (`:447`), analytics (`:466`).
- **Current behavior:** No auth dependency anywhere; any reachable client can
  upload documents, read every stored document + OCR text + LLM analysis, and read
  system logs. This directly contradicts `SECURITY.md` ("minimum privilege",
  "expiring human approval for external writes").
- **Fix:** Add an auth dependency (`Depends(...)`, API key/bearer/session) on all
  data endpoints; do not rely on nginx alone. Bind uvicorn to `127.0.0.1:8001`
  (`entrypoint.sh:9`, `server.py:500`) so the backend isn't directly reachable if
  port 8001 leaks.
- **Confidence:** High. _Context:_ `backend/` is labelled a "legacy demo" in the
  README, but it ships via `Dockerfile`/`entrypoint.sh`.

### F4 — MEDIUM/HIGH — Decimal-interest regex causes false red "sum ≠ 1.0" conflicts
- **File / source:** `grocery_report_pipeline.py:823` (`_DECIMAL_RX`), used at
  `:937` and `:1045-1059`.
- **Current behavior:** `(...)(0?\.\d{4,9})` requires **4–9 fractional digits**, so
  legitimate `0.5`, `0.25`, `0.125` are never captured; and the literal word
  `decimal` must be adjacent to the number, which fails for tab-joined xlsx/csv
  rows (`_extract_xlsx`, `:476`).
- **Scenario:** Owners at `0.75000000` + `0.25` → only the 8-digit value captured →
  `dec_sum = 0.75` → a **red** `decimal-sum` conflict on a tract that actually
  balances. Two sub-4-digit owners → `dec_sum = None` → a real imbalance reported
  "OK".
- **Fix:** Allow `0?\.\d+` (any precision), decouple capture from the adjacent word
  for tabular sources, and only assert sum-to-1.0 when the owner set is known
  complete.
- **Confidence:** High (verified in source).

### F5 — MEDIUM/HIGH — CORS wildcard combined with `allow_credentials=True`
- **File / source:** `backend/server.py:40-46` (`allow_origins=["*"]`,
  `allow_credentials=True`, `allow_methods/headers=["*"]`).
- **Scenario:** Once any cookie/credential auth exists (the F3 fix), Starlette
  reflects the `Origin` and sets `Access-Control-Allow-Credentials: true`, letting
  `evil.com` make credentialed cross-origin reads in a victim's browser.
- **Fix:** Explicit trusted-origin allowlist; never pair `["*"]` with
  `allow_credentials=True`.
- **Confidence:** High.

### F6 — MEDIUM — `recover=True` XML parse can silently drop title rows during repair
- **File / source:** `horizon/repair.py:55`.
- **Current behavior:** `etree.XMLParser(recover=True)` discards unparseable XML
  instead of raising. If a worksheet has one error-formula (→ `changed=True`) plus
  any malformed region, `repair_workbook` re-serializes the *recovered* tree,
  potentially deleting whole `<row>`/`<c>` (title rows), while `RepairResult.error`
  stays empty and the orchestrator reports success.
- **Fix:** Parse without `recover=True`, or compare row/cell counts pre/post and
  refuse the write on any loss.
- **Confidence:** Medium-High.

### F7 — MEDIUM — `write_report` drops non-data sheets when source has no media
- **File / source:** `horizon/report_io.py:69`.
- **Current behavior:** Preservation of other sheets is gated on `_has_media`
  (presence of `xl/media/`). A source carrying the OGL register / runsheet / plat
  tabs **as worksheets** but no images takes the `else` branch → a fresh workbook
  with only the data sheet, silently discarding those source registers in the
  emitted `_vNNN`.
- **Fix:** Preserve the source whenever it has *any* extra sheets, not only media
  (copy template, replace only `DATA_SHEET_TITLE`).
- **Confidence:** Medium.

### F8 — MEDIUM — `_is_broken_formula` substring match flags valid formulas
- **File / source:** `horizon/workbook_qa.py:139-141`.
- **Current behavior:** `any(token in upper for token in EXCEL_ERROR_VALUES)`
  substring-matches error strings inside a valid formula:
  `=IFERROR(VLOOKUP(...),"#N/A")` contains `#N/A` → classified `broken_formula`,
  `repairable=True` → `controlled_loop` restores the template formula over the
  operator's working one (a silent, unnecessary mutation).
- **Fix:** Detect errors on the cached result / `data_type=='e'`, not by scanning
  the formula text.
- **Confidence:** High (verified in source).

### F9 — MEDIUM — `Dockerfile` prints `.env` into build logs / image history
- **File / source:** `Dockerfile:9-10` (`RUN echo "${FRONTEND_ENV}" … > /app/.env`
  then `RUN cat /app/.env`).
- **Fix:** Remove the `RUN cat /app/.env` debug line; inject runtime config at
  container start, not as build args baked into layers.
- **Confidence:** High.

### F10 — MEDIUM — `--apply-quarantine` can overwrite a distinct quarantined file
- **File / source:** `grocery_report_pipeline.py:723-725`.
- **Current behavior:** `dst = qdir/f"{src.stem}__{sha256[:8]}{suffix}"`. For an
  exact-dup group the hash is identical, so two byte-identical files with the same
  basename (e.g. `report.txt` in two subfolders) map to the same `dst`; the second
  `shutil.move` silently overwrites the first — breaking the "moves, never deletes"
  invariant and losing directory provenance.
- **Fix:** Make `dst` collision-proof (append a counter or a path hash) or check
  `dst.exists()` first.
- **Confidence:** High.

### F11 — MEDIUM — Identifier interpolation in `insert_many` (SQL-injection vector)
- **File / source:** `doto_image_commander/core/database.py:196-198`.
- **Current behavior:** Values are parameterized (safe) but `table` and column
  names from `rows[0].keys()` are interpolated verbatim. If any caller ever derives
  column names from an uploaded CSV/Excel header, that input is injected.
- **Fix:** Whitelist `table`; validate/quote columns against the table's known set.
- **Confidence:** Medium (depends on caller trust; no unsafe caller found today).

### F12 — LOW/MEDIUM — Unvalidated file upload (no size/type cap, full read to RAM)
- **File / source:** `backend/server.py:270-277` (`await file.read()`).
- **Fix:** Enforce a max size and content-type allowlist before processing.
- **Confidence:** High.

### F13 — LOW — Insecure default `MOCK_AUTH=true` in `.env.example`
- **File / source:** `.env.example:5`. Copying the template to `.env` runs with
  auth mocked on. **Fix:** default to `MOCK_AUTH=false` (or remove).

### F14 — LOW — Non-deterministic dedupe keeper selection
- **File / source:** `horizon/foundation.py` `scan` (125-149) / `fidelity` (57-64) /
  `dedupe` (174-190). `os.walk` order is OS-dependent and `fidelity()`'s final
  tiebreak is only `-len(rel)`; equal-length distinct paths tie, so which byte-
  identical copy is kept vs. trashed (and recorded in receipts) is not reproducible.
  **Fix:** Sort records by `rel` before grouping and add `self.rel` as the final
  tiebreak. (Content identical; this is a reproducibility/provenance gap.)

### F15 — LOW — `_STATE_RX` matches bare "OK"/"CO"/"LA" as a state
- **File / source:** `grocery_report_pipeline.py:828`. A doc containing "OK" yields
  a fabricated `state` at 0.6 (not `< 0.6`, so unflagged). **Fix:** require a
  state-like context, or lower the confidence below the review threshold.

### F16 — LOW — Internal exception text returned to clients
- **File / source:** `backend/server.py:195,245,312` (`detail=f"…{str(e)}"`).
  **Fix:** generic client message; log detail server-side only.

### F17 — LOW — `requirements.txt` has conflicting duplicate pins
- **File / source:** `requirements.txt` — `pydantic` (`>=2.9.2` L27 / `==2.9.2`
  L35), plus duplicate `python-dotenv`, `fastapi`, `uvicorn`, `requests` with
  differing specifiers. pip takes the last, but the mixed `>=`/`==` is fragile.
  **Fix:** de-duplicate to one pin per package.

### F18 — LOW — Dead / misleading code in the grocery pipeline
- `:255` unused `sep`; `:817` unused `_ACRE_RX`; `:970` `hasattr(dict,...)` branch
  that is always dead. Harmless; remove to reduce confusion.

---

## Confidence
High on all F1–F12 mechanisms (each traced to source; F1 empirically reproduced,
core math runtime-verified). The reachability of F1/F6 in the *current* controlled
loop is partial — `controlled_loop` prefers `restore_formula_from_template`, but
`Orchestrator.repair` uses the vulnerable default fixer, and the validation gate
cannot independently catch an introduced error value (see note below).

## Remaining blockers
- Whether `Orchestrator` (repair.py path) is still an active production entry point
  or fully superseded by `controlled_loop` — this sets F1/F6 between CRITICAL and
  latent. Needs a writer (Codex) to confirm.
- **Validation gate limitation (context):** `validation._validate_row_interest`
  (`validation.py:202`) skips rows with `status != "ok"` and reconstructs
  `grantor_side = conveyed + retained` from the row's own numbers, making
  `reconcile()` trivially "balanced"; it only catches `sum > 1` (over-8/8). So the
  emit gate will **not** independently catch a broken/fabricated value introduced
  upstream — which is why F1/F2/F8 are load-bearing.

## Recommended next action
1. **F1, F2** first — they are the two that can put an unflagged wrong title fact
   into a deliverable. Hand to the owning writer (Codex) with the fixes above.
2. **F3/F5/F9** before any non-local backend deployment.
3. Add regression tests: an errored-formula workbook must NOT converge (F1); a
   deed with no recording label must leave `recording_date` blank + flagged (F2);
   `0.5 + 0.5` decimals must reconcile to 1.0 (F4).

## Estimated impact
- F1/F2: eliminate the two paths that can emit an unflagged fabricated/erroneous
  title fact — directly protects deliverable accuracy for the active sections.
- F4: removes false red conflicts that would waste examiner time and mask real
  imbalances.
- F3/F5/F9: close the backend data-exposure surface.

---

## Appendix A — Runtime verification performed
```text
1/3 × 160 acres            → 53.3333        (exact)
reconcile(1/2 − 3/4)       → over_conveyance
reconcile(None, 1/2)       → examiner_review
parse("12.5% of 8/8")      → 1/8
parse("0.1")               → 1/10           (exact, no float)
legal_ties("Sec 3","Sec 31")     → False    (no false substring tie)
legal_ties("Sec 3","Sec 3 T12N") → True
_fix_worksheet_xml(<c t="e">…<v>#REF!</v>) → <c><v>#REF!</v></c>  (F1 confirmed)
pytest                     → 146 passed, 10 skipped
```
