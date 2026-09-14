# Portfolio QA dashboard (read-only)

Builds a local CSV + Markdown + HTML dashboard from a **cited-receipt ledger**.
It does not open abstracts, does not write packages, and does not call Drive.

## Rules

- `UNKNOWN` stays `UNKNOWN`. It is never converted to zero.
- Source evidence outranks receipts; receipts outrank model conclusions.
- A source hold is not a control/custody hold.
- P15 / §15 is a frozen benchmark only.

## Usage

```bash
python3 -m tools.portfolio_qa.dashboard \
  --ledger /path/to/cited_ledger.json \
  --output-dir /path/to/isolated/portfolio-qa-dashboard-<UTC>
```

The ledger must contain exactly one row each for P1, P2, P3, P10, P11, P12,
P13 Campbell, P14, P15, Johnson P13, Johnson P24, and Horizon §7.

Do not commit a populated client ledger to this public repository.
Keep live exports in a timestamped isolated folder outside git.

## Tests

```bash
python3 -m pytest tests/test_portfolio_qa_dashboard.py -v
```
