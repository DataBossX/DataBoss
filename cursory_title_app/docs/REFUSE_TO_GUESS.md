# Refuse To Guess

This app is a research and drafting assistant. It is **not a lawyer**, it does
**not issue title opinions**, and it does **not resolve legal questions**. When a
value depends on legal judgment, on illegible source material, or on information
not stated in the document, the app must NOT guess. It records what it can,
leaves the uncertain field empty or marked, and writes a flag into the Review (T)
and/or NEED/ACTION (U) columns so a human resolves it.

Preserving uncertainty is a feature, not a failure.

## Things the app must REFUSE to guess

- **Net-acre calculations / interest math.** These depend on the live O–S
  formulas and on legal judgment about what conveyed. The app never computes
  these as answers. -> `VERIFY: net acres calculation`
- **Grantor / grantee spelling when handwriting is unclear.** Do not normalize a
  guessed name into a confident value. -> `VERIFY: grantor/grantee spelling`
- **Whether a lease is released, expired, or held by production (HBP).** This is a
  legal/status determination. -> `NEED: determine if released/HBP`,
  `NEED: review lease terms`
- **Current ownership.** The app does not chain title to a present owner.
  -> `NEED: confirm current ownership`
- **Legal description when illegible.** Do not reconstruct a legal from a blurry
  scan. -> `NEED: verify legal description`, `NEED: pull clearer image`
- **Conveyance fractions not stated in the document.** If the instrument does not
  state the fraction/interest, do not infer one. -> `VERIFY: net acres
  calculation` (and leave the fraction blank with a note)
- **Section / township / range when ambiguous.** If the S-T-R is unclear or could
  be read multiple ways, flag rather than pick. -> `VERIFY: legal description` /
  `NEED: verify legal description`
- **Any cursive/OCR read that is low-confidence** — and ALL handwriting reads are
  low-confidence by default. -> `VERIFY: OCR uncertain`

## Exact flag vocabulary

Use these strings verbatim in the NEED/ACTION (U) and Review (T) columns. Do not
invent variants.

```
NEED: pull clearer image
NEED: verify legal description
NEED: confirm current ownership
NEED: review lease terms
NEED: determine if released/HBP
VERIFY: OCR uncertain
VERIFY: grantor/grantee spelling
VERIFY: net acres calculation
```

Convention:
- `NEED: ...` = an action a human must take (get a better scan, pull a document,
  make a legal determination) before the row can be trusted.
- `VERIFY: ...` = a value the app produced but cannot stand behind; a human must
  confirm or correct it.

Multiple flags can apply to one row; separate them clearly (e.g.
`VERIFY: OCR uncertain; NEED: verify legal description`).

## Legal limit (state this plainly)

This tool assists with research and drafting only. It does not practice law, does
not render title opinions, and does not make ownership, validity, or status
determinations. All uncertain or judgment-dependent items are preserved as flags
for a qualified human to review. A licensed professional is responsible for the
final title work.
