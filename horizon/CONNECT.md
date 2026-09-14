# Connection, occurrence build, and Drive readback

These gates do not finish a section package. They make the missing
Drive/PC/chat/OCR/Excel connections and the P11 crop→ledger hop
machine-checkable.

## Connection status

```bash
python3 -m horizon.connect_status \
  --root "pc=/mnt/d/DataBossX/Projects" \
  --root "drive=/mnt/g/My Drive/DataBossX/Projects" \
  --output /path/to/connect-status-receipt.json
```

`technical_pass` means at least one labeled root exists and is readable.
`packages_complete` stays false. Slack/Notion still need Cursor Desktop
auth. Do not start a second Landman Helper controller.

## Current cloud-agent blockers

This Linux cloud VM cannot finish live 15/13/11 packages. Re-probe each
run before treating a connection as available:

- No `cursor worker` is registered (`list-self-hosted-workers` is empty)
- Slack and Notion MCP still need Cursor Desktop authentication
- `/mnt` and `/media` are empty; no rclone/gdrive credentials
- Microsoft Excel, LibreOffice, tesseract, and pdftotext are not installed
- Client PDFs, xlsx masters, and handwritten indexes are not in this repo

The PC that can see Drive remains the only host that can run
`pc_operator --execute`, attest Print Preview / owner-review / 2+ source
delta drafts / one-source templates / Section 11 crop drafts, transcribe
hashed handwritten scans, and promote authority. OCR is not a source of
legal facts. Chat and OCR files hashed into
`sectionN-supporting-record-queue.json` are review-only and must not
fill index cells. After `--execute`, review `remaining-plan.json` in
order 15, then 13, then 11. Do not start a second controller.

## PC work order

On the host that can see Drive/PC roots:

```bash
python3 -m horizon.pc_operator \
  --root "pc=/mnt/d/DataBossX/Projects" \
  --root "drive=/mnt/g/My Drive/DataBossX/Projects" \
  --section 15 --section 13 --section 11 \
  --receipt-dir /mnt/d/DataBossX/AcquisitionReceipts \
  --output /mnt/d/DataBossX/AcquisitionReceipts/pc-operator.json
```

The operator probes connections, runs Phase 1 inventory, writes
`authority-draft.json` (`UNAPPROVED_DRAFT`) under `--receipt-dir`, and
emits per-section next commands (three-workbook `index_export`, PDF census
inventory, then `package_finish`). Pass `--execute` on the PC to run those isolated hops
into a private `--receipt-dir` outside this repository. It does not copy
client files into the repo. A named examiner runs `horizon.authority_promote`
with live roots; the next `--execute` discovers the promoted manifests and
takes a Phase 2 snapshot. Phase 2 requires both a typed `index` and a
`handwritten_index`; one cannot substitute for the other. See
[`PC_OPERATOR.md`](PC_OPERATOR.md).

## Occurrence packet from page-render crops

```bash
python3 -m horizon.occurrence_build \
  --page-render-packet /path/to/page-render-crop-packet.json \
  --output /path/to/occurrence-packet.json
```

The finish runner builds this automatically when `--page-render-packet` is
passed without `--occurrence-packet`. Bare-docno crops are `high_risk`.

## Drive readback

```bash
python3 -m horizon.drive_readback \
  --workbook /path/to/isolated-letter.xlsx \
  --readback /path/to/drive-copy.xlsx \
  --output /path/to/drive-readback-receipt.json
```

The two paths must be distinct files with the same SHA-256. The PC
operator may publish the isolated Letter/delta onto a mounted `drive=`
section folder so this gate can bind; the gate itself still only compares
hashes and does not upload.
