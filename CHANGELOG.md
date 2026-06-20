# Changelog

All notable changes to DataBossX are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Scriptable subcommand CLI (`databossx.cli`) exposed as the `databossx` console
  script and via `python -m databossx`: `health`, `backup`, `scan`, `map`,
  `mock-workbook`, `inspect`, `review`, `fingerprint`, `preflight`,
  `diagnostics`, `first-task`, and `menu`. Supports `--json` output and a
  `scan --fail-on-tracked` CI gate.
- `pyproject.toml` packaging with a console entry point, `dev`/`ocr` extras, and
  tool config for pytest, black, mypy, and coverage.
- Project documentation: a real top-level `README.md`, `CONTRIBUTING.md`, and
  this changelog.
- Unit tests for the CLI (`tests/test_cli.py`).
- Package version (`databossx.__version__`).

### Changed
- `pytest` now defaults to collecting only the `tests/` unit suite (via
  `pyproject.toml`), keeping the maintained suite fast and deterministic.

### Fixed
- `backend_test.py` integration tests are now opt-in (`RUN_BACKEND_INTEGRATION=1`)
  and no longer error in unit-only CI; they use repo-relative paths instead of a
  hard-coded `/app` path.
- Build/CI: deduplicated the `tenacity` pin and bumped `paddlepaddle` to 2.6.2 so
  dependency installation resolves.

## [0.1.0] — baseline

### Added
- Safety primitives (`core/`): central paths, health check, secret scanner,
  zip backup with SHA-256 manifest, project map, guarded file copy/delete, and a
  diagnostics bundle.
- Excel tooling (`excel/`): workbook fingerprinting, mock runsheet generation,
  read-only inspection with hyperlink export, and review-copy creation with AI
  columns added to the copy only.
- Title pipeline (`title/`): document schema, OCR validator, confidence gate,
  row comparison, mock OCR, and the gated TitlePreviewFixer 3-row preflight.
- Budget guard (`agents/cost_guard`) and the interactive command center
  (`ui/command_center`).
