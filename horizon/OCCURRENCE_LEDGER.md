# Occurrence / unique-key / candidate ledger

Use this gate to compare an isolated packet of index occurrences, a unique-key
ledger, and candidate rows (for example an R6 sheet). It does not open Drive,
PC, or chat roots and does not mutate a canonical workbook.

The packet must be assembled by a reviewer from source-bound identities. This
repository only ships synthetic fixtures. Prefer house stable keys from
`horizon.stable_key` (`<docno>|<book>-<page>`). If most rows are document
numbers only, run `horizon.reextraction_gate` first — that ledger cannot
correct itself.

## What it checks

- raw occurrence count versus unique keys derived from those occurrences
- unique keys from occurrences versus the supplied unique-key ledger
- candidate row count versus both unique-key universes
- duplicate, orphan, and missing stable keys
- source SHA-256 binding across occurrences, ledger, candidate, and allowlist
- field consensus among occurrences of the same key, then exact comparison
  to the candidate row
- resume-cursor / `closed_same_hash` skipping so already proved same-hash
  items are not re-reviewed blindly

Count and hash contradictions stay visible even when those items are skipped
for field re-review.

## Packet

```bash
python3 -m horizon.occurrence_ledger \
  --packet /path/to/isolated-packet.json \
  --output /path/to/ledger-receipt.json \
  --resume-cursor /path/to/resume-cursor.json \
  --write-resume-cursor /path/to/next-cursor.json
```

Exit codes:

- `0`: the packet has no ledger contradiction
- `2`: a receipt was written, but counts, hashes, or fields disagree
- `1`: the packet or cursor is malformed; no receipt is promised

`technical_pass` is ledger-consistency only. It is not package release, legal
correctness, or a substitute for `verify_snapshot` / workbook QA / native
Excel / human release.
