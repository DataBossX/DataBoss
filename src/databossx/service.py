from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from uuid import uuid4

from .audit import AuditWriter, utc_now
from .config import KernelConfig
from .db import Database
from .extractors import extract_vault_object
from .vault import Vault, VaultError

SKIP_DIRECTORIES = {
    ".git",
    ".venv",
    ".venv-kernel",
    "__pycache__",
    "node_modules",
}


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def _pid_is_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


class KernelService:
    def __init__(self, config: KernelConfig) -> None:
        self.config = config
        self.db = Database(config)
        self.db.initialize()
        self.vault = Vault(config)
        self.audit = AuditWriter()
        self._write_lock = threading.RLock()
        self._recover_abandoned_runs()

    def _recover_abandoned_runs(self) -> None:
        with self._write_lock, self.db.transaction(immediate=True) as connection:
            for table, object_type in (
                ("ingest_runs", "ingest_run"),
                ("pipeline_runs", "pipeline_run"),
            ):
                running = connection.execute(
                    f"SELECT id, project_id, owner_pid FROM {table} "
                    "WHERE status='RUNNING'"
                ).fetchall()
                for row in running:
                    if _pid_is_alive(row["owner_pid"]):
                        continue
                    connection.execute(
                        f"""
                        UPDATE {table}
                           SET status='INTERRUPTED', completed_at=?,
                               error='Owning process stopped before completion'
                         WHERE id=? AND status='RUNNING'
                        """,
                        (utc_now(), row["id"]),
                    )
                    self.audit.append(
                        connection,
                        action=f"{object_type}.interrupted",
                        object_type=object_type,
                        object_id=row["id"],
                        project_id=row["project_id"],
                        run_id=row["id"],
                        details={"reason": "owner process is no longer running"},
                        actor="kernel-recovery",
                    )

    def create_project(
        self, name: str, source_root: str | Path, source_kind: str = "local"
    ) -> dict:
        name = name.strip()
        if not name or len(name) > 120:
            raise ValueError("Project name must contain 1–120 characters")
        try:
            source = Path(source_root).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError(f"Project folder is unavailable: {source_root}") from exc
        if not source.is_dir():
            raise ValueError("Project source must be an existing folder")
        if source_kind not in {"local", "synthetic"}:
            raise ValueError("Unsupported source kind")
        if source_kind != "synthetic" and _is_relative_to(source, self.config.runtime_root):
            raise ValueError("A project source cannot be inside DataBossX runtime storage")
        project_id = uuid4().hex
        with self._write_lock, self.db.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO projects(id, name, source_root, source_kind, status, created_at)
                VALUES (?, ?, ?, ?, 'DRAFT', ?)
                """,
                (project_id, name, str(source), source_kind, utc_now()),
            )
            self.audit.append(
                connection,
                action="project.created",
                object_type="project",
                object_id=project_id,
                project_id=project_id,
                details={"name": name, "source_kind": source_kind},
            )
        return self.get_project(project_id)

    def create_synthetic_project(self) -> dict:
        from grocery_report_pipeline import make_synthetic_corpus

        source = self.config.runtime_root / "synthetic" / uuid4().hex
        make_synthetic_corpus(source)
        return self.create_project(
            "Synthetic Golden Project", source, source_kind="synthetic"
        )

    def list_projects(self) -> list[dict]:
        with self.db.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT p.*,
                           (SELECT count(*) FROM ingest_runs i
                             WHERE i.project_id=p.id) AS ingest_count,
                           (SELECT count(*) FROM asset_versions a
                             WHERE a.project_id=p.id) AS asset_count
                      FROM projects p ORDER BY p.created_at DESC
                    """
                )
            ]

    def get_project(self, project_id: str) -> dict:
        with self.db.connect() as connection:
            project = _row(
                connection.execute(
                    "SELECT * FROM projects WHERE id = ?", (project_id,)
                ).fetchone()
            )
        if not project:
            raise KeyError("Project not found")
        return project

    def ingest_project(self, project_id: str) -> dict:
        project = self.get_project(project_id)
        source_root = Path(project["source_root"]).resolve(strict=True)
        run_id = uuid4().hex
        with self._write_lock:
            with self.db.transaction(immediate=True) as connection:
                connection.execute(
                    """
                    INSERT INTO ingest_runs(
                        id, project_id, status, started_at, owner_pid
                    ) VALUES (?, ?, 'RUNNING', ?, ?)
                    """,
                    (run_id, project_id, utc_now(), os.getpid()),
                )
                self.audit.append(
                    connection,
                    action="ingest.started",
                    object_type="ingest_run",
                    object_id=run_id,
                    project_id=project_id,
                    run_id=run_id,
                    details={"source_kind": project["source_kind"]},
                )
            try:
                entries, issues = self._ingest_files(
                    project_id, run_id, source_root
                )
                manifest = json.dumps(
                    sorted(entries, key=lambda item: item["rel_path"]),
                    sort_keys=True,
                    separators=(",", ":"),
                )
                manifest_hash = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
                unique_blobs = len({entry["sha256"] for entry in entries})
                with self.db.transaction(immediate=True) as connection:
                    connection.execute(
                        """
                        UPDATE ingest_runs
                           SET status='SUCCEEDED', completed_at=?, manifest_sha256=?,
                               asset_count=?, unique_blob_count=?, issue_count=?
                         WHERE id=?
                        """,
                        (
                            utc_now(), manifest_hash, len(entries),
                            unique_blobs, issues, run_id,
                        ),
                    )
                    connection.execute(
                        "UPDATE projects SET status='INVENTORY_REVIEW' WHERE id=?",
                        (project_id,),
                    )
                    self.audit.append(
                        connection,
                        action="ingest.completed",
                        object_type="ingest_run",
                        object_id=run_id,
                        project_id=project_id,
                        run_id=run_id,
                        details={
                            "manifest_sha256": manifest_hash,
                            "asset_count": len(entries),
                            "unique_blob_count": unique_blobs,
                            "issue_count": issues,
                        },
                    )
            except Exception as exc:
                with self.db.transaction(immediate=True) as connection:
                    connection.execute(
                        """
                        UPDATE ingest_runs
                           SET status='FAILED', completed_at=?, error=?,
                               issue_count=(
                                   SELECT count(*) FROM ingest_issues
                                    WHERE ingest_run_id=?
                               )
                         WHERE id=?
                        """,
                        (utc_now(), str(exc), run_id, run_id),
                    )
                    self.audit.append(
                        connection,
                        action="ingest.failed",
                        object_type="ingest_run",
                        object_id=run_id,
                        project_id=project_id,
                        run_id=run_id,
                        details={"error": str(exc)},
                    )
                raise
        return self.get_ingest(run_id)

    def _ingest_files(
        self, project_id: str, run_id: str, source_root: Path
    ) -> tuple[list[dict], int]:
        entries: list[dict] = []
        issues = 0

        def walk_error(error: OSError) -> None:
            failed_path = Path(error.filename) if error.filename else source_root
            try:
                relative = failed_path.relative_to(source_root).as_posix()
            except ValueError:
                relative = str(failed_path)
            self._record_ingest_issue(
                project_id,
                run_id,
                relative,
                "ERROR",
                "DIRECTORY_READ_FAILED",
                str(error),
            )
            raise RuntimeError(f"Unable to inventory source directory {relative}") from error

        for current, directories, filenames in os.walk(
            source_root, topdown=True, followlinks=False, onerror=walk_error
        ):
            current_path = Path(current)
            for name in directories:
                candidate = current_path / name
                if candidate.is_symlink():
                    issues += 1
                    self._record_ingest_issue(
                        project_id,
                        run_id,
                        candidate.relative_to(source_root).as_posix(),
                        "WARNING",
                        "SYMLINK_SKIPPED",
                        "Symbolic-link directories are never followed",
                    )
                elif name in SKIP_DIRECTORIES or _is_relative_to(
                    candidate.resolve(), self.config.runtime_root
                ):
                    issues += 1
                    self._record_ingest_issue(
                        project_id,
                        run_id,
                        candidate.relative_to(source_root).as_posix(),
                        "WARNING",
                        "POLICY_DIRECTORY_SKIPPED",
                        "Tooling or DataBossX runtime directory excluded by policy",
                    )
            directories[:] = sorted(
                name
                for name in directories
                if name not in SKIP_DIRECTORIES
                and not (current_path / name).is_symlink()
                and not _is_relative_to(
                    (current_path / name).resolve(), self.config.runtime_root
                )
            )
            for filename in sorted(filenames):
                source = current_path / filename
                if source.is_symlink() or not source.is_file():
                    issues += 1
                    self._record_ingest_issue(
                        project_id,
                        run_id,
                        source.relative_to(source_root).as_posix(),
                        "WARNING",
                        "NON_REGULAR_FILE_SKIPPED",
                        "Symbolic links and non-regular files are never ingested",
                    )
                    continue
                relative = source.relative_to(source_root)
                if ".." in relative.parts:
                    raise RuntimeError(f"Unsafe source path encountered: {relative}")
                try:
                    receipt = self.vault.put_file(source)
                except VaultError as exc:
                    issues += 1
                    self._record_ingest_issue(
                        project_id,
                        run_id,
                        relative.as_posix(),
                        "ERROR",
                        "VAULT_COPY_FAILED",
                        str(exc),
                    )
                    raise RuntimeError(
                        f"Evidence copy failed for {relative.as_posix()}: {exc}"
                    ) from exc
                asset_id = uuid4().hex
                extraction = extract_vault_object(receipt.destination, source.suffix)
                if extraction.status != "COMPLETE":
                    issues += 1
                stat = source.stat()
                extraction_id = uuid4().hex
                with self.db.transaction(immediate=True) as connection:
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO blobs(
                            sha256, size_bytes, vault_relpath, created_at
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            receipt.sha256, receipt.size_bytes,
                            receipt.relative_path, utc_now(),
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO asset_versions(
                            id, project_id, ingest_run_id, rel_path, extension,
                            size_bytes, source_mtime_ns, blob_sha256, custody_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            asset_id, project_id, run_id, relative.as_posix(),
                            source.suffix.lower(), receipt.size_bytes,
                            stat.st_mtime_ns, receipt.sha256, utc_now(),
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO text_extractions(
                            id, asset_version_id, status, extractor,
                            extractor_version, text_sha256, text_content,
                            char_count, note, created_at
                        ) VALUES (?, ?, ?, ?, '1', ?, ?, ?, ?, ?)
                        """,
                        (
                            extraction_id, asset_id, extraction.status,
                            extraction.extractor, extraction.text_sha256,
                            extraction.text, len(extraction.text),
                            extraction.note, utc_now(),
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO provenance_edges(
                            id, parent_type, parent_id, child_type, child_id,
                            recipe, recipe_version, created_at
                        ) VALUES (?, 'asset_version', ?, 'text_extraction', ?,
                                  'deterministic-text-extraction', '1', ?)
                        """,
                        (uuid4().hex, asset_id, extraction_id, utc_now()),
                    )
                    self.audit.append(
                        connection,
                        action="asset.ingested",
                        object_type="asset_version",
                        object_id=asset_id,
                        project_id=project_id,
                        run_id=run_id,
                        details={
                            "rel_path": relative.as_posix(),
                            "sha256": receipt.sha256,
                            "size_bytes": receipt.size_bytes,
                            "extraction_status": extraction.status,
                        },
                    )
                    if extraction.status != "COMPLETE":
                        connection.execute(
                            """
                            INSERT INTO ingest_issues(
                                id, ingest_run_id, rel_path, severity,
                                code, detail, created_at
                            ) VALUES (?, ?, ?, 'WARNING', ?, ?, ?)
                            """,
                            (
                                uuid4().hex, run_id, relative.as_posix(),
                                f"EXTRACTION_{extraction.status}",
                                extraction.note or "No searchable text extracted",
                                utc_now(),
                            ),
                        )
                entries.append(
                    {
                        "rel_path": relative.as_posix(),
                        "sha256": receipt.sha256,
                        "size_bytes": receipt.size_bytes,
                    }
                )
        return entries, issues

    def _record_ingest_issue(
        self,
        project_id: str,
        run_id: str,
        rel_path: str,
        severity: str,
        code: str,
        detail: str,
    ) -> None:
        with self.db.transaction(immediate=True) as connection:
            issue_id = uuid4().hex
            connection.execute(
                """
                INSERT INTO ingest_issues(
                    id, ingest_run_id, rel_path, severity, code, detail, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (issue_id, run_id, rel_path, severity, code, detail, utc_now()),
            )
            self.audit.append(
                connection,
                action="ingest.issue_recorded",
                object_type="ingest_issue",
                object_id=issue_id,
                project_id=project_id,
                run_id=run_id,
                details={
                    "rel_path": rel_path,
                    "severity": severity,
                    "code": code,
                    "detail": detail,
                },
            )

    def get_ingest(self, run_id: str) -> dict:
        with self.db.connect() as connection:
            result = _row(
                connection.execute(
                    "SELECT * FROM ingest_runs WHERE id=?", (run_id,)
                ).fetchone()
            )
        if not result:
            raise KeyError("Ingest run not found")
        return result

    def list_assets(self, project_id: str) -> list[dict]:
        self.get_project(project_id)
        with self.db.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT a.*, e.status AS extraction_status,
                           e.extractor, e.char_count, e.note
                      FROM asset_versions a
                      JOIN text_extractions e ON e.asset_version_id=a.id
                     WHERE a.project_id=?
                     ORDER BY a.custody_at DESC, a.rel_path
                    """,
                    (project_id,),
                )
            ]

    def search(self, project_id: str, query: str, limit: int = 50) -> list[dict]:
        self.get_project(project_id)
        terms = re.findall(r"[\w'-]+", query, re.UNICODE)
        if not terms:
            return []
        match = " AND ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT f.asset_version_id, f.rel_path, a.blob_sha256,
                       e.extractor, e.text_content
                  FROM asset_text_fts f
                  JOIN asset_versions a ON a.id=f.asset_version_id
                  JOIN text_extractions e ON e.asset_version_id=a.id
                 WHERE f.project_id=? AND asset_text_fts MATCH ?
                 ORDER BY bm25(asset_text_fts) LIMIT ?
                """,
                (project_id, match, min(max(limit, 1), 100)),
            ).fetchall()
        needle = terms[0].casefold()
        results = []
        for row in rows:
            text = row["text_content"]
            start = max(text.casefold().find(needle), 0)
            excerpt_start = max(0, start - 90)
            excerpt_end = min(len(text), start + len(terms[0]) + 170)
            results.append(
                {
                    "asset_version_id": row["asset_version_id"],
                    "rel_path": row["rel_path"],
                    "source_sha256": row["blob_sha256"],
                    "extractor": row["extractor"],
                    "char_start": start,
                    "char_end": start + len(terms[0]),
                    "excerpt": text[excerpt_start:excerpt_end],
                }
            )
        return results

    def run_grocery(self, project_id: str) -> dict:
        self.get_project(project_id)
        with self.db.connect() as connection:
            ingest = connection.execute(
                """
                SELECT * FROM ingest_runs
                 WHERE project_id=? AND status='SUCCEEDED'
                 ORDER BY completed_at DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        if not ingest:
            raise ValueError("Complete an ingest before running reports")
        run_id = uuid4().hex
        run_dir = self.config.projects_root / project_id / "runs" / run_id
        input_dir = run_dir / "input"
        output_dir = run_dir / "output"
        input_dir.mkdir(parents=True)
        with self.db.connect() as connection:
            assets = connection.execute(
                "SELECT * FROM asset_versions WHERE ingest_run_id=? ORDER BY rel_path",
                (ingest["id"],),
            ).fetchall()
        for asset in assets:
            destination = (input_dir / asset["rel_path"]).resolve()
            if not _is_relative_to(destination, input_dir.resolve()):
                raise ValueError("Unsafe stored relative path")
            self.vault.materialize(asset["blob_sha256"], destination)

        with self._write_lock, self.db.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO pipeline_runs(
                    id, project_id, ingest_run_id, pipeline, pipeline_version,
                    input_manifest_sha256, status, run_dir, started_at, owner_pid
                ) VALUES (?, ?, ?, 'grocery-report', '1', ?, 'RUNNING', ?, ?, ?)
                """,
                (
                    run_id, project_id, ingest["id"],
                    ingest["manifest_sha256"], str(run_dir), utc_now(), os.getpid(),
                ),
            )
            self.audit.append(
                connection,
                action="pipeline.started",
                object_type="pipeline_run",
                object_id=run_id,
                project_id=project_id,
                run_id=run_id,
                details={"pipeline": "grocery-report"},
            )

        command = [
            sys.executable,
            str(self.config.repo_root / "grocery_report_pipeline.py"),
            "--root", str(input_dir),
            "--output-dir", str(output_dir),
            "--report-name", "Grocery_Report",
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=self.config.repo_root,
                capture_output=True,
                text=True,
                timeout=1800,
                check=False,
            )
            (run_dir / "stdout.log").write_text(completed.stdout, encoding="utf-8")
            (run_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")
            if completed.returncode:
                raise RuntimeError(
                    f"Report pipeline exited {completed.returncode}: "
                    f"{completed.stderr[-500:]}"
                )
            with self._write_lock, self.db.transaction(immediate=True) as connection:
                self._register_pipeline_artifacts(connection, run_id, output_dir)
                connection.execute(
                    """
                    UPDATE pipeline_runs
                       SET status='SUCCEEDED', completed_at=?, exit_code=0
                     WHERE id=?
                    """,
                    (utc_now(), run_id),
                )
                self.audit.append(
                    connection,
                    action="pipeline.succeeded",
                    object_type="pipeline_run",
                    object_id=run_id,
                    project_id=project_id,
                    run_id=run_id,
                    details={"exit_code": 0},
                )
        except Exception as exc:
            with self._write_lock, self.db.transaction(immediate=True) as connection:
                connection.execute(
                    """
                    UPDATE pipeline_runs
                       SET status='FAILED', completed_at=?, error=?
                     WHERE id=? AND status='RUNNING'
                    """,
                    (utc_now(), str(exc)[-2000:], run_id),
                )
                self.audit.append(
                    connection,
                    action="pipeline.failed",
                    object_type="pipeline_run",
                    object_id=run_id,
                    project_id=project_id,
                    run_id=run_id,
                    details={"error": str(exc)[-2000:]},
                )
            raise
        return self.get_run(run_id)

    def _register_pipeline_artifacts(
        self, connection: sqlite3.Connection, run_id: str, output_dir: Path
    ) -> None:
        for artifact_path in sorted(output_dir.rglob("*")):
            if not artifact_path.is_file():
                continue
            receipt = self.vault.put_file(artifact_path)
            artifact_id = uuid4().hex
            rel_path = artifact_path.relative_to(output_dir).as_posix()
            connection.execute(
                """
                INSERT OR IGNORE INTO blobs(
                    sha256, size_bytes, vault_relpath, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    receipt.sha256, receipt.size_bytes,
                    receipt.relative_path, utc_now(),
                ),
            )
            connection.execute(
                """
                INSERT INTO artifacts(
                    id, pipeline_run_id, rel_path, blob_sha256,
                    size_bytes, media_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id, run_id, rel_path, receipt.sha256,
                    receipt.size_bytes,
                    mimetypes.guess_type(rel_path)[0] or "application/octet-stream",
                    utc_now(),
                ),
            )
            connection.execute(
                """
                INSERT INTO provenance_edges(
                    id, parent_type, parent_id, child_type, child_id,
                    recipe, recipe_version, created_at
                ) VALUES (?, 'pipeline_run', ?, 'artifact', ?,
                          'grocery-report', '1', ?)
                """,
                (uuid4().hex, run_id, artifact_id, utc_now()),
            )

    def get_run(self, run_id: str) -> dict:
        with self.db.connect() as connection:
            run = _row(
                connection.execute(
                    "SELECT * FROM pipeline_runs WHERE id=?", (run_id,)
                ).fetchone()
            )
        if not run:
            raise KeyError("Pipeline run not found")
        return run

    def list_runs(self, project_id: str) -> list[dict]:
        self.get_project(project_id)
        with self.db.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM pipeline_runs WHERE project_id=? ORDER BY started_at DESC",
                    (project_id,),
                )
            ]

    def list_artifacts(self, run_id: str) -> list[dict]:
        self.get_run(run_id)
        with self.db.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM artifacts WHERE pipeline_run_id=? ORDER BY rel_path",
                    (run_id,),
                )
            ]

    def artifact(self, artifact_id: str) -> tuple[dict, Path]:
        with self.db.connect() as connection:
            artifact = _row(
                connection.execute(
                    "SELECT * FROM artifacts WHERE id=?", (artifact_id,)
                ).fetchone()
            )
        if not artifact:
            raise KeyError("Artifact not found")
        return artifact, self.vault.object_path(artifact["blob_sha256"])

    def audit_events(self, project_id: str) -> list[dict]:
        self.get_project(project_id)
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events WHERE project_id=? ORDER BY sequence DESC",
                (project_id,),
            ).fetchall()
            valid, tip = self.audit.verify(connection)
        events = [dict(row) for row in rows]
        for event in events:
            event["details"] = json.loads(event.pop("details_json"))
            event["chain_valid"] = valid
            event["chain_tip"] = tip
        return events

    def health(self) -> dict:
        with self.db.connect() as connection:
            audit_valid, audit_tip = self.audit.verify(connection)
            project_count = connection.execute("SELECT count(*) FROM projects").fetchone()[0]
        return {
            "status": "ok" if audit_valid else "degraded",
            "audit_chain_valid": audit_valid,
            "audit_chain_tip": audit_tip,
            "project_count": project_count,
            "local_only": True,
            "external_writes": False,
        }
