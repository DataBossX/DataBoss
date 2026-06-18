# Changelog

## v2.0 - Hardened production release

Everything from v1 plus substantial reliability, safety, cost, and usability
upgrades.

### Added
- **Automated test suite** (`tests/test_logic.py`, 23 tests) covering config
  validation, Excel header/hyperlink/comparison/writing, Drive workbook
  selection, the AI consensus router, caching, and the HTML report. Run with
  `RUN_TESTS.bat` or `python -m pytest`.
- **Preflight doctor** (`preflight.py`, `RUN_DOCTOR.bat`): a PASS/WARN/FAIL
  checklist of Python, packages, config, API keys, county login, and folders.
  The full review refuses to start on critical FAILs.
- **Dry-run mode** (`--dry-run`, `RUN_DRY_RUN.bat`): exercises link extraction
  and the full browser/View/capture flow with **zero AI cost**, so the county
  login and links can be validated cheaply before a paid run.
- **HTML report** (`report.py`): `logs/report.html` - a color-coded, browser-
  friendly summary of every row for non-coders. Regenerate with `--report`.
- **AI result cache** (`cache.py`): results are cached by a hash of the
  document image(s) + model, so re-runs don't re-pay for documents already
  read. Only the AI's text output is cached - never the county images.
- **Usage tracking**: per-model AI call counts, cache hits, and token totals
  printed in the run summary and saved to `summary.csv`.
- **Config schema validation** (`config_schema.py`): typos and wrong types in
  `config.yaml` now fail fast with a clear message instead of mid-run.
- **Excel polish**: a leading `_AI_Review_Summary` sheet with stats + color
  legend, bold/colored review headers, frozen header row, and tuned widths.
- **Direct image capture**: if a link or the post-View URL is a direct image,
  its bytes are fetched through the authenticated session.
- **Optional debug screenshots**: captured pages are saved to `debug/` only
  when `debug_save_screenshots: true`.

### Changed
- `config.yaml` gains: `dry_run`, `enable_ai_cache`, `cache_dir`,
  `generate_html_report`, `request_jitter_seconds`, `openai_fallback_models`.
- `.gitignore` now also excludes `.cache/`.

### Unchanged guarantees
- REVIEW ONLY by default; the original workbook and cells are never modified
  unless `apply_corrections: true`.
- Document images stay in memory; temp wiped per row unless debugging.
- No secrets in git; `.env` / `.auth` / token files ignored.
