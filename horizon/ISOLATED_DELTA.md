# Isolated source-proved deltas

Apply a writer-held packet to an **isolated workbook copy**. The source
workbook is never overwritten. New rows are not invented. This is not
package release.

Use this when a face or page crop has proved a blank required cell (legal,
party, recorded date, or document type) and a human writer holds the packet.
Do not hard-code client facts into the repository.

## Packet

Schema `dbx.source_proved_delta_packet` / `1.0`. Required top-level keys:

- `packet_id`
- `source_workbook_sha256` — SHA-256 of the **current** source workbook
- `deltas` — non-empty list

Each delta requires `row_key`, `field`, `value`, `source_sha256`, `page`,
`crop_id`, and `replace`.

`row_key` is the house stable key `<docno>|<book>-<page>`. A bare document
number is treated as `<docno>|` and matches only a row whose book/page is
empty. Two rows that share a document number are distinguished by book/page.

Allowed fields: `document_type`, `grantor`, `grantee`, `recorded_date`,
`legal_description`, `book_page`, `document_date`, `comments`.
`instrument_number` cannot be rewritten.

Values must be non-empty source text. Double commas (`,,`) are rejected.
Newlines are allowed only on grantor, grantee, and legal description.

`replace` must be `true` only when the writer has source proof that the
already-populated cell is wrong. Otherwise a differing populated cell fails
closed and the isolated copy is deleted.

Write a packet from examiner-held deltas. Horizon does not invent values.

`pc_operator --execute` writes `sectionN-delta-draft.json`
(`dbx.source_proved_delta_draft`, `UNAPPROVED_DRAFT`) only for remaining
medium/high (2+ source) blanks. One-source blanks and conflicts stay out.
That draft cannot bind `isolated_delta`. Attest it with a named examiner.

```bash
python3 -m horizon.isolated_delta \
  --attest \
  --from-draft /path/to/section15-delta-draft.json \
  --workbook /path/to/isolated-letter.xlsx \
  --output /path/to/source-proved-delta.json \
  --operator "Pat Examiner"
```

After a packet is applied, the operator archives it and keeps the newest
`sectionN-delta.xlsx` / `sectionN-delta-2.xlsx` / … as the current isolated
workbook. A later hash-matched packet applies onto the next generation
instead of freezing the first copy.

The older path still wraps examiner-authored `sectionN-deltas.json` for
one-source source-proved fills:

```bash
python3 -m horizon.isolated_delta \
  --write \
  --workbook /path/to/isolated-letter.xlsx \
  --deltas /path/to/examiner-deltas.json \
  --output /path/to/source-proved-delta.json \
  --packet-id SECTION13-DELTA
```

## Command

```bash
python3 -m horizon.isolated_delta \
  --workbook /path/to/source-index.xlsx \
  --packet /path/to/source-proved-delta.json \
  --output /path/to/isolated-index.xlsx \
  --receipt /path/to/isolated-delta-receipt.json
```

The finish runner can chain this before workbook QA:

```bash
python3 -m horizon.package_finish \
  --section 13 \
  --workbook /path/to/source-index.xlsx \
  --delta-packet /path/to/source-proved-delta.json \
  --delta-output /path/to/isolated-index.xlsx \
  --output /path/to/package-finish-receipt.json
```

Exit codes:

- `0`: every delta applied or already present; copy written
- `2`: receipt written but `technical_pass` is false
- `1`: packet, hash, or apply failed; no isolated copy is left behind

`technical_pass` is not package release. Native Excel Print Preview, Drive
readback, and a human release token remain required.
