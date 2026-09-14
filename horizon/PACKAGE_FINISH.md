# Package finish runner

One command for the PC or WSL host that can see section roots. It chains the
Horizon gates already in this branch and **never promotes a package**.

```bash
python3 -m horizon.package_finish \
  --section 15 --section 13 --section 11 \
  --root "pc=/mnt/d/DataBossX/Projects" \
  --root "drive=/mnt/g/My Drive/DataBossX/Projects" \
  --tract-export /path/to/tract-ledger-export.json \
  --occurrence-packet /path/to/occurrence-packet.json \
  --workbook /path/to/source-index.xlsx \
  --delta-packet /path/to/source-proved-delta.json \
  --delta-output /path/to/isolated-index.xlsx \
  --public-plat campbell,45n,76w \
  --public-plat johnson,47n,77w \
  --output /path/to/package-finish-receipt.json
```

`--workbook` defaults to `horizon/profiles/penterra_index_v1.json`: seven-row
header block, then the nine-column Penterra table. Required cells are document
type, grantor, grantee, Doc No, Rec Date, and legal description. Book-Page may
be blank on modern e-recorded rows. The Index sheet must be US Letter
(`paper_size` 1), landscape, with print titles on rows 1–8. A4 or a missing
`pageSetup` / Print_Titles block fails. Pass `--workbook-profile` to override.

`--delta-packet` plus `--delta-output` apply a writer-held source-proved
packet to a **new** isolated copy, then run workbook QA on that copy. The
source workbook is not modified. See [`ISOLATED_DELTA.md`](ISOLATED_DELTA.md).

`packages_complete` stays `false` until a verified acquisition snapshot,
source-backed rows, native Excel Print Preview, Drive readback, and a human
release token all exist. This runner cannot create those from an empty cloud
VM.

Public township plats are fetched only from the wy.blm.gov allowlist. Their
hashes are cadastral evidence, not an abstract package.

Independently fetched on 2026-09-14 from `wy.blm.gov` (not Drive):

| Township | Bytes | SHA-256 |
|---|---:|---|
| Campbell 45N-76W | 20075602 | `a4c03d5bc71225de8ff95c4e181d1b6437181332464a0e53fca200d64605824b` |
| Johnson 47N-77W | 6191692 | `88e0e79db9120bb56feb88feb3f99a82c2803b0109c2d9dc1d3e9ffcbc918526` |

Johnson matches the public-source hash recorded by an earlier lane. Re-run the
command on the PC; a different hash means the published plat changed or the
fetch was not byte-exact.
