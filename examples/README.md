# Example outputs (SYNTHETIC)

The files in `sample_output_synthetic/` were produced by running:

```
py grocery_report_pipeline.py --self-test
```

They are generated from a **fictional, clearly-labeled synthetic corpus** (see
`grocery_report_pipeline.make_synthetic_corpus`). They contain **no real
ownership, lease, party, or recording data** and exist only to show the shape of
the deliverables a real run produces into `./output/`.

What to look at:

| File | Shows |
| --- | --- |
| `status_dashboard.html` | RAG status per stage, % complete, blockers, Monday delivery-risk banner. Open in any browser. |
| `Grocery_Report_Executive_Summary.md` | The one-page executive summary. |
| `extracted_facts.csv` | Structured facts — note per-owner rows from the ownership CSV, each with a `source_page` row anchor, and blank (never fabricated) fields. |
| `review_required.csv` | Validation issues, red first (impossible date, decimals not summing to 1.0, stale prior draft, …). |
| `document_classification.csv` | Deterministic multi-label classification. |
| `conflicts_and_gaps.xlsx` | Reconciliation conflicts / chain gaps. |
| `run_manifest.json` | Run counts, optional-deps present, warnings/errors. |

The seeded synthetic corpus deliberately contains defects so you can see the
validators fire: an exact duplicate, an impossible recording date (2099), a
tract whose decimals sum to 0.95 (should be 1.0), and a prior draft to
re-verify. A clean tract (Section 8, summing to exactly 1.0) is intentionally
**not** flagged.
