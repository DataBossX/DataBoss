"""Report improver.

Reads the best candidate report and improves its structure, completeness, and
citations against the workbook manifest, validation results, source documents,
and escalation queue. It NEVER adds unverified legal facts. Every claim is
labeled with one of the status tags below and improved reports are written as
new versioned exports (found reports are never overwritten).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Explicit provenance labels required by the mission.
LABEL_VERIFIED = "VERIFIED"
LABEL_UNVERIFIED = "UNVERIFIED"
LABEL_ESCALATED = "ESCALATED"
LABEL_BLOCKED_SPEND = "BLOCKED BY SPEND CAP"
LABEL_BLOCKED_CREDS = "BLOCKED BY MISSING CREDENTIALS"
LABEL_NEEDS_REVIEW = "NEEDS EXAMINER REVIEW"


def _read_source_report(path: Path | None) -> str:
    if path and path.suffix.lower() in {".md", ".txt"} and path.exists():
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
    return ""


def build_improved_markdown(*, run_id: str, mode: str,
                            source_report: Path | None,
                            manifest: dict, validation_results: list[dict],
                            source_documents: list[dict],
                            escalations: list[dict], spend: dict,
                            credentials_ok: bool, timestamp: str) -> str:
    lines: list[str] = []
    a = lines.append
    a(f"# DataBossX Validation Report — Improved")
    a("")
    a(f"- **Run ID:** {run_id}")
    a(f"- **Mode:** {mode}")
    a(f"- **Generated:** {timestamp}")
    if source_report:
        a(f"- **Improved from:** `{source_report}`")
    a("")
    a("> This report is machine-assembled. Every legal/title/source fact is "
      "labeled by provenance. Facts are **never fabricated**; unverifiable "
      "items are escalated to the human examiner.")
    a("")

    # --- Validation scorecard ---
    a("## Validation Scorecard")
    a("")
    a("| Gate | Status | Severity | Repairable | Subject |")
    a("|------|--------|----------|-----------|---------|")
    for r in validation_results:
        a(f"| {r.get('gate_name','')} | {r.get('status','')} | "
          f"{r.get('severity','')} | {'yes' if r.get('repairable') else 'no'} "
          f"| {r.get('affected_subject','')} |")
    a("")

    # --- Provenance summary ---
    passed = sum(1 for r in validation_results if r.get("status") == "PASS")
    a(f"- {LABEL_VERIFIED}: {passed} gate(s) passed.")
    a(f"- {LABEL_ESCALATED}: {len(escalations)} item(s) require examiner review.")
    if not credentials_ok:
        a(f"- {LABEL_BLOCKED_CREDS}: live source retrieval unavailable.")
    a("")

    # --- Missing / source document table ---
    a("## Source Document Status")
    a("")
    a("| Reference | Type | Status | Origin | Label |")
    a("|-----------|------|--------|--------|-------|")
    for d in source_documents:
        status = d.get("status", "")
        if status in {"found_local", "retrieved"}:
            label = LABEL_VERIFIED
        elif status == "blocked":
            label = LABEL_BLOCKED_SPEND
        elif status == "queued" and not credentials_ok:
            label = LABEL_BLOCKED_CREDS
        else:
            label = LABEL_NEEDS_REVIEW
        a(f"| {d.get('reference_key','')} | {d.get('doc_type','')} | "
          f"{status} | {d.get('source_origin','')} | {label} |")
    if not source_documents:
        a("| _(none referenced)_ | | | | |")
    a("")

    # --- Examiner action list ---
    a("## Examiner Action List (Escalations)")
    a("")
    if escalations:
        for i, e in enumerate(escalations, 1):
            a(f"{i}. **[{LABEL_ESCALATED}] {e.get('category', e.get('gate_name',''))}"
              f"** — {e.get('reason','')}")
            if e.get("recommended_action"):
                a(f"   - Recommended: {e['recommended_action']}")
    else:
        a("_No escalations. All automated gates are satisfied._")
    a("")

    # --- Spend ---
    a("## Spend Ledger Summary")
    a("")
    a(f"- Cumulative spend: **${spend.get('cumulative', 0):.2f}** of "
      f"cap **${spend.get('cap', 100):.2f}**.")
    a(f"- Remaining: **${spend.get('remaining', 0):.2f}**.")
    a("")

    # --- Workbook manifest snapshot ---
    a("## Workbook Snapshot")
    a("")
    a(f"- File: `{manifest.get('file_name','')}`")
    a(f"- SHA-256: `{manifest.get('sha256','')}`")
    a(f"- Sheets: {len(manifest.get('sheets', []))}")
    a(f"- Macro-enabled: {manifest.get('is_macro_enabled')}")
    a("")

    original = _read_source_report(source_report)
    if original:
        a("## Prior Report (preserved verbatim, unverified)")
        a("")
        a(f"> The following is carried over from the source report and is "
          f"labeled **{LABEL_UNVERIFIED}** until an examiner confirms it.")
        a("")
        a("```")
        a(original[:20000])
        a("```")
    return "\n".join(lines) + "\n"


def improve_report(run_manager, *, run_id: str, mode: str,
                   source_report: Path | None, manifest: dict,
                   validation_results: list[dict], source_documents: list[dict],
                   escalations: list[dict], spend: dict, credentials_ok: bool,
                   db=None, timestamp: str | None = None) -> Path:
    """Write an improved, versioned markdown report into exports/."""
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    md = build_improved_markdown(
        run_id=run_id, mode=mode, source_report=source_report,
        manifest=manifest, validation_results=validation_results,
        source_documents=source_documents, escalations=escalations,
        spend=spend, credentials_ok=credentials_ok, timestamp=ts,
    )
    out_path = run_manager.unique_export_path("improved_report.md")
    out_path.write_text(md, encoding="utf-8")
    if db:
        from core.run_manager import sha256_file
        db.record_report_export(run_id, "markdown", out_path.name,
                                str(out_path), sha256_file(out_path),
                                note="improved report")
    return out_path
