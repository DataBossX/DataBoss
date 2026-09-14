# PC work-order operator

One command for the machine that can see section 15/13/11 files. It does
**not** finish a package.

```bash
python3 -m horizon.pc_operator \
  --root "pc=/mnt/d/DataBossX/Projects" \
  --root "drive=/mnt/g/My Drive/DataBossX/Projects" \
  --section 15 --section 13 --section 11 \
  --execute \
  --receipt-dir /mnt/d/DataBossX/AcquisitionReceipts \
  --output /mnt/d/DataBossX/AcquisitionReceipts/pc-operator.json
```

## What it does

1. Probes labeled roots, Excel/OCR tools, Slack/Notion Desktop auth, and
   whether a `cursor worker` is registered on this host.
2. If at least one root exists and is readable, runs **Phase 1** source
   inventory (hash + classify). It does **not** take a Phase 2 snapshot and
   does **not** treat filename classification as legal authority.
3. When `--receipt-dir` is set (with or without `--execute`), writes
   `authority-draft.json` (`dbx.source_authority_draft`, status
   `UNAPPROVED_DRAFT`). Empty `project_id` / `decision_id` / `approved_by`.
   That file cannot be passed as `--authority-manifest`. The receipt names a
   `horizon.authority_promote` command. A named examiner replaces
   `EXAMINER_PROJECT_ID` / `EXAMINER_DECISION_ID` / `EXAMINER_NAME`, confirms
   sections whose required roles are classified, and the promoter re-hashes
   live roots before writing `source-authority.json` plus a hash-bound
   `project_manifest.json`. A later `--execute` on the same receipt-dir
   discovers those files and snapshots `intake-snapshot/sectionN`. Later
   executes verify that snapshot from `sectionN-acquisition.json` and export
   authorized workbooks from the snapshot, not from drifted live files.
   Writer-held native-print, owner-review, page-render crop, source-proved
   delta, and PDF census JSON dropped in the receipt directory are discovered
   on the next `--execute`. A `sectionN-pdfs/` directory is bound as
   `--pdf-bind-dir`. If that directory exists and no census packet is present,
   `--execute` inventories it (`expected_pages` = counted `/Type /Page`, not
   a row count) into `sectionN-pdf-census-packet.json`. After Phase 2,
   authorized `source_document` PDFs in the snapshot are measured the same
   way when `sectionN-pdfs/` is absent. Deltas apply to an isolated
   `sectionN-delta.xlsx`. Native print, owner-review, and Drive readback
   bind that current isolated workbook, not a stale Letter copy. When a
   `drive=` root is mounted, `--execute` publishes that isolated file into
   the Drive section folder (it will not overwrite a different hash) and
   binds SHA-256 readback.    Client source files are never copied into this
   repository.    After recon/repair, `--execute` writes
   `sectionN-examiner-queue.json` listing remaining blanks and conflicts
   with provenance. One-source blanks stay blank until a writer-held
   source-proved delta. It also writes `sectionN-native-print-draft.json`
   bound to the current isolated workbook hash. Attest that draft after
   Windows Excel Print Preview; Horizon does not invent the page count.
   Native-print and owner-review packets that do not match the current
   isolated hash are unbound so the next command reprints and reissues.
   `--execute` also writes `sectionN-owner-review-draft.json`; attest it
   with a named examiner after owner review only.
4. For each requested section, names classified-file gaps and still-unauthorized
   required roles, picks the first sorted master / PDF-index / handwritten /
   working workbook candidates, and writes copy-paste `horizon.index_export`
   plus `horizon.package_finish` commands that point at a private receipt
   directory.
5. With `--execute`, those isolated hops actually run into `--receipt-dir`.
   The directory must be outside this repository. Source workbooks are not
   modified. Writer-held `--authority-manifest` / `--project-manifest` /
   `--snapshot-directory` are passed through so Phase 2 can authorize
   acquisition.    Page-render, native-print, owner-review, and PDF census JSON packets
   are discovered by `schema_id` when present, or passed explicitly.
   Census packets are kept on the matching `SECTION{N}` / `sectionN` id.
   `packages_complete` is true only if every requested section's finish
   receipt already satisfies the owner-review completion predicate.

## What it never does

- Copy client files into this public repository
- Invent legal, party, recorded-date, or document-type values
- Start a second Landman Helper controller
- Claim `packages_complete` from Phase 1 or from an unapproved draft
- Treat filename classification as legal authority
- Bind `authority-draft.json` as Phase 2

`technical_pass` means Phase 1 inventory ran against readable roots.
`--execute` does not start Phase 2 and does not invent field values.
Phase 1 is expected to leave required-role gaps until a human-approved
authority manifest exists. Receipt schema `1.3` records the draft path and
the promote command.

Do not commit the operator receipt. It can contain private paths and hashes.
