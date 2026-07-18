from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import sqlite3
from fractions import Fraction
from pathlib import Path
from uuid import uuid4

from ...audit import AuditWriter, utc_now
from ...config import KernelConfig
from ...db import Database
from ...vault import Vault
from .ledger import calculate_ownership, fraction_text
from .render import render_pdf, render_xlsx


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _positive_fraction(value: dict, field: str) -> Fraction:
    try:
        result = Fraction(int(value["numerator"]), int(value["denominator"]))
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"{field} must provide an exact numerator and denominator") from exc
    if result < 0:
        raise ValueError(f"{field} cannot be negative")
    return result


class TitleManager:
    def __init__(
        self,
        config: KernelConfig,
        database: Database,
        vault: Vault,
        audit: AuditWriter,
    ) -> None:
        self.config = config
        self.db = database
        self.vault = vault
        self.audit = audit

    def create_case(self, project_id: str, payload: dict) -> dict:
        name = str(payload.get("name", "")).strip()
        legal = str(payload.get("legal_description", "")).strip()
        if not name or not legal:
            raise ValueError("Title case name and legal description are required")
        gross = _positive_fraction(payload.get("gross_acres", {}), "gross_acres")
        opening = payload.get("opening_ownership")
        instruments = payload.get("instruments")
        if not isinstance(opening, list) or not opening:
            raise ValueError("At least one opening owner is required")
        if not isinstance(instruments, list):
            raise ValueError("Instruments must be a list")
        case_id = uuid4().hex

        with self.db.transaction(immediate=True) as connection:
            if not connection.execute(
                "SELECT 1 FROM projects WHERE id=?", (project_id,)
            ).fetchone():
                raise KeyError("Project not found")
            connection.execute(
                """
                INSERT INTO title_cases(
                    id, project_id, name, legal_description,
                    gross_acres_num, gross_acres_den, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id, project_id, name, legal,
                    gross.numerator, gross.denominator, utc_now(),
                ),
            )
            for item in opening:
                interest = _positive_fraction(item.get("interest", {}), "opening interest")
                owner = str(item.get("owner_name", "")).strip()
                if not owner:
                    raise ValueError("Every opening ownership row requires an owner")
                connection.execute(
                    """
                    INSERT INTO title_opening_ownership(
                        id, title_case_id, owner_name, interest_num, interest_den
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (uuid4().hex, case_id, owner, interest.numerator, interest.denominator),
                )
            for position, item in enumerate(instruments, start=1):
                self._insert_instrument(connection, case_id, project_id, item, position)
            self.audit.append(
                connection,
                action="title_case.created",
                object_type="title_case",
                object_id=case_id,
                project_id=project_id,
                details={
                    "name": name,
                    "instrument_count": len(instruments),
                    "source": "operator-reviewed-structured-records",
                },
            )
        return self.get_case(case_id)

    def _insert_instrument(
        self,
        connection: sqlite3.Connection,
        case_id: str,
        project_id: str,
        item: dict,
        default_sequence: int,
    ) -> None:
        interest = _positive_fraction(item.get("conveyed_interest", {}), "conveyed interest")
        basis = item.get("interest_basis")
        if basis not in {"ABSOLUTE_ESTATE", "OF_GRANTOR"}:
            raise ValueError("interest_basis must be ABSOLUTE_ESTATE or OF_GRANTOR")
        review_status = item.get("review_status", "NEEDS_REVIEW")
        if review_status not in {"REVIEWED", "NEEDS_REVIEW"}:
            raise ValueError("Invalid instrument review status")
        evidence_id = item.get("evidence_asset_version_id")
        char_start = item.get("evidence_char_start")
        char_end = item.get("evidence_char_end")
        if evidence_id:
            evidence = connection.execute(
                """
                SELECT e.char_count
                  FROM asset_versions a
                  JOIN text_extractions e ON e.asset_version_id=a.id
                 WHERE a.id=? AND a.project_id=?
                """,
                (evidence_id, project_id),
            ).fetchone()
            if not evidence:
                raise ValueError("Evidence asset does not belong to this project")
            if (
                not isinstance(char_start, int)
                or not isinstance(char_end, int)
                or char_start < 0
                or char_end <= char_start
                or char_end > evidence["char_count"]
            ):
                raise ValueError("Evidence character range is outside extracted source text")
        elif review_status == "REVIEWED":
            raise ValueError("A reviewed instrument must cite an ingested evidence span")
        required = {
            "instrument_type": item.get("instrument_type"),
            "recording_reference": item.get("recording_reference"),
            "grantor_name": item.get("grantor_name"),
            "grantee_name": item.get("grantee_name"),
        }
        if any(not str(value or "").strip() for value in required.values()):
            raise ValueError(
                "Instrument type, recording reference, grantor and grantee are required"
            )
        connection.execute(
            """
            INSERT INTO title_instruments(
                id, title_case_id, sequence_no, instrument_type,
                recording_reference, effective_date, grantor_name, grantee_name,
                conveyed_num, conveyed_den, interest_basis,
                evidence_asset_version_id, evidence_char_start, evidence_char_end,
                review_status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid4().hex, case_id, int(item.get("sequence_no", default_sequence)),
                str(required["instrument_type"]).strip(),
                str(required["recording_reference"]).strip(),
                item.get("effective_date"),
                str(required["grantor_name"]).strip(),
                str(required["grantee_name"]).strip(),
                interest.numerator, interest.denominator, basis, evidence_id,
                char_start, char_end, review_status, str(item.get("notes", "")),
            ),
        )

    def get_case(self, case_id: str) -> dict:
        with self.db.connect() as connection:
            case = connection.execute(
                "SELECT * FROM title_cases WHERE id=?", (case_id,)
            ).fetchone()
            if not case:
                raise KeyError("Title case not found")
            opening = connection.execute(
                """
                SELECT owner_name, interest_num, interest_den
                  FROM title_opening_ownership WHERE title_case_id=?
                 ORDER BY owner_name
                """,
                (case_id,),
            ).fetchall()
            instruments = connection.execute(
                "SELECT * FROM title_instruments WHERE title_case_id=? ORDER BY sequence_no",
                (case_id,),
            ).fetchall()
        result = dict(case)
        result["opening_ownership"] = [dict(row) for row in opening]
        result["instruments"] = [dict(row) for row in instruments]
        return result

    def list_cases(self, project_id: str) -> list[dict]:
        with self.db.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM title_cases WHERE project_id=? ORDER BY created_at DESC",
                    (project_id,),
                )
            ]

    def build_package(self, case_id: str) -> dict:
        title_case = self.get_case(case_id)
        project_id = title_case["project_id"]
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
            raise ValueError("A completed evidence ingest is required")
        ledger = calculate_ownership(
            title_case["opening_ownership"], title_case["instruments"]
        )
        run_id = uuid4().hex
        output_dir = self.config.projects_root / project_id / "runs" / run_id / "output"
        output_dir.mkdir(parents=True)
        input_hash = hashlib.sha256(_canonical(title_case)).hexdigest()
        with self.db.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO pipeline_runs(
                    id, project_id, ingest_run_id, pipeline, pipeline_version,
                    input_manifest_sha256, status, run_dir, started_at, owner_pid
                ) VALUES (?, ?, ?, 'title-examiner-packet', '1', ?, 'RUNNING', ?, ?, ?)
                """,
                (
                    run_id, project_id, ingest["id"], input_hash,
                    str(output_dir.parent), utc_now(), os.getpid(),
                ),
            )
            self.audit.append(
                connection,
                action="title_package.started",
                object_type="pipeline_run",
                object_id=run_id,
                project_id=project_id,
                run_id=run_id,
                details={"title_case_id": case_id, "input_sha256": input_hash},
            )
        try:
            xlsx = output_dir / "Title_Examiner_Packet.xlsx"
            pdf = output_dir / "Draft_Abstract_Aid.pdf"
            summary = output_dir / "title_case_summary.json"
            render_xlsx(
                xlsx,
                title_case,
                title_case["opening_ownership"],
                title_case["instruments"],
                ledger,
            )
            render_pdf(pdf, title_case, ledger)
            summary_payload = {
                "notice": "DRAFT — NOT A CERTIFIED ABSTRACT OR TITLE OPINION",
                "title_case_id": case_id,
                "input_sha256": input_hash,
                "ownership": {
                    owner: {
                        "fraction": fraction_text(interest),
                        "numerator": interest.numerator,
                        "denominator": interest.denominator,
                    }
                    for owner, interest in sorted(ledger.ownership.items())
                },
                "defects": [defect.__dict__ for defect in ledger.defects],
            }
            summary.write_bytes(_canonical(summary_payload))
            artifact_manifest = [
                {
                    "rel_path": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "size_bytes": path.stat().st_size,
                }
                for path in (xlsx, pdf, summary)
            ]
            manifest_payload = {
                "schema": "databossx.title-package.v1",
                "title_case_id": case_id,
                "input_sha256": input_hash,
                "artifacts": artifact_manifest,
                "blocking_defect_count": len(ledger.blocking_defects),
                "human_approval_required": True,
            }
            manifest_hash = hashlib.sha256(_canonical(manifest_payload)).hexdigest()
            manifest_payload["package_manifest_sha256"] = manifest_hash
            (output_dir / "package_manifest.json").write_bytes(_canonical(manifest_payload))
            with self.db.transaction(immediate=True) as connection:
                for defect in ledger.defects:
                    connection.execute(
                        """
                        INSERT INTO title_defects(
                            id, pipeline_run_id, code, severity, sequence_no,
                            recording_reference, detail, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            uuid4().hex, run_id, defect.code, defect.severity,
                            defect.sequence_no, defect.recording_reference,
                            defect.detail, utc_now(),
                        ),
                    )
                self._register_artifacts(connection, run_id, output_dir)
                connection.execute(
                    """
                    INSERT INTO title_package_details(
                        pipeline_run_id, title_case_id, package_manifest_sha256,
                        blocking_defect_count, review_status
                    ) VALUES (?, ?, ?, ?, 'AWAITING_REVIEW')
                    """,
                    (run_id, case_id, manifest_hash, len(ledger.blocking_defects)),
                )
                connection.execute(
                    """
                    UPDATE pipeline_runs
                       SET status='WAITING_HUMAN', completed_at=?, exit_code=0
                     WHERE id=?
                    """,
                    (utc_now(), run_id),
                )
                connection.execute(
                    "UPDATE title_cases SET status='EXAMINER_REVIEW' WHERE id=?",
                    (case_id,),
                )
                self.audit.append(
                    connection,
                    action="title_package.awaiting_review",
                    object_type="pipeline_run",
                    object_id=run_id,
                    project_id=project_id,
                    run_id=run_id,
                    details={
                        "manifest_sha256": manifest_hash,
                        "blocking_defect_count": len(ledger.blocking_defects),
                    },
                )
        except Exception as exc:
            with self.db.transaction(immediate=True) as connection:
                connection.execute(
                    """
                    UPDATE pipeline_runs SET status='FAILED', completed_at=?, error=?
                     WHERE id=?
                    """,
                    (utc_now(), str(exc)[-2000:], run_id),
                )
                self.audit.append(
                    connection,
                    action="title_package.failed",
                    object_type="pipeline_run",
                    object_id=run_id,
                    project_id=project_id,
                    run_id=run_id,
                    details={"error": str(exc)[-2000:]},
                )
            raise
        return self.package_details(run_id)

    def _register_artifacts(
        self, connection: sqlite3.Connection, run_id: str, output_dir: Path
    ) -> None:
        for path in sorted(output_dir.iterdir()):
            if not path.is_file():
                continue
            receipt = self.vault.put_file(path)
            artifact_id = uuid4().hex
            connection.execute(
                """
                INSERT OR IGNORE INTO blobs(
                    sha256, size_bytes, vault_relpath, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (receipt.sha256, receipt.size_bytes, receipt.relative_path, utc_now()),
            )
            connection.execute(
                """
                INSERT INTO artifacts(
                    id, pipeline_run_id, rel_path, blob_sha256,
                    size_bytes, media_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id, run_id, path.name, receipt.sha256, receipt.size_bytes,
                    mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    utc_now(),
                ),
            )
            connection.execute(
                """
                INSERT INTO provenance_edges(
                    id, parent_type, parent_id, child_type, child_id,
                    recipe, recipe_version, created_at
                ) VALUES (?, 'pipeline_run', ?, 'artifact', ?,
                          'title-examiner-packet', '1', ?)
                """,
                (uuid4().hex, run_id, artifact_id, utc_now()),
            )

    def package_details(self, run_id: str) -> dict:
        with self.db.connect() as connection:
            package = connection.execute(
                """
                SELECT d.*, r.project_id, r.status AS run_status
                  FROM title_package_details d
                  JOIN pipeline_runs r ON r.id=d.pipeline_run_id
                 WHERE d.pipeline_run_id=?
                """,
                (run_id,),
            ).fetchone()
            if not package:
                raise KeyError("Title package not found")
            defects = connection.execute(
                "SELECT * FROM title_defects WHERE pipeline_run_id=? ORDER BY severity, code",
                (run_id,),
            ).fetchall()
            artifacts = connection.execute(
                "SELECT * FROM artifacts WHERE pipeline_run_id=? ORDER BY rel_path",
                (run_id,),
            ).fetchall()
        result = dict(package)
        result["defects"] = [dict(row) for row in defects]
        result["artifacts"] = [dict(row) for row in artifacts]
        return result

    def review_package(
        self,
        run_id: str,
        manifest_sha256: str,
        reviewer: str,
        decision: str,
        notes: str = "",
    ) -> dict:
        reviewer = reviewer.strip()
        decision = decision.upper()
        if not reviewer:
            raise ValueError("Reviewer name is required")
        if decision not in {"APPROVE", "REJECT"}:
            raise ValueError("Decision must be APPROVE or REJECT")
        with self.db.transaction(immediate=True) as connection:
            package = connection.execute(
                """
                SELECT d.*, r.project_id
                  FROM title_package_details d
                  JOIN pipeline_runs r ON r.id=d.pipeline_run_id
                 WHERE d.pipeline_run_id=?
                """,
                (run_id,),
            ).fetchone()
            if not package:
                raise KeyError("Title package not found")
            if package["review_status"] != "AWAITING_REVIEW":
                raise ValueError("This package already has a review decision")
            if manifest_sha256 != package["package_manifest_sha256"]:
                raise ValueError("Approval hash does not match the current package")
            if decision == "APPROVE" and package["blocking_defect_count"]:
                raise ValueError("Blocking defects must be resolved before approval")
            if decision == "APPROVE":
                self._verify_package_artifacts(
                    connection, run_id, package["package_manifest_sha256"]
                )
            connection.execute(
                """
                INSERT INTO title_review_decisions(
                    id, pipeline_run_id, package_manifest_sha256,
                    reviewer, decision, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex, run_id, manifest_sha256, reviewer,
                    decision, notes, utc_now(),
                ),
            )
            review_status = "APPROVED" if decision == "APPROVE" else "REJECTED"
            run_status = "SUCCEEDED" if decision == "APPROVE" else "FAILED_TERMINAL"
            connection.execute(
                """
                UPDATE title_package_details
                   SET review_status=?, approved_manifest_sha256=?,
                       reviewed_by=?, reviewed_at=?
                 WHERE pipeline_run_id=?
                """,
                (
                    review_status,
                    manifest_sha256 if decision == "APPROVE" else None,
                    reviewer,
                    utc_now(),
                    run_id,
                ),
            )
            connection.execute(
                "UPDATE pipeline_runs SET status=? WHERE id=?",
                (run_status, run_id),
            )
            connection.execute(
                "UPDATE title_cases SET status=? WHERE id=?",
                (
                    "APPROVED_FOR_EXPORT" if decision == "APPROVE" else "EXAMINER_REVIEW",
                    package["title_case_id"],
                ),
            )
            self.audit.append(
                connection,
                action=f"title_package.{review_status.lower()}",
                object_type="pipeline_run",
                object_id=run_id,
                project_id=package["project_id"],
                run_id=run_id,
                details={
                    "manifest_sha256": manifest_sha256,
                    "reviewer": reviewer,
                    "decision": decision,
                    "notes": notes,
                },
            )
        return self.package_details(run_id)

    def _verify_package_artifacts(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        expected_manifest_hash: str,
    ) -> None:
        artifacts = connection.execute(
            "SELECT rel_path, blob_sha256 FROM artifacts WHERE pipeline_run_id=?",
            (run_id,),
        ).fetchall()
        by_name = {row["rel_path"]: row["blob_sha256"] for row in artifacts}
        manifest_blob = by_name.get("package_manifest.json")
        if not manifest_blob:
            raise ValueError("Package manifest artifact is missing")
        for checksum in by_name.values():
            self.vault.object_path(checksum)
        manifest = json.loads(self.vault.object_path(manifest_blob).read_text("utf-8"))
        embedded_hash = manifest.pop("package_manifest_sha256", None)
        actual_hash = hashlib.sha256(_canonical(manifest)).hexdigest()
        if embedded_hash != expected_manifest_hash or actual_hash != expected_manifest_hash:
            raise ValueError("Package manifest failed hash verification")
        listed = {
            item["rel_path"]: item["sha256"] for item in manifest.get("artifacts", [])
        }
        registered = {
            name: checksum for name, checksum in by_name.items()
            if name != "package_manifest.json"
        }
        if listed != registered:
            raise ValueError("Registered package artifacts do not match the manifest")
