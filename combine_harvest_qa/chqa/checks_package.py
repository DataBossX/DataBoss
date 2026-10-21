"""Package checks: ZIP integrity, SHA-256, required client files, internal-QA leakage."""
from __future__ import annotations

import hashlib
import os
import re
import zipfile

from .findings import Report

INTERNAL_PAT = re.compile(r"(^|/)(QA_INTERNAL|qa|report_.*\.json|.*_qa_.*|.*internal.*|.*\.b64|.*scratch.*)", re.I)


def sha256_file(path: str, block: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def check_zip(path: str, rep: Report, *, required: list[str] | None = None, expected_sha: str | None = None) -> dict:
    rep.inputs.setdefault("files", []).append(path)
    info = {"file": os.path.basename(path), "bytes": os.path.getsize(path), "sha256": sha256_file(path)}
    if expected_sha and expected_sha.lower() != info["sha256"]:
        rep.add("zip_sha256", "error", path, "SHA-256 differs from expected", expected=expected_sha, actual=info["sha256"])
    try:
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            if bad:
                rep.add("zip_integrity", "error", path, "corrupt member (CRC)", actual=bad)
            names = [n for n in z.namelist() if not n.endswith("/")]
    except zipfile.BadZipFile as e:
        rep.add("zip_integrity", "error", path, f"not a valid zip: {e}")
        return info
    info["members"] = names
    for req in required or []:
        if not any(re.search(req, n) for n in names):
            rep.add("missing_client_file", "error", path, "required client file missing", expected=req)
    for n in names:
        if INTERNAL_PAT.search(n):
            rep.add("internal_in_client_package", "error", path, "internal QA/scratch file inside client package", actual=n)
    dup = {n for n in names if names.count(n) > 1}
    for n in dup:
        rep.add("zip_duplicate_member", "error", path, "duplicate member name", actual=n)
    return info


def required_client_files(section: str, blm_serials: list[str]) -> list[str]:
    pats = [rf"{section}.*Abstract_Index.*\.ods$", rf"{section}.*Abstract_Index.*\.xlsx$",
            r"Abstract_Checklist.*\.xlsx$", r"Certification_Letter.*\.docx$", r"Certification_Letter.*\.pdf$"]
    pats += [rf"{s}.*\.ods$" for s in blm_serials]
    return pats
