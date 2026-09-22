# Source-bound finish toolkit

Deterministic, fail-closed helpers for abstract-package finishing.

This package is **public-safe machinery**. It does not contain client sources,
legal descriptions, owner names, Drive identifiers, or certified abstracts.

## Rules

- Original source pixels/bytes outrank OCR and model consensus.
- `UNKNOWN` is not `ZERO`. Missing evidence stays blank or `UNRESOLVED`.
- Physical pages are not client rows. Only a `MATERIAL_START` earns a row.
- One material document or agency action gets one physical start page.
- Client Comments stay blank except the exact lowercase phrase `missing image`.
- A preparation date is never a search-through or instrument date.
- Filing is not approval.
- An index locator is not a recorded face.
- No sole-writer acknowledgement means `REPORT_WRITES=0`.

## Commands

```bash
python -m source_bound_finish access --root /path/to/local/sources
python -m source_bound_finish census --root /path/to/local/sources
python -m source_bound_finish ledger file-a.pdf file-b.pdf
python -m source_bound_finish purity rows.json
python -m source_bound_finish package package.zip --member report.xlsx
python -m source_bound_finish tournament packet.json --receipt cycle.json
```

Run these on the machine that already holds the authenticated source files.
This cloud checkout does not include those files.

## Tournament dimensions

Each cycle independently tests:

| Code | Dimension |
| --- | --- |
| A | Source completeness |
| B | Factual / stable-key |
| C | Client purity / format |
| D | Native reopen / every rendered page |
| E | Byte / package membership, SHA-256, ZIP CRC |

A cycle is `COMPLETE` only when all five dimensions `PASS` on fresh evidence.
A cached identical receipt does not increment the clean-cycle count.
Five repetitions cannot cure a missing source.

## Publication boundary

Do not commit real project manifests, source hashes of client files, folder
IDs, or candidate workbooks to this public repository. Keep those in an
approved private workspace.
