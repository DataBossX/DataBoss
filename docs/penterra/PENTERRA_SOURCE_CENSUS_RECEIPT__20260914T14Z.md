# PENTERRA COMPLETION — SOURCE-CENSUS-FIRST EXECUTION RECEIPT

`RECEIPT_UTC = 2026-09-14T14:00Z`
`WORKBOOK_WRITES = 0 · PACKAGE_WRITES = 0 · DRIVE_WRITES = 0 · WRITER_COUNT = 0`
`READY_TO_TURN_IN: P11 = NO · P13 = NO (owner action) · P14 = NO (owner action)`

Precedence honoured: SOURCE PIXELS > newest exact-target receipt > deterministic/native QA > model.
UNKNOWN was never converted to zero. No canonical source file was modified.

---

## 0. WRITER LAW — WHY NO PRODUCTION WRITE HAPPENED

The newest Drive control (`P11_PC_PARALLEL_FINISH_PROMPT__20260914.md`, 13:28:01Z) assigns
Lanes 1–4 of Campbell 11 to the **PC/Codex writer**, bound to R5 preimage
`df7b994b99aa023054d408cc397ff939b9bc4598c8a4cf7c85f7e174df20e815`. That writer published
`P11_SECTION11_RECONCILIATION_AUDIT__20260914.xlsx` and
`P11_SECTION11_OWNER_REVIEW_AND_RECONCILIATION__20260914.zip` at 13:27–13:28Z.

**One mutable target = one writer.** I did not acquire the P11 county workbook, the P11
federal workbooks, or any package. I executed only lanes that cannot collide: independent
census proof, and the deterministic toolkit.

Also read and obeyed: `PENTERRA_2PM_TARGET_ORDER__20260914.txt` (P13 primary, P14 fallback,
**P11 explicitly not the 2 PM primary**) and `PORTFOLIO_OWNER_REVIEW_CONTROL_ADDENDUM__20260914.md`.

---

## 1. P11 FEDERAL CENSUS — PROVED DETERMINISTICALLY

Reproduced by `penterra/tools/pdf_census.py` from the per-file part manifest, with SRPs held
strictly separate from casefile parts. **Every figure you specified reproduces exactly.**

| Serial | Casefile files | Casefile pages | SRP files | SRP pages | Total files | Total pages |
|---|---:|---:|---:|---:|---:|---:|
| WYW-005955 | **1** | **243** | 1 | 3 | 2 | 246 |
| WYW-047318 | **4** | **462** | 1 | 5 | 5 | 467 |
| WYW-051704 | **6** | **949** | 1 | 11 | 7 | 960 |
| **Casefile total** | **11** | **1,654** | — | — | — | — |
| **SRP total** | — | — | **3** | **19** | — | — |
| **Broader total** | — | — | — | — | **14** | **1,673** |

Part-page arithmetic, independently recomputed:
- WYW-047318: 189 + 177 + 94 + 2 = **462** ✓
- WYW-051704: 225 + 184 + 239 + 168 + 131 + 2 = **949** ✓
- Casefile: 243 + 462 + 949 = **1,654** ✓ · SRP: 3 + 5 + 11 = **19** ✓ · Broader: **1,673** ✓

`problems = []` — **no duplicate Part, no missing Part, no double-counted SRP or index.**
The tool is adversarially tested: it raises on an injected duplicate Part 3 and on a
Part-2 gap (see §3).

### Source-file → physical-page → report-event ledger (state)

The source-file → physical-page half is **complete and proved above**. The
→ report-event half is **open**, and the audit shows exactly where:

| Serial | R5 report rows | Fuller same-serial comparator | Gap |
|---|---:|---:|---|
| WYW-005955 | 32 | none established | 243-page casefile not proved abstracted; 59 explicit `Unknown` cells |
| WYW-047318 | 93 | 189 (Section 13) | Part 4 absent from R5 |
| WYW-051704 | 69 | 105 (Section 3) | Part 6 and a separate SRP label absent |
| **Total** | **194** | — | document/action accounting NOT complete |

Physical inventory complete; **report-level accounting is not**. Part 4 (2 pp.) and Part 6
(2 pp.) are physically present but unrepresented in R5 labels.

---

## 2. CAMPBELL 11 — 461-ENTRY UNIVERSE (READ-ONLY CONFIRMATION)

The controlling denominator is **461**, not 62. Confirmed from the 13:27Z audit:

| Measure | Count |
|---|---:|
| Handwritten tract-index rows (pp. 1–11: 45,44,42,44,44,42,41,40,42,41,21) | 446 |
| Typed Tyler rows (pp. 12–14) | 27 |
| Raw rows before dedup | 473 |
| **Controlling unique entries** | **461** |
| Implied handwritten/typed overlap (473 − 461) | **12 — ledger still unnamed** |
| County source PDFs / pages | 474 / 25,738 |
| Report rows in R5 | 62 |
| Verified tract-index matches | **57 (12.36% of 461)** |
| Reported absent | **401** (399 with source PDFs, 2 source-unknown) |
| **Unpartitioned: 461 − 57 − 401** | **3 — unnamed** |

**The partition does not close.** Three entries are unaccounted and twelve overlaps are
unnamed. Until both are named, no completion percentage is certifiable. `62/461 = 13.45%`
and `62/474 = 13.08%` are raw ratios that do **not** prove source-to-row matching; the only
defensible figure is **57/461 = 12.36%**.

`stable_key.dedupe()` is built and tested to produce exactly this artifact: it returns the
unique-key map **and names every overlap**, and its invariant `raw − unique == overlaps` is
asserted in the test suite. It is ready for the 461-key ledger the moment the writer is free.

---

## 3. DETERMINISTIC REUSABLE TOOLKIT — BUILT AND TESTED

`penterra/tools/` — nine tools, all pure/read-only, tested on synthetic fixtures only.
**62/62 assertions pass** (`python3 penterra/tests/test_tools.py`).

| Tool | Purpose | Notable proven behaviour |
|---|---|---|
| `stable_key` | tract-index stable-key parsing | handles modern `YYYY-NNNNN`, legacy, `25MR-0347`, `005M-0119`; **refuses** an empty identity; `dedupe()` names overlaps |
| `identity` | source-file identity matching | resolves the real `dddd-dddd` ambiguity (below); dispositions MATCHED/NON_INDEX/DUPLICATE/AMBIGUOUS/UNDETERMINED |
| `pdf_census` | PDF page/part census | reproduces all federal totals; detects duplicate and missing Parts; counts pages from the PDF object graph and cross-checks `/Count` |
| `dupe_pages` | duplicate-page SHA detection | separates cross-file duplicates (must be dispositioned) from intra-file repeats (usually legitimate) |
| `blanks` | blank classification | INTENTIONAL / INAPPLICABLE / SOURCE_MISSING / UNREADABLE / TRUE_HOLD; classes **partition exactly**; never returns a value |
| `parity` | Section-15 parity | compares presentation keys only; **raises `ParityViolation` if a fact key is offered**; skips known donor defects instead of inheriting them |
| `package` | CRC / SHA-256 / exact membership | detects extra members, container-hash drift, member-order drift; **fails closed** on a missing package |
| `replay` | no-replay detection | flags any re-assertion of a source-rejected value; strict mode raises |
| `lease` | one-writer lease/fence | atomic `O_CREAT\|O_EXCL` acquire; blocks a second writer; **blocks preimage drift**; fence strictly increases; stale writer blocked after handoff |

### A real defect the toolkit caught

`3305-0366` (BOOK-PAGE) and `2023-00118` (modern doc number) are **the same shape**:
`dddd-dddd`. Campbell book numbers have passed 3400, so a book literally numbered 2023
can exist. My first implementation silently mis-parsed `3305-0366.pdf` as a document
number — the test caught it. The fix does **not** guess: `candidate_keys()` emits every
reading, the tract index resolves which one is real, and a stem whose *both* readings exist
in the index is dispositioned **`AMBIGUOUS`** for face adjudication. This matters directly:
`3305-0366` and `1063795|3269-0038` are both live Section 11/13 identities.

---

## 4. CAMPBELL 14 — OWNER-STYLE READBACK ONLY (PRIORITY 1)

Exact-eight package preserved. **No reopen, no write, no hold reopened.**

- `P14_45N-76W-14__CODEX_SOURCE_PIXELS_CORRECTED_R2__20260914.zip`
- Drive ID `1_Yw6XOwVzLJbD28fyyMmSFweakc4Jkos` — **live**, 284,676 bytes
- Recorded SHA-256 `399bb218642a18b704f3947d28ed1fb947d551b142f75ea85a2b2a3d09db56d8`
- Direct-source corrections carried: `D13 = 5297`; `F24 = 09/12/2019`; `G24 = 09/18/2019`

**Readback checks performed:** object exists; single live copy at the controlling ID; byte
size stable; **receipt ordering correct** — the zip was last modified `12:39:59.872Z` and its
verifying receipt was written `12:42:20Z`, so the receipt postdates the bytes it attests.
No evidence of post-receipt mutation.

The **seven disclosed source holds were not reopened**, per instruction. No new source
arrived for them in this session.

---

## 5. P13 — READ-ONLY, UNCHANGED

No P13 write. The controlling artifact is now the corrected exact-five R2
(`P13_45N-76W-13_OWNER_REVIEW_SOURCE_MERGED_R2_EXACT5__20260914.zip`, SHA
`1ccee41336c8de6daee219d37376968a2c2c10365fff4f63f781b984ac06c986`), which supersedes the
earlier "source-union" claim whose ZIP was not found on Drive. My 12:40Z findings stand:
the four defects raised (SRP pull-date-as-Rec-Date, SRP serial in Grantee, Part 4
under-abstraction, `933403` date inversion) remain open and are unaffected by the R2 merge.

---

## 6. DECLARED LIMITATION — WHAT I CANNOT DO FROM HERE

The terminal gate you specified (native Excel/Word open → calculate → save → close →
reopen → exact value/formula diff → render EVERY outgoing page → CRC → SHA-256 every
member → local readback → Drive raw readback → independent final-byte referee)
**cannot be executed in this session.**

Drive returns file bytes only as base64 into the conversation. Reproducing them back to
disk fails integrity: a 24,058-byte ODS round-tripped to **11,207 bytes**, SHA
`fed8409a…` against the required `2ecc089d…`. That route is unreliable at package scale and
I will not report a gate as passed by inference.

`package.py` implements that gate correctly and is tested — it needs to run **on the PC**,
where the bytes and native Office are. It is written to be dropped straight into that lane.

---

## 7. NEXT UNIQUE BATCH

Non-colliding and executable by me now (no production writer needed):

1. **Name the 12 overlaps and the 3 unpartitioned entries** — needs the authenticated
   14-page tract-index PDF bound to `stable_key.dedupe()`. This is Blocker #1 on the P11
   release list and is pure read-only analysis.
2. **BLM document-start ledger for Parts 4 and 6** (2 pages each) — the smallest decisive
   source read that closes the two absent Part labels.
3. **WYW-005955 casefile reconciliation** — 243 pages, 32 rows, 59 `Unknown` cells; no
   comparator exists, so this is the largest federal gap.

Requiring the PC writer (do not start here): the 399-entry county abstraction, the native
terminal gate, metadata correction `Section 2 → Section 11`.

**Nothing was signed, certified, sent, renamed READY, or externally released.**
