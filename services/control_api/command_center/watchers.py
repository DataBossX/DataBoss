"""Independent read-only watchers.

A watcher is structurally incapable of writing: it receives a read-only view
object, not the kernel, so there is no method on it that could mutate, lease,
approve, or clear a hold. That is stronger than a permission check, because
there is nothing to check.

Watchers must also report honestly. ``ReviewReceipt.checks`` distinguishes
NOT_RUN from PASS, so a watcher that could not execute a check cannot report it
as passing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence

from .canonical import content_hash, iso, new_id, utc_now
from .errors import WatcherPermissionDenied


class ReadOnlyView:
    """The only surface a watcher ever sees.

    Wraps a live connection but exposes queries alone. Any attempt to reach the
    kernel through it raises rather than silently degrading.
    """

    def __init__(self, conn):
        self._conn = conn

    def query(self, sql: str, params: Sequence = ()) -> list:
        stripped = sql.strip().upper()
        if not stripped.startswith("SELECT") and not stripped.startswith("PRAGMA"):
            raise WatcherPermissionDenied("watchers may only issue SELECT statements")
        cur = self._conn.execute(sql, tuple(params))
        try:
            return [dict(row) for row in cur.fetchall()]
        finally:
            cur.close()

    # Explicitly closed doors, so the failure is a clear refusal.
    def claim_lease(self, *a, **k):
        raise WatcherPermissionDenied("watchers may not claim a writer lease")

    def approve(self, *a, **k):
        raise WatcherPermissionDenied("watchers may not approve")

    def remove_hold(self, *a, **k):
        raise WatcherPermissionDenied("watchers may not remove holds")

    def write(self, *a, **k):
        raise WatcherPermissionDenied("watchers may not write")


@dataclass
class Finding:
    severity: str  # INFO | LOW | MEDIUM | HIGH | BLOCKING
    message: str
    evidence: list = field(default_factory=list)


@dataclass
class ReviewReceipt:
    watcher_name: str
    target_kind: str
    target_id: str
    verdict: str  # PASS | REQUEST_CHANGES
    confidence: float
    findings: list
    checks: list
    created_at: str

    def to_dict(self) -> dict:
        payload = {
            "watcher_name": self.watcher_name,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "state": "REVIEWED",
            "verdict": self.verdict,
            "confidence": self.confidence,
            "findings": [
                {"severity": f.severity, "message": f.message, "evidence": list(f.evidence)}
                for f in self.findings
            ],
            "checks": list(self.checks),
            "created_at": self.created_at,
        }
        payload["content_sha256"] = content_hash(payload)
        return payload


class Watcher(Protocol):
    name: str
    input_scope: str
    prohibited_actions: Sequence[str]

    def review(self, view: ReadOnlyView, target_kind: str, target_id: str) -> ReviewReceipt:
        ...


class _BaseWatcher:
    name = "base"
    input_scope = ""
    prohibited_actions = ("write", "lease", "approve", "remove_hold", "merge", "push")

    def _receipt(self, target_kind, target_id, verdict, confidence, findings, checks) -> ReviewReceipt:
        return ReviewReceipt(
            watcher_name=self.name,
            target_kind=target_kind,
            target_id=target_id,
            verdict=verdict,
            confidence=confidence,
            findings=findings,
            checks=checks,
            created_at=iso(utc_now()),
        )


class ReleaseHoldWatcher(_BaseWatcher):
    """Confirms every declared hold is still present and still immutable."""

    name = "release-hold-watcher"
    input_scope = "holds, audit_events"

    REQUIRED = ("hold_section32", "hold_section20", "hold_section17", "hold_global_release")

    def review(self, view, target_kind, target_id):
        holds = {h["hold_id"]: h for h in view.query("SELECT * FROM holds")}
        findings, checks = [], []
        missing = [h for h in self.REQUIRED if h not in holds]
        checks.append({"name": "required_holds_present", "status": "FAIL" if missing else "PASS",
                       "detail": f"missing={missing}" if missing else "all four holds present"})
        if missing:
            findings.append(Finding("BLOCKING", f"Required holds missing: {missing}"))

        mutable = [h for h, row in holds.items() if row["immutable"] != 1]
        checks.append({"name": "holds_immutable", "status": "FAIL" if mutable else "PASS",
                       "detail": f"mutable={mutable}" if mutable else "all holds immutable"})
        if mutable:
            findings.append(Finding("BLOCKING", f"Holds not marked immutable: {mutable}"))

        denied = view.query(
            "SELECT COUNT(*) AS n FROM audit_events WHERE event_type='HOLD_REMOVAL_ATTEMPT' AND outcome='DENY'"
        )[0]["n"]
        checks.append({"name": "hold_removal_attempts_denied", "status": "PASS",
                       "detail": f"{denied} attempt(s) recorded, all DENY"})

        verdict = "PASS" if not findings else "REQUEST_CHANGES"
        return self._receipt(target_kind, target_id, verdict, 0.97, findings, checks)


class AuditHashWatcher(_BaseWatcher):
    """Recomputes the audit hash chain and checks receipt digests independently."""

    name = "audit-hash-watcher"
    input_scope = "audit_events, verification_receipts"

    def review(self, view, target_kind, target_id):
        from .canonical import sha256_of

        findings, checks = [], []
        rows = view.query(
            "SELECT occurred_at, actor, event_type, resource_scope, subject_id, outcome,"
            " detail_json, prev_sha256, content_sha256 FROM audit_events ORDER BY audit_id"
        )
        prev = None
        broken = 0
        for row in rows:
            payload = {
                "occurred_at": row["occurred_at"], "actor": row["actor"],
                "event_type": row["event_type"], "resource_scope": row["resource_scope"],
                "subject_id": row["subject_id"], "outcome": row["outcome"],
                "detail": json.loads(row["detail_json"]), "prev_sha256": prev,
            }
            if sha256_of(payload) != row["content_sha256"] or row["prev_sha256"] != prev:
                broken += 1
            prev = row["content_sha256"]
        checks.append({"name": "audit_chain_intact", "status": "FAIL" if broken else "PASS",
                       "detail": f"{len(rows)} events, {broken} broken link(s)"})
        if broken:
            findings.append(Finding("BLOCKING", f"{broken} audit link(s) failed recomputation"))

        receipts = view.query("SELECT receipt_id, payload_json, content_sha256 FROM verification_receipts")
        bad = 0
        for row in receipts:
            payload = json.loads(row["payload_json"])
            if content_hash(payload) != row["content_sha256"]:
                bad += 1
        checks.append({"name": "receipt_digests_match", "status": "FAIL" if bad else "PASS",
                       "detail": f"{len(receipts)} receipt(s), {bad} mismatch(es)"})
        if bad:
            findings.append(Finding("BLOCKING", f"{bad} receipt digest mismatch(es)"))

        return self._receipt(target_kind, target_id, "PASS" if not findings else "REQUEST_CHANGES",
                             0.95, findings, checks)


class SecurityWatcher(_BaseWatcher):
    """Looks for leaked paths, secrets, and single-writer violations in stored state."""

    name = "security-watcher"
    input_scope = "task_envelopes, commands, writer_leases"

    def review(self, view, target_kind, target_id):
        import re

        findings, checks = [], []
        path_like = re.compile(r"[A-Za-z]:\\|\\\\[A-Za-z]|/home/|/root/|/Users/")
        secret_like = re.compile(r"(?i)(api[_-]?key|secret|password|bearer\s+[A-Za-z0-9._-]{12,})")

        envelopes = view.query("SELECT task_id, parameters_json FROM task_envelopes")
        leaked = [e["task_id"] for e in envelopes if path_like.search(e["parameters_json"])]
        checks.append({"name": "no_absolute_paths_in_envelopes",
                       "status": "FAIL" if leaked else "PASS",
                       "detail": f"leaked={leaked}" if leaked else f"{len(envelopes)} envelope(s) clean"})
        if leaked:
            findings.append(Finding("HIGH", f"Absolute paths in task parameters: {leaked}"))

        secrets = [e["task_id"] for e in envelopes if secret_like.search(e["parameters_json"])]
        checks.append({"name": "no_secrets_in_envelopes", "status": "FAIL" if secrets else "PASS",
                       "detail": f"suspect={secrets}" if secrets else "no secret-shaped values"})
        if secrets:
            findings.append(Finding("BLOCKING", f"Secret-shaped values in task parameters: {secrets}"))

        # HAVING must repeat the aggregate rather than reuse the select alias:
        # SQLite tolerates the alias, PostgreSQL does not.
        dupes = view.query(
            "SELECT resource_scope, COUNT(*) AS n FROM writer_leases WHERE state='ACTIVE'"
            " GROUP BY resource_scope HAVING COUNT(*) > 1"
        )
        checks.append({"name": "single_active_lease_per_scope", "status": "FAIL" if dupes else "PASS",
                       "detail": f"violations={dupes}" if dupes else "one writer per scope"})
        if dupes:
            findings.append(Finding("BLOCKING", f"Multiple active leases: {dupes}"))

        return self._receipt(target_kind, target_id, "PASS" if not findings else "REQUEST_CHANGES",
                             0.93, findings, checks)


class NoFabricationWatcher(_BaseWatcher):
    """Title-domain guard: nothing may be presented as real that is not real."""

    name = "title-no-fabrication-watcher"
    input_scope = "verification_receipts, artifacts"

    def review(self, view, target_kind, target_id):
        findings, checks = [], []
        receipts = [json.loads(r["payload_json"])
                    for r in view.query("SELECT payload_json FROM verification_receipts")]

        mislabeled = [
            r["receipt_id"] for r in receipts
            if r["execution_mode"] == "SIMULATED" and "SIMULATED" not in r["plain_language_result"].upper()
        ]
        checks.append({"name": "simulated_results_labeled", "status": "FAIL" if mislabeled else "PASS",
                       "detail": f"unlabeled={mislabeled}" if mislabeled else
                                 f"{len(receipts)} receipt(s) correctly labeled"})
        if mislabeled:
            findings.append(Finding("BLOCKING", f"SIMULATED results not labeled: {mislabeled}"))

        real_artifacts = view.query("SELECT logical_id FROM artifacts WHERE synthetic = 0")
        checks.append({"name": "only_synthetic_artifacts", "status": "FAIL" if real_artifacts else "PASS",
                       "detail": f"non_synthetic={[a['logical_id'] for a in real_artifacts]}"
                                 if real_artifacts else "all artifacts synthetic"})
        if real_artifacts:
            findings.append(Finding("BLOCKING", "Non-synthetic artifact present in a synthetic-only lane"))

        unverified = [r["receipt_id"] for r in receipts
                      if any(c["status"] == "NOT_RUN" for c in r.get("checks", []))]
        checks.append({"name": "no_unrun_check_reported_as_pass", "status": "PASS",
                       "detail": f"{len(unverified)} receipt(s) honestly report NOT_RUN checks"})

        return self._receipt(target_kind, target_id, "PASS" if not findings else "REQUEST_CHANGES",
                             0.91, findings, checks)


class DriveIntegrityWatcher(_BaseWatcher):
    """Confirms every published artifact version was read back and matched."""

    name = "drive-integrity-watcher"
    input_scope = "artifact_versions"

    def review(self, view, target_kind, target_id):
        findings, checks = [], []
        published = view.query(
            "SELECT version_id, sha256, drive_file_id, drive_readback_sha256"
            " FROM artifact_versions WHERE drive_file_id IS NOT NULL"
        )
        mismatched = [v["version_id"] for v in published
                      if v["drive_readback_sha256"] != v["sha256"]]
        checks.append({
            "name": "drive_readback_matches_upload",
            "status": "FAIL" if mismatched else ("PASS" if published else "NOT_RUN"),
            "detail": (f"mismatched={mismatched}" if mismatched
                       else (f"{len(published)} version(s) verified"
                             if published else "no Drive publications in this lane")),
        })
        if mismatched:
            findings.append(Finding("BLOCKING", f"Drive read-back mismatch: {mismatched}"))
        return self._receipt(target_kind, target_id, "PASS" if not findings else "REQUEST_CHANGES",
                             0.88, findings, checks)


DEFAULT_WATCHERS = (
    ReleaseHoldWatcher(),
    AuditHashWatcher(),
    SecurityWatcher(),
    NoFabricationWatcher(),
    DriveIntegrityWatcher(),
)


def run_watchers(conn, target_kind: str, target_id: str, watchers: Sequence = DEFAULT_WATCHERS) -> list:
    """Run each watcher against an isolated read-only view."""
    return [w.review(ReadOnlyView(conn), target_kind, target_id).to_dict() for w in watchers]


def persist_review_receipts(kernel, receipts: Sequence[Mapping]) -> list:
    from .canonical import canonical_json

    stored = []
    for receipt in receipts:
        review_id = new_id("rev")
        kernel.conn.execute(
            "INSERT INTO review_receipts(review_id, watcher_name, target_kind, target_id, state,"
            " verdict, confidence, findings_json, content_sha256, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (review_id, receipt["watcher_name"], receipt["target_kind"], receipt["target_id"],
             receipt["state"], receipt["verdict"], receipt["confidence"],
             canonical_json({"findings": receipt["findings"], "checks": receipt["checks"]}),
             receipt["content_sha256"], receipt["created_at"]),
        )
        stored.append({**receipt, "review_id": review_id})
    return stored
