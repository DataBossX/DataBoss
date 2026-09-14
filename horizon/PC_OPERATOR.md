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
   sections whose required roles are classified (source document, master,
   typed index, and handwritten index as separate faces), and the promoter re-hashes
   live roots before writing `source-authority.json` plus a hash-bound
   `project_manifest.json`.    A later `--execute` on the same receipt-dir
   discovers those files and snapshots `intake-snapshot/sectionN`. Later
   executes verify that snapshot from `sectionN-acquisition.json` and export
   authorized workbooks from the snapshot, not from drifted live files.
   The leftover `authority-draft.json` rewrite cannot override
   `source-authority.json`; receipt next-actions stop asking for promote.
   Writer-held native-print, owner-review, page-render crop, source-proved
   delta, and PDF census JSON dropped in the receipt directory are discovered
   on the next `--execute` only when the filename or `packet_id` names that
   section. First-wins discovery is per section, not across the shared
   receipt directory. A `sectionN-pdfs/` directory is bound as
   `--pdf-bind-dir`. If that directory exists and no census packet is present,
   `--execute` inventories it (`expected_pages` = counted `/Type /Page`, not
   a row count) into `sectionN-pdf-census-packet.json` and lists
   image-only empty-text files in `sectionN-empty-text-queue.json`.
   After Phase 2,
   authorized `source_document` PDFs in the snapshot are measured the same
   way when `sectionN-pdfs/` is absent. Deltas apply to an isolated
   `sectionN-delta.xlsx`. Native print, owner-review, and Drive readback
   bind that current isolated workbook, not a stale Letter copy. When a
   `drive=` root is mounted, `--execute` publishes that isolated file into
   Drive `Section N/Isolated/` (it will not overwrite a different hash) and
   binds SHA-256 readback. A receipt-dir same-hash copy can satisfy the
   hash gate. After `--execute` publishes Isolated/, a leftover
   receipt-dir bind is upgraded so finish records `isolated_copy`.
   Remaining-plan and next-commands keep
   `Copy {name} into Drive Section N/Isolated/` until the bound copy is
   under Isolated/ and hashes that same isolated file. Next-commands
   keep Isolated/ when the Drive copy is the right name but the wrong
   hash.    Client source
   files are never copied into this
   repository.    After recon/repair, `--execute` writes
   `sectionN-examiner-queue.json` listing remaining blanks and conflicts
   with provenance. One-source blanks stay blank until a writer-held
   source-proved delta. It also writes `sectionN-native-print-draft.json`
   bound to the current isolated workbook hash. Attest that draft after
   Windows Excel Print Preview; Horizon does not invent the page count.
   Native-print and owner-review packets that do not match the current
   isolated hash are unbound so the next command reprints and reissues.
   `--execute` also writes `sectionN-owner-review-draft.json`; attest it
   with a named examiner after owner review only. Remaining 2+ source
   blanks are written to `sectionN-delta-draft.json`; attest that draft
   to apply them. One-source blanks stay out of the draft. Remaining
   one-source blanks and conflicts are written to
   `sectionN-onesource-template.json` with empty values; attest only after
   a writer holds source-proved text. A matching
   packet applies onto the next isolated generation (`sectionN-delta-2.xlsx`
   after the first apply) and the spent packet is archived so the next
   attest can reuse `sectionN-delta-packet.json`. For section 11,
   `--execute` writes `section11-crops-draft.json` from hashed files in
   `section11-renders/` (or `section11-crops/`). After Phase 2, authorized
   snapshot `source_document` renders are used when that examiner
   directory is absent. Phase 1 live files are not hashed into the draft.
   Empty crop skeletons are seeded per hashed page. Existing crop text
   is not overwritten. `--execute` also writes
   `section11-crop-fill-queue.json` for remaining face fills. Attest the
   draft after a writer holds source-proved text. Crop packets whose
   page hashes no longer match the live renders are unbound.
   Handwritten-index images/PDFs are hashed into
   `sectionN-handwritten-scan-draft.json` from
   `sectionN-handwritten-scans/` or, after Phase 2, authorized snapshot
   scans. Remaining pages go to `sectionN-handwritten-scan-queue.json`
   for transcription into a Penterra xlsx. Horizon does not OCR.
   Chat and OCR supporting files are hashed into
   `sectionN-supporting-record-draft.json` from `sectionN-chat/`,
   `sectionN-ocr/`, `sectionN-supporting/`, or Phase 2 authorized
   snapshot files. The queue is review-only and is not legal authority.
4. For each requested section, names classified-file gaps and still-unauthorized
   required roles, picks the first sorted master / PDF-index / handwritten /
   working workbook candidates, and writes copy-paste `horizon.index_export`
   plus `horizon.package_finish` commands that point at a private receipt
   directory.    Fill hops (Section 11 crops, 2+ drafts, one-source
   templates) are listed before native Print Preview and owner-review.
   The first `--execute` keeps `sectionN-letter.xlsx` (print-layout
   repaired) as the isolated workbook and does not promote the pre-layout
   repair copy over it. If that Letter or a later `sectionN-delta.xlsx`
   already exists, later `--execute` runs still apply new medium/high 2+
   source fills onto the next isolated generation instead of freezing
   that copy.    Promoted and follow-up isolated copies also receive the
   Letter/landscape/print-title layout so A4 or missing titles do not
   persist. An existing Letter or later delta is repaired in place when
   it still has A4 or missing print titles.
   Copy-paste finish/export commands also point `--workbook` / `--candidate`
   at that current isolated file and do not reprint over an existing Letter.
   Later `--execute` rebuilds `sectionN-index-packet.json` from that isolated
   file, not from leftover live working-abstract blanks.
   Drive readback only binds Isolated/ or receipt-dir copies of that
   section's file, not another section's Letter and not the live working
   abstract. Inventory classifies `sectionN-letter.xlsx` /
   `sectionN-delta.xlsx` by that filename even when the file sits under
   another section folder. Drive publish dest is the section-named
   folder, never Isolated itself, so later execute does not write
   Isolated/Isolated.
   Writer-held attested deltas still apply first; the same execute then
   runs auto-repair on the new isolated copy for any remaining 2+ fills
   and rewrites `sectionN-finish.json` against that current isolated file,
   even when follow-up repair finds nothing left to apply. The first
   execute also rewrites finish against the new Letter so reconciliation
   scores that file, not the live repair loop.
5. With `--execute`, those isolated hops actually run into `--receipt-dir`.
   The directory must be outside this repository. Source workbooks are not
   modified. Writer-held `--authority-manifest` / `--project-manifest` /
   `--snapshot-directory` are passed through so Phase 2 can authorize
   acquisition.    Page-render, native-print, owner-review, and PDF census JSON packets
   are discovered by `schema_id` when present, or passed explicitly.
   Discovery keeps only packets whose name or `packet_id` names that
   section (`SECTION{N}` / `sectionN` / `P{N}`). A leftover that names
   more than one priority section is not bound. Unlabeled leftovers are
   not auto-bound. Census packets, crop packets, native-print receipts,
   and owner-review tokens stay on the matching section the same way.
   Crops rebound with `sectionN-renders` before finish.
   After `--execute`, each section gets `sectionN-remaining-plan.json`
   and the receipt directory gets `remaining-plan.json` in priority
   order 15, then 13, then 11. Do `next` first. The operator receipt
   names that hop as `Next (section N):` without a host path.
   Connection mounts come first when no labeled root is readable. The plan names the current isolated
   Letter or delta (name and SHA-256 only), unfinished gates,
   files that are still missing, classified typed/handwritten index
   roles that still need Phase-2 `authority_promote`, per-field
   blank/conflict counts from the examiner queue (field names only),
   existing queues, and a connection snapshot (roots readable, Excel,
   Slack/Notion, cursor worker). Until those hops pass, `missing`
   includes `Print Preview {name} on Windows Excel`,
   `Copy {name} into Drive Section N/Isolated/`, and
   `Attest owner-review of {name}` so they stay bound to that file.
   Finish next-actions and next-commands use the same named hops.
   After an isolated Letter or delta exists, next-commands list fills
   and Print Preview of that file before a copy-paste re-export. It
   does not invent field values or copy cell text.
      `packages_complete` is true only if every requested section's finish
   receipt already satisfies the owner-review completion predicate,
   including a Drive Isolated/ copy of that section's file, and that
   section's remaining-plan is also complete. A missing remaining-plan
   (write failure or empty plan list) is fail-closed. Examiner-queue
   blanks or conflicts keep the operator receipt incomplete. Open
   crop-fill, handwritten-scan, empty-text, one-source, and
   delta-draft queues keep remaining-plan incomplete when they are
   hash-bound to the current isolated file. Chat/OCR supporting
   queues are review-only.

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
