# DataBossX Title Report Engine v2

Evidence-based, deterministic **oil & gas title / ownership report** builder for
**Section 31-12N-24W, Roger Mills County, Oklahoma** (and reusable for any
section). It turns a runsheet + OGL sheet + formatting template into a clean
final XLSX with a full audit trail — **without inventing owners, leases, OGL
numbers, assignments, acreage, or book/page data.**

> **Runsheet controls. Template controls formatting. Engine controls the math.
> Audit log controls trust.**

---

## ⚠️ Read this first — where the real files live

This engine must be **run where the source files actually are**. In the cloud /
CI checkout there are **no** Section 31 source documents — no runsheet, no
`template.xlsx`, no OGL sheet. They live on the operator's machine, e.g.
`D:\Desktop\Horizon`. The cloud cannot see that drive, and the engine will
**never fabricate** the missing data. So:

- **On your Windows machine:** double-click `run_app.bat` (it targets
  `D:\Desktop\Horizon`) — or run the command below. It produces the real report.
- **In this repo:** the engine is proven end-to-end against a **clearly-labeled
  synthetic demo corpus** (`demo/`). The committed `demo/sample_output/` files
  show exactly what a real run produces. **That demo data is fake test data — it
  is not real Roger Mills title.**

## Run it (Windows, where the files live)

```bat
py -m pip install -r requirements.txt
py app.py --root "D:\Desktop\Horizon" --section "31-12N-24W" ^
    --output "D:\Desktop\Horizon\SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx"
```

or just: **`run_app.bat`**.

### Deliverables produced

| File | Location |
| --- | --- |
| Final ownership/title report (XLSX) | `<root>\SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx` |
| Audit log | `logs\SECTION31_AUDIT_LOG.xlsx` |
| Source-file ranking | `logs\SOURCE_FILE_RANKING.xlsx` |
| Copy of report + all inputs | `data\output\`, `data\input\` |

## Try the demo (any machine)

```bash
pip install -r requirements.txt
python demo/make_demo_data.py
python app.py --root demo/horizon_sample --section "31-12N-24W" \
    --output demo/horizon_sample/SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx
pytest tests/            # 15 passing end-to-end + unit tests
```

---

## Pipeline

```
ingest → parser → ogl_matcher → chain → verifier → writer
                     (audit records every material action throughout)
```

| Module | Job |
| --- | --- |
| `engine/ingest.py` | Discover + **rank** workbooks; detect runsheet / OGL / tract / overview sheets. |
| `engine/parser.py` | Map messy headers → structured `EvidenceRow` with `source_sheet`/`source_row`. |
| `engine/ogl_matcher.py` | Match leases to the OGL sheet; attach authoritative OGL numbers. |
| `engine/chain.py` | Chain ownership per tract; reject impossible conveyances; ASSN = leasehold only. |
| `engine/verifier.py` | Balance checks, review flags, evidence score, pre-export validation gate. |
| `engine/writer.py` | Export final XLSX **from the template**, preserving all formatting. |
| `engine/audit.py` | The trust record — every action + evidence + flag. |
| `engine/models.py` | Typed model; **Decimal** for all acreage/interest math. |

## Rules the engine enforces

- Runsheet is the controlling source; existing tract sheets are **not trusted**
  unless runsheet-backed.
- Title Sheet shows **final calculated owners only** (no intermediate owners who
  conveyed everything away).
- **OGL column contains OGL numbers only** — never assignment book/page.
- OGL number carried down beside each leased owner (Tract 1 pattern).
- Assignments recorded as **ASSN** and transfer **leasehold only**.
- Each tract totals **exactly** to its acreage (Decimal), or is flagged yellow.
- No negative ownership; a grantor cannot convey more than owned — such
  conveyances are **rejected and flagged**, never force-fit.
- **Yellow highlight = a true unresolved review item only.** No decorative color.
- Every material change is written to the **Audit Log** with its evidence source.

## Validation gate (must pass before export is trusted)

workbook opens · no `#REF!` · no negative acres/WI · every tract balances or is
flagged · OGL column holds only OGL-style refs · Title Sheet present · Audit Log
present · Review Flags present · output file exists.
