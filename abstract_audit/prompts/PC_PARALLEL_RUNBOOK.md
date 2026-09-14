# PC Parallel Runbook — Abstract 4576

Drop-in instructions for running the same audit locally, in parallel with
the Drive-side work. Point each worker at a different slice so they never
touch the same files.

## 0. One-time setup

```bash
pip install openpyxl pytest
python -m pytest tests/ -q        # expect 8 passed
```

## 1. Ground truth first (no AI needed)

```bash
python run_audit.py --root "D:/Abstract4576" --json status_local.json
```

This prints, and writes to JSON:
- BLM lease count, part-PDF count, and **any missing `Part N of M`**
- image counts per section and **any gap in the numbered sequence**
- per-index row counts, required-cell fill rate, blank-cell locations,
  duplicate document numbers
- one overall percent-complete figure

Run this **before** and **after** any AI pass. The delta is the real
progress measurement — not the model's self-report.

## 2. Vision extraction slices

Split by section so workers never collide. One worker per slice:

| Worker | Slice | Input |
| --- | --- | --- |
| A | Section 11 | `p11-index-*.png` |
| B | Section 13 | `p13-index-*.png` |
| C | Section 14 | `p14-index-*.png` |
| D | BLM serial register pages | `Serial Register Page WYW-*.pdf` |

### Vision prompt (use verbatim)

> You are transcribing a handwritten/scanned county records index for an
> oil & gas mineral title abstract, Campbell County Wyoming, T45N-R76W.
>
> Return **CSV only**, no prose, with exactly these 9 columns in this order:
> `Document Type,Grantor,Grantee,Doc No,Book-Page,Date of Doc,Rec Date,Legal Description,Comments`
>
> Rules:
> - One CSV row per document entry. Do not merge or split entries.
> - `Doc No` is either 4-8 digits (`1043044`) or `YYYY-NNNNN` (`2026-03115`).
> - `Book-Page` looks like `3145-0695` or `20LIEN-0432`. Modern e-recorded
>   documents have **no** Book-Page — leave it empty, do not invent one.
> - Dates are `M/D/YYYY`. If a year is ambiguous, leave the cell empty.
> - Legal descriptions use the section's own form, e.g.
>   `All of 15-45N-76W, aol`, `Lots 11-14 of 15-45N-76W, aol`,
>   `SW/4 of 15-45N-76W, aol`, or `Outside Lands Only`.
> - **If a value is not legible, leave the cell empty.** Never guess a
>   grantor, grantee, document number, or date. An empty cell is a task;
>   a wrong cell is a defect that survives review.
> - Quote any field containing a comma.

### Why "leave it empty" matters

`index_audit.py` reports blank required cells with their row numbers, so
empty cells become a worklist. Invented values look complete and pass
straight through to turn-in. Never trade a blank for a guess.

## 3. Merge and re-audit

Append each worker's CSV under the 7-row header block, keeping column
order, then:

```bash
python index_audit.py "45N-76W-14_Campbell_Co_Penterra_Abstract_Index.xlsx"
```

Fix what it flags. Re-run until `blanks=0` and `dupes=0`.

## 4. Header block — set the date

Every turn-in workbook needs its header block current:

```
Index County:      Campbell
Lands:             T45N-R76W Section NN: All
Date:              9/14/2026
Starting Date:     Inception
Date Posted Thru:  <the county's actual posted-through date>
Indexed By:        Ryan Gille
Project:           Abstract 4576 Overtime
```

`Date` is when the index was produced. `Date Posted Thru` is a fact about
county records — it is **not** today's date and must not be changed to
match it.

## 5. Model routing

| Task | Route to |
| --- | --- |
| Handwriting / faint scans | Strongest vision model available |
| Clean typed pages | Cheaper/faster vision model |
| CSV cleanup, dedupe, legal-description normalization | Local text model |
| Final conformance check | `run_audit.py` — deterministic, not a model |

Never let a model be the last word on a count. The script is.
