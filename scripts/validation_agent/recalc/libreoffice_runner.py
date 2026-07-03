"""Headless LibreOffice recalculation.

Recalculates a copied workbook version by converting it through headless
LibreOffice, producing a NEW version file. If LibreOffice is missing, the
failure is logged and reported honestly — success is never faked. The original
good version is never overwritten with corrupt output.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

_COMMON_PATHS = [
    "/usr/bin/libreoffice",
    "/usr/bin/soffice",
    "/opt/libreoffice/program/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]


def detect_libreoffice(configured_path: str = "") -> Optional[str]:
    """Return a usable LibreOffice executable path, or None."""
    if configured_path and Path(configured_path).exists():
        return configured_path
    which = shutil.which("libreoffice") or shutil.which("soffice")
    if which:
        return which
    for p in _COMMON_PATHS:
        if Path(p).exists():
            return p
    return None


class LibreOfficeResult:
    def __init__(self, ok: bool, output_path: Optional[Path] = None,
                 error: str = "", available: bool = True):
        self.ok = ok
        self.output_path = output_path
        self.error = error
        self.available = available

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "available": self.available,
            "output_path": str(self.output_path) if self.output_path else None,
            "error": self.error,
        }


def recalculate(source_version: str | Path, dest_version: str | Path,
                configured_path: str = "", timeout: int = 120
                ) -> LibreOfficeResult:
    """Recalculate ``source_version`` -> ``dest_version`` (never overwrites)."""
    source = Path(source_version)
    dest = Path(dest_version)
    if dest.exists():
        return LibreOfficeResult(False, error=f"Refusing to overwrite {dest}")

    exe = detect_libreoffice(configured_path)
    if not exe:
        return LibreOfficeResult(
            False, available=False,
            error="LibreOffice not found; recalculation skipped (dependency "
                  "failure logged, not faked).",
        )

    with tempfile.TemporaryDirectory(prefix="dbx_lo_") as tmp:
        tmp_dir = Path(tmp)
        # Convert to xlsx in an isolated profile so we don't touch anything.
        profile = tmp_dir / "profile"
        cmd = [
            exe, "--headless", "--calc",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to", "xlsx:Calc MS Excel 2007 XML",
            "--outdir", str(tmp_dir), str(source),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return LibreOfficeResult(False, error="LibreOffice timed out.")
        except Exception as e:
            return LibreOfficeResult(False, error=f"LibreOffice error: {e}")
        if proc.returncode != 0:
            return LibreOfficeResult(
                False, error=f"LibreOffice exit {proc.returncode}: "
                             f"{proc.stderr.decode(errors='ignore')[:400]}",
            )
        produced = tmp_dir / (source.stem + ".xlsx")
        if not produced.exists():
            # Fall back to any produced xlsx.
            candidates = list(tmp_dir.glob("*.xlsx"))
            if not candidates:
                return LibreOfficeResult(
                    False, error="LibreOffice produced no output file.")
            produced = candidates[0]

        # Verify the produced file opens before accepting it.
        try:
            import openpyxl
            wb = openpyxl.load_workbook(produced, read_only=True)
            wb.close()
        except Exception as e:
            return LibreOfficeResult(
                False, error=f"Recalc output failed to open (corrupt): {e}")

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(produced, dest)
        return LibreOfficeResult(True, output_path=dest)
