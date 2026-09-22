# Package finish runner

One command for the PC or WSL host that can see section roots. It chains the
Horizon gates already in this branch and **never promotes a package**.

To learn which files and commands that host still needs, run
`python3 -m horizon.pc_operator` first ([`PC_OPERATOR.md`](PC_OPERATOR.md)).
That is Phase 1 inventory plus a work order, not package finish.

```bash
python3 -m horizon.package_finish \
  --section 15 --section 13 --section 11 \
  --root "pc=/mnt/d/DataBossX/Projects" \
  --root "drive=/mnt/g/My Drive/DataBossX/Projects" \
  --connect-status \
  --page-render-packet /path/to/page-render-crop-packet.json \
  --pdf-census-packet /path/to/pdf-page-census-packet.json \
  --pdf-bind-dir /path/to/federal-pdfs \
  --image-bind-dir /path/to/section-images \
  --image-account-packet /path/to/image-account-packet.json \
  --occurrence-packet /path/to/occurrence-packet.json \
  --index-packet /path/to/index-reconciliation-packet.json \
  --workbook /path/to/source-index.xlsx \
  --repair-dir /path/to/isolated-repair \
  --print-layout-output /path/to/isolated-letter.xlsx \
  --native-print-receipt /path/to/native-excel-print-receipt.json \
  --drive-readback /path/to/Section 15/Isolated/section15-letter.xlsx \
  --human-release-token /path/to/owner-review-token.json \
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

`--index-packet` reconciles master, PDF, and handwritten indexes, scores
required fields with provenance and confidence, and emits isolated-delta
proposals only when at least two sources agree. If the packet is omitted,
`--master-workbook` / `--pdf-workbook` / `--handwritten-workbook` (and the
candidate `--workbook`) build that packet in memory. Do not pass both a
packet and the three workbooks unless `--repair-dir` owns the hop. When
`--workbook` is set without `--repair-dir`, finish refreshes the packet's
candidate faces from that isolated file before scoring, so leftover blanks
on the live working abstract do not keep the gate open after isolated 2+
fills. See [`INDEX_RECONCILIATION.md`](INDEX_RECONCILIATION.md).

`--repair-dir` runs up to `--max-loops` (default 10) isolated
detect-and-repair passes: export the current candidate, reconcile, apply
only medium/high proposals to a new copy, then QA. Use it with
`--index-packet` or with `--master-workbook` / `--pdf-workbook` /
`--handwritten-workbook`. Do not combine `--repair-dir` with
`--delta-packet`. See [`INDEX_RECONCILIATION.md`](INDEX_RECONCILIATION.md).

`--delta-packet` plus `--delta-output` apply a writer-held source-proved
packet to a **new** isolated copy, then run workbook QA on that copy. The
source workbook is not modified. See [`ISOLATED_DELTA.md`](ISOLATED_DELTA.md).

`--print-layout-output` writes US Letter, landscape, and print titles from
the Penterra profile onto an isolated copy. It does not replace native Excel.

If `--page-render-packet` and `--tract-export` are omitted, the isolated
`--workbook` is projected into `reextraction` and `occurrence_ledger`.
Blank book/page and bare document numbers stay bare. Sections 15 and 13
can satisfy those gates from the Penterra index; section 11 still needs
page-render crops for bare document numbers.

`--native-print-receipt` binds a writer-held Microsoft Excel / Windows Print
Preview receipt to the current workbook hash. Page count must match the
writer-held `expected_page_count`. LibreOffice, A4, or a missing print-title
claim fails. This still is not Drive readback.

Phase 2 source authority is opt-in: pass `--authority-manifest`,
`--project-manifest`, and a new `--snapshot-directory` outside every source
root. Later runs verify the existing snapshot from `--acquisition-receipt`
instead of creating a second copy. Downstream index export must read those
verified snapshot bytes, not drifted live Drive/PC files. Without Phase 2
controls, acquisition stays Phase 1 inventory and cannot authorize
extraction. `packages_complete` is true only when every required gate passed,
index reconciliation recorded `candidate_from=workbook` against the isolated
hash (or a repair loop ended with no blanks), Drive readback is an Isolated/
copy, a writer-held `--human-release-token` matches that hash, and the
examiner queue has no remaining blanks or conflicts.
Finish next-actions name `Print Preview {name} on Windows Excel`,
`Copy {name} into Drive Section N/Isolated/`, and
`Attest owner-review of {name}` until those hops are bound.
The token statement must be the owner-review declaration;
`external_release` must be false. `READY_TO_SUBMIT` and external-delivery
claims are rejected. This runner cannot satisfy that predicate from an
empty cloud VM.

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
