from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
from fractions import Fraction
from pathlib import Path
from uuid import uuid4

from ...audit import AuditWriter, utc_now
from ...config import KernelConfig
from ...db import Database
from ...vault import Vault, sha256_file
from .economics import calculate_economics
from .ledger import calculate_ownership, fraction_text, recording_reference_key
from .render import render_pdf, render_xlsx

XLSX_FILENAME = "Title_Examiner_Packet.xlsx"
PDF_FILENAME = "Draft_Abstract_Aid.pdf"
SUMMARY_FILENAME = "title_case_summary.json"
MANIFEST_FILENAME = "package_manifest.json"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _positive_fraction(value: dict, field: str) -> Fraction:
    try:
        numerator = value["numerator"]
        denominator = value["denominator"]
        if type(numerator) is not int or type(denominator) is not int:
            raise TypeError
        result = Fraction(numerator, denominator)
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"{field} must provide an exact numerator and denominator") from exc
    if result < 0:
        raise ValueError(f"{field} cannot be negative")
    return result


def _evidence_records(title_case: dict) -> list[dict]:
    records = list(title_case["instruments"])
    for unit in title_case["economic_units"]:
        records.append(unit)
        records.extend(unit["events"])
    return records


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
        economic_units = payload.get("economic_units", [])
        if not isinstance(opening, list) or not opening:
            raise ValueError("At least one opening owner is required")
        if not isinstance(instruments, list):
            raise ValueError("Instruments must be a list")
        if not isinstance(economic_units, list):
            raise ValueError("economic_units must be a list")
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
            evidence_ingests = {
                ingest_id
                for position, item in enumerate(instruments, start=1)
                if (
                    ingest_id := self._insert_instrument(
                        connection, case_id, project_id, item, position
                    )
                )
            }
            for unit in economic_units:
                evidence_ingests.update(
                    self._insert_economic_unit(
                        connection, case_id, project_id, unit
                    )
                )
            if len(evidence_ingests) > 1:
                raise ValueError(
                    "All reviewed title instruments must cite one evidence snapshot"
                )
            self.audit.append(
                connection,
                action="title_case.created",
                object_type="title_case",
                object_id=case_id,
                project_id=project_id,
                details={
                    "name": name,
                    "instrument_count": len(instruments),
                    "economic_unit_count": len(economic_units),
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
    ) -> str | None:
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
        evidence_ingest_id = None
        source_sha256 = None
        extraction_sha256 = None
        span_sha256 = None
        span_text = None
        if evidence_id:
            evidence = connection.execute(
                """
                SELECT e.char_count, e.text_content, e.text_sha256,
                       a.blob_sha256, a.ingest_run_id
                  FROM asset_versions a
                  JOIN text_extractions e ON e.asset_version_id=a.id
                 WHERE a.id=? AND a.project_id=?
                """,
                (evidence_id, project_id),
            ).fetchone()
            if not evidence:
                raise ValueError("Evidence asset does not belong to this project")
            if (
                type(char_start) is not int
                or type(char_end) is not int
                or char_start < 0
                or char_end <= char_start
                or char_end > evidence["char_count"]
            ):
                raise ValueError("Evidence character range is outside extracted source text")
            evidence_ingest_id = evidence["ingest_run_id"]
            source_sha256 = evidence["blob_sha256"]
            extraction_sha256 = evidence["text_sha256"]
            span_text = evidence["text_content"][char_start:char_end]
            span_sha256 = hashlib.sha256(span_text.encode("utf-8")).hexdigest()
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
        sequence = item.get("sequence_no", default_sequence)
        if type(sequence) is not int or sequence < 1:
            raise ValueError("Instrument sequence_no must be a positive integer")
        recording = str(required["recording_reference"]).strip()
        connection.execute(
            """
            INSERT INTO title_instruments(
                id, title_case_id, sequence_no, instrument_type,
                recording_reference, effective_date, grantor_name, grantee_name,
                conveyed_num, conveyed_den, interest_basis,
                evidence_asset_version_id, evidence_char_start, evidence_char_end,
                review_status, notes, recording_reference_key,
                evidence_ingest_run_id, evidence_source_sha256,
                evidence_extraction_sha256, evidence_span_sha256, evidence_span_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid4().hex, case_id, sequence,
                str(required["instrument_type"]).strip(),
                recording,
                item.get("effective_date"),
                str(required["grantor_name"]).strip(),
                str(required["grantee_name"]).strip(),
                interest.numerator, interest.denominator, basis, evidence_id,
                char_start, char_end, review_status, str(item.get("notes", "")),
                recording_reference_key(recording), evidence_ingest_id,
                source_sha256, extraction_sha256, span_sha256, span_text,
            ),
        )
        return evidence_ingest_id

    def _bind_evidence(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        payload: dict,
        review_status: str,
    ) -> dict:
        evidence_id = payload.get("evidence_asset_version_id")
        start = payload.get("evidence_char_start")
        end = payload.get("evidence_char_end")
        empty = {
            "asset_id": None,
            "ingest_id": None,
            "char_start": None,
            "char_end": None,
            "source_sha256": None,
            "extraction_sha256": None,
            "span_sha256": None,
            "span_text": None,
        }
        if not evidence_id:
            if review_status == "REVIEWED":
                raise ValueError("Reviewed economic records require an evidence span")
            return empty
        evidence = connection.execute(
            """
            SELECT e.char_count, e.text_content, e.text_sha256,
                   a.blob_sha256, a.ingest_run_id
              FROM asset_versions a
              JOIN text_extractions e ON e.asset_version_id=a.id
             WHERE a.id=? AND a.project_id=?
            """,
            (evidence_id, project_id),
        ).fetchone()
        if not evidence:
            raise ValueError("Economic evidence asset does not belong to this project")
        if (
            type(start) is not int
            or type(end) is not int
            or start < 0
            or end <= start
            or end > evidence["char_count"]
        ):
            raise ValueError("Economic evidence range is outside extracted source text")
        span_text = evidence["text_content"][start:end]
        return {
            "asset_id": evidence_id,
            "ingest_id": evidence["ingest_run_id"],
            "char_start": start,
            "char_end": end,
            "source_sha256": evidence["blob_sha256"],
            "extraction_sha256": evidence["text_sha256"],
            "span_sha256": hashlib.sha256(span_text.encode("utf-8")).hexdigest(),
            "span_text": span_text,
        }

    def _insert_economic_unit(
        self,
        connection: sqlite3.Connection,
        case_id: str,
        project_id: str,
        item: dict,
    ) -> set[str]:
        label = str(item.get("unit_label", "")).strip()
        legal = str(item.get("legal_description", "")).strip()
        recording = str(item.get("lease_recording_reference", "")).strip()
        depth_scope = str(item.get("depth_scope", "")).strip()
        product_scope = str(item.get("product_scope", "")).strip()
        if not all((label, legal, recording, depth_scope, product_scope)):
            raise ValueError(
                "Economic unit label, legal description, lease reference, "
                "depth scope, and product scope are required"
            )
        gross = _positive_fraction(item.get("gross_acres", {}), "unit gross acres")
        mineral = _positive_fraction(
            item.get("leased_mineral_interest", {}),
            "leased mineral interest",
        )
        royalty = _positive_fraction(item.get("base_royalty", {}), "base royalty")
        wi_basis = item.get("wi_basis")
        if wi_basis not in {"WI_EQUALS_LEASEHOLD", "EXPLICIT_ALLOCATION"}:
            raise ValueError("Invalid reviewed working-interest basis")
        review_status = item.get("review_status", "NEEDS_REVIEW")
        if review_status not in {"REVIEWED", "NEEDS_REVIEW"}:
            raise ValueError("Invalid economic unit review status")
        evidence = self._bind_evidence(
            connection, project_id, item, review_status
        )
        unsupported = item.get("unsupported_terms", "")
        if isinstance(unsupported, list):
            unsupported = "; ".join(str(value) for value in unsupported)
        unit_id = uuid4().hex
        connection.execute(
            """
            INSERT INTO title_economic_units(
                id, title_case_id, unit_label, legal_description,
                lease_recording_reference, recording_reference_key,
                effective_as_of, depth_scope, product_scope,
                gross_acres_num, gross_acres_den,
                leased_mineral_num, leased_mineral_den,
                base_royalty_num, base_royalty_den, wi_basis,
                review_status, unsupported_terms,
                evidence_asset_version_id, evidence_ingest_run_id,
                evidence_char_start, evidence_char_end,
                evidence_source_sha256, evidence_extraction_sha256,
                evidence_span_sha256, evidence_span_text
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
            """,
            (
                unit_id, case_id, label, legal, recording,
                recording_reference_key(recording), item.get("effective_as_of"),
                depth_scope, product_scope, gross.numerator, gross.denominator,
                mineral.numerator, mineral.denominator,
                royalty.numerator, royalty.denominator, wi_basis,
                review_status, str(unsupported),
                evidence["asset_id"], evidence["ingest_id"],
                evidence["char_start"], evidence["char_end"],
                evidence["source_sha256"], evidence["extraction_sha256"],
                evidence["span_sha256"], evidence["span_text"],
            ),
        )
        ingest_ids = {evidence["ingest_id"]} if evidence["ingest_id"] else set()
        events = item.get("events", [])
        if not isinstance(events, list):
            raise ValueError("Economic unit events must be a list")
        for position, event in enumerate(events, start=1):
            event_ingest = self._insert_economic_event(
                connection, unit_id, project_id, event, position
            )
            if event_ingest:
                ingest_ids.add(event_ingest)
        return ingest_ids

    def _insert_economic_event(
        self,
        connection: sqlite3.Connection,
        unit_id: str,
        project_id: str,
        item: dict,
        default_sequence: int,
    ) -> str | None:
        event_kind = item.get("event_kind")
        if event_kind not in {
            "OPENING_LEASEHOLD",
            "ASSIGNMENT",
            "WORKING_INTEREST",
            "REVENUE_BURDEN",
        }:
            raise ValueError("Invalid economic event kind")
        basis = item.get("interest_basis")
        if basis not in {"ABSOLUTE_UNIT", "OF_ASSIGNOR", "LEASE_8_8"}:
            raise ValueError("Invalid economic event interest basis")
        sequence = item.get("sequence_no", default_sequence)
        if type(sequence) is not int or sequence < 1:
            raise ValueError("Economic event sequence must be a positive integer")
        recording = str(item.get("recording_reference", "")).strip()
        to_party = str(item.get("to_party", "")).strip()
        if not recording or not to_party:
            raise ValueError("Economic event recording reference and recipient are required")
        interest = _positive_fraction(item.get("interest", {}), "economic interest")
        review_status = item.get("review_status", "NEEDS_REVIEW")
        if review_status not in {"REVIEWED", "NEEDS_REVIEW"}:
            raise ValueError("Invalid economic event review status")
        evidence = self._bind_evidence(
            connection, project_id, item, review_status
        )
        connection.execute(
            """
            INSERT INTO title_economic_events(
                id, unit_id, sequence_no, event_kind, recording_reference,
                recording_reference_key, from_party, to_party,
                interest_num, interest_den, interest_basis, burden_kind,
                burden_treatment, review_status, notes, evidence_asset_version_id,
                evidence_ingest_run_id, evidence_char_start, evidence_char_end,
                evidence_source_sha256, evidence_extraction_sha256,
                evidence_span_sha256, evidence_span_text
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                uuid4().hex, unit_id, sequence, event_kind, recording,
                recording_reference_key(recording),
                str(item.get("from_party", "")).strip() or None, to_party,
                interest.numerator, interest.denominator, basis,
                str(item.get("burden_kind", "")).strip() or None,
                str(item.get("burden_treatment", "")).strip() or None,
                review_status, str(item.get("notes", "")),
                evidence["asset_id"], evidence["ingest_id"],
                evidence["char_start"], evidence["char_end"],
                evidence["source_sha256"], evidence["extraction_sha256"],
                evidence["span_sha256"], evidence["span_text"],
            ),
        )
        return evidence["ingest_id"]

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
            economic_units = connection.execute(
                """
                SELECT * FROM title_economic_units
                 WHERE title_case_id=? ORDER BY unit_label
                """,
                (case_id,),
            ).fetchall()
            units = []
            for unit in economic_units:
                unit_data = dict(unit)
                unit_data["events"] = [
                    dict(row)
                    for row in connection.execute(
                        """
                        SELECT * FROM title_economic_events
                         WHERE unit_id=? ORDER BY sequence_no
                        """,
                        (unit["id"],),
                    )
                ]
                units.append(unit_data)
        result = dict(case)
        result["opening_ownership"] = [dict(row) for row in opening]
        result["instruments"] = [dict(row) for row in instruments]
        result["economic_units"] = units
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
        self._verify_case_evidence(title_case)
        with self.db.connect() as connection:
            evidence_ingests = {
                record["evidence_ingest_run_id"]
                for record in _evidence_records(title_case)
                if record.get("evidence_ingest_run_id")
            }
            if len(evidence_ingests) > 1:
                raise ValueError("Title case cites more than one evidence snapshot")
            if evidence_ingests:
                ingest = connection.execute(
                    """
                    SELECT * FROM ingest_runs
                     WHERE id=? AND project_id=? AND status='SUCCEEDED'
                    """,
                    (next(iter(evidence_ingests)), project_id),
                ).fetchone()
            else:
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
        economics = [
            calculate_economics(unit, unit["events"])
            for unit in title_case["economic_units"]
        ]
        economic_defects = [
            defect for result in economics for defect in result.defects
        ]
        blocking_defect_count = len(ledger.blocking_defects) + sum(
            len(result.blocking_defects) for result in economics
        )
        run_id = uuid4().hex
        output_dir = self.config.projects_root / project_id / "runs" / run_id / "output"
        output_dir.mkdir(parents=True)
        input_payload = dict(title_case)
        if not economics:
            input_payload.pop("economic_units", None)
        input_hash = _canonical_sha256(input_payload)
        package_version = "2" if economics else "1"
        with self.db.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO pipeline_runs(
                    id, project_id, ingest_run_id, pipeline, pipeline_version,
                    input_manifest_sha256, status, run_dir, started_at, owner_pid
                ) VALUES (?, ?, ?, 'title-examiner-packet', ?, ?, 'RUNNING', ?, ?, ?)
                """,
                (
                    run_id, project_id, ingest["id"], package_version, input_hash,
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
            xlsx = output_dir / XLSX_FILENAME
            pdf = output_dir / PDF_FILENAME
            summary = output_dir / SUMMARY_FILENAME
            render_xlsx(
                xlsx,
                title_case,
                title_case["opening_ownership"],
                title_case["instruments"],
                ledger,
                economics,
            )
            render_pdf(pdf, title_case, ledger, economics)
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
                "defects": [
                    defect.__dict__
                    for defect in (*ledger.defects, *economic_defects)
                ],
                "evidence_citations": [
                    {
                        "sequence_no": item["sequence_no"],
                        "recording_reference": item["recording_reference"],
                        "asset_version_id": item["evidence_asset_version_id"],
                        "source_sha256": item.get("evidence_source_sha256"),
                        "extraction_sha256": item.get("evidence_extraction_sha256"),
                        "span_sha256": item.get("evidence_span_sha256"),
                        "char_start": item["evidence_char_start"],
                        "char_end": item["evidence_char_end"],
                    }
                    for item in title_case["instruments"]
                ],
            }
            if economics:
                summary_payload["economics"] = [
                    {
                        "unit_id": result.unit_id,
                        "unit_label": result.unit_label,
                        "leased_mineral_fraction": fraction_text(
                            result.leased_mineral_fraction
                        ),
                        "base_royalty": fraction_text(result.base_royalty),
                        "leasehold": {
                            party: fraction_text(value)
                            for party, value in sorted(result.leasehold.items())
                        },
                        "working_interest": {
                            party: fraction_text(value)
                            for party, value in sorted(
                                result.working_interest.items()
                            )
                        },
                        "nri": {
                            party: fraction_text(value)
                            for party, value in sorted(result.nri.items())
                        },
                        "royalty_share": fraction_text(result.royalty_share),
                    }
                    for result in economics
                ]
            summary.write_bytes(_canonical(summary_payload))
            artifact_manifest = [
                {
                    "rel_path": path.name,
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                }
                for path in (xlsx, pdf, summary)
            ]
            manifest_payload = {
                "schema": (
                    "databossx.title-package.v2"
                    if economics
                    else "databossx.title-package.v1"
                ),
                "title_case_id": case_id,
                "input_sha256": input_hash,
                "artifacts": artifact_manifest,
                "blocking_defect_count": blocking_defect_count,
                "human_approval_required": True,
            }
            manifest_hash = _canonical_sha256(manifest_payload)
            manifest_payload["package_manifest_sha256"] = manifest_hash
            (output_dir / MANIFEST_FILENAME).write_bytes(_canonical(manifest_payload))
            with self.db.transaction(immediate=True) as connection:
                for defect in (*ledger.defects, *economic_defects):
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
                    (run_id, case_id, manifest_hash, blocking_defect_count),
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
                        "blocking_defect_count": blocking_defect_count,
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

    def _verify_case_evidence(self, title_case: dict) -> None:
        with self.db.connect() as connection:
            for record in _evidence_records(title_case):
                asset_id = record["evidence_asset_version_id"]
                if not asset_id:
                    continue
                evidence = connection.execute(
                    """
                    SELECT a.blob_sha256, a.ingest_run_id,
                           e.text_sha256, e.text_content
                      FROM asset_versions a
                      JOIN text_extractions e ON e.asset_version_id=a.id
                     WHERE a.id=? AND a.project_id=?
                    """,
                    (asset_id, title_case["project_id"]),
                ).fetchone()
                if not evidence:
                    raise ValueError("Cited evidence asset is no longer available")
                self.vault.object_path(evidence["blob_sha256"])
                start = record["evidence_char_start"]
                end = record["evidence_char_end"]
                span_text = evidence["text_content"][start:end]
                span_sha256 = hashlib.sha256(span_text.encode("utf-8")).hexdigest()
                expected = (
                    evidence["ingest_run_id"],
                    evidence["blob_sha256"],
                    evidence["text_sha256"],
                    span_sha256,
                    span_text,
                )
                recorded = (
                    record["evidence_ingest_run_id"],
                    record["evidence_source_sha256"],
                    record["evidence_extraction_sha256"],
                    record["evidence_span_sha256"],
                    record["evidence_span_text"],
                )
                if recorded != expected:
                    raise ValueError(
                        "Cited evidence hashes or source span changed after review"
                    )

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

    def register_reviewer(self, display_name: str, role: str, pin: str) -> dict:
        display_name = display_name.strip()
        role = role.upper()
        if not display_name:
            raise ValueError("Reviewer display name is required")
        if role not in {"QUALIFIED_EXAMINER", "ATTORNEY"}:
            raise ValueError("Reviewer role must be QUALIFIED_EXAMINER or ATTORNEY")
        if len(pin) < 6:
            raise ValueError("Reviewer PIN must contain at least 6 characters")
        salt = secrets.token_bytes(16)
        pin_hash = hashlib.scrypt(
            pin.encode("utf-8"), salt=salt, n=2**14, r=8, p=1
        ).hex()
        reviewer_id = uuid4().hex
        with self.db.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO title_reviewers(
                    id, display_name, role, pin_salt, pin_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    reviewer_id,
                    display_name,
                    role,
                    salt.hex(),
                    pin_hash,
                    utc_now(),
                ),
            )
            self.audit.append(
                connection,
                action="title_reviewer.registered",
                object_type="title_reviewer",
                object_id=reviewer_id,
                details={"display_name": display_name, "role": role},
            )
        return {"id": reviewer_id, "display_name": display_name, "role": role}

    def list_reviewers(self) -> list[dict]:
        with self.db.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT id, display_name, role, created_at FROM title_reviewers "
                    "ORDER BY display_name"
                )
            ]

    def _authenticate_reviewer(
        self, connection: sqlite3.Connection, reviewer_id: str, pin: str
    ) -> sqlite3.Row:
        reviewer = connection.execute(
            "SELECT * FROM title_reviewers WHERE id=?", (reviewer_id,)
        ).fetchone()
        if not reviewer:
            raise ValueError("Reviewer credential not found")
        actual = hashlib.scrypt(
            pin.encode("utf-8"),
            salt=bytes.fromhex(reviewer["pin_salt"]),
            n=2**14,
            r=8,
            p=1,
        ).hex()
        if not hmac.compare_digest(actual, reviewer["pin_hash"]):
            raise ValueError("Reviewer credential is invalid")
        return reviewer

    def review_package(
        self,
        run_id: str,
        manifest_sha256: str,
        reviewer_id: str,
        reviewer_pin: str,
        decision: str,
        notes: str = "",
    ) -> dict:
        decision = decision.upper()
        if decision not in {"APPROVE", "REJECT"}:
            raise ValueError("Decision must be APPROVE or REJECT")
        with self.db.transaction(immediate=True) as connection:
            reviewer = self._authenticate_reviewer(
                connection, reviewer_id, reviewer_pin
            )
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
                    reviewer, decision, notes, created_at, reviewer_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex, run_id, manifest_sha256,
                    reviewer["display_name"], decision, notes, utc_now(),
                    reviewer_id,
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
                    reviewer["display_name"],
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
                    "reviewer_id": reviewer_id,
                    "reviewer": reviewer["display_name"],
                    "reviewer_role": reviewer["role"],
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
        manifest_blob = by_name.get(MANIFEST_FILENAME)
        if not manifest_blob:
            raise ValueError("Package manifest artifact is missing")
        for checksum in by_name.values():
            self.vault.object_path(checksum)
        manifest = json.loads(self.vault.object_path(manifest_blob).read_text("utf-8"))
        embedded_hash = manifest.pop("package_manifest_sha256", None)
        actual_hash = _canonical_sha256(manifest)
        if embedded_hash != expected_manifest_hash or actual_hash != expected_manifest_hash:
            raise ValueError("Package manifest failed hash verification")
        listed = {
            item["rel_path"]: item["sha256"] for item in manifest.get("artifacts", [])
        }
        registered = {
            name: checksum for name, checksum in by_name.items()
            if name != MANIFEST_FILENAME
        }
        if listed != registered:
            raise ValueError("Registered package artifacts do not match the manifest")
