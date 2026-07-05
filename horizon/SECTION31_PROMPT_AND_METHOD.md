# Section 31-12N-24W — how the report is built, and the prompt to build it better

This is the method + a copy-paste prompt for regenerating the **31-12N-24W Roger Mills
Co. cursory title report** from your workbook (Overview map + OGL + Runsheet) into the
tract-tab template. It encodes the Tract 1 gold-standard so every other tab is chained
the same way.

## The gold standard = Tract 1

Tract 1 is the pattern every tract and WI tab must match:

| Where | What it holds |
|---|---|
| Row 1 | instrument **type** across the columns (PAT, SD, DEED, ASSN, WD, MD, DECREE …) |
| Row 2 | instrument **number** |
| Row 3 | **Book/Page** |
| Row 4 | **date** |
| Row 5 | **Conveyance** — `ARTI` (all right, title & interest) or a fraction (`UND 1/2`) |
| Col A | notes (`open`, etc.) | 
| Col B | **OGL number** carried down next to the leased owner (e.g. `4, 66` = base 4 + top lease 66) |
| Col C | **net acres** |
| Col D | **owner** |
| Col E | **total** royalty decimal |
| Col G+ | the conveyance matrix: `+` receives interest, `−` conveys it away |

Only the rows with net acres in Col C are **final owners** — those are what flows to the
Title tab. Base OGL + top-lease OGL numbers ride in Col B next to the name.

## The rules (do not break these)

1. **Instrument number is the primary key.** Cross-reference OGL ↔ Runsheet on the
   instrument number, never on names alone (OCR variants exist — "Mitchel" vs "Mitchell").
2. **A tract gets an instrument only if the instrument's legal description covers that
   tract's lands.** Filter the runsheet by aliquot (N/2 NE/4, SW/4 NE/4, …) before placing
   it on a tab. Missing = the chain breaks; extra = a stranger on the tract.
3. **OGL column = OGL numbers, never assignment Book/Page.** Leasehold/WI assignments are
   referenced by Book/Page **in the comment**, and the OGL column shows the *base* OGL(s)
   the assignment rides on (the Alexander wellbore / all-section chain = base OGLs 1–30).
4. **Grantor − Conveyed = Retained.** Only let a party convey what the runsheet Note says
   they hold (`ARTI`, `UND 1/2`, `43.496666/791.47`, `10 NMA`, …). If the Note is silent,
   flag it — do **not** invent a fraction.
5. **Net mineral acres ≤ gross acres.** If a chain sums to more than the tract acreage it
   **over-conveys**; disclose the delta as curative and flag it yellow. Do **not** silently
   shave named owners to force a tie — that is a title determination that needs the deed
   image. (Tract 2 currently: 221.70 NMA identified vs 160.00 ac → 61.70 NMA over.)
6. **Conveyance label = the instrument's nature.** Mineral chain = `ARTI` / fraction.
   Working-interest chain = `ASSN` (assignment), like WI 1.
7. **No fabrication.** Anything not supported by the runsheet/OGL is left blank and flagged
   **yellow** — the one and only highlight color. No other highlights.
8. **Title tab = final owners only**, per tract, with: Net Acres, OGL No. (base + top),
   Royalty, Expiration (HBP / real exp date / Open), Comments. Totals = tract acreage or a
   disclosed, flagged delta.

## Copy-paste prompt

> You are a senior Oklahoma landman. Build the 31-12N-24W Roger Mills cursory title report
> from my workbook (tabs: Overview map, OGL, Runsheet) into the tract-tab template.
> **Chain out each tract exactly like Tract 1.** For every tract:
> 1. Pull only the runsheet instruments whose legal description covers that tract's aliquot.
> 2. Order them by date and chain grantor→grantee; each party may convey only what the
>    runsheet Note says it holds (ARTI = all; otherwise the stated fraction/NMA). Grantor −
>    Conveyed = Retained.
> 3. List final owners (those left holding net acres). Put their base OGL and top-lease OGL
>    numbers in the OGL column next to the name and carry them down — never put assignment
>    Book/Page in the OGL column; Book/Page goes in the comment.
> 4. Keep net mineral acres ≤ tract acres. If the record over/under-conveys, carry every
>    owner at their record fraction, disclose the delta as a curative item, and highlight
>    that total cell yellow. Never guess a fraction to force a balance.
> 5. Chain the working interest on WI 1/WI 2 the same way but label the conveyance **ASSN**;
>    the base OGLs for the wellbore/all-section leasehold are 1–30.
> 6. Title tab shows **final owners only** with Net Acres, OGL No., Royalty, Expiration
>    (HBP or exp date or Open), Comments.
> 7. **The only highlight is yellow, and only on cells I still need to examine** (open
>    balances, undetermined owners, unlocated vesting, over-conveyance, curative). No other
>    colors. Leave unsupported facts blank and flag them — do not fabricate.
> Verify at the end that every tract's Title net acres tie to its acreage or carry a
> disclosed, yellow-flagged delta, and that the ten tract acreages sum to 637.42.

## Regenerate the clean turn-in from the working workbook

```bash
py horizon/section31_finalize.py \
    --in  "31-12N-24W ... FINAL TURN-IN WORKBOOK.xlsx" \
    --out "SECTION31_12N_24W_ROGER_MILLS_FINAL_CLEAN.xlsx"
```

Then open in Excel and press **Ctrl+Alt+F9** to force a full recalc before distribution
(the tract net-acre cells are `=Royalty × Tract Acres` formulas).
