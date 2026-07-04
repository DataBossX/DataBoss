"""Exhaustive per-run audit report (Component 9) — lives beside the workbook."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class AuditReportBuilder:
    def __init__(self, conn: sqlite3.Connection, run_id: str) -> None:
        self._conn = conn
        self._run_id = run_id

    def build(self, out_path: Path) -> Path:
        lines: list[str] = []
        w = lines.append
        w(f"# Validation & Repair Audit — run {self._run_id}")
        w(f"Generated {datetime.now(timezone.utc).isoformat()}\n")

        w("## Versions")
        for row in self._conn.execute(
            "SELECT version, path, sha256, created_ts FROM versions "
            "WHERE run_id=? ORDER BY version", (self._run_id,)
        ):
            w(f"- v{row['version']}: `{Path(row['path']).name}` "
              f"sha256={row['sha256'][:12]}… @ {row['created_ts']}")
        w("")

        w("## Per-iteration validation results")
        for row in self._conn.execute(
            "SELECT version, gate, passed, severity, message, metric, expected "
            "FROM validation_results WHERE run_id=? ORDER BY id", (self._run_id,)
        ):
            mark = "PASS" if row["passed"] else row["severity"]
            metric = "" if row["metric"] is None else f" [{row['metric']:.6g} vs {row['expected']}]"
            w(f"- v{row['version']} {row['gate']} **{mark}** — {row['message']}{metric}")
        w("")

        w("## Fixes applied")
        n_fixes = 0
        for row in self._conn.execute(
            "SELECT version, strategy_id, risk, coord, before, after, justification "
            "FROM fixes WHERE run_id=? ORDER BY id", (self._run_id,)
        ):
            n_fixes += 1
            w(f"- v{row['version']} `{row['strategy_id']}` ({row['risk']}) "
              f"@ {row['coord']}: {row['before']} → {row['after']} — {row['justification']}")
        if n_fixes == 0:
            w("- (none)")
        w("")

        w("## Escalations (halt + examiner handoff)")
        n_esc = 0
        for row in self._conn.execute(
            "SELECT version, gate, category, reason FROM escalations "
            "WHERE run_id=? ORDER BY id", (self._run_id,)
        ):
            n_esc += 1
            w(f"- v{row['version']} {row['gate']}/{row['category']}: {row['reason']}")
        if n_esc == 0:
            w("- (none)")
        w("")

        w("## API spend ledger")
        total = 0.0
        for row in self._conn.execute(
            "SELECT ts, cost_usd, note FROM spend_ledger WHERE run_id=? ORDER BY id",
            (self._run_id,)
        ):
            total += float(row["cost_usd"])
            w(f"- {row['ts']} ${row['cost_usd']} {row['note']}")
        w(f"\n**Total spend: ${total:.2f}**")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return out_path
