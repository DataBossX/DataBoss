"""land_title_os — the control layer every DataBossX agent must share.

Stdlib-only foundation modules:

- ``util``       stable IDs, hashing, UTC timestamps
- ``manifest``   one machine-readable manifest per land-section project
- ``assets``     master asset inventory (SQLite: stable IDs, SHA-256, duplicates)
- ``evidence``   evidence ledger with source-authority ranking + multi-axis confidence
- ``receipts``   immutable, hash-chained run receipts ("no receipt, no work")
- ``promotion``  SOURCE → STAGING → EXTRACTED → RECONCILED → QA → APPROVED → DELIVERED
- ``issues``     open-item management (unique IDs, severity, human approval)
- ``qa_engine``  deterministic title-report QA checks (exact fractions, no floats)

Design law: agents may propose; only recorded evidence, passing checks, and
(where flagged) human approval let work advance. Nothing here fabricates data.
"""

__all__ = [
    "util",
    "manifest",
    "assets",
    "evidence",
    "receipts",
    "promotion",
    "issues",
    "qa_engine",
]
