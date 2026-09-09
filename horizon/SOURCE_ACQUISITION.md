# Section Source Acquisition

Run source acquisition where Google Drive for Desktop and the local project
folders are visible. The gate only reads and hashes source files, then writes a
receipt outside the source roots. It never copies, deletes, renames, uploads,
or chooses an authoritative file.

## Prepare private source roots

1. If Slack or Notion records are needed, authenticate from Cursor Desktop.
   Cloud agents cannot complete interactive sign-in.
2. Mount Google Drive with Google Drive for Desktop, or download a byte-exact
   private copy. Never put client documents or exported chats in this public
   repository.
3. When chat instructions or custody receipts are evidence, export them to a
   private local folder.
4. Keep receipt output in a separate audit folder, outside every source root.

Example Windows layout:

```text
D:\DataBossX\Projects\                 local working files
G:\My Drive\DataBossX\Projects\        Google Drive for Desktop
D:\DataBossX\PrivateChatExports\       Slack/Notion exports
D:\DataBossX\AcquisitionReceipts\      generated JSON receipts
```

## Run the priority intake gate

```bat
py -m horizon.source_acquisition ^
  --root "pc=D:\DataBossX\Projects" ^
  --root "drive=G:\My Drive\DataBossX\Projects" ^
  --root "chat=D:\DataBossX\PrivateChatExports" ^
  --section 15 --section 13 --section 11 ^
  --output "D:\DataBossX\AcquisitionReceipts\sections-15-13-11.json"
```

Exit codes:

- `0`: every requested section has the required source roles and no same-path
  hash conflicts or rejected source links.
- `2`: the receipt was written, but intake is blocked.
- `1`: the roots or output location are unsafe or malformed.

The default required roles are:

- `source_document`: a recorded face or other authoritative document/image;
- `master_workbook`: a workbook whose name includes `master`, `report`, or
  `runsheet` (an abstract checklist alone is not a master);
- `index`: a typed or explicitly named handwritten index.

Require an explicit handwritten index when the project calls for one:

```bat
py -m horizon.source_acquisition ^
  --root "pc=D:\DataBossX\Projects" ^
  --root "drive=G:\My Drive\DataBossX\Projects" ^
  --section 15 ^
  --require-role source_document ^
  --require-role master_workbook ^
  --require-role index ^
  --require-role handwritten_index ^
  --output "D:\DataBossX\AcquisitionReceipts\section-15.json"
```

Folders or filenames must explicitly identify the section, for example
`Section 15`, `sec_13`, or `11-45N-76W`. Instrument numbers containing `11`,
`13`, or `15` are not treated as section identifiers.

## Resolve a blocked receipt

- `hash_conflict`: the same relative path differs between roots. Preserve both
  files and obtain an authority decision; do not choose by modification time.
- `source_symlink_rejected`: acquire the actual file and hash it directly.
- `source_empty`: reacquire the zero-byte file.
- `source_changed_during_hash`: stop writers and rerun against a stable snapshot.
- missing `source_document`: no recorded face or source document was found.
- missing `master_workbook`: identify the current master candidate.
- missing `index` or `handwritten_index`: acquire and name the index explicitly.

A passing receipt proves only that the expected source categories are present,
byte-accounted, and free of same-path conflicts. It does not prove the legal
facts inside them. Next run OCR/extraction, row-level provenance and confidence,
master/index reconciliation, strict workbook QA, native Excel Print Preview,
Drive readback, and the hash-bound human release gate.
