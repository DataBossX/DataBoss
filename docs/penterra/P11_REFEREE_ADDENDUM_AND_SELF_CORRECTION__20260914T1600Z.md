# P11 REFEREE — ADDENDUM, SELF-CORRECTION, AND LIVE BATCH CONFLICT

`RECEIPT_UTC = 2026-09-14T16:00Z`
`MODE = READ-ONLY REFEREE · WRITES = 0 · WRITER_COUNT = 0`

New PC-writer artifacts appeared at 14:11–15:10Z. Refereed read-only. The P11 writer was
not taken.

---

## 1. SELF-CORRECTION — I was wrong about 17 vs 37

In `P11_TRACT_LEDGER_REFEREE__20260914T1505Z.md` I wrote that the scrub's
`MATCHED_IN_REPORT = 37` had **"no row-level basis"** and that **"17 is the only match count
with a row-level basis."**

**I withdraw that.** `T194_EXECUTION_RECEIPT__GROK_SCRUB.md` documents the delta as
**"+20 Vision DocNo recoveries"** — a genuine second pass over the page renders that
recovered 20 document numbers previously carried as `SOURCE_UNREADABLE`, moving them to
`MATCHED_IN_REPORT` and taking `SOURCE_UNREADABLE` from 189 to 169.

My error was one of scope, not arithmetic: I refereed `P11_TRACT_INDEX_LEDGER__t194.csv`
(13:54Z) and did not open `P11_TRACT_INDEX_LEDGER__t194_SCRUBBED.json` (14:09Z), which
postdates it. The pre-scrub ledger legitimately shows 17; the scrub is a later, better read.
**37 is supported.** The scrubbed ledger remains the artifact that settles it row-by-row, and
I have not opened it — so I assert only that my "no basis" claim was unfounded.

---

## 2. CORROBORATED — 437 is independently confirmed, and 461 is explicitly rejected

Grok's receipt states, unprompted and from the other side of the work:

> `Page-count audit: **CONFIRMED 437** (Vision 45/41/43/43/42/40/41/39/43/40/20)` —
> **"no adjust; do not invent to 461"**

That is the same per-page vector and the same conclusion I reached independently at 14:35Z.
Two separate readers, from different directions, now reject 461 in favour of the measured
437. **This item is closed.**

Grok also independently flags **"digit-ambiguous candidates left unread (e.g. 395790)"**,
which corroborates my doc-number accuracy finding from a different angle.

---

## 3. WITHDRAWN IN PART — the mineral batch is better built than I assumed

I recommended freezing the insertion queue outright. Having now read
`P11_NEXT_MINERAL_BATCH.json`, that was too broad. Each queued item carries:

```
instrument_key       : COUNTY:DOC:842508|BP:2016-0067
representation_key   : TRACT:P09:L014|COUNTY:DOC:842508|BP:2016-0067
source_files[].sha256: 9af64fec878e71b01c4c943dc636d7cf16cbc45445323bd136f668ab2a7f9f1f
```

It is keyed on **document number AND Book/Page**, bound to a **source file SHA-256**, and
anchored to a **tract page/line**. That is the cross-key method I recommended, already in
use, plus `mineral_with_reused_hash_bound_direct_review: 89`. **The batch is not the blind
doc-number operation I warned against**, and my blanket freeze recommendation is withdrawn
for items built this way.

---

## 4. LIVE CONFLICT in the queued batch — item 2 should not be worked as keyed

Cross-keying all four queued items against the Section 13 workbook oracle:

| Tract | Batch DOC | Batch BP | Oracle verdict |
|---|---|---|---|
| P09 L014 | `842508` | `2016-0067` | **OK** — oracle agrees `842508` owns `2016-0067` |
| P09 L024 | `866196` | `2132-0102` | **CONFLICT** |
| P11 L012 | `1055623` | `3215-0026` | **OK** — oracle agrees |
| P12 L009 | `2020-01337` | `3287-0533` | oracle silent — cannot corroborate |

**The conflict:** the Section 13 workbook records Book/Page **`2132-0102`** as belonging to
document **`864987`** — *Memorandum of Operating Agreement*, Wms Prod. RMT et al → The
Public, recorded 2/27/2006. The batch keys that same Book/Page to document **`866196`**, with
character *"Supp. Memo Oper. Agree.?"*.

Digit distance `866196` vs `864987` is **4** — far too large for the single-digit
substitutions seen elsewhere. So this is **not** an ordinary misread. Either:

- the tract line genuinely names a *different* instrument (a supplemental memorandum) and the
  Book/Page binding is wrong, or
- the Book/Page is right and the document number is wrong.

**Both halves of `instrument_key` cannot be correct.** This item should be adjudicated from
the face before it is worked. Note the batch's own character string already carries a
question mark, so the uncertainty was detected — it simply was not blocked.

---

## 5. Two further observations on the batch

**Item 4 has no source at all.** `2020-01337 | 3287-0533` carries `source_files: []`. It is
queued for direct review with nothing to review — one of the two `omitted_source_missing`
entries. It should be dispositioned **`SOURCE_MISSING`**, not queued for a review that cannot
happen.

**Item 3's source is 642 pages / 58.8 MB** for a single ORRI conveyance. The identity is
sound (`1055623 | 3215-0026`, corroborated by the oracle as Moriah Powder River → Powder
River VPP, 7/10/2019 → 7/24/2019), but a one-instrument ORRI conveyance is rarely 642 pages.
The Book/Page binding has likely pulled an entire photo book rather than the instrument.
Worth confirming before a reviewer is pointed at it — this is a source-binding question, not
an identity question.

---

## 6. Remaining denominator inconsistency

`P11_NEXT_MINERAL_BATCH.json` (15:10Z) still carries:

```
tract_denominator : 461
partition         : MATCHED 57 | OMITTED 401 | UNRESOLVED 3
```

while Grok's 14:11Z receipt says **CONFIRMED 437, do not invent to 461**. Two live artifacts
in the same hour disagree on the controlling denominator, and the batch still carries the
old 461-based partition. **This is the one item from my 14:35Z referee that remains open.**

---

## Standing position, revised

| Item | Status |
|---|---|
| Denominator 437, not 461 | **corroborated** by Grok independently — but not yet propagated to the batch summary |
| `MATCHED_IN_REPORT = 37` | **accepted**; my "no basis" claim withdrawn |
| Blanket freeze on the insertion queue | **withdrawn** for Book/Page + SHA-keyed items |
| Batch item 2 (`866196` / `2132-0102`) | **hold** — key conflict, adjudicate from the face |
| Batch item 4 (`2020-01337`) | **reclassify** `SOURCE_MISSING`; cannot be reviewed |
| Batch item 3 source binding | **confirm** — 642 pages for one ORRI conveyance |
| Doc-number error rate 15–19% on unscrubbed pages | **stands** |
| County workbook row total (68 measured vs 61/56/62) | **stands, unanswered** |

Nothing was written. No ledger, workbook, batch or package was modified.
