# Horizon Command Center

An autonomous system to **ingest, clean, validate, chain, and perfect** oil & gas
cursory title reports. It is built to run **on the machine where the source files
live** (e.g. `D:\Desktop\Horizon`) — a cloud assistant cannot see that drive, so
Horizon is a portable, unit-tested, run-it-locally package rather than a script
that would have to invent data.

> **No fabrication.** Where a balance, document, or HBP fact is not supported by
> the files, Horizon tags the tract **`Needs Examiner Review`** or flags the row
> **`ESCALATED`** — it never guesses to make the numbers tie out.

## Install & run

```bash
py -m pip install -r horizon/requirements.txt

# point it at the folder where your title files live
py horizon/main.py --root "D:\Desktop\Horizon"

# or set HORIZON_ROOT and just run it
set HORIZON_ROOT=D:\Desktop\Horizon
py horizon/main.py
```

Useful flags: `--section 31-12N-24W`, `--base <report-stem>`, `--max-loops N`,
`--no-backup`, `--dry-run` (scan + validate only).

## What it does (maps to the mission spec)

| Mission section | Module |
| --- | --- |
| 1. File system & cleanup — scan, unzip → `temp_raw`, SHA256 dedup → `trash`, snapshot backup | `foundation.py` |
| 2. Interest logic — `Grantor − Conveyed = Retained`, **Fraction/Decimal only, no floats**, net-acre reconciliation | `interest.py` |
| 2. Chaining — `Instrument_Number`-keyed cross-reference of OGL ↔ runsheet, chain-out reconciliation, tie to legal descriptions | `chaining.py` |
| 3. Autonomous loop — Ingest → Validate → Repair → Evaluate → Iterate (5-loop cap) | `orchestrator.py` |
| 3. Repair — XML-based (`lxml`) worksheet repair that preserves `xl/media` plats byte-for-byte | `repair.py` |
| 3. Validate — gates against the Golden Source (`project_notes_updated.xlsx`) | `validation.py`, `models.py` |
| 4. Zero-destruction — every write is a new `_vNNN` file | `versioning.py` |
| 5. Entry point, audit log to `horizon_audit.log` | `main.py`, `audit.py`, `config.py` |

## The Law of Horizon

- **Zero destruction.** Sources are only read/copied. Duplicates are *moved* to
  `trash`, never deleted. Every output is a new `_vNNN` version.
- **Golden Source of Truth.** `project_notes_updated.xlsx` defines the validation
  gates. When it is absent, Horizon falls back to the built-in canonical schema
  (so the loop still runs and is testable).
- **Instrument number is the primary key.** The OGL↔runsheet cross-reference is
  keyed on the normalized `Instrument_Number`; every unmatched key is reported as
  a chain break.

## Tests

```bash
pytest tests/test_horizon_*.py -q
```

61 unit tests cover exact-fraction interest math, chaining/chain-breaks,
SHA256 dedup, versioning, validation gates, lxml repair (media preservation),
and the bounded improvement loop.
