"""
Headless LibreOffice recalculation.

Recalculates a COPY of a workbook version and writes a new version. If
LibreOffice is not installed, returns a clean dependency-failure result (which
the orchestrator escalates) — it never pretends success. Output is verified to
open and be a valid ZIP; corrupt output never replaces good input.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

COMMON_PATHS = [
    "/usr/bin/libreoffice", "/usr/bin/soffice", "/usr/local/bin/soffice",
    "/opt/libreoffice/program/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]


@dataclass
class RecalcResult:
    ok: bool
    reason: str
    output_path: Optional[str] = None
    libreoffice_path: Optional[str] = None


def detect_libreoffice(configured: str = "") -> Optional[str]:
    if configured and Path(configured).exists():
        return configured
    which = shutil.which("libreoffice") or shutil.which("soffice")
    if which:
        return which
    for p in COMMON_PATHS:
        if Path(p).exists():
            return p
    return None


def recalc(source_version: str | Path, dest_path: str | Path,
           configured_path: str = "", timeout: int = 180) -> RecalcResult:
    src = Path(source_version)
    dest = Path(dest_path)
    if dest.exists():
        return RecalcResult(False, f"Refusing to overwrite existing version: {dest}")
    lo = detect_libreoffice(configured_path)
    if not lo:
        return RecalcResult(False, "LibreOffice not found — dependency failure (escalate)")

    with tempfile.TemporaryDirectory() as tmp:
        profile = Path(tmp) / "lo_profile"
        outdir = Path(tmp) / "out"
        outdir.mkdir()
        # Use a macro-free convert; LibreOffice recalculates on load by default
        # when the workbook has fullCalcOnLoad set (our xml_editor sets it).
        cmd = [lo, "--headless", "--nologo", "--nofirststartwizard",
               f"-env:UserInstallation=file://{profile}",
               "--calc", "--convert-to", "xlsx:Calc MS Excel 2007 XML",
               "--outdir", str(outdir), str(src)]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                                  env={**os.environ, "HOME": tmp})
        except subprocess.TimeoutExpired:
            return RecalcResult(False, "LibreOffice recalculation timed out (escalate)",
                                libreoffice_path=lo)
        except Exception as e:  # pragma: no cover
            return RecalcResult(False, f"LibreOffice invocation error: {e}", libreoffice_path=lo)

        produced = outdir / (src.stem + ".xlsx")
        if not produced.exists():
            return RecalcResult(False,
                f"LibreOffice produced no output (rc={proc.returncode}); keeping prior version",
                libreoffice_path=lo)
        if not zipfile.is_zipfile(produced):
            return RecalcResult(False, "Recalc output is not a valid workbook; rollback",
                                libreoffice_path=lo)
        with zipfile.ZipFile(produced) as z:
            if z.testzip() is not None or "[Content_Types].xml" not in z.namelist():
                return RecalcResult(False, "Recalc output failed structure check; rollback",
                                    libreoffice_path=lo)
        shutil.copy2(produced, dest)
    return RecalcResult(True, "recalculated", output_path=str(dest), libreoffice_path=lo)
