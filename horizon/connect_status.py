"""Probe whether this host can see the systems the abstract packages need.

The probe does not invent client documents, start a second controller, or
claim package release. It records which roots, tools, and desktop sessions
are actually present so the next connection step is specific.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from argparse import ArgumentTypeError
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .source_acquisition import SourceAcquisitionError, parse_root

RECEIPT_SCHEMA_ID = "dbx.connect_status_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
EXCEL_CANDIDATES = (
    Path(r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE"),
    Path("/mnt/c/Program Files/Microsoft Office/root/Office16/EXCEL.EXE"),
    Path("/mnt/c/Program Files (x86)/Microsoft Office/root/Office16/EXCEL.EXE"),
)


class ConnectStatusError(ValueError):
    """Raised when connection-status controls are malformed."""


@dataclass
class RootProbe:
    label: str
    path: str
    exists: bool
    is_dir: bool
    readable: bool


@dataclass
class ConnectStatusReceipt:
    generated_utc: str
    roots: List[RootProbe]
    tools: Dict[str, bool]
    desktop_sessions: Dict[str, str]
    connected_root_count: int
    technical_pass: bool
    packages_complete: bool
    next_actions: List[str]
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            "technical_pass means at least one labeled root exists and is readable",
            "packages_complete stays false",
            "Do not start a second Landman Helper controller",
        ]
    )

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _probe_excel() -> bool:
    return any(path.exists() for path in EXCEL_CANDIDATES)


def _probe_root(raw: str) -> RootProbe:
    try:
        parsed = parse_root(raw)
    except (ArgumentTypeError, ValueError) as exc:
        raise ConnectStatusError(str(exc)) from exc
    path = parsed.path.expanduser()
    exists = path.exists()
    is_dir = path.is_dir()
    readable = False
    if exists:
        try:
            os.listdir(path if is_dir else path.parent)
            readable = True
        except OSError:
            readable = False
    return RootProbe(
        label=parsed.label,
        path=str(path),
        exists=exists,
        is_dir=is_dir,
        readable=readable,
    )


def probe_connections(roots: Sequence[str] = ()) -> ConnectStatusReceipt:
    probes = [_probe_root(raw) for raw in roots]
    tools = {
        "tesseract": shutil.which("tesseract") is not None,
        "libreoffice": shutil.which("soffice") is not None
        or shutil.which("libreoffice") is not None,
        "microsoft_excel": _probe_excel(),
        "pdftotext": shutil.which("pdftotext") is not None,
    }
    desktop = {
        "slack_mcp": "needs_cursor_desktop_auth",
        "notion_mcp": "needs_cursor_desktop_auth",
        "cursor_worker": (
            "env_private_worker"
            if os.environ.get("CURSOR_WORKER")
            else "not_registered_on_this_host"
        ),
    }
    connected = sum(1 for item in probes if item.exists and item.readable)
    actions: List[str] = []
    if not probes:
        actions.append(
            "Pass --root pc=<abs> and --root drive=<abs> on the machine "
            "that can see section 15/13/11 files"
        )
        actions.append(
            "On that host run python3 -m horizon.pc_operator for a "
            "Phase 1 per-section work order"
        )
    for item in probes:
        if not item.exists or not item.readable:
            actions.append(f"Mount or grant read access to {item.label}={item.path}")
    if desktop["cursor_worker"] != "env_private_worker":
        actions.append(
            "Start `cursor worker` on the PC with Drive/PC roots; do not "
            "start a second Landman Helper controller"
        )
    if desktop["slack_mcp"] == "needs_cursor_desktop_auth":
        actions.append("Authenticate Slack and Notion in Cursor Desktop")
    if not tools["microsoft_excel"]:
        actions.append(
            "Run native Excel Print Preview on Windows for Section 15 Letter proof"
        )
    if not tools["tesseract"]:
        actions.append(
            "OCR is not on this host; use writer-held page-render crops instead "
            "of guessing document numbers"
        )
    actions.append(
        "Review Slack/chat/OCR supporting files only; they are not legal "
        "authority and must not fill index cells"
    )
    actions.append(
        "Transcribe hashed handwritten scans into a Penterra xlsx; "
        "Horizon does not OCR index rows"
    )
    actions.append("Do not treat this receipt as package release")
    return ConnectStatusReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        roots=probes,
        tools=tools,
        desktop_sessions=desktop,
        connected_root_count=connected,
        technical_pass=connected > 0,
        packages_complete=False,
        next_actions=actions,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe Drive/PC/tool connections without claiming release."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", action="append", default=[])
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        receipt = probe_connections(args.root)
        args.output.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except (OSError, SourceAcquisitionError, ConnectStatusError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "connected_root_count": receipt.connected_root_count,
                "technical_pass": receipt.technical_pass,
                "packages_complete": receipt.packages_complete,
                "next_actions": receipt.next_actions,
            },
            indent=2,
        )
    )
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
