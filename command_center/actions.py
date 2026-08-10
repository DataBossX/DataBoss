"""Bounded action registry.

Every action declares its contract up front (inputs, read/write roots,
timeout, max attempts, cost class, acceptance test) and only ever writes
into a project's own _DataBossX_Working subfolder -- never into a client
source, share, or protected original.
"""
import csv
import io
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from discovery import EVIDENCE_HINTS, WORKING_SUBDIR, _walk_shallow

DANGEROUS_KEYWORDS = (
    "delete", "rm -rf", "format", "overwrite_source", "send_email",
    "purchase", "credential", "shell_exec",
)


class ActionRefused(Exception):
    """Raised when an action would violate a hard safety boundary."""


@dataclass
class ActionResult:
    ok: bool
    summary: str
    output: dict = field(default_factory=dict)
    files_changed: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


@dataclass
class ActionSpec:
    key: str
    label: str
    lane: str  # "penterra" | "horizon" | "databossx" | "any"
    cost_class: str  # FREE | LOCAL | LOW | PREMIUM
    timeout_seconds: int
    max_attempts: int
    write_scope: str  # "working_dir_only" | "none"
    runner: Callable
    acceptance_test: str


def _project_dir(project_path: str) -> Path:
    p = Path(project_path)
    if not p.exists() or not p.is_dir():
        raise ActionRefused(f"Project path does not exist or is not a directory: {project_path}")
    return p


def _working_dir(project_path: str) -> Path:
    wd = _project_dir(project_path) / WORKING_SUBDIR
    wd.mkdir(parents=True, exist_ok=True)
    return wd


def _write_receipt_file(project_path: str, name: str, content: str) -> Path:
    """The only way actions in this module write to disk: always inside
    the project's own working subfolder, never the source tree."""
    wd = _working_dir(project_path)
    out = wd / name
    out.write_text(content, encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Deterministic (Level 0) action implementations
# ---------------------------------------------------------------------------

def act_scan_project(inputs: dict) -> ActionResult:
    project_path = inputs["project_path"]
    p = _project_dir(project_path)
    files = list(_walk_shallow(p))
    total_size = sum((f.stat().st_size for f in files if _stat_ok(f)), 0)
    return ActionResult(
        ok=True,
        summary=f"Scanned {p.name}: {len(files)} files, {total_size} bytes.",
        output={"file_count": len(files), "total_size_bytes": total_size},
    )


def _stat_ok(entry) -> bool:
    try:
        entry.stat()
        return True
    except OSError:
        return False


def act_find_missing_evidence(inputs: dict) -> ActionResult:
    project_path = inputs["project_path"]
    p = _project_dir(project_path)
    names = [e.name.lower() for e in _walk_shallow(p)]
    missing = [hint for hint in EVIDENCE_HINTS if not any(hint in n for n in names)]
    present = [hint for hint in EVIDENCE_HINTS if hint not in missing]
    return ActionResult(
        ok=True,
        summary=f"{len(present)} evidence types present, {len(missing)} not detected by filename.",
        output={"present": present, "missing": missing},
        warnings=["Detection is filename-based only; absence here is a hint, not proof."],
    )


def act_build_worklist(inputs: dict) -> ActionResult:
    project_path = inputs["project_path"]
    p = _project_dir(project_path)
    files = sorted(_walk_shallow(p), key=lambda e: e.name.lower())
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["file_name", "relative_path", "size_bytes", "modified"])
    for entry in files:
        try:
            st = entry.stat()
        except OSError:
            continue
        rel = str(Path(entry.path).relative_to(p))
        modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
        writer.writerow([entry.name, rel, st.st_size, modified])
    out_path = _write_receipt_file(project_path, "worklist.csv", buf.getvalue())
    return ActionResult(
        ok=True,
        summary=f"Built worklist with {len(files)} rows.",
        output={"row_count": len(files)},
        files_changed=[str(out_path)],
    )


def act_inspect_candidates(inputs: dict) -> ActionResult:
    project_path = inputs["project_path"]
    p = _project_dir(project_path)
    candidates = [
        e for e in _walk_shallow(p)
        if e.name.lower().endswith((".xlsx", ".xlsm", ".docx", ".pdf"))
    ]
    candidates.sort(key=lambda e: _mtime(e), reverse=True)
    top = [
        {"name": e.name, "path": e.path, "modified": _mtime(e)}
        for e in candidates[:10]
    ]
    return ActionResult(
        ok=True,
        summary=f"Found {len(candidates)} candidate document(s); showing most recent {len(top)}.",
        output={"candidates": top},
    )


def _mtime(entry) -> float:
    try:
        return entry.stat().st_mtime
    except OSError:
        return 0.0


def act_open_project_folder(inputs: dict) -> ActionResult:
    project_path = inputs["project_path"]
    p = _project_dir(project_path)
    return ActionResult(
        ok=True,
        summary=f"Path ready to open: {p}",
        output={"path": str(p)},
    )


def act_run_structure_qa(inputs: dict) -> ActionResult:
    """Deterministic workbook-structure QA. Uses openpyxl if available,
    otherwise falls back to existence/size checks only."""
    project_path = inputs["project_path"]
    p = _project_dir(project_path)
    xlsx_files = [e for e in _walk_shallow(p) if e.name.lower().endswith((".xlsx", ".xlsm"))]
    findings = []
    try:
        import openpyxl  # noqa: local, optional
        for entry in xlsx_files:
            try:
                wb = openpyxl.load_workbook(entry.path, read_only=True, data_only=True)
                findings.append({
                    "file": entry.name,
                    "sheets": wb.sheetnames,
                    "status": "OPENED_OK",
                })
                wb.close()
            except Exception as exc:  # noqa: broad-except - QA must not crash on bad files
                findings.append({"file": entry.name, "status": "OPEN_FAILED", "error": str(exc)})
    except ImportError:
        for entry in xlsx_files:
            findings.append({
                "file": entry.name,
                "status": "PRESENT_ONLY",
                "note": "openpyxl not installed; only existence checked.",
            })
    ok_count = sum(1 for f in findings if f["status"] in ("OPENED_OK", "PRESENT_ONLY"))
    return ActionResult(
        ok=True,
        summary=f"QA checked {len(findings)} workbook(s); {ok_count} readable.",
        output={"findings": findings},
    )


def act_summarize_status(inputs: dict) -> ActionResult:
    project_path = inputs["project_path"]
    p = _project_dir(project_path)
    files = list(_walk_shallow(p))
    latest = max((f for f in files if _stat_ok(f)), key=_mtime, default=None)
    return ActionResult(
        ok=True,
        summary=f"{p.name}: {len(files)} files. Most recent activity: "
                f"{latest.name if latest else 'none'}.",
        output={
            "file_count": len(files),
            "most_recent_file": latest.name if latest else None,
        },
    )


REGISTRY: dict[str, ActionSpec] = {
    "scan_project": ActionSpec(
        key="scan_project", label="Update Me", lane="any", cost_class="FREE",
        timeout_seconds=30, max_attempts=2, write_scope="none",
        runner=act_scan_project, acceptance_test="file_count >= 0 and no exception",
    ),
    "inspect_project": ActionSpec(
        key="inspect_project", label="Inspect Project", lane="any", cost_class="FREE",
        timeout_seconds=30, max_attempts=2, write_scope="none",
        runner=act_summarize_status, acceptance_test="summary text produced",
    ),
    "inspect_candidates": ActionSpec(
        key="inspect_candidates", label="Open Best Current Candidate", lane="any", cost_class="FREE",
        timeout_seconds=30, max_attempts=2, write_scope="none",
        runner=act_inspect_candidates, acceptance_test="candidate list produced (possibly empty)",
    ),
    "find_missing_evidence": ActionSpec(
        key="find_missing_evidence", label="Find Missing Evidence", lane="any", cost_class="FREE",
        timeout_seconds=30, max_attempts=2, write_scope="none",
        runner=act_find_missing_evidence, acceptance_test="present/missing lists produced",
    ),
    "build_worklist": ActionSpec(
        key="build_worklist", label="Build / Update Worklist", lane="any", cost_class="FREE",
        timeout_seconds=60, max_attempts=1, write_scope="working_dir_only",
        runner=act_build_worklist, acceptance_test="worklist.csv exists in _DataBossX_Working",
    ),
    "run_qa": ActionSpec(
        key="run_qa", label="Run QA", lane="any", cost_class="FREE",
        timeout_seconds=60, max_attempts=1, write_scope="none",
        runner=act_run_structure_qa, acceptance_test="each workbook has a QA status",
    ),
    "open_project_folder": ActionSpec(
        key="open_project_folder", label="Open Working Folder", lane="any", cost_class="FREE",
        timeout_seconds=5, max_attempts=1, write_scope="none",
        runner=act_open_project_folder, acceptance_test="path returned",
    ),
}


def is_dangerous(task_key: str, inputs: dict) -> bool:
    haystack = json.dumps({"task": task_key, "inputs": inputs}).lower()
    return any(kw in haystack for kw in DANGEROUS_KEYWORDS)


def run_action(task_key: str, inputs: dict) -> ActionResult:
    if task_key not in REGISTRY:
        raise ActionRefused(f"Unknown action '{task_key}'. Refusing to execute arbitrary commands.")
    if is_dangerous(task_key, inputs):
        raise ActionRefused(f"Action '{task_key}' matched a hard-stop safety rule and was refused.")
    spec = REGISTRY[task_key]
    return spec.runner(inputs)
