"""STAGED_EVIDENCE lane for AI/OCR extraction output.

Model or OCR output never flows straight into an authoritative client
workbook. It lands here first, where deterministic checks run:

* structure validation (required evidence fields present and typed)
* SHA-256 fingerprinting of each record (dedupe of identical proposals)
* section-contamination detection (record claims a different section)
* stable-key collisions (two proposals for one key that disagree)
* missing-evidence flags (no page / pixel anchor / source hash)

The output is a patch manifest: proposed cell deltas keyed by stable key,
each carrying its evidence. Only the sole section writer applies a delta,
and only after checking the source pixels itself.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

DISPOSITIONS = frozenset({
    "INCLUDE",
    "EXISTING_SEMANTIC_MATCH",
    "SUPPORT_CONTINUATION",
    "DUPLICATE",
    "NON_TARGET",
    "ADMIN",
    "MISSING_IMAGE",
    "UNRESOLVED",
})

REQUIRED_FIELDS = ("section", "stable_key", "source_drive_id", "source_sha256", "disposition")
EVIDENCE_FIELDS = ("physical_page", "visible_anchor")
PATCHABLE_FIELDS = (
    "doc_type", "grantor", "grantee", "doc_no", "book_page",
    "date_of_doc", "rec_date", "sec12_legal", "formation_depth",
)
PIXEL = "PIXEL_READ"


@dataclass
class Issue:
    code: str
    stable_key: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "stable_key": self.stable_key, "detail": self.detail}


@dataclass
class StagingResult:
    accepted: list[dict[str, Any]] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    duplicates: int = 0

    def by_code(self, code: str) -> list[Issue]:
        return [i for i in self.issues if i.code == code]


def record_fingerprint(record: dict[str, Any]) -> str:
    """Stable SHA-256 over the record's canonical JSON (key order independent)."""
    blob = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _norm(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(" ".join(str(v).split()) for v in value)
    if isinstance(value, str):
        return " ".join(value.split())
    return value


def validate(records: Iterable[dict[str, Any]], section: str) -> StagingResult:
    """Run every deterministic staging check over *records* for *section*."""
    result = StagingResult()
    seen: set[str] = set()
    by_key: dict[str, dict[str, Any]] = {}
    for rec in records:
        key = str(rec.get("stable_key") or "?")
        fp = record_fingerprint(rec)
        if fp in seen:
            result.duplicates += 1
            continue
        seen.add(fp)

        missing = [f for f in REQUIRED_FIELDS if not rec.get(f)]
        if missing:
            result.issues.append(Issue("MISSING_FIELD", key, ",".join(missing)))
            continue
        if rec["disposition"] not in DISPOSITIONS:
            result.issues.append(Issue("BAD_DISPOSITION", key, str(rec["disposition"])))
            continue
        if str(rec["section"]) != section:
            result.issues.append(Issue("SECTION_CONTAMINATION", key, str(rec["section"])))
            continue
        evidence = rec.get("evidence") or []
        anchored = [e for e in evidence if all(e.get(f) not in (None, "") for f in EVIDENCE_FIELDS)]
        if not anchored:
            result.issues.append(Issue("MISSING_EVIDENCE", key, "no page + visible anchor"))
        if rec.get("confidence") != PIXEL:
            result.issues.append(Issue("NOT_PIXEL_AUTHORITY", key, str(rec.get("confidence"))))

        prior = by_key.get(key)
        if prior is not None:
            diffs = [f for f in PATCHABLE_FIELDS if _norm(prior.get(f)) != _norm(rec.get(f))]
            diffs += ["disposition"] if prior["disposition"] != rec["disposition"] else []
            if diffs:
                result.issues.append(Issue("STABLE_KEY_COLLISION", key, ",".join(diffs)))
            continue
        by_key[key] = rec
        result.accepted.append(rec)
    return result


def patch_manifest(
    staged: StagingResult,
    current: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Proposed deltas versus *current* rows (stable_key -> field -> value).

    Only pixel-read, evidence-anchored, collision-free records produce deltas.
    """
    blocked = {i.stable_key for i in staged.issues
               if i.code in {"MISSING_EVIDENCE", "NOT_PIXEL_AUTHORITY", "STABLE_KEY_COLLISION"}}
    out: list[dict[str, Any]] = []
    for rec in staged.accepted:
        key = str(rec["stable_key"])
        if key in blocked:
            continue
        row = current.get(key, {})
        changes = {}
        for f in PATCHABLE_FIELDS:
            new = rec.get(f)
            if new in (None, "", []):
                continue
            if _norm(row.get(f)) != _norm(new):
                changes[f] = {"from": row.get(f), "to": new}
        if changes or rec["disposition"] not in {"INCLUDE", "EXISTING_SEMANTIC_MATCH"}:
            out.append({
                "stable_key": key,
                "disposition": rec["disposition"],
                "source_drive_id": rec["source_drive_id"],
                "source_sha256": rec["source_sha256"],
                "evidence": rec.get("evidence", []),
                "changes": changes,
            })
    return out


def load_staged(paths: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for p in paths:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        records.extend(data if isinstance(data, list) else [data])
    return records
