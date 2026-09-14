# Master / PDF / handwritten index reconciliation

Compare three named source indexes against the isolated candidate. Score
every required field (document type, grantor, grantee, recorded date, legal
description) with provenance and confidence. The gate does not open Drive,
invent rows, or apply fills.

## Confidence

| Sources that agree on the same stripped value | Confidence | Isolated delta |
|---|---|---|
| 3 | high | proposed if the candidate cell is blank |
| 2, third absent | medium | proposed if the candidate cell is blank |
| 1 | low | never proposed |
| 2+ disagree, or candidate differs | conflict | never proposed |

A single source is not enough to fill a blank. Conflicts block
`technical_pass`. Unexpected orphans (a key missing from one of the three
sources) also block unless the packet names them on `orphan_allowlist` with
the exact `present_in` set and a source hash.

`expected_counts` is required and must match the packet lists. Put live
section counts in the PC packet, not in this repository.

## Command

```bash
python3 -m horizon.index_reconciliation \
  --packet /path/to/index-reconciliation-packet.json \
  --output /path/to/index-reconciliation-receipt.json
```

The finish runner accepts the same packet:

```bash
python3 -m horizon.package_finish \
  --section 15 --section 13 --section 11 \
  --index-packet /path/to/index-reconciliation-packet.json \
  --output /path/to/package-finish-receipt.json
```

Proposed deltas in the receipt are writer-held. Apply them only through
`horizon.isolated_delta` against a copy whose SHA-256 matches the delta
packet. `technical_pass` is not package release.

## Export and repair loop

Export a Penterra workbook as faces, or run up to 10 isolated
detect-and-repair passes. Each pass refreshes `candidate_rows` from the
current copy, reconciles, and applies only medium/high proposals to a **new**
file. Conflicts apply nothing. The original workbook is not modified.

```bash
python3 -m horizon.index_export \
  --workbook /path/to/source-index.xlsx \
  --packet-id SYNTH-OR-LIVE-PACKET \
  --output /path/to/candidate-faces.json

python3 -m horizon.index_export \
  --packet-id SYNTH-OR-LIVE-PACKET \
  --master /path/to/master.xlsx \
  --pdf-index /path/to/pdf-index.xlsx \
  --handwritten /path/to/handwritten.xlsx \
  --candidate /path/to/working-index.xlsx \
  --output /path/to/index-reconciliation-packet.json

python3 -m horizon.repair_loop \
  --workbook /path/to/source-index.xlsx \
  --index-packet /path/to/index-reconciliation-packet.json \
  --output-dir /path/to/isolated-repair \
  --receipt /path/to/repair-loop-receipt.json \
  --packet-id live-repair \
  --max-loops 10
```

`--master-workbook`, `--pdf-workbook`, and `--handwritten-workbook` can
replace a pre-built packet when those indexes are themselves Penterra
workbooks. `packages_complete` stays false.

Remaining one-source blanks and conflicts are written to
`sectionN-examiner-queue.json` by `horizon.examiner_queue` / `pc_operator
--execute`. That queue does not invent values. The examiner puts only
source-proved text in `sectionN-deltas.json`.
