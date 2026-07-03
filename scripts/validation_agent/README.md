# DataBossX — Automated Validation & Repair Agent

A perfection-loop agent that validates oil-&-gas title workbooks, applies only
exact, non-inventive repairs at the XML level, and **escalates to a human
examiner whenever passing a gate would require inventing a legal or title
fact**.

> **The Golden Law**
> 1. AI handles the labor; the human examiner approves the risk.
> 2. Every action leaves append-only, immutable proof.
> 3. No legal or title facts are ever fabricated.
> 4. If a gate cannot pass without inventing a fact, automated repair halts and escalates.
> 5. No source-file overwrites — strict versioning only.
> 6. The $100 API cap is a hard mathematical ceiling; no silent paid calls.

## Location note

The architecture blueprint references the Windows path
`D:/Desktop/DataBossX/scripts/validation_agent/`. Inside this repository that
maps to **`scripts/validation_agent/`** (this directory). The root can be
overridden at runtime with the `DATABOSSX_ROOT` environment variable.

## Layout

```
validation_agent/
├── app/dashboard.py            # Streamlit examiner UI (read-only over SQLite)
├── config/settings.py          # paths, $100 cap, thresholds (637.42 acreage, ...)
├── core/
│   ├── run_manager.py          # immutable run folders + versioned copies
│   └── orchestrator.py         # the Section-4 perfection-loop state machine
├── db/
│   ├── schema.sql              # append-only tables
│   ├── db_client.py            # rejects UPDATE/DELETE (guard + SQLite authorizer)
│   └── audit_logger.py         # single write surface for the memory layer
├── ingestion/                  # safe read-only ingest, classify, manifest
├── validators/                 # gates 3–10 (interest, acreage, chain, ...)
├── sources/                    # curl-based OKCounty client + $100 spend guard
├── repair/                     # taxonomy classifier, planner, lxml XML editor
├── recalc/libreoffice_runner.py# headless LibreOffice recalculation
├── reports/output_generator.py # scorecards, certification, escalation packets
├── models.py / failure_taxonomy.py
└── tests/                      # unit + end-to-end (synthetic fixtures)
```

## Run it

```bash
export PYTHONPATH=scripts
pip install -r scripts/validation_agent/requirements.txt
python -m validation_agent.main path/to/workbook.xlsx
# examiner dashboard:
streamlit run scripts/validation_agent/app/dashboard.py
```

Outputs land in `scripts/validation_agent/outputs/validation_run_<timestamp>/`
(overridable via `DATABOSSX_ROOT`). The source workbook is copied to `v0` and
**never modified**.

## Perfection loop (Section 4)

```
INIT → INGEST → VALIDATE → TRIAGE → EVALUATE
   ├── 100% pass ............................ → CERTIFY
   ├── unsafe / max-iter / API-block ........ → ESCALATE
   └── only safe errors ..................... → REPAIR → RECALC → ITERATE
```

Hard cap of 5 iterations. Verification (API) and validation (math/logic)
complete and are logged **before** any repair mutates a workbook.

## Safe repairs vs. escalations

Only two mutations are ever automated, both exact and non-inventive:
* **restore_formula** — reinstate a `=SUM(...)` over a visible data range.
* **normalize_fraction** — turn a rounded decimal into the exact fraction the
  other columns already imply.

Everything else — missing probate, vesting gaps, orphaned leases, unverifiable
sources, spend blocks — routes to a fully-populated 9-field escalation packet
(Section 7). The system never invents the missing fact.

## External dependencies

* **`curl`** — the OKCounty client shells out to curl (no shell string; argv
  list) so an authenticated request to the operator's own subscription presents
  a normal browser fingerprint. Credentials come from `OKCOUNTY_USERNAME` /
  `OKCOUNTY_PASSWORD` and are never logged.
* **`soffice`** (LibreOffice) — headless recalculation after a repair. If
  LibreOffice is unavailable on a host, the loop degrades gracefully: the
  repaired workbook (formula present) is promoted as the canonical version and
  the next iteration's Workbook-Integrity gate backstops any corruption.

## Tests

```bash
PYTHONPATH=scripts python -m pytest scripts/validation_agent/tests -q
```

Fixtures in `tests/make_fixture.py` are **synthetic test data only** — no value
represents a real tract, lease, well, or chain of title. Two scenarios are
exercised end-to-end: a repairable workbook that certifies, and a workbook with
a missing probate that halts and escalates.
