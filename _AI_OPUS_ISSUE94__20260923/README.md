# Issue #94 — adversarial fail-closed regression packet

These are drop-in pytest modules for the seven mandatory regressions in
[DataBossX/DataBoss#94](https://github.com/DataBossX/DataBoss/issues/94).
They use synthetic fixtures only. Every workbook, document and upload is
generated inside a pytest `tmp_path`. Nothing reads client, P10 or report
bytes, nothing calls a network or LLM, and no production file was edited
from this lane.

| File | Purpose |
|---|---|
| `test_issue94_integrity.py` | Regressions 1–4 (Horizon repair/orchestrator, grocery pipeline). 50 tests. |
| `test_backend_security.py` | Regressions 5–7 (FastAPI `TestClient`). 95 tests. |
| `FIX_NOTES.md` | Smallest production patch that turns this packet green, verified on a scratch copy, plus the updated repair test. |
| `RECEIPT.md` | Exact bases, commands, counts and hashes. |

## Results

| Tree | integrity | backend | full `tests/` |
|---|---|---|---|
| `582d951` pre-fix main | 38 fail / 12 pass | 79 fail / 16 pass (needs SDK stubs even to import) | — |
| `c87d85d` current branch HEAD | **13 fail** / 37 pass | **2 fail** / 93 pass | 172 pass |
| `c87d85d` + `FIX_NOTES.md` patch | 50 pass | 95 pass | 317 pass in total (`tests/` + packet) |

Most of the tests that pass pre-fix are positive controls: a labeled
recording date is still captured, template restore works, and a clean
workbook keeps every cell. Two more are guards against new bugs a fix could
introduce: out-of-range decimals coerced to 1.0, and duplicate schedules
double-counted. Those pass on pre-fix main only because it could not parse
`0.5` at all.

## Copying into `tests/`

Both modules resolve the repo root from `Path(__file__).parents[1]`, so they
run unchanged from `tests/` or from this folder. Beware that `tests/`
already has smaller files with the same names, committed by the current
writer. Either replace them or rename these, for example to
`test_issue94_adversarial.py` and `test_backend_security_adversarial.py`.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest _AI_OPUS_ISSUE94__20260923/ -q -p no:cacheprovider
```

Dependencies: `lxml`, `openpyxl`, `pytest`, `fastapi`, `httpx` and
`python-multipart`. The modules import `lxml` unconditionally on purpose.
A missing parser must fail the suite, not skip it.

## Contracts the tests rely on

These are all adjustable via constants at the top of each module.

* **Backend:** `backend.server.create_app()` reads env at call time. The
  env variables are `DATABOSSX_DEMO_TOKEN` (the token; auth is
  `Authorization: Bearer <token>`), `DATABOSSX_DEMO_MODE`,
  `DATABOSSX_CORS_ORIGINS` and `DATABOSSX_BIND`. The synthetic marker is
  the header `X-Databossx-Synthetic: 1` or a `SYNTHETIC_` filename prefix.
  Public paths are `/api/health`, `/healthz`, `/docs`, `/openapi.json` and
  `/redoc`.
* **Pipeline:** owner-set completeness is proved by the phrase in
  `COMPLETE_OWNER_SET_MARKER` (`"Complete owner set"`). Review rows are
  read from `review_required.csv`. Decimal checks are read from
  `reconciliation_table.xlsx` → `acreage_decimal_calc`.
* **Repair:** a refusal means `output is None`, `repaired is False`,
  non-empty `error`, `promoted` false (or absent), and `dest` plus any
  temporary file removed.

## Regressions and intended assertions

### 1. `<c t="e"><f>…</f><v>#REF!</v></c>` never becomes a literal and never converges

* **`test_error_formula_repair_is_refused_not_downgraded`** runs over six
  cell shapes: the issue's exact form, a valid formula body with a cached
  `#REF!`, `#DIV/0!`, a shared-formula child, openpyxl's untyped `=#REF!`,
  and a cached error with `t` missing. It asserts that `repair_workbook`
  refuses, the source bytes are unchanged, and no `.xlsx` anywhere under
  `tmp_path` holds an Excel error token without `t="e"`.
* **`test_repair_without_lxml_refuses_instead_of_copying`** covers the
  missing-lxml fallback, which currently copies `src` to `dest` and returns
  it.
* **`test_template_restore_leaves_no_cached_error_literal`** is a positive
  control for the one approved alternative. It restores the exact template
  `<f>` with no `<v>`, so native recalculation is required, and media stays
  byte-identical.
* **`test_errored_workbook_failing_validation_never_promotes`** runs the
  orchestrator on an errored v001. It asserts no convergence, no v002, and
  an `ESCALATED` audit entry.
* **`test_errored_workbook_cannot_converge_even_if_model_validates`** covers
  the case where the in-memory model passes but v001 carries `#REF!` and a
  plat. Today `emit_version(template=current)` copies the errored sheet
  forward and reports `converged=True`. **This test fails on current
  HEAD.**

### 2. Malformed worksheet XML is a hard defect, with zero promotion and no cell loss

* **`test_malformed_worksheet_is_hard_defect_with_zero_promotion`** covers
  seven shapes: an unclosed `<row>`, a mismatched close tag, a bare `&`, an
  undefined entity, a duplicate attribute, a truncated part, and an unclosed
  row that also contains `#REF!`. That last shape is the one where
  recover-mode "fixes" the error and silently drops rows. Each must be
  refused with nothing left on disk.
* **`test_repair_rejects_any_row_or_cell_loss`** injects a lossy
  `worksheet_fixer` that drops a row or a cell. The repair must refuse.
  **This test fails on current HEAD.**
* **`test_clean_workbook_repair_preserves_every_cell_and_media`** is a
  positive control. If an output exists, its cell map is identical and the
  media is byte-identical.
* **`test_malformed_workbook_never_versioned_by_orchestrator`** and
  **`test_template_restore_refuses_malformed_candidate`** assert no
  version, no `.repairing` leftovers, and staged bytes unchanged.

### 3. Effective or execution date without a recording label

The fixtures cover four cases:

* dates only;
* an instrument number plus a notary expiry date and no recording label;
* the `"unrecorded lease dated …"` substring trap;
* a labeled control.

The assertions for each:

* `recording_date == ""` for the first three.
* A `review_required.csv` row whose rule contains "recording" exists for
  each of the first three. **On current HEAD, the instrument case and the
  `unrecorded` case fail**: the instrument number suppresses the only
  warning, and `recorded` matches inside `unrecorded`.
* The effective and execution dates stay in their own fields.
* The labeled control still yields `2020-02-02` and has no recording review
  row.

### 4. `0.5 + 0.5` reconciles to 1.0, and incomplete owner sets assert nothing

* **Parsing.** `_DECIMAL_RX` returns exactly `[0.5]`, `[0.25]`, `[0.125]`
  (including `.125` and `0.12500000`), `[0.00390625]` and `[1.0]`. It must
  never return 1.0 for `1.5`, `10.5` or `12`. **That last check fails on
  current HEAD**, because of the `1(?:\.0+)?` branch.
* **Reconciliation.** A complete 0.5 + 0.5 set gives `decimal_sum == 1.0`,
  `decimal_check` starting with `OK`, and no `decimal-sum` issue. The same
  holds for a mixed-precision 0.25 + 0.125 + .125 + 0.50000000 set.
* **Incomplete sets.** A "PARTIAL" set, and an "OWNERSHIP schedule
  (excerpt)" with no completeness proof, must have a check that neither
  starts with `OK` nor contains `expected 1.0`, and no `decimal-sum` issue.
  **The excerpt case fails on current HEAD** because of the
  "ownership + two decimals" completeness heuristic.
* **Controls against over-correction.**
  * A complete set that sums to 0.75 is still flagged red with 0.75 in the
    detail.
  * An exact duplicate copy of a complete 1.0 schedule must not produce a
    2.0 conflict. **This fails on current HEAD.**
  * `make_synthetic_corpus` must mark its 0.95 schedule complete
    explicitly. **This fails on current HEAD.**

### 5. Every non-health data endpoint rejects unauthenticated access

* **Route coverage.** The tests enumerate every registered `APIRoute` that
  is not public, and every method on it. Unauthenticated requests must
  return 401 or 403, and a 500 does not count as a rejection. A fixed list
  of known data routes is also checked, so that shrinking discovery cannot
  hide a route.
* **Bad credentials.** Ten bad-credential shapes are tested on three
  routes: wrong, empty, prefix and suffix tokens, no scheme, Basic, the
  wrong demo header, the token in the query string, and the token in a
  cookie.
* **Unset server token.** When no server token is configured, everyone is
  denied, including `Bearer `, `Bearer None` and `Bearer null`.
* **Path variants.** Trailing slash, `//`, `%2e%2e` and `../` variants are
  never an unauthenticated 200.
* **Positive controls.** `/api/health` is 200 and a valid token gets 200.
* **Default deny.** A route added after `create_app()`, under `/api/` or
  elsewhere, must require auth. **This fails on current HEAD**, because
  auth applies only to `PROTECTED_PREFIXES`.
* **Import hygiene.** A subprocess imports `backend.server` with
  `openai`, `anthropic` and `google.generativeai` blocked on
  `sys.meta_path`. The import must succeed and create no files, such as
  `logs/` or `*.db`.

### 6. Untrusted origins cannot make credentialed requests

* **Untrusted origins.** Eight are tested: an evil origin, `null`, the
  suffix trick `trusted.test.evil…`, a port change, a scheme change, a
  path-embedded trusted origin, and the two localhost defaults when the
  allowlist is overridden. They run against a public GET, a credentialed
  data GET (with Bearer and a cookie), and preflight `OPTIONS`. The
  response must never have ACAO equal to that origin, never `*` together
  with `Allow-Credentials: true`, and ACAO must be absent or exactly the
  trusted origin.
* **Wildcard configuration.** Setting `DATABOSSX_CORS_ORIGINS` to `*`,
  `trusted,*` or ` * ` must either raise at `create_app()` or grant
  nothing.
* **Defaults and control.** The default configuration grants nothing to a
  foreign origin. As a positive control, the trusted origin receives an
  exact ACAO.

### 7. Real-upload mode refuses mock OCR and never emits invented legal facts

* **Real-mode refusal.** With a valid token and demo mode off, uploading a
  real-looking `.pdf`, `.png` or `.txt` returns a 4xx. The body has no
  `ocr` or `raw_text`, no mock markers (`Mock OCR result`,
  `DataBossX Corp`, `Client ABC`, `Sample Legal Document`, and so on), no
  stack trace or path leak, and not today's date.
* **Spoofing.** In real mode, a spoofed `X-Databossx-Synthetic: 1` header
  plus a `SYNTHETIC_` filename is still refused.
* **Demo mode.** Demo mode still refuses non-synthetic files. A synthetic
  demo upload must be labeled SYNTHETIC, with confidence 0 or absent, no
  date in the OCR text, and no `Parties: <value>` line.
* **No persistence.** A refused upload never shows up in `/api/documents`.
* **Type and size limits.** `.exe`, `.html`, anything over 32 MiB, and
  0-byte files are refused.
* **Direct helper.** Calling `process_ocr()` directly on a real input
  raises, or returns no text.
* **Bind posture.** No hard-coded `0.0.0.0`, and `bind_host()` stays on
  loopback unless `DATABOSSX_ALLOW_NONLOCAL_BIND` is set.
