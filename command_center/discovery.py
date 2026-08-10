"""Deterministic, metadata-first project discovery.

No hashing every byte, no OCR, no AI calls. Just directory listings and
mtimes, cached incrementally in SQLite so repeat launches are fast.
"""
import json
import os
import time
from pathlib import Path

# Roots are configurable via env vars so this runs identically on Ryan's
# Windows box (C:\DataBoss\...) and in a dev/test sandbox. Read live (not
# frozen at import time) so tests can point at a scratch directory and
# authorization checks always see the current configuration.
_ROOT_ENV_DEFAULTS = {
    "penterra": ("DATABOSSX_PENTERRA_ROOT", r"C:\DataBoss\Penterra"),
    "horizon": ("DATABOSSX_HORIZON_ROOT", r"C:\DataBoss\Horizon"),
}


def get_roots() -> dict:
    return {lane: os.environ.get(var, default) for lane, (var, default) in _ROOT_ENV_DEFAULTS.items()}


class _LiveRoots:
    """Dict-like view so existing `DEFAULT_ROOTS[...]` / `in` callers keep
    working while always reflecting the current environment."""

    def __getitem__(self, key):
        return get_roots()[key]

    def __contains__(self, key):
        return key in get_roots()

    def __iter__(self):
        return iter(get_roots())

    def items(self):
        return get_roots().items()

    def keys(self):
        return get_roots().keys()


DEFAULT_ROOTS = _LiveRoots()

EVIDENCE_HINTS = (
    "runsheet", "abstract", "report", "deed", "title", "lease",
    "division order", "probate", "affidavit", "patent",
)

WORKING_SUBDIR = "_DataBossX_Working"


def _safe_listdir(path: Path):
    try:
        return list(os.scandir(path))
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return []


def discover_lane(lane: str, root: str):
    """Scan one lane root (Penterra/Horizon) for project subfolders.

    Returns a list of lightweight project summaries. Never opens/reads
    file contents -- only names, sizes, and mtimes.
    """
    root_path = Path(root)
    entries = _safe_listdir(root_path)
    projects = []
    for entry in entries:
        if not entry.is_dir(follow_symlinks=False):
            continue
        if entry.name == WORKING_SUBDIR or entry.name.startswith("."):
            continue
        projects.append(_summarize_project(lane, Path(entry.path)))
    projects.sort(key=lambda p: p["last_mtime"], reverse=True)
    return projects


def _summarize_project(lane: str, project_path: Path):
    files = []
    total_size = 0
    latest_mtime = project_path.stat().st_mtime if project_path.exists() else 0.0
    evidence_found = set()
    for entry in _walk_shallow(project_path):
        try:
            st = entry.stat()
        except OSError:
            continue
        total_size += st.st_size
        latest_mtime = max(latest_mtime, st.st_mtime)
        files.append(entry.name)
        lower = entry.name.lower()
        for hint in EVIDENCE_HINTS:
            if hint in lower:
                evidence_found.add(hint)

    return {
        "lane": lane,
        "project": project_path.name,
        "path": str(project_path),
        "file_count": len(files),
        "total_size_bytes": total_size,
        "last_mtime": latest_mtime,
        "last_mtime_iso": time.strftime(
            "%Y-%m-%d %H:%M", time.localtime(latest_mtime)
        ) if latest_mtime else None,
        "evidence_present": sorted(evidence_found),
        "working_dir": str(project_path / WORKING_SUBDIR),
    }


def _walk_shallow(project_path: Path, max_depth: int = 2):
    """Yield DirEntry objects up to max_depth without following symlinks."""
    stack = [(project_path, 0)]
    while stack:
        current, depth = stack.pop()
        for entry in _safe_listdir(current):
            if entry.name.startswith(".") or entry.name == WORKING_SUBDIR:
                continue
            if entry.is_dir(follow_symlinks=False):
                if depth < max_depth:
                    stack.append((Path(entry.path), depth + 1))
            else:
                yield entry


def discover_all():
    result = {}
    for lane, root in DEFAULT_ROOTS.items():
        result[lane] = discover_lane(lane, root)
    return result


def cache_projects(conn, lane: str, projects: list) -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    for p in projects:
        conn.execute(
            """
            INSERT INTO project_cache (path, project, client, lane, last_scan, file_count, last_mtime, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                project=excluded.project, lane=excluded.lane, last_scan=excluded.last_scan,
                file_count=excluded.file_count, last_mtime=excluded.last_mtime, meta_json=excluded.meta_json
            """,
            (p["path"], p["project"], None, lane, now, p["file_count"], p["last_mtime"], json.dumps(p)),
        )
    conn.commit()
