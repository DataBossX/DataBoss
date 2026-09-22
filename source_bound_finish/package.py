"""Exact ZIP membership, CRC, and SHA-256 verification."""

from __future__ import annotations

import zipfile
from pathlib import Path

from .hashing import sha256_bytes, sha256_file


def verify_package(
    zip_path: str | Path,
    expected_members: list[str] | None = None,
    expected_sha256: str | None = None,
    expected_member_sha: dict[str, str] | None = None,
    *,
    ordered: bool = False,
) -> dict:
    path = Path(zip_path)
    result: dict = {"zip": str(path), "exists": path.exists(), "pass": False}
    if not path.exists():
        result["errors"] = ["package does not exist"]
        return result

    errors: list[str] = []
    result["sha256"] = sha256_file(path)
    result["bytes"] = path.stat().st_size
    if expected_sha256 and result["sha256"] != expected_sha256:
        errors.append("container sha mismatch")

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        result["members"] = names
        result["member_count"] = len(names)
        crc_bad = archive.testzip()
        result["crc_pass"] = crc_bad is None
        if crc_bad is not None:
            errors.append(f"CRC failure in member {crc_bad}")
        if expected_members is not None:
            if ordered:
                if names != list(expected_members):
                    errors.append("member order mismatch")
            else:
                extra = sorted(set(names) - set(expected_members))
                missing = sorted(set(expected_members) - set(names))
                if extra:
                    errors.append(f"unexpected members: {extra}")
                if missing:
                    errors.append(f"missing members: {missing}")
            if len(names) != len(expected_members):
                errors.append(
                    f"exact-membership count {len(names)} != {len(expected_members)}"
                )
        member_sha = {name: sha256_bytes(archive.read(name)) for name in names}
        result["member_sha256"] = member_sha
        for name, wanted in (expected_member_sha or {}).items():
            got = member_sha.get(name)
            if got is None:
                errors.append(f"member absent for hash check: {name}")
            elif got != wanted:
                errors.append(f"member sha mismatch: {name}")

    result["errors"] = errors
    result["pass"] = not errors
    return result
