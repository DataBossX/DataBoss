"""SQLite control plane for auditable DataBossX work.

The database stores metadata and receipts, not document bytes. Source files stay
read-only at their recorded locations and are identified by their SHA-256 hash,
computed through a TOCTOU-hardened stable handle. Classification is stored at
project-asset scope on a validated lattice, secrets are redacted before
persistence, and canonical promotions to APPROVED/DELIVERED require an
authenticated, single-use, expiring, exact-hash/exact-state approval record
verified with a trusted public key held outside the database.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from . import classification as cls
from . import redaction
from .approval import ApprovalError, ApprovalVerifier, VerifierNotConfigured, load_verifier
from .paths import hash_file_stable, safe_resolve_file

SCHEMA_VERSION = 2
LIFECYCLE = (
    "SOURCE",
    "STAGING",
    "EXTRACTED",
    "RECONCILED",
    "QA",
    "APPROVED",
    "DELIVERED",
)
APPROVAL_REQUIRED_STATES = frozenset({"APPROVED", "DELIVERED"})

# Content the control plane always treats as at least confidential.
_CONFIDENTIAL_CONTENT_FLOOR = cls.CONFIDENTIAL

_LOAD_VERIFIER_FROM_ENV = object()


class PromotionError(ValueError):
    """Raised when a canonical-file promotion violates a control."""


class LedgerError(RuntimeError):
    """Raised when the promotion ledger fails integrity verification."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


class ControlPlane:
    """Persistent project, asset, evidence, QA, and promotion ledger."""

    def __init__(
        self,
        database: str | Path,
        *,
        intake_roots: Sequence[str | Path] | None = None,
        approval_verifier: Any = _LOAD_VERIFIER_FROM_ENV,
    ) -> None:
        self.database = Path(database)
        self.intake_roots = [str(Path(root)) for root in (intake_roots or ())]
        self._verifier_setting = approval_verifier

    # -- approval verifier -------------------------------------------------
    def _get_verifier(self) -> ApprovalVerifier | None:
        setting = self._verifier_setting
        if setting is _LOAD_VERIFIER_FROM_ENV:
            return load_verifier()
        return setting

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self, backup_dir: str | Path | None = None) -> Path | None:
        """Initialize the schema, backing up an existing database first."""
        backup = None
        if self.database.exists() and self.database.stat().st_size:
            destination = (
                Path(backup_dir) if backup_dir else self.database.parent / "backups"
            )
            destination.mkdir(parents=True, exist_ok=True)
            backup = (
                destination
                / f"{self.database.stem}-{datetime.now():%Y%m%d-%H%M%S%f}.sqlite3-backup"
            )
            try:
                with sqlite3.connect(self.database) as source, sqlite3.connect(backup) as target:
                    source.backup(target)
                    integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
            except sqlite3.Error:
                backup.unlink(missing_ok=True)
                raise
            if integrity != "ok":
                backup.unlink(missing_ok=True)
                raise OSError(f"database backup integrity check failed: {integrity}")

        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(_SCHEMA)
            current = connection.execute("SELECT MAX(version) FROM schema_versions").fetchone()[0]
            if current is None:
                connection.execute(
                    "INSERT INTO schema_versions(version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, _now()),
                )
            elif current != SCHEMA_VERSION:
                raise RuntimeError(f"unsupported schema version {current}")
        return backup

    # -- projects ----------------------------------------------------------
    def create_project(self, manifest: Mapping[str, Any]) -> str:
        project_id = str(manifest["project_id"]).strip()
        if not project_id:
            raise ValueError("project_id is required")
        required = ("jurisdiction", "county", "section")
        missing = [field for field in required if not str(manifest.get(field, "")).strip()]
        if missing:
            raise ValueError(f"missing project fields: {', '.join(missing)}")
        security = cls.normalize(manifest.get("security_classification", cls.CONFIDENTIAL))
        created_at = _now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO projects(
                       id, client, jurisdiction, county, section, township, range_name,
                       status, security_classification, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project_id,
                    manifest.get("client"),
                    manifest["jurisdiction"],
                    manifest["county"],
                    manifest["section"],
                    manifest.get("township"),
                    manifest.get("range"),
                    manifest.get("status", "active"),
                    security,
                    created_at,
                ),
            )
            self._create_manifest_revision_locked(
                connection, project_id, manifest, (), inherit=False
            )
        return project_id

    # -- intake ------------------------------------------------------------
    def ingest_asset(
        self,
        project_id: str,
        path: str | Path,
        *,
        source_authority: int,
        security_classification: str = cls.CONFIDENTIAL,
        role: str = "source",
    ) -> str:
        with self.connect() as connection:
            return self._ingest_asset_locked(
                connection,
                project_id,
                path,
                source_authority=source_authority,
                security_classification=security_classification,
                role=role,
            )

    def intake_assets(
        self,
        project_id: str,
        paths: Sequence[str | Path],
        *,
        source_authority: int,
        security_classification: str = cls.CONFIDENTIAL,
        role: str = "source",
        source_locations: Sequence[str] = (),
    ) -> tuple[list[str], str]:
        """Ingest assets and carry the authoritative manifest policy forward.

        The new manifest revision inherits the latest revision's policy
        (``required_checks``, ``release_policy``, jurisdiction, ...) and
        atomically adds the ingested asset IDs, all in one transaction.
        """
        with self.connect() as connection:
            asset_ids = [
                self._ingest_asset_locked(
                    connection,
                    project_id,
                    path,
                    source_authority=source_authority,
                    security_classification=security_classification,
                    role=role,
                )
                for path in paths
            ]
            revision_id = self._create_manifest_revision_locked(
                connection,
                project_id,
                {"source_locations": list(source_locations)},
                asset_ids,
                inherit=True,
            )
        return asset_ids, revision_id

    def _ingest_asset_locked(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        path: str | Path,
        *,
        source_authority: int,
        security_classification: str,
        role: str,
    ) -> str:
        if not 1 <= source_authority <= 8:
            raise ValueError("source_authority must be ranked from 1 (highest) to 8")
        project = connection.execute(
            "SELECT 1 FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise ValueError(f"unknown project: {project_id}")

        # Confidential floor for content plus a validated project-asset scope.
        requested = cls.normalize(security_classification)
        scope_classification = cls.strictest(requested, _CONFIDENTIAL_CONTENT_FLOOR)

        source = safe_resolve_file(path, authorized_roots=self.intake_roots or None)
        sha256, size_bytes = hash_file_stable(
            source, authorized_roots=self.intake_roots or None
        )
        asset_id = f"asset:{sha256}"
        created_at = _now()

        existing = connection.execute(
            "SELECT security_classification FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()
        effective = cls.ensure_not_downgraded(
            existing["security_classification"] if existing else None,
            scope_classification,
        )
        connection.execute(
            """INSERT INTO assets(
                   id, sha256, size_bytes, media_type, security_classification, created_at
               ) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET security_classification = excluded.security_classification
               WHERE excluded.security_classification IS NOT NULL""",
            (
                asset_id,
                sha256,
                size_bytes,
                mimetypes.guess_type(source.name)[0] or "application/octet-stream",
                effective,
                created_at,
            ),
        )
        # Enforce "never downgrade" explicitly regardless of insert path.
        connection.execute(
            "UPDATE assets SET security_classification = ? WHERE id = ?",
            (effective, asset_id),
        )
        connection.execute(
            """INSERT INTO asset_locations(
                   asset_id, project_id, location, role, source_authority, verified_at
               ) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(asset_id, project_id, location) DO NOTHING""",
            (asset_id, project_id, str(source), role, source_authority, created_at),
        )
        connection.execute(
            """INSERT INTO asset_classifications(
                   project_id, asset_id, classification, updated_at
               ) VALUES (?, ?, ?, ?)
               ON CONFLICT(project_id, asset_id) DO UPDATE SET
                   classification = excluded.classification, updated_at = excluded.updated_at""",
            (project_id, asset_id, scope_classification, created_at),
        )
        connection.execute(
            """INSERT INTO asset_states(
                   project_id, asset_id, state, updated_at
               ) VALUES (?, ?, 'SOURCE', ?)
               ON CONFLICT(project_id, asset_id) DO NOTHING""",
            (project_id, asset_id, created_at),
        )
        return asset_id

    # -- manifests ---------------------------------------------------------
    def create_manifest_revision(
        self, project_id: str, manifest: Mapping[str, Any], asset_ids: Sequence[str] = ()
    ) -> str:
        with self.connect() as connection:
            return self._create_manifest_revision_locked(
                connection, project_id, manifest, asset_ids, inherit=True
            )

    def _create_manifest_revision_locked(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        manifest: Mapping[str, Any],
        asset_ids: Sequence[str],
        *,
        inherit: bool,
    ) -> str:
        payload: dict[str, Any] = {}
        prior_asset_ids: set[str] = set()
        if inherit:
            prior = connection.execute(
                """SELECT payload_json FROM manifest_revisions
                   WHERE project_id = ? ORDER BY version DESC LIMIT 1""",
                (project_id,),
            ).fetchone()
            if prior is not None:
                payload = json.loads(prior["payload_json"])
                prior_asset_ids = set(payload.get("asset_ids", ()))
        payload.update(dict(manifest))
        payload["project_id"] = project_id
        combined = set(asset_ids) | prior_asset_ids | set(payload.get("asset_ids", ()) or ())
        payload["asset_ids"] = sorted(combined)

        revision_id = f"manifest:{_digest(payload)}"
        for asset_id in payload["asset_ids"]:
            self._require_asset(connection, project_id, asset_id)
        version = connection.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM manifest_revisions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        connection.execute(
            """INSERT OR IGNORE INTO manifest_revisions(
                   id, project_id, version, payload_json, created_at
               ) VALUES (?, ?, ?, ?, ?)""",
            (revision_id, project_id, version, _json(payload), _now()),
        )
        return revision_id

    # -- evidence ----------------------------------------------------------
    def record_evidence(
        self,
        *,
        project_id: str,
        asset_id: str,
        locator: str,
        extracted_text: str,
        conclusion: str,
        confidence: Mapping[str, float],
        verification_status: str = "UNVERIFIED",
        legal_description: str | None = None,
        effective_date: str | None = None,
        citation: str | None = None,
        explanation: str | None = None,
        security_classification: str = cls.CONFIDENTIAL,
    ) -> str:
        if not locator.strip() or not extracted_text.strip() or not conclusion.strip():
            raise ValueError("locator, extracted_text, and conclusion are required")
        invalid = {
            name: score for name, score in confidence.items() if not 0 <= score <= 1
        }
        if invalid:
            raise ValueError(f"confidence scores must be between 0 and 1: {invalid}")
        # Extracted text, conclusions, and legal descriptions are confidential.
        evidence_classification = cls.strictest(
            security_classification, _CONFIDENTIAL_CONTENT_FLOOR
        )
        payload = {
            "project_id": project_id,
            "asset_id": asset_id,
            "locator": locator,
            "extracted_text": extracted_text,
            "conclusion": conclusion,
            "confidence": confidence,
            "verification_status": verification_status,
            "legal_description": legal_description,
            "effective_date": effective_date,
            "citation": citation,
            "explanation": explanation,
            "security_classification": evidence_classification,
        }
        evidence_id = f"evidence:{_digest(payload)}"
        with self.connect() as connection:
            self._require_asset(connection, project_id, asset_id)
            connection.execute(
                """INSERT OR IGNORE INTO evidence(
                       id, project_id, asset_id, locator, citation, extracted_text,
                       legal_description, effective_date, conclusion, confidence_json,
                       verification_status, explanation, security_classification, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    evidence_id,
                    project_id,
                    asset_id,
                    locator,
                    citation,
                    extracted_text,
                    legal_description,
                    effective_date,
                    conclusion,
                    _json(confidence),
                    verification_status,
                    explanation,
                    evidence_classification,
                    _now(),
                ),
            )
        return evidence_id

    # -- runs --------------------------------------------------------------
    def start_run(
        self,
        *,
        project_id: str,
        manifest_revision_id: str,
        agent: str,
        model: str,
        prompt_version: str,
        parameters: Mapping[str, Any] | None = None,
        code_revision: str | None = None,
    ) -> str:
        run_id = f"run:{uuid.uuid4()}"
        safe_parameters = redaction.redact(dict(parameters or {}))
        with self.connect() as connection:
            manifest = connection.execute(
                "SELECT 1 FROM manifest_revisions WHERE id = ? AND project_id = ?",
                (manifest_revision_id, project_id),
            ).fetchone()
            if manifest is None:
                raise ValueError("manifest revision does not belong to project")
            connection.execute(
                """INSERT INTO runs(
                       id, project_id, manifest_revision_id, agent, model, prompt_version,
                       parameters_json, code_revision, status, started_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'RUNNING', ?)""",
                (
                    run_id,
                    project_id,
                    manifest_revision_id,
                    agent,
                    model,
                    prompt_version,
                    _json(safe_parameters),
                    code_revision,
                    _now(),
                ),
            )
        return run_id

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        output_asset_ids: Sequence[str] = (),
        errors: Sequence[str] = (),
        cost: float = 0,
    ) -> None:
        if status not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            raise ValueError("invalid terminal run status")
        safe_errors = [redaction.redact_message(error) for error in errors]
        with self.connect() as connection:
            run = connection.execute(
                "SELECT project_id FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise ValueError(f"unknown run: {run_id}")
            for asset_id in output_asset_ids:
                self._require_asset(connection, run["project_id"], asset_id)
                connection.execute(
                    "INSERT OR IGNORE INTO run_assets(run_id, asset_id, role) VALUES (?, ?, 'output')",
                    (run_id, asset_id),
                )
            cursor = connection.execute(
                """UPDATE runs SET status = ?, completed_at = ?, errors_json = ?, cost = ?
                   WHERE id = ? AND status = 'RUNNING'""",
                (status, _now(), _json(safe_errors), cost, run_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("run is already terminal")

    # -- QA ----------------------------------------------------------------
    def record_qa(
        self,
        *,
        project_id: str,
        run_id: str,
        subject_id: str,
        check_name: str,
        severity: str,
        passed: bool,
        detail: str,
        evidence_ids: Sequence[str] = (),
        policy_version: str = "1",
    ) -> str:
        severity = severity.lower()
        if severity not in {"info", "warn", "review", "error", "critical"}:
            raise ValueError(f"invalid QA severity: {severity}")
        qa_id = f"qa:{uuid.uuid4()}"
        with self.connect() as connection:
            run = connection.execute(
                """SELECT manifest_revision_id FROM runs
                   WHERE id = ? AND project_id = ? AND status = 'SUCCEEDED'""",
                (run_id, project_id),
            ).fetchone()
            if run is None:
                raise ValueError("QA requires a successful project run")
            output = connection.execute(
                """SELECT 1 FROM run_assets
                   WHERE run_id = ? AND asset_id = ? AND role = 'output'""",
                (run_id, subject_id),
            ).fetchone()
            if output is None:
                raise ValueError("QA subject must be an output of the run")
            manifest_payload = connection.execute(
                "SELECT payload_json FROM manifest_revisions WHERE id = ?",
                (run["manifest_revision_id"],),
            ).fetchone()[0]
            manifest_asset_ids = set(json.loads(manifest_payload).get("asset_ids", ()))
            if not evidence_ids:
                raise ValueError("QA results require evidence")
            for evidence_id in evidence_ids:
                row = connection.execute(
                    "SELECT asset_id FROM evidence WHERE id = ? AND project_id = ?",
                    (evidence_id, project_id),
                ).fetchone()
                if row is None:
                    raise ValueError(f"unknown project evidence: {evidence_id}")
                if row["asset_id"] not in manifest_asset_ids:
                    raise ValueError(f"evidence is outside the run manifest: {evidence_id}")
            connection.execute(
                """INSERT INTO qa_results(
                       id, project_id, run_id, subject_id, check_name, policy_version,
                       severity, passed, detail, evidence_ids_json, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    qa_id,
                    project_id,
                    run_id,
                    subject_id,
                    check_name,
                    policy_version,
                    severity,
                    int(passed),
                    detail,
                    _json(sorted(set(evidence_ids))),
                    _now(),
                ),
            )
        return qa_id

    # -- promotion ---------------------------------------------------------
    def promote(
        self,
        *,
        project_id: str,
        asset_id: str,
        to_state: str,
        actor: str,
        reason: str,
        approval: Mapping[str, Any] | None = None,
    ) -> str:
        """Promote exactly one lifecycle step and emit a hash-chained receipt."""
        if to_state not in LIFECYCLE:
            raise PromotionError(f"invalid state: {to_state}")
        if not actor.strip() or not reason.strip():
            raise PromotionError("actor and reason are required")
        with self.connect() as connection:
            asset = self._require_asset(connection, project_id, asset_id)
            row = connection.execute(
                "SELECT state FROM asset_states WHERE project_id = ? AND asset_id = ?",
                (project_id, asset_id),
            ).fetchone()
            if row is None:
                raise PromotionError("asset has no lifecycle state")
            from_state = row["state"]
            expected = (
                LIFECYCLE[LIFECYCLE.index(from_state) + 1]
                if from_state != LIFECYCLE[-1]
                else None
            )
            if to_state != expected:
                raise PromotionError(
                    f"invalid transition {from_state} -> {to_state}; expected {expected}"
                )
            if to_state in {"QA", "APPROVED", "DELIVERED"}:
                self._require_qa_clearance(connection, project_id, asset_id)

            approval_id: str | None = None
            if to_state in APPROVAL_REQUIRED_STATES:
                approval_id = self._consume_approval(
                    connection,
                    approval,
                    project_id=project_id,
                    asset_id=asset_id,
                    asset_sha256=asset["sha256"],
                    from_state=from_state,
                    to_state=to_state,
                    actor=actor,
                )
            elif approval is not None:
                raise PromotionError(f"{to_state} does not accept an approval record")

            previous = connection.execute(
                """SELECT receipt_hash FROM promotions
                   WHERE project_id = ? ORDER BY created_at DESC, id DESC LIMIT 1""",
                (project_id,),
            ).fetchone()
            payload = {
                "project_id": project_id,
                "asset_id": asset_id,
                "from_state": from_state,
                "to_state": to_state,
                "actor": actor,
                "reason": reason,
                "approval_id": approval_id,
                "previous_hash": previous["receipt_hash"] if previous else None,
                "created_at": _now(),
            }
            receipt_hash = _digest(payload)
            promotion_id = f"promotion:{receipt_hash}"
            connection.execute(
                """INSERT INTO promotions(
                       id, project_id, asset_id, from_state, to_state, actor, reason,
                       approval_id, previous_hash, receipt_hash, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    promotion_id,
                    project_id,
                    asset_id,
                    from_state,
                    to_state,
                    actor,
                    reason,
                    approval_id,
                    payload["previous_hash"],
                    receipt_hash,
                    payload["created_at"],
                ),
            )
            connection.execute(
                """UPDATE asset_states SET state = ?, updated_at = ?
                   WHERE project_id = ? AND asset_id = ?""",
                (to_state, payload["created_at"], project_id, asset_id),
            )
        return promotion_id

    def _consume_approval(
        self,
        connection: sqlite3.Connection,
        approval: Mapping[str, Any] | None,
        *,
        project_id: str,
        asset_id: str,
        asset_sha256: str,
        from_state: str,
        to_state: str,
        actor: str,
    ) -> str:
        if approval is None:
            raise PromotionError(f"{to_state} requires a signed approval record")
        verifier = self._get_verifier()
        if verifier is None:
            raise PromotionError(
                f"{to_state} is blocked: no trusted approval verifier is configured "
                "(fail closed)"
            )
        try:
            record = verifier.verify(
                approval,
                project_id=project_id,
                asset_id=asset_id,
                asset_sha256=asset_sha256,
                from_state=from_state,
                to_state=to_state,
            )
        except (ApprovalError, VerifierNotConfigured) as exc:
            raise PromotionError(f"{to_state} approval rejected: {exc}") from exc

        # Single-use: a re-used nonce is a replay and is rejected.
        replayed = connection.execute(
            "SELECT 1 FROM approvals WHERE nonce = ?", (record.nonce,)
        ).fetchone()
        if replayed is not None:
            raise PromotionError(f"{to_state} approval replay rejected: nonce already used")

        approval_id = f"approval:{_digest(json.loads(record.token_json))}"
        connection.execute(
            """INSERT INTO approvals(
                   id, project_id, asset_id, nonce, key_id, subject, from_state, to_state,
                   asset_sha256, scope, issued_at, expires_at, token_json, used_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                approval_id,
                project_id,
                asset_id,
                record.nonce,
                record.key_id,
                record.subject,
                from_state,
                to_state,
                record.asset_sha256,
                record.scope,
                record.issued_at,
                record.expires_at,
                record.token_json,
                _now(),
            ),
        )
        return approval_id

    # -- ledger verification ----------------------------------------------
    def verify_ledger(self, project_id: str) -> dict[str, Any]:
        """Recompute the hash chain and detect tampering.

        Detects: broken/edited receipts, broken previous-hash linkage, asset
        states that disagree with the ledger (direct state edits), and forged or
        invalid approval records on APPROVED/DELIVERED promotions.
        """
        issues: list[str] = []
        verifier = self._get_verifier()
        with self.connect() as connection:
            promotions = connection.execute(
                """SELECT id, asset_id, from_state, to_state, actor, reason, approval_id,
                          previous_hash, receipt_hash, created_at
                   FROM promotions WHERE project_id = ?
                   ORDER BY created_at, id""",
                (project_id,),
            ).fetchall()

            previous_hash: str | None = None
            final_state: dict[str, str] = {}
            for promotion in promotions:
                payload = {
                    "project_id": project_id,
                    "asset_id": promotion["asset_id"],
                    "from_state": promotion["from_state"],
                    "to_state": promotion["to_state"],
                    "actor": promotion["actor"],
                    "reason": promotion["reason"],
                    "approval_id": promotion["approval_id"],
                    "previous_hash": promotion["previous_hash"],
                    "created_at": promotion["created_at"],
                }
                recomputed = _digest(payload)
                if recomputed != promotion["receipt_hash"]:
                    issues.append(
                        f"receipt {promotion['id']} hash mismatch (tampered fields)"
                    )
                if promotion["previous_hash"] != previous_hash:
                    issues.append(
                        f"receipt {promotion['id']} breaks the hash chain linkage"
                    )
                previous_hash = promotion["receipt_hash"]
                final_state[promotion["asset_id"]] = promotion["to_state"]

                if promotion["to_state"] in APPROVAL_REQUIRED_STATES:
                    self._verify_approval_receipt(
                        connection, project_id, promotion, verifier, issues
                    )

            # Direct state edits: asset_states must agree with the ledger.
            states = connection.execute(
                "SELECT asset_id, state FROM asset_states WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            for state in states:
                expected = final_state.get(state["asset_id"], "SOURCE")
                if state["state"] != expected:
                    issues.append(
                        f"asset {state['asset_id']} state {state['state']!r} disagrees "
                        f"with ledger {expected!r} (direct state edit)"
                    )

        return {"project_id": project_id, "ok": not issues, "issues": issues,
                "promotions": len(promotions)}

    def _verify_approval_receipt(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        promotion: sqlite3.Row,
        verifier: ApprovalVerifier | None,
        issues: list[str],
    ) -> None:
        approval_id = promotion["approval_id"]
        if not approval_id:
            issues.append(
                f"receipt {promotion['id']} promoted to {promotion['to_state']} "
                "without an approval record"
            )
            return
        row = connection.execute(
            "SELECT token_json, asset_id, from_state, to_state, asset_sha256 FROM approvals WHERE id = ?",
            (approval_id,),
        ).fetchone()
        if row is None:
            issues.append(f"receipt {promotion['id']} references a missing approval")
            return
        if verifier is None:
            issues.append(
                f"approval for {promotion['id']} cannot be verified: no trusted "
                "verifier configured (fail closed)"
            )
            return
        try:
            verifier.verify(
                json.loads(row["token_json"]),
                project_id=project_id,
                asset_id=row["asset_id"],
                asset_sha256=row["asset_sha256"],
                from_state=row["from_state"],
                to_state=row["to_state"],
                now=None,
            )
        except (ApprovalError, VerifierNotConfigured) as exc:
            # Expiry at verification time is expected for historical approvals; a
            # signature/binding failure indicates forgery.
            message = str(exc)
            if "expired" not in message:
                issues.append(f"approval for {promotion['id']} is invalid: {message}")

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _require_qa_clearance(
        connection: sqlite3.Connection, project_id: str, asset_id: str
    ) -> None:
        run = connection.execute(
            """SELECT runs.id, manifests.payload_json
               FROM runs
               JOIN run_assets ON run_assets.run_id = runs.id
               JOIN manifest_revisions manifests ON manifests.id = runs.manifest_revision_id
               WHERE runs.project_id = ? AND runs.status = 'SUCCEEDED'
                 AND run_assets.asset_id = ? AND run_assets.role = 'output'
               ORDER BY runs.completed_at DESC, runs.id DESC LIMIT 1""",
            (project_id, asset_id),
        ).fetchone()
        if run is None:
            raise PromotionError("QA promotion requires a successful producing run")
        required_checks = set(json.loads(run["payload_json"]).get("required_checks", ()))
        if not required_checks:
            raise PromotionError("run manifest must define required_checks")
        results = connection.execute(
            """SELECT check_name, severity, passed FROM qa_results
               WHERE project_id = ? AND subject_id = ? AND run_id = ?
               ORDER BY created_at, id""",
            (project_id, asset_id, run["id"]),
        ).fetchall()
        latest = {row["check_name"]: row for row in results}
        missing_or_failed = sorted(
            check for check in required_checks if check not in latest or not latest[check]["passed"]
        )
        blocking = sorted(
            name
            for name, row in latest.items()
            if not row["passed"] and row["severity"] in {"critical", "error"}
        )
        failures = sorted(set(missing_or_failed + blocking))
        if failures:
            raise PromotionError(f"required QA checks are missing or failing: {', '.join(failures)}")

    @staticmethod
    def _require_asset(
        connection: sqlite3.Connection, project_id: str, asset_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            """SELECT a.* FROM assets a
               JOIN asset_locations l ON l.asset_id = a.id
               WHERE a.id = ? AND l.project_id = ?""",
            (asset_id, project_id),
        ).fetchone()
        if row is None:
            raise ValueError(f"asset {asset_id} is not registered to project {project_id}")
        return row


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    client TEXT,
    jurisdiction TEXT NOT NULL,
    county TEXT NOT NULL,
    section TEXT NOT NULL,
    township TEXT,
    range_name TEXT,
    status TEXT NOT NULL,
    security_classification TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    size_bytes INTEGER NOT NULL,
    media_type TEXT NOT NULL,
    security_classification TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS asset_locations (
    asset_id TEXT NOT NULL REFERENCES assets(id),
    project_id TEXT NOT NULL REFERENCES projects(id),
    location TEXT NOT NULL,
    role TEXT NOT NULL,
    source_authority INTEGER NOT NULL CHECK(source_authority BETWEEN 1 AND 8),
    verified_at TEXT NOT NULL,
    PRIMARY KEY(asset_id, project_id, location)
);
CREATE TABLE IF NOT EXISTS asset_classifications (
    project_id TEXT NOT NULL REFERENCES projects(id),
    asset_id TEXT NOT NULL REFERENCES assets(id),
    classification TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(project_id, asset_id)
);
CREATE TABLE IF NOT EXISTS asset_states (
    project_id TEXT NOT NULL REFERENCES projects(id),
    asset_id TEXT NOT NULL REFERENCES assets(id),
    state TEXT NOT NULL CHECK(state IN ('SOURCE','STAGING','EXTRACTED','RECONCILED','QA','APPROVED','DELIVERED')),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(project_id, asset_id)
);
CREATE TABLE IF NOT EXISTS manifest_revisions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    version INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(project_id, version)
);
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    asset_id TEXT NOT NULL REFERENCES assets(id),
    locator TEXT NOT NULL,
    citation TEXT,
    extracted_text TEXT NOT NULL,
    legal_description TEXT,
    effective_date TEXT,
    conclusion TEXT NOT NULL,
    confidence_json TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    explanation TEXT,
    security_classification TEXT NOT NULL DEFAULT 'CONFIDENTIAL',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    manifest_revision_id TEXT NOT NULL REFERENCES manifest_revisions(id),
    agent TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    code_revision TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    errors_json TEXT,
    cost REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS run_assets (
    run_id TEXT NOT NULL REFERENCES runs(id),
    asset_id TEXT NOT NULL REFERENCES assets(id),
    role TEXT NOT NULL,
    PRIMARY KEY(run_id, asset_id, role)
);
CREATE TABLE IF NOT EXISTS qa_results (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    run_id TEXT NOT NULL REFERENCES runs(id),
    subject_id TEXT NOT NULL,
    check_name TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    severity TEXT NOT NULL,
    passed INTEGER NOT NULL CHECK(passed IN (0, 1)),
    detail TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    asset_id TEXT NOT NULL REFERENCES assets(id),
    nonce TEXT NOT NULL UNIQUE,
    key_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    asset_sha256 TEXT NOT NULL,
    scope TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    token_json TEXT NOT NULL,
    used_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS promotions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    asset_id TEXT NOT NULL REFERENCES assets(id),
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    approval_id TEXT REFERENCES approvals(id),
    previous_hash TEXT,
    receipt_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS immutable_manifest_update
BEFORE UPDATE ON manifest_revisions BEGIN SELECT RAISE(ABORT, 'manifest revisions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_manifest_delete
BEFORE DELETE ON manifest_revisions BEGIN SELECT RAISE(ABORT, 'manifest revisions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_update
BEFORE UPDATE ON evidence BEGIN SELECT RAISE(ABORT, 'evidence records are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_delete
BEFORE DELETE ON evidence BEGIN SELECT RAISE(ABORT, 'evidence records are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_qa_update
BEFORE UPDATE ON qa_results BEGIN SELECT RAISE(ABORT, 'QA results are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_qa_delete
BEFORE DELETE ON qa_results BEGIN SELECT RAISE(ABORT, 'QA results are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_approval_update
BEFORE UPDATE ON approvals BEGIN SELECT RAISE(ABORT, 'approval records are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_approval_delete
BEFORE DELETE ON approvals BEGIN SELECT RAISE(ABORT, 'approval records are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_promotion_update
BEFORE UPDATE ON promotions BEGIN SELECT RAISE(ABORT, 'promotion receipts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_promotion_delete
BEFORE DELETE ON promotions BEGIN SELECT RAISE(ABORT, 'promotion receipts are immutable'); END;
"""
