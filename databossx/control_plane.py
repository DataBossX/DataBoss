"""SQLite control plane for auditable DataBossX work.

The database stores metadata and receipts, not document bytes. Source files stay
read-only at their recorded locations and are identified by their SHA-256 hash.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

SCHEMA_VERSION = 1
LIFECYCLE = ("SOURCE", "STAGING", "EXTRACTED", "RECONCILED", "QA", "APPROVED", "DELIVERED")


class PromotionError(ValueError):
    """Raised when a canonical-file promotion violates a control."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _file_digest(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ControlPlane:
    """Persistent project, asset, evidence, QA, and promotion ledger."""

    def __init__(self, database: str | Path) -> None:
        self.database = Path(database)

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
            destination = Path(backup_dir) if backup_dir else self.database.parent / "backups"
            destination.mkdir(parents=True, exist_ok=True)
            backup = destination / f"{self.database.stem}-{datetime.now():%Y%m%d-%H%M%S%f}.sqlite3"
            shutil.copy2(self.database, backup)
            if _file_digest(backup) != _file_digest(self.database):
                backup.unlink(missing_ok=True)
                raise OSError("database backup verification failed")

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

    def create_project(self, manifest: Mapping[str, Any]) -> str:
        project_id = str(manifest["project_id"]).strip()
        if not project_id:
            raise ValueError("project_id is required")
        required = ("jurisdiction", "county", "section")
        missing = [field for field in required if not str(manifest.get(field, "")).strip()]
        if missing:
            raise ValueError(f"missing project fields: {', '.join(missing)}")
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
                    manifest.get("security_classification", "CONFIDENTIAL"),
                    created_at,
                ),
            )
        self.create_manifest_revision(project_id, manifest)
        return project_id

    def ingest_asset(
        self,
        project_id: str,
        path: str | Path,
        *,
        source_authority: int,
        security_classification: str = "CONFIDENTIAL",
        role: str = "source",
    ) -> str:
        """Inventory one file without modifying it."""
        source = Path(path).expanduser().resolve(strict=True)
        if not source.is_file():
            raise ValueError(f"asset is not a file: {source}")
        if not 1 <= source_authority <= 8:
            raise ValueError("source_authority must be ranked from 1 (highest) to 8")
        sha256 = _file_digest(source)
        asset_id = f"asset:{sha256}"
        stat = source.stat()
        created_at = _now()
        with self.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO assets(
                       id, sha256, size_bytes, media_type, security_classification, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    asset_id,
                    sha256,
                    stat.st_size,
                    mimetypes.guess_type(source.name)[0] or "application/octet-stream",
                    security_classification,
                    created_at,
                ),
            )
            connection.execute(
                """INSERT OR IGNORE INTO asset_locations(
                       asset_id, project_id, location, role, source_authority, verified_at
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (asset_id, project_id, str(source), role, source_authority, created_at),
            )
            connection.execute(
                """INSERT OR IGNORE INTO asset_states(
                       project_id, asset_id, state, updated_at
                   ) VALUES (?, ?, 'SOURCE', ?)""",
                (project_id, asset_id, created_at),
            )
        return asset_id

    def create_manifest_revision(
        self, project_id: str, manifest: Mapping[str, Any], asset_ids: Sequence[str] = ()
    ) -> str:
        payload = dict(manifest)
        payload["project_id"] = project_id
        payload["asset_ids"] = sorted(set(asset_ids or payload.get("asset_ids", ())))
        revision_id = f"manifest:{_digest(payload)}"
        with self.connect() as connection:
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
    ) -> str:
        if not locator.strip() or not extracted_text.strip() or not conclusion.strip():
            raise ValueError("locator, extracted_text, and conclusion are required")
        invalid = {name: score for name, score in confidence.items() if not 0 <= score <= 1}
        if invalid:
            raise ValueError(f"confidence scores must be between 0 and 1: {invalid}")
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
        }
        evidence_id = f"evidence:{_digest(payload)}"
        with self.connect() as connection:
            self._require_asset(connection, project_id, asset_id)
            connection.execute(
                """INSERT OR IGNORE INTO evidence(
                       id, project_id, asset_id, locator, citation, extracted_text,
                       legal_description, effective_date, conclusion, confidence_json,
                       verification_status, explanation, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    _now(),
                ),
            )
        return evidence_id

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
                    _json(parameters or {}),
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
        with self.connect() as connection:
            run = connection.execute("SELECT project_id FROM runs WHERE id = ?", (run_id,)).fetchone()
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
                (status, _now(), _json(list(errors)), cost, run_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("run is already terminal")

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
                "SELECT 1 FROM runs WHERE id = ? AND project_id = ?", (run_id, project_id)
            ).fetchone()
            if run is None:
                raise ValueError("run does not belong to project")
            for evidence_id in evidence_ids:
                row = connection.execute(
                    "SELECT 1 FROM evidence WHERE id = ? AND project_id = ?",
                    (evidence_id, project_id),
                ).fetchone()
                if row is None:
                    raise ValueError(f"unknown project evidence: {evidence_id}")
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

    def promote(
        self,
        *,
        project_id: str,
        asset_id: str,
        to_state: str,
        actor: str,
        reason: str,
        human_approved: bool = False,
    ) -> str:
        """Promote exactly one lifecycle step and emit a hash-chained receipt."""
        if to_state not in LIFECYCLE:
            raise PromotionError(f"invalid state: {to_state}")
        if not actor.strip() or not reason.strip():
            raise PromotionError("actor and reason are required")
        with self.connect() as connection:
            self._require_asset(connection, project_id, asset_id)
            row = connection.execute(
                "SELECT state FROM asset_states WHERE project_id = ? AND asset_id = ?",
                (project_id, asset_id),
            ).fetchone()
            if row is None:
                raise PromotionError("asset has no lifecycle state")
            from_state = row["state"]
            expected = LIFECYCLE[LIFECYCLE.index(from_state) + 1] if from_state != LIFECYCLE[-1] else None
            if to_state != expected:
                raise PromotionError(f"invalid transition {from_state} -> {to_state}; expected {expected}")
            if to_state in {"APPROVED", "DELIVERED"} and not human_approved:
                raise PromotionError(f"{to_state} requires explicit human approval")
            if to_state in {"QA", "APPROVED", "DELIVERED"}:
                evidence_count = connection.execute(
                    "SELECT COUNT(*) FROM evidence WHERE project_id = ? AND asset_id = ?",
                    (project_id, asset_id),
                ).fetchone()[0]
                qa_count = connection.execute(
                    "SELECT COUNT(*) FROM qa_results WHERE project_id = ? AND subject_id = ?",
                    (project_id, asset_id),
                ).fetchone()[0]
                if not evidence_count or not qa_count:
                    raise PromotionError("QA promotion requires linked evidence and QA results")
                blocking = connection.execute(
                    """SELECT COUNT(*) FROM qa_results failed
                       WHERE failed.project_id = ? AND failed.subject_id = ?
                         AND failed.passed = 0 AND failed.severity IN ('critical', 'error')
                         AND NOT EXISTS (
                             SELECT 1 FROM qa_results resolved
                             WHERE resolved.project_id = failed.project_id
                               AND resolved.subject_id = failed.subject_id
                               AND resolved.check_name = failed.check_name
                               AND resolved.passed = 1
                               AND resolved.created_at > failed.created_at
                         )""",
                    (project_id, asset_id),
                ).fetchone()[0]
                if blocking:
                    raise PromotionError(f"{blocking} blocking QA failure(s) remain")

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
                "human_approved": human_approved,
                "previous_hash": previous["receipt_hash"] if previous else None,
                "created_at": _now(),
            }
            receipt_hash = _digest(payload)
            promotion_id = f"promotion:{receipt_hash}"
            connection.execute(
                """INSERT INTO promotions(
                       id, project_id, asset_id, from_state, to_state, actor, reason,
                       human_approved, previous_hash, receipt_hash, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    promotion_id,
                    project_id,
                    asset_id,
                    from_state,
                    to_state,
                    actor,
                    reason,
                    int(human_approved),
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
CREATE TABLE IF NOT EXISTS promotions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    asset_id TEXT NOT NULL REFERENCES assets(id),
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    human_approved INTEGER NOT NULL CHECK(human_approved IN (0, 1)),
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
CREATE TRIGGER IF NOT EXISTS immutable_promotion_update
BEFORE UPDATE ON promotions BEGIN SELECT RAISE(ABORT, 'promotion receipts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_promotion_delete
BEFORE DELETE ON promotions BEGIN SELECT RAISE(ABORT, 'promotion receipts are immutable'); END;
"""
