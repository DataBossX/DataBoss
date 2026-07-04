"""Headless LibreOffice recalculation.

If LibreOffice is not found, the runner logs a dependency failure and returns a
clear ``unavailable`` result — it never pretends success. Recalc operates on a
copied version and writes a new version; a corrupt result never overwrites a
good file.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

COMMON_PATHS = [
    "/usr/bin/soffice", "/usr/bin/libreoffice", "/usr/local/bin/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]


def detect_libreoffice(configured: Optional[str] = None) -> Optional[str]:
    if configured and Path(configured).exists():
        return configured
    which = shutil.which("soffice") or shutil.which("libreoffice")
    if which:
        return which
    for p in COMMON_PATHS:
        if Path(p).exists():
            return p
    return None


def recalculate(src_version: Path, dest_version: Path,
                libreoffice_path: Optional[str] = None) -> Dict[str, Any]:
    src_version, dest_version = Path(src_version), Path(dest_version)
    if dest_version.exists():
        raise FileExistsError(f"refusing to overwrite {dest_version}")
    binary = detect_libreoffice(libreoffice_path)
    if not binary:
        return {"status": "unavailable", "reason": "LibreOffice not found",
                "recommended_action": "Install LibreOffice or set LIBREOFFICE_PATH."}

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        work = tmp / src_version.name
        shutil.copy2(src_version, work)
        profile = tmp / "profile"
        cmd = [binary, "--headless", "--norestore",
               f"-env:UserInstallation=file://{profile}",
               "--convert-to", "xlsx:Calc MS Excel 2007 XML",
               "--outdir", str(tmp), str(work)]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=180, text=True)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return {"status": "error", "reason": f"LibreOffice failed: {e}"}
        produced = tmp / (work.stem + ".xlsx")
        if not produced.exists() or proc.returncode != 0:
            return {"status": "error", "reason": "LibreOffice produced no output",
                    "stderr": (proc.stderr or "")[:400]}
        # Validate before promoting.
        import zipfile
        if not zipfile.is_zipfile(produced):
            return {"status": "error", "reason": "recalc output not a valid workbook"}
        dest_version.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(produced, dest_version)
    return {"status": "ok", "output": str(dest_version)}
