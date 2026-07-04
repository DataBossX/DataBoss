"""Zero-Destruction versioned writes.

The Law of Horizon: *never overwrite a source or a prior output*. Every write is
a new file with a monotonically increasing ``_vNNN`` suffix. This module owns
the discovery of "the next version" and the "current/latest" version so the
orchestrator's ingest step always reads the newest iteration.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

_VERSION_RE = re.compile(r"_v(\d{3,})(?=\.[^.]+$|$)")


def parse_version(path: Path) -> Optional[int]:
    """Extract the integer version from a ``*_vNNN.ext`` name, else None."""
    m = _VERSION_RE.search(path.name)
    return int(m.group(1)) if m else None


def stem_without_version(path: Path) -> str:
    """The base stem with any ``_vNNN`` removed (extension dropped)."""
    stem = path.stem
    return _VERSION_RE.sub("", stem)


def list_versions(folder: Path, base_stem: str, ext: str = ".xlsx") -> List[Path]:
    """All versioned files for ``base_stem`` in ``folder``, sorted ascending."""
    if not folder.exists():
        return []
    base = _VERSION_RE.sub("", base_stem)
    matches = []
    for p in folder.glob(f"*{ext}"):
        if stem_without_version(p) == base and parse_version(p) is not None:
            matches.append(p)
    return sorted(matches, key=lambda p: parse_version(p) or 0)


def latest_version(folder: Path, base_stem: str, ext: str = ".xlsx") -> Optional[Path]:
    versions = list_versions(folder, base_stem, ext)
    return versions[-1] if versions else None


def next_version_path(folder: Path, base_stem: str, ext: str = ".xlsx") -> Path:
    """Compute the path for the next version (``_v001`` if none exist yet).

    Pure/deterministic: it does not create the file, only names it.
    """
    base = _VERSION_RE.sub("", base_stem)
    existing = list_versions(folder, base, ext)
    n = (parse_version(existing[-1]) or 0) + 1 if existing else 1
    return folder / f"{base}_v{n:03d}{ext}"
