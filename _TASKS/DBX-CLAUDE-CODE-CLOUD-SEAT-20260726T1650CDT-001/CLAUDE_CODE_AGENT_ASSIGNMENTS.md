# CLAUDE CODE — AGENT ASSIGNMENTS

**Timestamp:** 2026-07-26 17:08 CDT · **Task:** `DBX-CLAUDE-CODE-CLOUD-SEAT-20260726T1650CDT-001`
**Issued as proposals to Codex, the sole controller.** This seat does not dispatch, does not hold a
lease, and does not create a second authority. Every task below routes through the existing
DataBoss intake gate and the established Drive inbox.

**New requirement on every envelope: a `requires:` capability field.** At least two Claude Code
seats with different capabilities answer to the same name; an envelope that does not declare the
capability it needs will stall silently on the wrong seat (see `CLAUDE_CODE_BRIDGE_VERIFICATION.md`).

---

## T-01 · Freeze the S17 A10 lease — **STOP-WORK, do first**
**Owner:** Codex · **requires:** `controller`
**Input:** `LEASE-S17-CURSOR-A10-20260726T1510CDT-001`; defects D-01, D-02
**Output:** `LEASE_FROZEN.json`, superseding the current lease without changing authorized scope
**Rollback:** none required — no mutation
**Validation:** lease state re-read and confirmed frozen
**Why:** the lease targets a disputed cell address in a workbook that does not contain the subject
instrument. Executing as written risks overwriting a correct classification in a client deliverable.

## T-02 · S17 hash lineage arbitration
**Owner:** Codex · **requires:** `windows_fs`, `byte_exact_io`
**Input:** pinned local candidate; Drive `1W_FwItz7xmFogVEwzUYk8jFI7iujdH0j`; the three competing
hashes `B19A6B97…`, `80A8D365…`, `B53B0876…` (D-11)
**Output:** `S17_ARTIFACT_LINEAGE.json` — which hash derives from which, by what operation, and
which artifact is the client deliverable
**Rollback:** read-only
**Validation:** every hash recomputed from bytes on disk; no hash carried over from a prior document
**Note:** this seat **cannot** perform this task — large binary payloads are not byte-transportable
through it. Do not route hashing to a `drive_only` seat.

## T-03 · Repair `0285-0528` mineral-reservation warning — **highest-value repair**
**Owner:** Codex writer under a new exact lease · **requires:** `windows_fs`, `native_excel`
**Input:** authoritative S17 workbook (per T-02); E1 face `0285-0528.pdf`
SHA-256 `F7E4D6F1385F8E6FEEDEAC6FA7B6D4E37FD9EF702CA2BD94EE167D63EDB148F6`, 4/4 pages
**Change authorized:** `Comments` cell of the `0285-0528` row **only** — add the mineral-reservation
and surface-only effect warning. No other cell, formula, style, defined name, hyperlink,
relationship, workbook property, print setting, VBA part, or package part may change.
**Rollback:** task-local immutable backup hashed before edit
**Validation:** exhaustive used-cell diff; package-part diff; native repair-free reopen; output
hash; distinct Claude B exact-byte PASS/FAIL
**Why:** D-04 — the row currently implies minerals passed to Carter Oil Company. They did not.

## T-04 · S17 defect-list re-baseline
**Owner:** Claude Code (this seat) · **requires:** `drive_only` · **lease:** none needed (read-only)
**Input:** Drive S17 artifact; current advisory defect register
**Output:** corrected open/closed defect list — D-03 (`0331-0490`) is **already closed** in the
artifact and should stop consuming lease cycles
**Validation:** every open/closed call re-read from the artifact in the same pass

## T-05 · Section 20 read-only content audit
**Owner:** Claude Code (this seat) · **requires:** `drive_only` · **lease:** none needed
**Input:** `INTERNAL_REVIEW_COPY__PENTERRA_CAMPBELL_SEC20__20260726.xlsx` (`1GWpxOfS8IoPQelufJ5RW-mfWvmjf_8r4`)
**Output:** row inventory vs 136 expected; the ten Book-Page gaps and seventeen missing dates
enumerated by row; Doc-No/Rec-Date monotonicity anomalies; **cross-section contamination check**
(any `17-47N-75W` string in a Section 20 workbook); source-requirement bindings for the
twenty-seven unresolved cells
**Rollback:** read-only
**Constraint:** do **not** copy Section 17 values into Section 20 — pull each face once and bind
independently in both.

## T-06 · Section 32 copy-identity proof and PENDING annotation
**Owner:** Codex · **requires:** `windows_fs`, `byte_exact_io`
**Input:** the three 2,991,406-byte copies (`1CuhEg1bzvcgX0rtpcRu6DmNYfjiq6um_`,
`11eSRgFonY5l_6SwAbmPDIsbGeaLXyudO`, `112CZEOJtSUoY_O_BkVM4cVIchCbimkpk`)
**Output:** three SHA-256 values; if equal, annotate the PENDING copy `UNREPAIRED_HOLD_COPY`
**Rollback:** annotation only; **delete nothing** — all three are evidence
**Why:** D-14 — an unrepaired workbook is sitting in PENDING FINAL VERIFICATION.

## T-07 · Missing-source recovery
**Owner:** Codex · **requires:** `windows_fs`; escalate to county re-pull if absent
**Input:** `030M-0595.pdf`, `030M-0615.pdf`, `05ML-0463`, `033M-0425` — **none are in Drive** (D-15;
searched `030M`, `033M`, `05ML`, `0463`)
**Output:** located paths + hashes + full-page renders, **or** one exact blocker recording every
path searched, sizes, hashes, commands, exit codes and stderr
**Constraint:** do not infer title facts from filenames. Do not guess the contents of an unreadable
instrument. Note `033M-0425` may not exist as a distinct instrument — Doc 118065 is identified at
`033M-0435` (D-16).

## T-08 · Sequence-anomaly face adjudication
**Owner:** Cursor (isolated) → distinct Claude validator · **requires:** `windows_fs`
**Input:** faces for D-05 (`0307-0002`, Doc `368354`, probable transposition of `388354`), D-06
(`1513-0025`), D-07 (`1791-0124`), D-08 (`3123-0423`), D-09 (`2139-0282`), D-10 (`1551-0214`)
**Output:** per-row confirm/correct with quotation and page cite
**Constraint:** transposition is a **hypothesis**, not a licence to edit. No correction without the face.

## T-09 · Section 32 reconciliation via existing controlled loop
**Owner:** Cursor (isolated) + Codex · **requires:** `windows_fs`, `native_excel`
**Gate:** blocked until T-06 and the lineage/counting-rule freeze complete
**Method:** `horizon.controlled_loop` **only** — already package-preserving, already gated, already
rollback-capable. **Build no new edit tooling.** Do not invent missing authority hashes.
**Output:** each of the 4 unexplained instruments and 90 missing-source rows classified into
exactly one of the nine required categories.

## T-10 · Native-Doc export adapter — zero-credential workaround
**Owner:** Claude Code (`drive_only` seat) · **lease:** none needed
**Finding:** the local `drive_intake` cannot read Google-native Docs (`OSError errno 22`, no OAuth
credentials) — but **this seat reads native Docs natively.** A `drive_only` Claude seat can read a
native-Doc directive and republish it as raw `.md`/`.txt` into the watched inbox, making it
executable with **no code change and no credential grant**.
**Constraint:** republish content verbatim; do not interpret prose as commands. The
bounded-command sidecar boundary stays exactly as it is.

---

## CONFLICT MATRIX — no two agents write the same artifact

| Artifact | Sole writer | Everyone else |
| --- | --- | --- |
| S17 workbook | Codex under one exact lease (T-03) | read-only |
| S20 workbook | **nobody** — no lease exists | read-only (T-05) |
| S32 workbook | **nobody** — hold | read-only; annotation only (T-06) |
| Lease records | Codex | read-only |
| This seat's Drive folder `1_xQjtW0S3vD2MNfOyJ-fu-VQ-moPP4Go` | Claude Code (this seat) | read-only |

## LOCAL MODELS — bounded
OCR comparison, text normalization suggestions, duplicate candidate generation, secondary
classification, independent critique. **Never** a canonical write; **never** a final determination
of legal effect without primary-source validation.

## TOURNAMENT (`C:\DataBoss\Tournament`) — optional, non-authoritative
Useful for: ranking D-05..D-10 by materiality; competing classifications for the `1783/118` face;
critiquing this plan. **Winning output is advisory and must still pass evidence, safety, and
validation gates before any use.**
