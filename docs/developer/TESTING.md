# Testing

Run all tests from the repository root with `python -m pytest -q`. Focused DataBoss checks are:

```text
python -m pytest -q tests/test_databoss_title_factory.py
python -m pytest -q tests/test_databoss_trusted_kernel.py
python -m pytest -q tests/test_databoss_operations_contract.py
```

Tests use temporary and synthetic documents. They cover path/archive controls, exact arithmetic, source hash changes, OCR provenance, untrusted candidates, resumable checkpoints, workbook preservation, auth/RBAC, release states, CLI parsing, launcher controls, documentation, and completion metadata.

Passing tests do not prove OCR accuracy on a production corpus, complete a title examination, validate jurisdiction-specific legal rules, certify security, or approve a client report. Real-corpus acceptance requires an authorized private environment and examiner-reviewed expected results.
