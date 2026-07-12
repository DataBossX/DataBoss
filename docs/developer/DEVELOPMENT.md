# Development

Use Python 3.11+. Create a virtual environment and install the package editable from `databoss_title_factory/`. The console entry point and `python -m databoss_title_factory` both call `cli.main`.

Keep core operations deterministic, local, allow-root constrained, and source-read-only. New stages must write under a run directory, record artifact hashes, preserve rejected/raw candidates, and fail closed on uncertainty. Never trust provider-supplied provenance or add a UI action without a real core/CLI operation.

Release vocabulary is fixed in `ReleaseStatus`; technical defects must not be converted to approval states. Update tests and documentation with behavior changes. Do not add real evidence or secrets. Existing `horizon/`, grocery pipeline, DOTO Image Commander, deal-room, and legacy demo subsystems remain separate and must not be described as one production service without integration evidence.
