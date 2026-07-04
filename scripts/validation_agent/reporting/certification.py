"""Certification (Component 9): stamp a certified version + title-picture summary."""
from __future__ import annotations

import hashlib
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..ingestion.workbook_map import WorkbookMapper
from ..models import LoopState


@dataclass
class CertifiedArtifact:
    workbook_path: Path
    summary_path: Path
    sha256: str
    version: int


class Certifier:
    def __init__(self, conn: sqlite3.Connection, run_id: str) -> None:
        self._conn = conn
        self._run_id = run_id

    def certify(
        self, final_version_path: Path, version: int, state: LoopState, out_dir: Path
    ) -> CertifiedArtifact:
        if state != LoopState.CERTIFIED:
            raise RuntimeError(
                f"certify() requires CERTIFIED state, got {state.value}"
            )
        out_dir.mkdir(parents=True, exist_ok=True)
        certified = out_dir / (final_version_path.stem + "_CERTIFIED.xlsx")
        shutil.copy(final_version_path, certified)
        digest = hashlib.sha256(certified.read_bytes()).hexdigest()
        self._conn.execute(
            "INSERT INTO versions(version, run_id, path, sha256, created_ts, parent_version) "
            "VALUES(?,?,?,?,?,?)",
            (version + 1, self._run_id, str(certified), digest,
             datetime.now(timezone.utc).isoformat(), version),
        )
        self._conn.commit()
        summary = self._title_picture(certified, out_dir)
        return CertifiedArtifact(certified, summary, digest, version + 1)

    def _title_picture(self, workbook: Path, out_dir: Path) -> Path:
        model = WorkbookMapper.load(workbook)
        lines = ["# Final Title Picture — Section 31-12N-24W, Roger Mills Co., OK", ""]
        title_name = next((n for n in model.wb.sheetnames if n.strip().lower() == "title"), None)
        if title_name:
            ws = model.wb[title_name]
            cur_tract = None
            for r in range(1, ws.max_row + 1):
                b = ws.cell(r, 2).value
                c = ws.cell(r, 3).value
                if isinstance(b, str) and b.upper().startswith("TRACT"):
                    cur_tract = b.strip()
                    lines.append(f"\n## {cur_tract}")
                elif isinstance(b, str) and b.strip() and c is not None and cur_tract:
                    lines.append(f"- {b.splitlines()[0]} — {c}")
        out = out_dir / "final_title_picture.md"
        out.write_text("\n".join(lines), encoding="utf-8")
        return out
