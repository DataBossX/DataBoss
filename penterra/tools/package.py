"""Package CRC / SHA-256 / exact-membership verification."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def verify_package(zip_path: str | Path, expected_members: list[str],
                   expected_sha256: str | None = None,
                   expected_member_sha: dict[str, str] | None = None,
                   *, ordered: bool = False) -> dict:
    """Verify exact membership, CRC, container hash and per-member hashes."""
    p = Path(zip_path)
    res: dict = {"zip": str(p), "exists": p.exists()}
    if not p.exists():
        res["pass"] = False
        res["errors"] = ["package does not exist"]
        return res

    errors: list[str] = []
    res["sha256"] = sha256_file(p)
    res["bytes"] = p.stat().st_size
    if expected_sha256 and res["sha256"] != expected_sha256:
        errors.append(f"container sha mismatch: {res['sha256']} != {expected_sha256}")

    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        res["members"] = names
        res["member_count"] = len(names)
        bad = z.testzip()
        res["crc_pass"] = bad is None
        if bad is not None:
            errors.append(f"CRC failure in member {bad}")

        if ordered:
            if names != list(expected_members):
                errors.append(f"member order mismatch: {names} != {list(expected_members)}")
        else:
            extra = sorted(set(names) - set(expected_members))
            missing = sorted(set(expected_members) - set(names))
            if extra:
                errors.append(f"unexpected members: {extra}")
            if missing:
                errors.append(f"missing members: {missing}")
        if len(names) != len(expected_members):
            errors.append(f"exact-membership count {len(names)} != {len(expected_members)}")

        member_sha = {n: hashlib.sha256(z.read(n)).hexdigest() for n in names}
        res["member_sha256"] = member_sha
        for name, want in (expected_member_sha or {}).items():
            got = member_sha.get(name)
            if got is None:
                errors.append(f"member absent for hash check: {name}")
            elif got != want:
                errors.append(f"member sha mismatch {name}: {got} != {want}")

    res["errors"] = errors
    res["pass"] = not errors
    return res
