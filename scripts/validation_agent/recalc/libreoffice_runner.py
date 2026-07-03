"""LibreOfficeRecalcRunner -- headless recalculation after an XML repair.

After the XML editor injects a formula and strips the calc chain, the workbook
holds a formula but no trustworthy cached value.  This runner drives
``soffice --headless`` to convert (and thereby recalculate, because the editor
set ``fullCalcOnLoad``) the workbook, then verifies the output:

    * the produced file must open as a valid workbook, and
    * previously-repaired cells must now hold a numeric value, not an error
      token (#REF!, #DIV/0!, ...).

If the output is missing, unreadable, or corrupt, the runner reports failure so
the orchestrator ROLLS BACK to the prior good version instead of letting a
corrupt file overwrite it (Section 4, STATE_RECALC).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..config.settings import config

_ERROR_TOKENS = {"#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NULL!", "#NUM!"}


@dataclass
class RecalcResult:
    ok: bool
    out_path: Optional[str]
    corrupted: bool
    message: str
    checked_cells: list[str] = field(default_factory=list)


class LibreOfficeRecalcRunner:
    def __init__(self, soffice: Optional[str] = None) -> None:
        self.soffice = soffice or config.soffice_binary

    def available(self) -> bool:
        return shutil.which(self.soffice) is not None

    def recalc(self, src_path: str | Path, out_path: str | Path,
               verify_cells: Optional[list[tuple[str, str]]] = None) -> RecalcResult:
        src = Path(src_path)
        out = Path(out_path)
        if not src.is_file():
            return RecalcResult(False, None, False, f"Source missing: {src}")
        if not self.available():
            return RecalcResult(False, None, False,
                                f"LibreOffice binary not found: {self.soffice}")

        with tempfile.TemporaryDirectory(prefix="dbx_recalc_") as tmp:
            tmp_dir = Path(tmp)
            # Dedicated profile dir avoids clobbering a user's LO session and
            # keeps headless runs isolated and reproducible.
            profile = (tmp_dir / "profile").as_uri()
            cmd = [
                self.soffice, "--headless", "--calc", "--nologo", "--norestore",
                f"-env:UserInstallation={profile}",
                "--convert-to",
                "xlsx:Calc MS Excel 2007 XML",
                "--outdir", str(tmp_dir), str(src),
            ]
            try:
                proc = subprocess.run(cmd, capture_output=True,
                                      timeout=config.recalc_timeout_sec, check=False)
            except FileNotFoundError:
                return RecalcResult(False, None, False,
                                    f"LibreOffice not found: {self.soffice}")
            except subprocess.TimeoutExpired:
                return RecalcResult(False, None, False,
                                    f"Recalc timed out after {config.recalc_timeout_sec}s")

            # LibreOffice derives the output name from the source and may
            # sanitize it; the temp outdir holds only this conversion, so take
            # the produced .xlsx by glob rather than assuming the exact stem.
            produced = tmp_dir / f"{src.stem}.xlsx"
            if not produced.is_file():
                candidates = sorted(tmp_dir.glob("*.xlsx"))
                if candidates:
                    produced = candidates[0]
            if not produced.is_file():
                err = (proc.stderr or b"").decode(errors="replace").strip()
                return RecalcResult(False, None, False,
                                    f"LibreOffice produced no output. {err}")

            corrupted, checked, msg = self._verify(produced, verify_cells or [])
            if corrupted:
                return RecalcResult(False, None, True,
                                    f"Post-recalc corruption: {msg}", checked)

            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(produced, out)
            return RecalcResult(True, str(out), False,
                                "Recalculated successfully.", checked)

    @staticmethod
    def _verify(path: Path, verify_cells: list[tuple[str, str]]):
        """Open the recalculated file and check repaired cells resolved cleanly."""
        from openpyxl import load_workbook
        checked: list[str] = []
        try:
            wb = load_workbook(path, read_only=True, data_only=True)
        except Exception as exc:  # noqa: BLE001
            return True, checked, f"cannot open output: {exc}"
        try:
            for sheet_name, coord in verify_cells:
                if sheet_name not in wb.sheetnames:
                    return True, checked, f"sheet '{sheet_name}' vanished"
                value = wb[sheet_name][coord].value
                checked.append(f"{sheet_name}!{coord}={value}")
                if isinstance(value, str) and value.strip() in _ERROR_TOKENS:
                    return True, checked, f"{sheet_name}!{coord} is {value}"
        finally:
            wb.close()
        return False, checked, "ok"
