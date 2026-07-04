"""LibreOffice headless recalculation.

Recalculates a *copied* workbook version and writes a new version. LibreOffice
is invoked with an argument list (never ``shell=True``). If LibreOffice is not
available the runner reports a clean dependency failure — it never pretends the
recalculation happened.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from core.hashing import sha256_file

_COMMON_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice",
    "/usr/bin/libreoffice",
    "/opt/libreoffice/program/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]


@dataclass
class RecalcResult:
    ok: bool
    output_path: Optional[Path]
    before_sha256: str
    after_sha256: Optional[str]
    detail: str
    dependency_missing: bool = False


def detect_libreoffice(configured: Optional[Path] = None) -> Optional[Path]:
    if configured:
        p = Path(configured)
        if p.exists():
            return p
    which = shutil.which("soffice") or shutil.which("libreoffice")
    if which:
        return Path(which)
    for candidate in _COMMON_PATHS:
        p = Path(candidate)
        if p.exists():
            return p
    return None


class LibreOfficeRunner:
    def __init__(self, soffice_path: Optional[Path] = None, timeout_sec: int = 120) -> None:
        self.soffice_path = detect_libreoffice(soffice_path)
        self.timeout_sec = timeout_sec

    @property
    def available(self) -> bool:
        return self.soffice_path is not None

    def recalculate(self, source_version: Path, dest_path: Path) -> RecalcResult:
        source_version = Path(source_version)
        before = sha256_file(source_version)

        if not self.available:
            return RecalcResult(
                ok=False,
                output_path=None,
                before_sha256=before,
                after_sha256=None,
                detail="LibreOffice not found; recalculation unavailable.",
                dependency_missing=True,
            )
        if dest_path.exists():
            return RecalcResult(
                ok=False,
                output_path=None,
                before_sha256=before,
                after_sha256=None,
                detail=f"refusing to overwrite existing version: {dest_path}",
            )

        profile = Path(tempfile.mkdtemp(prefix="dbx_lo_profile_"))
        out_dir = Path(tempfile.mkdtemp(prefix="dbx_lo_out_"))
        ext = source_version.suffix.lower().lstrip(".")
        convert_filter = (
            "xlsm:Calc MS Excel 2007 VBA" if ext == "xlsm"
            else "xlsx:Calc MS Excel 2007 XML"
        )
        # Standard headless convert. Opening the file forces a load-time
        # recalculation (the workbook carries fullCalcOnLoad after repair).
        args: List[str] = [
            str(self.soffice_path),
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--nodefault",
            "--nofirststartwizard",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to",
            convert_filter,
            "--outdir",
            str(out_dir),
            str(source_version),
        ]
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            shutil.rmtree(profile, ignore_errors=True)
            shutil.rmtree(out_dir, ignore_errors=True)
            return RecalcResult(
                ok=False,
                output_path=None,
                before_sha256=before,
                after_sha256=None,
                detail="LibreOffice recalculation timed out.",
            )

        produced = out_dir / (source_version.stem + source_version.suffix)
        if proc.returncode != 0 or not produced.exists():
            # LibreOffice sometimes writes with a normalized name; scan the dir.
            candidates = list(out_dir.glob(f"*{source_version.suffix}"))
            produced = candidates[0] if candidates else produced
        if not produced.exists():
            shutil.rmtree(profile, ignore_errors=True)
            shutil.rmtree(out_dir, ignore_errors=True)
            return RecalcResult(
                ok=False,
                output_path=None,
                before_sha256=before,
                after_sha256=None,
                detail=(
                    f"LibreOffice produced no output (rc={proc.returncode}): "
                    f"{proc.stderr[:400]}"
                ),
            )

        # validate produced workbook before adopting it
        try:
            with zipfile.ZipFile(produced) as zf:
                if zf.testzip() is not None:
                    raise zipfile.BadZipFile("bad entry")
        except zipfile.BadZipFile:
            shutil.rmtree(profile, ignore_errors=True)
            shutil.rmtree(out_dir, ignore_errors=True)
            return RecalcResult(
                ok=False,
                output_path=None,
                before_sha256=before,
                after_sha256=None,
                detail="Recalculated workbook is corrupt; not adopted.",
            )

        shutil.copy2(produced, dest_path)
        shutil.rmtree(profile, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)
        return RecalcResult(
            ok=True,
            output_path=dest_path,
            before_sha256=before,
            after_sha256=sha256_file(dest_path),
            detail="recalculated",
        )
