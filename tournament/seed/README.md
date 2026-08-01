# Synthetic seed package

**Everything in this directory is fictional.** No real client, owner, operator,
county, legal description, instrument, hash, or path appears here. Real project
data is Internal-classified (`docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md`)
and is not present in this environment at all.

The seed reproduces the *shape* of the three held matters so prototype
capabilities `P-10`, `P-11`, `P-21` and red-team test `RT-20` are testable
without touching client work:

| Seed project | Stands in for | Seeded state |
| --- | --- | --- |
| `SEED-HORIZON-32` | Horizon Section 32 | `HOLD` + a size-anomaly defect |
| `SEED-PENTERRA-20` | Penterra Section 20 | `INTERNAL_REVIEW` |
| `SEED-PENTERRA-17` | Penterra Section 17 | `INTERNAL_REVIEW` |

All three carry `release_state: FOR_REVIEW_HOLD_NO_EXTERNAL_RELEASE`.

The county is the fictional "Sandhill County", state code `ZZ`. Owner and
operator names are invented. Section/Township/Range values use real *formats*
with fabricated values so a parser can be exercised honestly.

Files:

- `projects.json` — the three seeded projects, their holds, defects, and review
  state
- `wells.json` — synthetic well/permit/production records for the well-brain
  surface
- `conflicts.json` — a deliberate contradictory-ownership pair (`RT-22`), a
  corrected filing (`RT-23`), an ambiguous well↔tract mapping (`RT-24`), and a
  licence-restricted source (`RT-25`)

A prototype must not require any data beyond this package.
