# abstract_builder

Deterministic builder for title-abstract index packages in a fixed reference format. It re-formats existing
candidate workbooks; it never invents a value. Anything blanked or changed is written to a QA register that stays
outside the client folder.

```bash
python -m abstract_builder.build --section 6 --twp 47 --rge 76 --county Example \
    --county-in candidate_county.xlsx --blm-in WYW-000001.xlsx --prep-date 2026-01-01 \
    --county-thru 2026-01-01 --profile profile.json --out out/S06
```

Outputs `CLIENT/` (index xlsx/ods/pdf, per-case federal indexes, checklist, letter) and `QA_INTERNAL/`
(OPEN_ITEMS.csv, CHANGE_LOG.csv, COUNTS.json, QA_GATES.json, SHA256SUMS.txt).

Real profiles, reference packages and source documents are private and must never be committed
(see `docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md`). Tests use synthetic names only.
