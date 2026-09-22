"""Five-dimension improvement tournament. Missing sources cannot pass."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .access import probe_access
from .dates import check_date_table
from .format_qa import check_format
from .hashing import sha256_bytes
from .identity import StableKey, find_duplicate_keys
from .ledger import SourceLedger, build_ledger
from .package import verify_package
from .purity import check_purity

DIMENSIONS = (
    "A_SOURCE_COMPLETENESS",
    "B_FACTUAL_STABLE_KEY",
    "C_CLIENT_PURITY_FORMAT",
    "D_NATIVE_EVERY_PAGE",
    "E_BYTE_PACKAGE",
)


@dataclass
class DimensionResult:
    name: str
    status: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CycleResult:
    cycle: int
    dimensions: list[DimensionResult]
    complete: bool
    consecutive_complete: int
    cached: bool
    evidence_sha256: str
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _status(ok: bool, blocked: bool) -> str:
    if blocked:
        return "BLOCKED"
    return "PASS" if ok else "FAIL"


def evaluate_packet(packet: dict) -> list[DimensionResult]:
    access = probe_access(packet.get("source_root"))
    ledger: SourceLedger | None = None
    if packet.get("source_paths"):
        ledger = build_ledger(
            packet["source_paths"],
            packet.get("dispositions_by_file") or {},
        )

    source_blockers = list(access.blockers)
    if ledger is None:
        if not access.source_root_exists:
            source_blockers.append("NO_SOURCE_CENSUS")
    else:
        source_blockers.extend(ledger.issues)
        unresolved_pages = sum(
            1
            for page in ledger.pages
            if page.disposition in {"UNRESOLVED", "MISSING_SOURCE", "UNREADABLE"}
        )
        if unresolved_pages:
            source_blockers.append(f"UNRESOLVED_PAGES={unresolved_pages}")

    rows = list(packet.get("rows") or [])
    purity = check_purity(rows)
    fmt = check_format(
        rows,
        columns=packet.get("columns"),
        profile=packet.get("profile") or "county",
    )
    dates = check_date_table(list(packet.get("date_rows") or []))
    keys = [
        StableKey(**item) if isinstance(item, dict) else item
        for item in packet.get("stable_keys") or []
    ]
    duplicates = find_duplicate_keys(keys)
    keys_missing = bool(rows) and not keys

    native = packet.get("native_reopen") or {}
    native_ok = bool(native.get("reopened")) and bool(native.get("every_page_inspected"))

    package = packet.get("package") or {}
    package_result = None
    if package.get("zip_path"):
        package_result = verify_package(
            package["zip_path"],
            expected_members=package.get("expected_members"),
            expected_sha256=package.get("expected_sha256"),
            expected_member_sha=package.get("expected_member_sha"),
            ordered=bool(package.get("ordered")),
        )

    return [
        DimensionResult(
            "A_SOURCE_COMPLETENESS",
            _status(not source_blockers, bool(source_blockers)),
            source_blockers or ["all source pages accounted"],
        ),
        DimensionResult(
            "B_FACTUAL_STABLE_KEY",
            _status(not duplicates and not dates and not keys_missing, keys_missing),
            [
                f"duplicates={duplicates}",
                f"date_findings={len(dates)}",
                f"keys_missing={keys_missing}",
            ],
        ),
        DimensionResult(
            "C_CLIENT_PURITY_FORMAT",
            _status(not purity and not fmt, False),
            [f"purity={len(purity)}", f"format={len(fmt)}"],
        ),
        DimensionResult(
            "D_NATIVE_EVERY_PAGE",
            _status(native_ok, not native_ok),
            [
                f"reopened={bool(native.get('reopened'))}",
                f"every_page_inspected={bool(native.get('every_page_inspected'))}",
            ],
        ),
        DimensionResult(
            "E_BYTE_PACKAGE",
            _status(
                bool(package_result and package_result.get("pass")),
                package_result is None,
            ),
            package_result.get("errors") if package_result else ["package not supplied"],
        ),
    ]


def run_tournament(
    packet: dict,
    *,
    previous_evidence_sha: str | None = None,
    consecutive_complete: int = 0,
    cycle: int = 1,
) -> CycleResult:
    dimensions = evaluate_packet(packet)
    payload = json.dumps([item.to_dict() for item in dimensions], sort_keys=True)
    evidence_sha = sha256_bytes(payload.encode("utf-8"))
    cached = bool(previous_evidence_sha) and previous_evidence_sha == evidence_sha
    complete = all(item.status == "PASS" for item in dimensions)
    blockers = [
        f"{item.name}:{item.status}"
        for item in dimensions
        if item.status != "PASS"
    ]
    if cached:
        next_consecutive = consecutive_complete
    elif complete:
        next_consecutive = consecutive_complete + 1
    else:
        next_consecutive = 0
    return CycleResult(
        cycle=cycle,
        dimensions=dimensions,
        complete=complete and not cached,
        consecutive_complete=next_consecutive,
        cached=cached,
        evidence_sha256=evidence_sha,
        blockers=blockers,
    )


def write_receipt(result: CycleResult, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination
