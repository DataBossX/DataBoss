from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable

CHUNK = 1 << 20


def sha256_stream(fh, chunk: int = CHUNK) -> str:
    h = hashlib.sha256()
    while True:
        b = fh.read(chunk)
        if not b:
            break
        h.update(b)
    return h.hexdigest()


def sha256_file(path: str | os.PathLike) -> str:
    with open(path, "rb") as fh:
        return sha256_stream(fh)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def fingerprint(obj: Any) -> str:
    return sha256_bytes(canonical_json(obj).encode("utf-8"))


def write_new_text(path: Path, text: str) -> str:
    """Atomically create ``path``. Refuses to overwrite. Returns sha256 of content."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    data = text.encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=path.suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        # os.link fails if the target exists, so it cannot clobber a racing writer.
        try:
            os.link(tmp, path)
        except FileExistsError:
            raise
        except OSError:  # filesystem without hard links: exclusive create is still non-clobbering
            with open(path, "xb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
    return sha256_bytes(data)


def write_new_json(path: Path, obj: Any) -> str:
    return write_new_text(path, json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n")


def write_new_csv(path: Path, header: list[str], rows: Iterable[Iterable[Any]]) -> str:
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return write_new_text(path, buf.getvalue())


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


_WS = re.compile(r"\s+")


def norm_text(value: Any) -> str:
    """Whitespace-collapsed, stripped string ('' for None)."""
    if value is None:
        return ""
    return _WS.sub(" ", str(value).replace(" ", " ")).strip()


_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def norm_compare(value: Any) -> str:
    """Case/punctuation/whitespace-insensitive form used only for comparison."""
    return _WS.sub(" ", _PUNCT.sub(" ", norm_text(value).casefold())).strip()
