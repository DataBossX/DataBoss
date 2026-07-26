# CLAUDE CODE — DEFECT REGISTER

**Timestamp:** 2026-07-26 17:08 CDT · **Task:** `DBX-CLAUDE-CODE-CLOUD-SEAT-20260726T1650CDT-001`
**Method:** independent read of Drive artifacts; no reliance on producing agents' conclusions.
**Primary artifact audited:** `PENDING__PENTERRA_CAMPBELL_SEC17__INTERNAL_REVIEW__20260726.xlsx`
Drive ID `1W_FwItz7xmFogVEwzUYk8jFI7iujdH0j` · 25,561 bytes · sheets `Index`, `QA Review`.

Severity: **BLOCKER** = can corrupt a deliverable or mislead a title conclusion · **HIGH** =
material accuracy risk · **MEDIUM** = must resolve before release · **PROCESS** = control-plane.

---

## D-01 — BLOCKER — `Index!A10` is off by one row

**Directive 00W records:** *"Drive ID 1W_FwItz7xmFogVEwzUYk8jFI7iujdH0j … Observed Index!A10: Order and Decree."*

**This seat reads the same Drive file as:**

| Row | `Index!A` value |
| --- | --- |
| 1–7 | metadata (`County:`, `Lands:`, `Date:`, `Starting Date:`, `Date Posted Thru:`, `Indexed By:`, `Project:`) |
| 8 | column headers (`Document Type`, `Grantor`, `Grantee`, `Doc No`, `Book-Page`, …) |
| **9** | **`Order and Decree`** (Doc 239266, Book-Page 0069-0532) |
| **10** | **`Release of Oil and Gas Leases`** (Doc 279471, Book-Page 0121-0487) |
| 11 | `Proof of Labor` (Doc 343689, 72MR-0371) |

`Order and Decree` is at **A9**, not A10. There is a **one-row indexing disagreement between
agents on the exact cell the active lease authorizes.**

**Failure scenario:** the lease `LEASE-S17-CURSOR-A10-20260726T1510CDT-001` authorizes exactly
one change at `Index!A10`. If the writer resolves A10 the way this seat does, it overwrites
`Release of Oil and Gas Leases` — a real instrument row — with `Articles of Agreement`, silently
destroying a correct document-type classification and producing a false chain entry. The lease's
own gate (`Index!A10 still equals Quitclaim Deed`) would fail-closed **only if** the writer reads
the same address; a header-offset difference between openpyxl (1-based, includes metadata rows)
and any viewer that skips metadata rows would defeat the check.

**Required action:** Codex must freeze the lease and republish it with the target identified by
**(Doc No + Book-Page)**, not by bare cell address. Cell addresses are not a safe interface
across seats.

---

## D-02 — BLOCKER — the Drive PENDING copy is a *different artifact*, not a stale one

00W classifies Drive ID `1W_FwItz7xmFogVEwzUYk8jFI7iujdH0j` as `STALE_OR_DIFFERENT_COPY`.
Independent reading shows it is materially different in kind:

- The pinned candidate is named `SECTION_17_INTERNAL_REVIEW_CANDIDATE__05ML_0463_SOURCE_PATH.xlsx`
  and is expected to contain `Index!A10 = Quitclaim Deed` bound to `05ML-0463` / Doc 59931.
- **The Drive PENDING copy contains no `05ML-0463` row at all.** Its Book-Page sequence runs
  `0069-0532, 0121-0487, 72MR-0371, 75MR-0449, 77MR-0525A, 0273-0532, 80MR-0291, 0285-0528,
  0286-0028, 82MR-0337, 0307-0002, 0307-0004, …` — no `05ML-` prefix anywhere in the index.
- The only `Quitclaim` strings in the file are two **`Mineral Quitclaim Deed`** rows far down the
  sheet (`2971-0670` Doc 1014739; `2987-0602` Doc 1016866) — neither is at or near row 10.

**Consequence:** the A10 lease is not merely aimed at a stale copy — it is aimed at a workbook
that **does not contain the instrument the lease is about**. Applying it here cannot be correct
under any row-index convention.

**Required action:** treat the two S17 workbooks as distinct artifacts with distinct lineage.
Do not reconcile by overwriting. Establish which is the client deliverable before any lease.

---

## D-03 — HIGH — the row-35 defect list is stale; the correction is already applied

Advisory findings (16:06 CDT) and 00W list *"row 35 legal-description overreach"* and *"a likely
false Doc No at row 35"* as open. The Drive PENDING copy already carries the corrected row:

```
Warranty Deed | Opal E. Marquiss | Donald W. Wagensen, Doris Wagensen |
Doc No: (blank) | 0331-0490 | 10/22/1975 | 10/22/1975 |
"W/2 and W/2 E/2 of 17-47N-75W, aol" |
"Source-supported correction: document date 10/22/1975. Document number is not shown on the
 reviewed face. Internal review only."
```

This **exactly satisfies** the E1 direct-source requirement published at 16:46 CDT (blank Doc No;
`W/2, W/2 E/2`; no `All of Section 17`). The synthesized `331490` Doc No is already gone.

**Consequence:** agents are being dispatched against a defect that is closed in this artifact,
consuming lease cycles. **Required action:** re-baseline the S17 defect list against the actual
artifact before issuing further repair leases.

---

## D-04 — BLOCKER — `0285-0528` is missing its mandatory mineral-reservation warning

E1 direct-face verification (4 of 4 pages rendered, PDF SHA-256
`F7E4D6F1385F8E6FEEDEAC6FA7B6D4E37FD9EF702CA2BD94EE167D63EDB148F6`) establishes that the grantors
**expressly excepted and reserved all oil, gas, coal and other minerals**, with entry and
surface-use rights. E1 required treatment: *"The row must carry a material mineral-reservation and
surface-only effect warning. It must not imply that the oil, gas, coal, or other minerals passed
to Carter Oil Company."*

**The workbook row's `Comments` field is empty:**

```
Warranty Deed | Roberta H. Napier, ... (Trustees) | Carter Oil Company |
379670 | 0285-0528 | 12/3/1973 | 1/28/1974 | "All of 17-47N-75W, aol" | (Comments: EMPTY)
```

**Consequence — this is the most dangerous defect in the register.** The row as written states a
Warranty Deed of *All of Section 17* to Carter Oil Company with no qualification. A reader
building the mineral chain from this workbook would conclude the minerals passed. They did not.
This is a substantive, examiner-relevant misstatement of legal effect, **evidence-confirmed**, and
it is currently sitting in the PENDING FINAL VERIFICATION folder.

**Required action:** highest-priority repair lease after D-01/D-02 are resolved. Add the
reservation/surface-only warning. Do not promote S17 in any form until this is fixed.

---

## D-05 — HIGH — `Doc No 368354` breaks strict document-number ordering (probable transposition)

The index is otherwise **strictly monotonic** in Doc No against Recording Date across the 1970s
block. One row violates it:

| Book-Page | Doc No | Rec Date | In sequence? |
| --- | --- | --- | --- |
| 0285-0528 | 379670 | 1/28/1974 | yes |
| 0286-0028 | 379775 | 1/31/1974 | yes |
| 82MR-0337 | 386033 | 8/20/1974 | yes |
| **0307-0002** | **368354** | **11/8/1974** | **NO — 368354 < 386033** |
| 0307-0004 | 388355 | 11/8/1974 | yes |
| 0326-0438 | 396262 | 8/8/1975 | yes |

`0307-0002` and `0307-0004` are adjacent book-pages recorded the **same day** to the same family
(Fred S. Wagensen grantor). Their document numbers should be adjacent. `388355` is present;
`368354` is almost certainly a **6↔8 digit transposition of `388354`**.

**Required action:** verify against the `0307-0002` instrument face; correct under an exact lease.
Do not "fix" by inference alone.

---

## D-06 · D-07 · D-08 · D-09 · D-10 — MEDIUM — further document-number sequence anomalies

Same monotonicity test, later blocks:

| ID | Book-Page | Doc No | Rec Date | Neighbours | Note |
| --- | --- | --- | --- | --- | --- |
| D-06 | 1513-0025 | `639458` | 11/20/1998 | 751606 (11/20/1998), 742800 (2/11/1999) | 639xxx belongs to ~1990; far out of range |
| D-07 | 1791-0124 | `862500` | 8/15/2002 | 800456 (7/30/2002), 805215 (10/24/2002) | 862500 out of range |
| D-08 | 3123-0423 | `1089993` | 1/19/2018 | 1039878 (1/16/2018), 1041197 (2/23/2018) | expected ~1040xxx |
| D-09 | 2139-0282 | `867651` | 5/23/2006 | 867754 @ 2139-0592 rec 3/24/2006 | lower doc# **and** lower book-page but **later** rec date — one of the two dates is wrong |
| D-10 | 1551-0214 | `743314` | 7/9/1999 | 748590 (6/24/1999) | lower doc# recorded later |

Each is a candidate transcription error in `Doc No` or `Rec Date`. **None may be corrected without
the instrument face.** Recorded here so they are not lost.

---

## D-11 — HIGH — three competing SHA-256 identities for "the" Section 17 workbook

| Hash | Claimed identity | Source |
| --- | --- | --- |
| `B19A6B9729E6D30F0EDD389BF83E3D0366FE915448316227A228160F45E3F97F` | pinned local candidate, `Index!A10 = Quitclaim Deed` | 00W |
| `80A8D3655159B09B4AEEA992D940DF57F7508B122BFD32FCE4AD4E5737CFD56E` | ChatGPT's download of Drive PENDING | 00W |
| `B53B08761F51596AED164770B5CB02D7E46AB59B621DEF8A0FCF4B58B89BDFC0` | *"Original review-copy SHA-256"* | **the PENDING workbook's own QA sheet** |

Three hashes, no stated lineage between them. The workbook is asserting a provenance hash that
appears in neither control document. **Required action:** Codex must publish one lineage graph
(which hash derives from which, by what operation) before any promotion.

---

## D-12 — HIGH — instrument count unreconciled (197 vs 198)

From the workbook's own `QA Review` sheet: `Populated instrument rows 197` · `Expected instrument
count 198` · `Unresolved count difference 1` · status `OPEN`. Required next action recorded there:
*"Identify the missing instrument from the authoritative index/source manifest without guessing."*
Concur — no guessing. This alone blocks any "fully reconciled abstract" claim.

## D-13 — MEDIUM — one wholly unpopulated instrument row

A row exists carrying `NOT DETERMINED` in **every** field except Book-Page `3163-0546` and the
boilerplate legal `All of 17-47N-75W, aol`. It is counted among the 197 populated rows but carries
no information. Determine whether it is the 198th-instrument placeholder or a genuine gap.

## D-14 — HIGH — Section 32 PENDING copy shows no evidence of repair

All three Drive Section 32 workbooks are **exactly 2,991,406 bytes** (7/23 original, 7/26
INTERNAL_REVIEW_COPY, 7/26 PENDING). Identical length across a claimed reconciliation cycle
indicates the PENDING artifact is a byte copy of the unrepaired 7/23 file. Correct under a hold —
but the file's location in PENDING FINAL VERIFICATION invites the opposite reading.
**Required action:** hash all three on the Windows seat; if equal, rename/annotate the PENDING copy
so it cannot be mistaken for remediated output.

## D-15 — MEDIUM — priority source PDFs are not recoverable from this seat

00W Phase 1 item 6 requires hash + full-page render of `05ML-0463`, `0331-0490`, `0285-0528`,
`030M-0595`, `030M-0615`, `033M-0425`.

| Source | Present in Drive? |
| --- | --- |
| `0331-0490.pdf` | **yes** — multiple copies, incl. `1e0Y5L9TKZkvwvcDh4MaNJsYPN5w-Gy4O` (490,174 B) |
| `0285-0528.pdf` | **yes** — incl. `1zw7W_KbgrQorkm1AFdYHtCEErtsitamv` (1,070,195 B) |
| `05ML-0463` | **not found** |
| `030M-0595.pdf` | **not found** |
| `030M-0615.pdf` | **not found** |
| `033M-0425.pdf` | **not found** (`033M-0463.pdf` exists — different instrument) |

Searches executed: `title contains '030M' / '033M' / '05ML' / '0463'`. The Book 30 Page 595
mortgage reported as *"located but unreadable from one agent seat"* is **not reachable from the
cloud seat either**. It must be recovered on the Windows host or re-pulled from the county.

## D-16 — MEDIUM — `033M-0425` vs `033M-0435` binding conflict, unresolved

Workbook `QA Review` sheet: *"Doc 118065 is identified at 033M-0435"*; proof for a separate
`033M-0425` reference is missing; status `OPEN`; instruction *"Keep 033M-0425 unresolved until
exact source proof exists."* Concur. Note 00W still lists `033M-0425` as a render target — it may
not exist as a distinct instrument.

## D-17 — PROCESS — envelope replay loop

Five near-identical 00W envelopes were written to Drive within ~11 minutes (21:34–21:45 UTC):
`…20260726T1632CDT.json`, `…__REPLAY_CURSOR_SCHEMA_FIXED.json`, `…__FINAL_SCHEMA_FIXED_REPLAY.json`,
`…__APPROVAL_GRANTED_REPLAY.json`, `00W_REPLAY_EXECUTOR_COMPATIBLE…json`. Same task ID, repeated
schema repairs. Each republication is another chance for a worker to claim a stale variant.
**Required action:** one canonical envelope per task ID; supersede explicitly, do not accumulate.

## D-18 — PROCESS — a known-false status source is still live

`00R_TERMINAL_RECEIPT__CLAUDE_CODE.json` records that `WATCHER_STATUS.json` reports the **dead**
`t013_watchers.py` (PID 42944, last heartbeat 2026-07-25T01:06:11-05:00, ~39 h stale against its
own 180-second threshold) as `health HEALTHY, mode RUNNING, pid_alive true`, and that it was
deliberately left untouched as evidence. That was a defensible call — but the file remains a live
status surface that will mislead any reader or automated check that trusts it.
**Required action:** leave the bytes as evidence, and add an adjacent `WATCHER_STATUS.INVALID`
marker so no consumer reads the stale record as current.

---

## SUMMARY

| Severity | Count | IDs |
| --- | --- | --- |
| BLOCKER | 3 | D-01, D-02, D-04 |
| HIGH | 5 | D-03, D-05, D-11, D-12, D-14 |
| MEDIUM | 8 | D-06, D-07, D-08, D-09, D-10, D-13, D-15, D-16 |
| PROCESS | 2 | D-17, D-18 |

**Single most urgent item: D-04** — an evidence-confirmed misstatement of mineral title in a file
already staged in PENDING FINAL VERIFICATION.
**Single most urgent control item: D-01 + D-02** — freeze the A10 lease before any writer consumes it.
