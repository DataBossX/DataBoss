"""safety_kernel plugin — wraps the existing DataBossX safety kernel.

The kernel is the Zero-Destruction machinery that already ships in this repo:

* ``horizon.versioning`` — versioned ``_vNNN`` writes, never overwrite
* ``horizon.audit``      — append-only, timestamped audit trail

This plugin WRAPS those originals (per the absorb mandate: wrap, do not
rewrite). Every entrypoint takes a JSON payload dict and returns a JSON-able
dict, matching the Foundry plugin contract.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

# The plugin lives at <repo>/plugins/safety_kernel; the wrapped originals live
# at <repo>/horizon. Make the repo root importable without touching them.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from horizon.audit import AuditLog  # noqa: E402
from horizon import versioning  # noqa: E402


def _audit(payload: Dict[str, Any]) -> AuditLog:
    log_path = payload.get("audit_log")
    return AuditLog(path=Path(log_path) if log_path else None, echo=False)


def versioned_write(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Write ``payload['data']`` as the next ``_vNNN`` version — never overwrite.

    payload: {"folder": str, "stem": str, "ext": str, "data": str,
              "audit_log": optional str}
    """
    missing = [k for k in ("folder", "stem", "ext", "data") if k not in payload]
    if missing:
        raise ValueError(f"versioned_write payload missing keys: {missing}")
    folder = Path(payload["folder"])
    folder.mkdir(parents=True, exist_ok=True)
    target = versioning.next_version_path(folder, str(payload["stem"]), str(payload["ext"]))
    target.write_text(str(payload["data"]), encoding="utf-8")
    audit = _audit(payload)
    event = audit.info("versioned_write", f"{target}")
    return {
        "ok": True,
        "path": str(target),
        "version": versioning.parse_version(target),
        "audit": event.format(),
    }


def latest(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Latest version path for a stem. payload: {"folder", "stem", "ext"}."""
    missing = [k for k in ("folder", "stem", "ext") if k not in payload]
    if missing:
        raise ValueError(f"latest payload missing keys: {missing}")
    found = versioning.latest_version(
        Path(payload["folder"]), str(payload["stem"]), str(payload["ext"])
    )
    return {
        "ok": True,
        "path": str(found) if found else None,
        "version": versioning.parse_version(found) if found else None,
    }


def audit_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Append one event to an audit log.

    payload: {"audit_log": str, "action": str, "detail": optional str,
              "level": optional str}
    """
    if "action" not in payload:
        raise ValueError("audit payload requires 'action'")
    audit = _audit(payload)
    event = audit.record(
        str(payload["action"]),
        str(payload.get("detail", "")),
        str(payload.get("level", "INFO")),
    )
    return {"ok": True, "line": event.format(), "log": str(audit.path) if audit.path else None}


def smoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Self-test: two versioned writes must yield v001 then v002, audited."""
    workdir = Path(payload.get("dir") or tempfile.mkdtemp(prefix="safety_kernel_smoke_"))
    audit_log = workdir / "audit.log"
    first = versioned_write({
        "folder": str(workdir), "stem": "smoke", "ext": ".txt",
        "data": "first", "audit_log": str(audit_log),
    })
    second = versioned_write({
        "folder": str(workdir), "stem": "smoke", "ext": ".txt",
        "data": "second", "audit_log": str(audit_log),
    })
    newest = latest({"folder": str(workdir), "stem": "smoke", "ext": ".txt"})
    ok = (
        first["version"] == 1
        and second["version"] == 2
        and newest["path"] == second["path"]
        and Path(first["path"]).read_text(encoding="utf-8") == "first"
        and audit_log.is_file()
        and len(audit_log.read_text(encoding="utf-8").splitlines()) == 2
    )
    return {
        "ok": ok,
        "dir": str(workdir),
        "writes": [first["path"], second["path"]],
        "latest": newest["path"],
        "audit_log": str(audit_log),
    }
