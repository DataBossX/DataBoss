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

The two paths must be distinct files with the same SHA-256.
