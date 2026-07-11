# Section 32-11N-25W, Beckham County, Oklahoma — Diversified Cursory Title Report

**Client project:** Diversified Energy cursory title report (Dan Dickensheet / Horizon).
**Status:** WORKING PROJECT — NOT A TITLE OPINION. Target delivery Friday 2026-07-17; QA/search-rerun checkpoint Thursday 2026-07-16.
**This folder:** provenance archive, QA verification, and knowledge assets mirrored from the Google Drive workspace on 2026-07-11. The report binary itself lives at `beckham32/final_delivery/` (see below).

## Canonical deliverable and chain of custody

The current canonical workbook is **FINAL_VERIFIED v2 (2026-07-11)**:

- Git path: `beckham32/final_delivery/32-11N-25W_Beckham_Co_Diversified_Cursory_Title_Report_FINAL_VERIFIED_2026-07-11.xlsx`
- SHA-256: `1d8b4a67c540ba41a6340530d9b17bae4e4c4c840de0e552daa2268ef3265b02` (660,580 bytes)
- Verified identical (byte hash) across three independent locations on 2026-07-11:
  1. this repository (merged from branch `claude/kimi-section31-qa-audit-5lccqy`, commit `adac769`),
  2. Google Drive file `GITHUB_CANDIDATE_32-11N-25W_Beckham_Co_Diversified_Cursory_Title_Report_2026-07-11.xlsx` (fileId `11U440SQ4Q3bCG1pUVGil3GZ6Ony2kQHe`),
  3. the SHA stated in `docs/FINAL_VERIFIED_v2_DELIVERY_NOTE_2026-07-11.txt`.
- Built by `beckham32/final_delivery/build_final_v2.py` on top of the v1 build (`build_final_verified.py`); v2 supersedes v1 per its delivery note.

### Core determinations (unchanged, correctly gated)

- Exact Diversified decimal established: **NO** — operative post-1988 instruments, schedules and exhibits remain unreviewed; no WI/NRI/net-acre decimal is stated or implied.
- Current vested entity established: **NO** — three separate Diversified-related portfolios carried (Tapstone/Sooner, Unbridled/Maverick, Canvas/DP Ponies).
- Direct-image cutoff: Bk 1014/P75, recorded 04/26/1988 (4,893 continuous supplied images).
- Index through-date 07/01/2026 (no formal abstractor certificate exists — carried as a through-date, not a certification); OKCR continuation closed through 07/09/2026; last entry Bk 2490/471-473 (WD, rec. 2026-07-07).
- Blank ownership fields mean **not determinable from supplied evidence**, never zero.

## Independent QA verification (this repo, 2026-07-11)

`scripts/verify_candidate_qa.py` re-measures the QA gates from scratch against the committed binary; results in `qa/FINAL_VERIFIED_v2_local_QA_2026-07-11.json`.

Confirmed: 13 sheets in exact template order with PLAT hidden · 0 negative constants · 0 formulas / 0 formula-error tokens · 0 external-link parts · 0 duplicate Runsheet book/page keys.

Measured variances, disclosed:

| Observation | Assessment |
|---|---|
| "Presidio WAB" appears at Runsheet row 98 (4 cells) | Explained — v2 intentionally carries the Presidio WAB and BCE-Mach **parallel chains flagged SEPARATE**, never blended into a Diversified branch (v2 delivery note item 1). Not prior-project residue. |
| 22 defined names present, 21 containing `#REF!` (plus stale `_Fill`/`_Sort`/`Test*` junk) | **OPEN mechanical item** — the 2026-07-11 readiness statement says 21 broken names were "purged", but they are present in the v2 binary. Harmless to values (workbook is values-only) but should be purged before client issuance. |
| Runsheet hyperlinks: 0 | The earlier BEST_AVAILABLE build carried 34 public-metadata hyperlinks; v2 carries none. Traceability now rests on the evidence-tier stamps per row. Flagged for examiner decision. |

## CONFLICTS disclosed (per never-fabricate rules — not resolved here)

1. **Three different SHA-256 values are associated with "FINAL_VERIFIED 2026-07-11"**: the readiness statement cites `fe6a8aa1…`; the v1 delivery note cites `25313784…` (654,243 bytes); the v2 delivery note cites `1d8b4a67…` (660,580 bytes, in git). v2 explicitly supersedes v1. The `fe6a8aa1…` artifact ("delivered in the Claude conversation") is not present in Drive or git — OPEN: locate or formally retire it.
2. **Direct-image ranges conflict between provenance docs**: READ_ME (2026-07-10) states Bk 845/P47 = images **4118-4119** and Bk 872/P279 = **4388-4393**; the readiness statement (2026-07-11) states 845/47 = **4120-4121** and 872/279 = **4386-4393**. Requires visual recheck against the numbered image set.
3. **Runsheet row counts differ across documents** (readiness statement: 51 rows; v1 note: 93; v2 note: 102). Consistent with successive rebuilds, but the readiness statement describes a different build than the canonical v2 binary.

## Unresolved critical requirements (carried from readiness statement + v2 note)

1. Approve and pull the 22-instrument Tier 1 OKCR queue (~$8.80 — **needs authorization; do not incur without approval**): 2340/403, 2340/490, 2371/470/495/514/533, 2389/500/581, 2393/1, 2395/415, 2400/551, 2451/4, 2476/1, 2476/121 + all exhibits/schedules. Decimals become possible only after these are reviewed.
2. Bridge 1988-2020 starting at 1014/76 ("Union Oil & Chemical et al." grantor is an unverified handwritten-index reading), 1014/228, 1016/38.
3. Resolve I-2011-001515 vs I-2011-001565 (p.47 handwritten reception number reads 1565) and Long Description records in the omitted 2011-2012 index interval.
4. Trace or carry: Hartman ORRI (376/287), GAEC formula ORRI, Great American/FNB Dallas mortgage family, MNR ABS/UMB liens (2415/410, /515), DP Ponies/UMB (2476/67, /109), Latigo/Lone Star/Prosperity family, Teocalli carveout (2401/214 — CRITICAL).
5. Obtain Order 156126 owner elections/payments and JOA No. 1580; keep every HBP conclusion lease-, formation-, depth-, unit- and order-specific.
6. Re-run exact-legal and party/lien continuation searches on the delivery date (2026-07-17) before issuance.

## Folder guide

| Path | Contents |
|---|---|
| `docs/` | Readiness statement, START_HERE brief (mirrored from Drive Google Docs), v1+v2 delivery notes, READ_ME audit/completion report |
| `audits/` | AUDIT_1 (workbook/template forensics), AUDIT_2 (accuracy/calculation), AUDIT_3 (instruments/sources/copy-pull plan) |
| `qa/` | Drive QA JSONs (BEST_AVAILABLE internal QA; native-Excel + visual QA) and this repo's independent scan output |
| `prompts/` | Staged AI cleanup prompts (reusable knowledge assets) |
| `scripts/` | Drive-recovered build/compare scripts + `verify_candidate_qa.py` (repeatable local QA gate) |
| `evidence_register/` | 2026-07-09 evidence register workbook (lineage artifact) |
| `../../beckham32/` | Report builder toolchain, final_delivery binary (canonical), checkpoint.json |

## Drive workspace pointers (source of truth for evidence; read-only Dropbox originals preserved)

- Project folder: `32-11N-25W Diversified Cursory - Beckham County - 2026-07` (folderId `1fhOPwB58SU7npZ6AmQzwFROUwDeEMK08`) with numbered subfolders 00_SOURCE_READ_ONLY … 09_FINAL_DELIVERY.
- Working Report Workbook (Google Sheet): `1CZ0FRCg4SkzSSlKM8tKwA0n1lhQNCNUD2kppaponM40` · Working Findings: `126P1PokviLq-Aqu4stk-hsOtZbZiGk-jicC71-dQ3kY` · Project Control/Source Inventory: `1DnS_zFKPa0_-TWmvv0XbNEclfdzgDxY3Okzzzhcr1cw`.
- Source images: `11N 25W 32.zip` (3.0 GB, fileId `1gk0hofK94kjkw8ygHFtE-3YmtC-hyw4H`) + `Images_4863_4893.zip`; 4,893 continuous title images.
