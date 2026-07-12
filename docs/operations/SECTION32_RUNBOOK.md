# Section 32 Runbook

Current production status is `BLOCKED_SOURCE_NOT_MOUNTED`. The repository has a configuration scaffold and synthetic tests, not the real Section 32 evidence corpus.

When an authorized read-only corpus is mounted:

1. Set `DATABOSS_PROJECT_ROOT` to its exact folder and record custody/scope outside this public repository.
2. Run health check, then `RUN_SOURCE_INVENTORY.bat`. Review counts, hashes, duplicates, unsupported files, and missing schedules/exhibits.
3. Run `RUN_OCR_PIPELINE.bat`. Review every failure and weak citation against the image.
4. Run `RUN_SECTION32_PIPELINE.bat` for a new complete run, or use CLI `pipeline --resume` only for the same validated run.
5. Review candidate archives, field conflicts, missing documents, runsheet chronology, legal descriptions, lease terms, and exact-interest traces.
6. Run template QA against the authorized client template. Export is a review package and exact template copy; client-cell population remains unimplemented.
7. Apply `release.py` gates. Limited source scope cannot be externally delivered; only complete approvals and non-limited scope can produce `APPROVED_FOR_DELIVERY`.
