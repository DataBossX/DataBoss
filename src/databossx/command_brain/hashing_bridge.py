"""Bridge to the existing content-addressed hashing helpers.

Kept separate so :mod:`state` never grows a filesystem import of its own, and so
"the bytes are not reachable from this runtime" is a first-class, honest answer
rather than an exception. A locator that does not resolve returns ``None``, and
the caller reports NOT_VERIFIED.
"""

from __future__ import annotations

from pathlib import Path

from ..hashing import sha256_file


def hash_registered_artifact(locator: str | None) -> str | None:
    if not locator:
        return None
    path = Path(locator)
    try:
        if not path.is_file():
            return None
        return sha256_file(path)
    except OSError:
        return None
