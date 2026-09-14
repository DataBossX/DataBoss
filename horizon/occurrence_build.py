"""Build an occurrence packet from page-render crops.

The builder does not invent rows, guess neighbouring document numbers, or
mutate a workbook. Bare-docno crops stay in the packet as high_risk so the
ledger can still see count/hash contradictions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .occurrence_ledger import (
    PACKET_SCHEMA_ID,
    PACKET_SCHEMA_VERSION,
    compare_packet,
    parse_occurrence_packet,
)
from .page_render_export import PageRenderExportError, compile_page_renders
from .stable_key import StableKeyError, stable_key

RISK_CHECKABLE = "novel"
RISK_BARE = "high_risk"


class OccurrenceBuildError(ValueError):
    """Raised when an occurrence packet cannot be built safely."""


def _fields(crop: Dict[str, object]) -> Dict[str, str]:
    grantor = str(crop.get("grantor") or "")
    grantee = str(crop.get("grantee") or "")
    rec_date = str(crop.get("rec_date") or "")
    return {
        "grantor": grantor,
        "grantee": grantee,
        "recorded_date": rec_date,
        "party": grantor or grantee,
        "date_role": "recorded" if rec_date else "",
    }


def _checkable(crop: Dict[str, object]) -> bool:
    bookpage = str(crop.get("bookpage") or "").strip()
    rec_date = str(crop.get("rec_date") or "").strip()
    party = str(crop.get("grantor") or crop.get("grantee") or "").strip()
    return bool(bookpage) or bool(rec_date and party)


def build_occurrence_packet(page_render_payload: Dict[str, object]) -> Dict[str, object]:
    compiled = compile_page_renders(page_render_payload)
    crops = page_render_payload["crops"]
    if not isinstance(crops, list):
        raise OccurrenceBuildError("crops must be a list")
    occurrences: List[Dict[str, object]] = []
    ledger: List[Dict[str, str]] = []
    candidates: List[Dict[str, object]] = []
    seen_keys: set[str] = set()
    for crop in crops:
        if not isinstance(crop, dict):
            raise OccurrenceBuildError("each crop must be an object")
        try:
            key = stable_key(
                str(crop.get("docno") or "") or None,
                str(crop.get("bookpage") or "") or None,
            )
        except StableKeyError as exc:
            raise OccurrenceBuildError(str(exc)) from exc
        digest = str(crop["source_sha256"]).casefold()
        occurrence = {
            "occurrence_id": str(crop["row_id"]),
            "stable_key": key,
            "source_sha256": digest,
            "page": crop["page"],
            "crop_id": str(crop["crop_id"]),
            "fields": _fields(crop),
            "risk": RISK_CHECKABLE if _checkable(crop) else RISK_BARE,
        }
        occurrences.append(occurrence)
        if key not in seen_keys:
            seen_keys.add(key)
            ledger.append({"stable_key": key, "source_sha256": digest})
            candidates.append(
                {
                    "row_id": str(crop["row_id"]),
                    "stable_key": key,
                    "source_sha256": digest,
                    "fields": _fields(crop),
                }
            )
    if not occurrences:
        raise OccurrenceBuildError("No crops to build occurrences from")
    packet = {
        "schema_id": PACKET_SCHEMA_ID,
        "schema_version": PACKET_SCHEMA_VERSION,
        "packet_id": compiled.packet_id,
        "occurrences": occurrences,
        "unique_key_ledger": ledger,
        "candidate_rows": candidates,
        "allowlist": [],
    }
    parse_occurrence_packet(packet)
    return packet


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OccurrenceBuildError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise OccurrenceBuildError(f"{path} must contain a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an occurrence packet from page-render crops."
    )
    parser.add_argument("--page-render-packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        packet = build_occurrence_packet(_load_json(args.page_render_packet))
        args.output.write_text(
            json.dumps(packet, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        receipt = compare_packet(parse_occurrence_packet(packet))
    except (
        OSError,
        OccurrenceBuildError,
        PageRenderExportError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "technical_pass": receipt.technical_pass,
                "occurrence_count": receipt.occurrence_count,
            },
            indent=2,
        )
    )
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
