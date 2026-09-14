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
   does **not** accept an authority manifest.
3. For each requested section, names classified-file gaps and still-unauthorized
   required roles, picks the first sorted master / PDF-index / handwritten /
   working workbook candidates, and writes copy-paste `horizon.index_export`
   plus `horizon.package_finish` commands that point at a private receipt
   directory. Filename classification is not legal authority.
4. With `--execute`, those isolated hops actually run into `--receipt-dir`.
   The directory must be outside this repository. Source workbooks are not
   modified. `packages_complete` is true only if every requested section's
   finish receipt already satisfies the owner-review completion predicate.

## What it never does

- Copy client files into this public repository
- Invent legal, party, recorded-date, or document-type values
- Start a second Landman Helper controller
- Claim `packages_complete`
- Treat filename classification as legal authority

`technical_pass` means Phase 1 inventory ran against readable roots.
`--execute` does not start Phase 2 and does not invent field values.
Phase 1 is expected to leave required-role gaps until a human-approved
authority manifest exists.

Do not commit the operator receipt. It can contain private paths and hashes.
