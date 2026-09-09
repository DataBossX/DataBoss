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

## Phase 1: inventory candidates

```bat
py -m horizon.source_acquisition ^
  --root "pc=D:\DataBossX\Projects" ^
  --root "drive=G:\My Drive\DataBossX\Projects" ^
  --root "chat=D:\DataBossX\PrivateChatExports" ^
  --section 15 --section 13 --section 11 ^
  --output "D:\DataBossX\AcquisitionReceipts\sections-15-13-11.json"
```

This first receipt is expected to exit `2`. Filename classification is only a
candidate inventory and cannot establish legal authority. Review its hashes,
then create a separate authority manifest from an approved custody or examiner
decision:

```json
{
  "schema_id": "dbx.source_authority_manifest",
  "schema_version": "1.0",
  "authorities": [
    {
      "root_label": "pc",
      "relative_path": "Section 15/Master Abstract.xlsx",
      "section": 15,
      "role": "master_workbook",
      "expected_sha256": "<approved 64-character SHA-256>"
    },
    {
      "root_label": "pc",
      "relative_path": "Section 15/County Index.pdf",
      "section": 15,
      "role": "index",
      "expected_sha256": "<approved 64-character SHA-256>"
    },
    {
      "root_label": "pc",
      "relative_path": "Section 15/Recorded Faces/Instrument 1.pdf",
      "section": 15,
      "role": "source_document",
      "expected_sha256": "<approved 64-character SHA-256>"
    }
  ]
}
```

Authority assertions use exact root labels, case-sensitive relative paths,
sections, roles, and hashes. Missing files, changed hashes, duplicate
assertions, path traversal, unknown roots, and unrequested sections fail
closed.

## Phase 2: authorize intake

```bat
py -m horizon.source_acquisition ^
  --root "pc=D:\DataBossX\Projects" ^
  --root "drive=G:\My Drive\DataBossX\Projects" ^
  --root "chat=D:\DataBossX\PrivateChatExports" ^
  --section 15 --section 13 --section 11 ^
  --authority-manifest "D:\DataBossX\Controls\source-authority.json" ^
  --output "D:\DataBossX\AcquisitionReceipts\sections-authorized.json"
```

Exit codes:

- `0`: every requested section has hash-matched authority assertions for all
  required roles and no path conflicts, rejected links, unstable files, or
  traversal failures.
- `2`: a receipt was written, but intake is blocked.
- `1`: CLI controls, roots, authority manifest, or output location are unsafe
  or malformed; no receipt is promised.

The default required roles are:

- `source_document`: a recorded face or other authoritative document/image;
- `master_workbook`: an examiner-authorized current master;
- `index`: an examiner-authorized typed or handwritten index.

Require an explicit handwritten index when the project calls for one:

```bat
py -m horizon.source_acquisition ^
  --root "pc=D:\DataBossX\Projects" ^
  --root "drive=G:\My Drive\DataBossX\Projects" ^
  --section 15 ^
  --authority-manifest "D:\DataBossX\Controls\section-15-authority.json" ^
  --require-role source_document ^
  --require-role master_workbook ^
  --require-role index ^
  --require-role handwritten_index ^
  --output "D:\DataBossX\AcquisitionReceipts\section-15.json"
```

Folders or filenames must explicitly identify the section, for example
`Section 15`, `sec_13`, or `11-45N-76W`. Instrument numbers containing `11`,
`13`, or `15` are not treated as section identifiers. Root labels must identify
their source kind: `pc`, `drive`, `chat`, or a suffixed form such as `drive_2`.

## Resolve a blocked receipt

- `hash_conflict`: preserve both files and obtain an authority decision; never
  choose by modification time.
- `source_symlink_rejected`, `source_directory_symlink_rejected`, or
  `source_traversal_failed`: mount and scan the actual readable source.
- `source_empty`: reacquire the zero-byte file.
- `source_link_or_race_rejected` or `source_changed_after_hash`: stop writers
  and rerun against a stable snapshot.
- `authority_file_missing`, `authority_hash_mismatch`, or
  `authority_source_unstable`: correct the custody decision or reacquire the
  exact asserted bytes.
- missing required role: add a valid authority assertion; renaming a candidate
  does not satisfy the gate.

A passing receipt proves only that externally authorized source categories are
present, byte-accounted, stable during the point-in-time scan, and free of
same-path conflicts. It does not prove the legal facts inside them. Next run
OCR/extraction, row-level provenance and confidence, master/index
reconciliation, strict workbook QA, native Excel Print Preview, Drive readback,
and the hash-bound human release gate.
