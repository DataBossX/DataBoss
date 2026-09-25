from __future__ import annotations

from datetime import datetime

from .database import DataBossDatabase

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - optional dependency
    BaseModel = None  # type: ignore[assignment,misc]


def _load_control_truth_builders():
    """Import the Landman Helper control-truth building blocks.

    ``horizon`` lives at the repository root, not under ``src/``, so make
    sure that root is importable regardless of how this package was
    installed or invoked.
    """
    try:
        from horizon.control_truth import build_control_truth
        from horizon.package_gate import GateReport
        from horizon.source_identity_guard import source_identity_guard
        from horizon.writer_gate import WriterGateState
    except ImportError:
        import sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from horizon.control_truth import build_control_truth
        from horizon.package_gate import GateReport
        from horizon.source_identity_guard import source_identity_guard
        from horizon.writer_gate import WriterGateState
    return build_control_truth, GateReport, source_identity_guard, WriterGateState


# These request models must live at module scope (not nested inside
# create_app): FastAPI resolves a route's annotations against the handler
# function's __globals__ only, which for a nested function is still this
# module's globals -- a class assigned to a local variable inside a factory
# function would never be found, and every request would 422 as an
# unresolvable forward reference.
if BaseModel is not None:

    class SourceIdentityRow(BaseModel):
        source_identity: str = ""
        disposition: str = ""

    class CoverageRow(BaseModel):
        source_identity: str = ""
        disposition: str = ""
        ocr_reviewed: bool = False
        pixel_reviewed: bool = False

    class WriterGateInput(BaseModel):
        writer_seat: str
        writer_instance: str
        exact_preimage_sha256: str
        observed_preimage_sha256: str
        exact_target_id: str
        observed_target_id: str
        lease_holder: str | None = None
        lease_expires_at: datetime | None = None
        heartbeat_at: datetime | None = None
        collision_count: int = 0
        max_heartbeat_age_seconds: float = 90.0
        now: datetime | None = None

    class CandidateIntegrityInput(BaseModel):
        outer_sha256: str
        member_sha256: dict[str, str] = {}
        failures: list[str] = []
        clean_cycle_streak: int = 0
        required_clean_cycles: int = 5

    class ControlTruthRequest(BaseModel):
        section: str
        source_identity_previous: list[SourceIdentityRow] = []
        source_identity_current: list[SourceIdentityRow] = []
        source_identity_expected_count: int | None = None
        coverage_records: list[CoverageRow] = []
        writer_gate: WriterGateInput
        integrity: CandidateIntegrityInput


def create_app(db_path: str):
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("FastAPI is required to create the DataBossX API app") from exc
    if BaseModel is None:  # pragma: no cover - optional dependency
        raise RuntimeError("Pydantic is required to create the DataBossX API app")

    build_control_truth, GateReport, source_identity_guard, WriterGateState = (
        _load_control_truth_builders()
    )

    db = DataBossDatabase(db_path)
    app = FastAPI(title="DataBossX Control API", version="0.1.0")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/control-truth")
    def control_truth(payload: ControlTruthRequest):
        """Compact section health projection. Public-safe only: this never
        returns source identities, filenames, legal descriptions, or Drive
        IDs -- see docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md."""
        si_report = source_identity_guard(
            (row.model_dump() for row in payload.source_identity_previous),
            (row.model_dump() for row in payload.source_identity_current),
            expected_count=payload.source_identity_expected_count,
        )
        writer_gate_kwargs = payload.writer_gate.model_dump(exclude_none=True)
        writer_gate = WriterGateState(**writer_gate_kwargs)
        gate_report = GateReport(
            outer_sha256=payload.integrity.outer_sha256,
            members=dict(payload.integrity.member_sha256),
            failures=list(payload.integrity.failures),
        )
        projection = build_control_truth(
            payload.section,
            source_identity=si_report,
            writer_gate=writer_gate,
            source_records=(row.model_dump() for row in payload.coverage_records),
            gate_report=gate_report,
            clean_cycle_streak=payload.integrity.clean_cycle_streak,
            required_clean_cycles=payload.integrity.required_clean_cycles,
        )
        return projection.public_dict()

    @app.get("/projects/{project_id}")
    def get_project(project_id: str):
        row = db.fetchone(
            "SELECT id, name, jurisdiction_code, policy_version, status, root_path FROM projects WHERE id = ?",
            (project_id,),
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return dict(row)

    @app.get("/projects/{project_id}/assets")
    def get_assets(project_id: str):
        rows = db.fetchall(
            """
            SELECT a.id, a.logical_key, a.asset_class, av.sha256, av.byte_size, av.original_locator
              FROM assets a
              JOIN asset_versions av ON av.asset_id = a.id
             WHERE a.project_id = ?
             ORDER BY a.id, av.id
            """,
            (project_id,),
        )
        return [dict(row) for row in rows]

    return app
