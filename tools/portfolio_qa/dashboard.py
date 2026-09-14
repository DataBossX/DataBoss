#!/usr/bin/env python3
"""Build a read-only portfolio QA dashboard from a cited-receipt ledger.

This tool does not open abstracts, does not write packages, and does not
talk to Drive. Feed it a local JSON ledger of *already cited* receipts.

Usage:
    python3 -m tools.portfolio_qa.dashboard \\
        --ledger /path/to/cited_ledger.json \\
        --output-dir /path/to/isolated/portfolio-qa-dashboard-<UTC>
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from tools.portfolio_qa.schema import (
    REQUIRED_COLUMNS,
    UNKNOWN_TOKEN,
    ZERO_COERCIONS,
    is_frozen_benchmark,
    refuse_zero_coercion,
)

EXTRA_COLUMNS: tuple[str, ...] = (
    "source_hold",
    "control_custody_hold",
    "evidence_class",
    "citations",
)

ALL_COLUMNS: tuple[str, ...] = REQUIRED_COLUMNS + EXTRA_COLUMNS

CANONICAL_PACKAGES: tuple[str, ...] = (
    "P1",
    "P2",
    "P3",
    "P10",
    "P11",
    "P12",
    "P13 Campbell",
    "P14",
    "P15",
    "Johnson P13",
    "Johnson P24",
    "Horizon §7",
)

MEASURED_COLUMNS: tuple[str, ...] = (
    "county_denominator",
    "county_matched",
    "missing_faces",
    "federal_pages",
    "federal_event_coverage",
)

TABLE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("package", "Package"),
    ("status", "Status"),
    ("confidence", "Confidence"),
    ("latest_verified_receipt_url_date", "Latest verified receipt URL/date"),
    ("county_denominator", "County denominator"),
    ("county_matched", "County matched"),
    ("missing_faces", "Missing faces"),
    ("federal_pages", "Federal pages"),
    ("federal_event_coverage", "Federal event coverage"),
    ("source_contradiction", "Source contradiction"),
    ("writer_gate", "Writer gate"),
    ("native_page_qa", "Native/page QA"),
    ("exact_membership", "Exact membership"),
    ("owner_action", "Owner action"),
    ("next_unique_action", "Next unique action"),
    ("source_hold", "Source hold"),
    ("control_custody_hold", "Control/custody hold"),
)

_FROZEN_EDIT_PHRASES: tuple[str, ...] = (
    "edit abstract",
    "overwrite frozen",
    "mutate the frozen",
)
_NEGATION_PHRASES: tuple[str, ...] = ("do not", "don't")

_UTC_STAMP = "%Y-%m-%dT%H:%MZ"


class LedgerError(ValueError):
    """Fail-closed ledger problem."""


def normalize_row(row: Mapping[str, Any]) -> dict[str, str]:
    package = str(row.get("package", "")).strip()
    if not package:
        raise LedgerError("every row needs a package name")
    out = {key: refuse_zero_coercion(row.get(key, UNKNOWN_TOKEN)) for key in ALL_COLUMNS}
    out["package"] = package
    return out


def _require_canonical_packages(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = [row["package"] for row in rows]
    missing = [name for name in CANONICAL_PACKAGES if name not in seen]
    extra = [name for name in seen if name not in CANONICAL_PACKAGES]
    if missing:
        raise LedgerError(f"ledger missing required packages: {missing}")
    if extra:
        raise LedgerError(f"ledger has unexpected packages: {extra}")
    if len(seen) != len(set(seen)):
        raise LedgerError("ledger has duplicate package rows")
    by_name = {row["package"]: row for row in rows}
    return [by_name[name] for name in CANONICAL_PACKAGES]


def load_ledger(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LedgerError("ledger root must be an object")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise LedgerError("ledger.rows must be a non-empty list")
    ordered = _require_canonical_packages([normalize_row(row) for row in rows])
    return {"meta": payload.get("meta") or {}, "rows": ordered}


def assert_unknown_never_zero(rows: list[Mapping[str, str]]) -> None:
    for row in rows:
        for key in MEASURED_COLUMNS:
            value = row[key]
            if value == UNKNOWN_TOKEN:
                continue
            if value.strip() in ZERO_COERCIONS:
                raise LedgerError(
                    f"{row['package']}.{key} is a bare zero without a cited "
                    "measurement; leave UNKNOWN if the receipt did not count it"
                )


def assert_holds_separated(rows: list[Mapping[str, str]]) -> None:
    for row in rows:
        source = row["source_hold"]
        control = row["control_custody_hold"]
        if source != UNKNOWN_TOKEN and source == control:
            raise LedgerError(
                f"{row['package']} collapsed source hold into control/custody hold"
            )


def assert_frozen_untouched(rows: list[Mapping[str, str]]) -> None:
    for row in rows:
        if not is_frozen_benchmark(row["status"]):
            continue
        action = row["next_unique_action"].lower()
        schedules_edit = any(phrase in action for phrase in _FROZEN_EDIT_PHRASES)
        negated = any(phrase in action for phrase in _NEGATION_PHRASES)
        if schedules_edit and not negated:
            raise LedgerError(
                f"{row['package']} is a frozen benchmark; do not schedule abstract edits"
            )


def write_csv(rows: list[Mapping[str, str]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ALL_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _generated_utc(meta: Mapping[str, Any]) -> str:
    return meta.get("generated_utc") or datetime.now(timezone.utc).strftime(_UTC_STAMP)


def _markdown_fields(row: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return (
        ("Status", row["status"]),
        (
            "Confidence / evidence class",
            f"{row['confidence']} / {row['evidence_class']}",
        ),
        ("Latest verified receipt URL/date", row["latest_verified_receipt_url_date"]),
        ("County denominator", row["county_denominator"]),
        ("County matched", row["county_matched"]),
        ("Missing faces", row["missing_faces"]),
        ("Federal pages", row["federal_pages"]),
        ("Federal event coverage", row["federal_event_coverage"]),
        ("Source contradiction", row["source_contradiction"]),
        ("Writer gate", row["writer_gate"]),
        ("Native/page QA", row["native_page_qa"]),
        ("Exact membership", row["exact_membership"]),
        ("Owner action", row["owner_action"]),
        ("Next unique action", row["next_unique_action"]),
        ("Source hold", row["source_hold"]),
        ("Control/custody hold", row["control_custody_hold"]),
        ("Citations", row["citations"]),
    )


def write_markdown(payload: Mapping[str, Any], path: Path) -> None:
    meta = payload["meta"]
    rows = payload["rows"]
    generated = _generated_utc(meta)
    lines = [
        "# Portfolio QA dashboard (read-only candidate)",
        "",
        f"Generated: `{generated}`",
        f"Drive live read this session: `{meta.get('drive_live_read', UNKNOWN_TOKEN)}`",
        f"Abstracts edited: `{meta.get('abstracts_edited', 'none')}`",
        "",
        "## Rules applied",
        "",
        "- UNKNOWN stays UNKNOWN; it is never converted to zero.",
        "- Source evidence outranks receipts; receipts outrank model conclusions.",
        "- A source hold is not a control/custody hold.",
        "- §15 / P15 is a frozen benchmark only. Abstracts were not edited.",
        "- No client facts were added beyond cited receipts.",
        "",
        "## Access",
        "",
        meta.get("access_note", UNKNOWN_TOKEN),
        "",
        "## Rows",
        "",
    ]
    for row in rows:
        lines.append(f"### {row['package']}")
        lines.append("")
        for label, value in _markdown_fields(row):
            lines.append(f"- **{label}:** {value}")
        lines.append("")
    lines.extend(
        [
            "## What this dashboard is not",
            "",
            "- Not a release, certification, or owner-review attestation.",
            "- Not a live Drive listing. If Drive live read is ACCESS_GAP, every URL is a citation, not a re-download.",
            "- Not permission to edit abstracts or enter an occupied writer lane.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _cell_class(value: str, column: str) -> str:
    if value == UNKNOWN_TOKEN:
        return "unknown"
    if column == "status" and is_frozen_benchmark(value):
        return "frozen"
    if column == "source_contradiction" or "CONTRADICTION" in value.upper():
        return "contradiction"
    if column == "status" and "HOLD" in value.upper():
        return "hold"
    return "cited"


def write_html(payload: Mapping[str, Any], path: Path) -> None:
    meta = payload["meta"]
    rows = payload["rows"]
    generated = html.escape(str(_generated_utc(meta)))
    access = html.escape(str(meta.get("drive_live_read", UNKNOWN_TOKEN)))
    access_note = html.escape(str(meta.get("access_note", UNKNOWN_TOKEN)))
    body_rows = []
    for row in rows:
        cells = [
            f'<td class="{_cell_class(row[key], key)}">{html.escape(row[key])}</td>'
            for key, _label in TABLE_COLUMNS
        ]
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    headers = "".join(f"<th>{html.escape(label)}</th>" for _key, label in TABLE_COLUMNS)
    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Portfolio QA dashboard — read-only candidate</title>
  <style>
    :root {{
      --ink: #1b1712;
      --paper: #f4efe4;
      --rule: #c8b89a;
      --unknown: #c47a12;
      --unknown-bg: #fff1d4;
      --hold: #8a2d2d;
      --hold-bg: #f6dede;
      --frozen: #245a7a;
      --frozen-bg: #dcecf4;
      --contradiction: #6b3fa0;
      --contradiction-bg: #efe6f8;
      --cited: #1b1712;
    }}
    html, body {{ margin: 0; background: var(--paper); color: var(--ink);
      font: 15px/1.45 "Iowan Old Style", "Palatino Linotype", Palatino, serif; }}
    header {{ padding: 28px 32px 16px; border-bottom: 3px solid var(--ink); }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0.01em; }}
    .banner {{ background: #2a2118; color: #f4efe4; padding: 12px 32px; font-size: 14px; }}
    .rules {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px; padding: 18px 32px; }}
    .rule {{ border: 1px solid var(--rule); padding: 10px 12px; background: #fffaf1; }}
    .rule strong {{ display: block; font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .scroll {{ overflow: auto; padding: 0 16px 40px; }}
    table {{ border-collapse: collapse; min-width: 2200px; width: 100%; }}
    th {{ position: sticky; top: 0; background: #2a2118; color: #f4efe4; text-align: left;
      font-size: 12px; letter-spacing: 0.04em; text-transform: uppercase; padding: 8px 10px; }}
    td {{ vertical-align: top; padding: 9px 10px; border-bottom: 1px solid var(--rule);
      max-width: 280px; }}
    td.unknown {{ background: var(--unknown-bg); color: var(--unknown); font-weight: 700; }}
    td.hold {{ background: var(--hold-bg); color: var(--hold); }}
    td.frozen {{ background: var(--frozen-bg); color: var(--frozen); font-weight: 700; }}
    td.contradiction {{ background: var(--contradiction-bg); color: var(--contradiction); }}
    footer {{ padding: 16px 32px 40px; color: #5c5346; font-size: 13px; }}
  </style>
</head>
<body>
  <header>
    <h1>Portfolio QA dashboard</h1>
    <p>Read-only candidate · generated {generated} · Drive live read: {access}</p>
  </header>
  <div class="banner">{access_note}</div>
  <section class="rules">
    <div class="rule"><strong>UNKNOWN</strong>Stays UNKNOWN. Never shown as zero.</div>
    <div class="rule"><strong>Evidence</strong>Source &gt; receipt &gt; model. No model fills.</div>
    <div class="rule"><strong>Holds</strong>Source hold ≠ control/custody hold.</div>
    <div class="rule"><strong>P15</strong>Frozen benchmark only. Abstracts not edited.</div>
  </section>
  <div class="scroll">
    <table>
      <thead><tr>{headers}</tr></thead>
      <tbody>
        {''.join(body_rows)}
      </tbody>
    </table>
  </div>
  <footer>
    Not a release. Not a certification. Not a live Drive listing.
    Isolated export only — do not treat this file as permission to write a package.
  </footer>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def build(ledger_path: Path, output_dir: Path) -> dict[str, Path]:
    payload = load_ledger(ledger_path)
    assert_unknown_never_zero(payload["rows"])
    assert_holds_separated(payload["rows"])
    assert_frozen_untouched(payload["rows"])
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "portfolio_qa_dashboard.csv"
    md_path = output_dir / "portfolio_qa_dashboard.md"
    html_path = output_dir / "portfolio_qa_dashboard.html"
    write_csv(payload["rows"], csv_path)
    write_markdown(payload, md_path)
    write_html(payload, html_path)
    (output_dir / "cited_ledger.snapshot.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {"csv": csv_path, "md": md_path, "html": html_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    written = build(args.ledger, args.output_dir)
    for label, path in written.items():
        print(f"{label}\t{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
