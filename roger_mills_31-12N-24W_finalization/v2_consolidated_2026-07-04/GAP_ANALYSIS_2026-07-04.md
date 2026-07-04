# Gap Analysis — closing open balances from data already in the record set
Section 31-12N-24W, Roger Mills Co., OK · 2026-07-04
(From the 106-sheet workbook's `rawdata` + `Overconveyance_Audit`. Cursory; confirm conveyed
fractions against the recorded images before certified reliance.)

## Finding 1 — name Cummins Minerals + Eagle Owl as current owners (Tracts 3, 4, 7, 10)
The Tract 4 balance carried a "candidate: Psi Lke → Cummins / Eagle Owl" note. The rawdata
holds the **complete two-step chain**, so these are identifiable current owners (quantum TBD):

- **2021-001068** (Mineral Deed, Bk 2467/0476, eff 06/01/2021): Grizzly Operating, LLC + Vanguard
  Operating, LLC → **Psi Lke, LLC** — legal: SE/4 NE/4, E/2 NW/4, N/2 NE/4 SW/4, NE/4 SE/4.
- **2022-000185** (Mineral Deed, Bk 2486/0262, eff 01/10/2022): Psi Lke, LLC → **Cummins Minerals,
  Ltd. (70%)** and **Eagle Owl, LP (30%)** — "All of 31-12N-24W."

Mapping to the 10-tract scheme: SE/4 NE/4 = **T3**, E/2 NW/4 = **T4**, N/2 NE/4 SW/4 = part of **T7**,
NE/4 SE/4 = **T10**.

➜ Added to `OWNER_LEDGER.csv` as named owners in Tracts 3/4/7/10 (70/30 split). **NMA is TBD** —
the fraction Grizzly/Vanguard conveyed to Psi Lke in 2021-001068 is not in the index; pull that
one image (Bk 2467/0476) to compute quantum. Owners and split are established of record.

## Finding 2 — the remaining open balances are overconveyance artifacts of pre-2000 roots
`Overconveyance_Audit` shows the balances are **not** unidentified living owners — they are the
arithmetic of grantors conveying out more than their in-record source-in, because their acquiring
instruments predate the 2000 county index. Examples: Roy A. Garrison (1915), H.L. & Myrtie Rowley
(1916), "United States of America" (1907), Clarence C. Bain / W.C. Bain Jr. Trustee (1988-1990).

➜ Tracts 2/5/7/9 balances **cannot** be closed by more data-mining; they need the specific
**pre-2000 vesting instruments** (deeds/probate/heirship) for those root parties from
okcountyrecords. This is a definitive answer, matching the prior AUDIT LOG's 67 preserved gaps.

## Net effect
- Tract 4 (and 3/7/10): Cummins Minerals Ltd (70%) + Eagle Owl LP (30%) now named; one image fixes NMA.
- All other open balances confirmed external-document-bound; disclosed as open, not invented.
