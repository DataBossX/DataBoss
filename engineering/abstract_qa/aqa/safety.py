"""Overwrite, missing-source and cloud-sync guards. Findings are evidence, never auto-fixed."""
from __future__ import annotations

import os
import re
import stat as statmod
from pathlib import Path
from typing import Any

# Windows reparse/offline attribute bits (st_file_attributes only exists on Windows).
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000
PLACEHOLDER_MASK = FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_OPEN | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS

CONFLICT_NAME = re.compile(r"(?i)(conflicted copy|\(\s*case conflict\)|-[A-Z0-9_.-]+-PC\b|\bsync-conflict\b)")
TEMP_NAME = re.compile(r"(^~\$|\.tmp$|\.part$|\.crdownload$|^\.~lock\.)", re.I)


def finding(level: str, code: str, detail: str, **extra: Any) -> dict[str, Any]:
    d = {"level": level, "code": code, "detail": detail}
    d.update(extra)
    return d


def _resolve(p: str | Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(p))))


def is_within(child: Path, parent: Path) -> bool:
    c = os.path.normcase(str(_resolve(child)))
    p = os.path.normcase(str(_resolve(parent)))
    return c == p or c.startswith(p.rstrip(os.sep) + os.sep)


def cloud_marker(path: str | Path, markers: list[str]) -> str | None:
    low = str(path).replace("\\", "/").casefold()
    for m in markers:
        if m.casefold() in low:
            return m
    return None


def is_placeholder(st: os.stat_result) -> bool:
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & PLACEHOLDER_MASK)


def preflight(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    out_root = _resolve(cfg["output_root"])
    markers = cfg["cloud_markers"]
    for root in cfg["source_roots"]:
        r = _resolve(root)
        if not r.is_dir():
            out.append(finding("BLOCK", "SOURCE_ROOT_MISSING", f"source root not found: {r}", path=str(r)))
            continue
        if is_within(out_root, r) or is_within(r, out_root):
            out.append(finding("BLOCK", "OUTPUT_OVERLAPS_SOURCE", f"output root {out_root} overlaps source root {r}"))
        m = cloud_marker(r, markers)
        if m:
            out.append(finding("WARN", "SOURCE_IN_CLOUD_SYNC", f"source root under cloud-sync marker '{m}': {r}; reads may hydrate files", path=str(r)))
    for prot in cfg["protected_paths"]:
        p = _resolve(prot)
        if is_within(out_root, p) or is_within(p, out_root):
            out.append(finding("BLOCK", "OUTPUT_OVERLAPS_PROTECTED", f"output root overlaps protected canonical path {p}"))
    m = cloud_marker(out_root, markers)
    if m:
        out.append(finding("BLOCK", "OUTPUT_IN_CLOUD_SYNC", f"output root under cloud-sync marker '{m}': {out_root}"))
    for var in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        base = os.environ.get(var)
        if base and is_within(out_root, Path(base)):
            out.append(finding("BLOCK", "OUTPUT_IN_CLOUD_SYNC", f"output root under ${var} ({base})"))
    return out


def classify_name(name: str) -> list[dict[str, Any]]:
    out = []
    base = os.path.basename(name)
    if CONFLICT_NAME.search(base):
        out.append(finding("WARN", "SYNC_CONFLICT_COPY", f"filename looks like a sync-conflict copy: {name}", path=name))
    if TEMP_NAME.search(base):
        out.append(finding("WARN", "TEMP_FILE_IN_SOURCE", f"temporary/lock file in source tree: {name}", path=name))
    return out


def compare_manifests(prev: list[dict[str, Any]], cur: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect disappeared, changed and unexpected-new sources between two inventories."""
    out: list[dict[str, Any]] = []
    pm = {e["path"]: e for e in prev if e.get("sha256")}
    cm = {e["path"]: e for e in cur if e.get("sha256")}
    for path, e in sorted(pm.items()):
        c = cm.get(path)
        if c is None:
            out.append(finding("BLOCK", "SOURCE_DISAPPEARED", f"previously inventoried source is missing: {path}", path=path, sha256=e["sha256"]))
        elif c["sha256"] != e["sha256"]:
            out.append(finding("BLOCK", "SOURCE_CHANGED", f"source bytes changed since baseline: {path}", path=path, was=e["sha256"], now=c["sha256"]))
    for path in sorted(set(cm) - set(pm)):
        out.append(finding("INFO", "SOURCE_NEW", f"source not in baseline: {path}", path=path))
    return out


def check_expected(expected: list[dict[str, Any]], cur: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_path = {e["path"]: e for e in cur}
    by_sha: dict[str, list[str]] = {}
    for e in cur:
        if e.get("sha256"):
            by_sha.setdefault(e["sha256"], []).append(e["path"])
    for exp in expected:
        p, sha = exp.get("path"), exp.get("sha256")
        e = by_path.get(p)
        if e is None:
            where = by_sha.get(sha, []) if sha else []
            out.append(finding("BLOCK", "EXPECTED_SOURCE_MISSING", f"expected source not found at {p}", path=p, found_elsewhere=where))
        elif sha and e.get("sha256") != sha:
            out.append(finding("BLOCK", "EXPECTED_SOURCE_HASH_MISMATCH", f"hash differs from expectation: {p}", path=p, expected=sha, actual=e.get("sha256")))
    return out


def stat_fingerprint(path: str | Path) -> tuple[int, int] | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns)


def mutation_check(before: dict[str, tuple[int, int] | None]) -> list[dict[str, Any]]:
    out = []
    for p, fp in sorted(before.items()):
        now = stat_fingerprint(p)
        if now != fp:
            out.append(finding("BLOCK", "SOURCE_MUTATED_DURING_RUN", f"source size/mtime changed while the run was reading: {p}", path=p))
    return out


class OutputGuard:
    """All writes go through here; anything outside the run dir or onto protected paths is refused."""

    def __init__(self, run_dir: Path, protected: list[str], source_roots: list[str]):
        self.run_dir = _resolve(run_dir)
        self._denied = [_resolve(p) for p in list(protected) + list(source_roots)]

    def check(self, path: Path) -> Path:
        p = _resolve(path)
        if not is_within(p, self.run_dir):
            raise PermissionError(f"write outside run dir refused: {p}")
        for d in self._denied:
            if is_within(p, d):
                raise PermissionError(f"write into protected/source path refused: {p}")
        return p
