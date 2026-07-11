"""Zero-Destruction versioned file writes for the Foundry core.

Every output the Foundry produces is a new ``*_vNNN.ext`` file; nothing is ever
overwritten. This mirrors the law enforced by the legacy Horizon safety kernel
(``horizon/versioning.py``) but is reimplemented here because core code never
imports plugins — the Horizon original is wrapped separately as the
``safety_kernel`` plugin.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, List, Optional, Union

_VERSION_RE = re.compile(r"_v(\d{3,})$")


def parse_version(path: Path) -> Optional[int]:
    """Integer version from a ``*_vNNN.ext`` name, else ``None``."""
    m = _VERSION_RE.search(path.stem)
    return int(m.group(1)) if m else None


def base_stem(path: Path) -> str:
    """Stem with any trailing ``_vNNN`` removed."""
    return _VERSION_RE.sub("", path.stem)


def list_versions(folder: Path, stem: str, ext: str) -> List[Path]:
    """All versioned files for ``stem`` in ``folder``, ascending by version."""
    if not folder.is_dir():
        return []
    stem = _VERSION_RE.sub("", stem)
    matches = [
        p
        for p in folder.glob(f"*{ext}")
        if base_stem(p) == stem and parse_version(p) is not None
    ]
    return sorted(matches, key=lambda p: parse_version(p) or 0)


def next_version_path(folder: Path, stem: str, ext: str) -> Path:
    """Path for the next version (``_v001`` if none exist). Does not create it."""
    existing = list_versions(folder, stem, ext)
    n = (parse_version(existing[-1]) or 0) + 1 if existing else 1
    clean = _VERSION_RE.sub("", stem)
    return folder / f"{clean}_v{n:03d}{ext}"


def versioned_write(folder: Path, stem: str, ext: str, data: Union[str, bytes]) -> Path:
    """Write ``data`` as the next version of ``stem``; never overwrites."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = next_version_path(folder, stem, ext)
    if isinstance(data, str):
        target.write_text(data, encoding="utf-8")
    else:
        target.write_bytes(data)
    return target


def versioned_write_json(folder: Path, stem: str, payload: Any) -> Path:
    return versioned_write(folder, stem, ".json", json.dumps(payload, indent=2, default=str) + "\n")
