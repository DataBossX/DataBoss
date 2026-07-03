"""ValidatorBase -- the standard contract every quality gate implements.

Section 3: an abstract class defining a standard ``execute_validation`` signature
returning structured validation result objects.  Concrete validators implement
``_run`` and stay pure (no DB writes, no network); the orchestrator is
responsible for persisting the returned results through the AuditLogger.  A
validator that raises is contained here and reported as a GateStatus.ERROR so
one broken gate never crashes the loop.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from ..models import GateResult, GateStatus

if TYPE_CHECKING:  # avoid a hard import cycle at runtime
    from ..ingestion.manifest_builder import WorkbookManifest


class ValidatorBase(abc.ABC):
    #: Human-readable gate name; set by each concrete validator.
    gate_name: str = "unnamed_gate"
    #: One validator may own several gate ids (e.g. acreage + formula integrity).
    gate_ids: tuple[int, ...] = ()

    @abc.abstractmethod
    def _run(self, manifest: "WorkbookManifest") -> list[GateResult]:
        """Return one GateResult per gate this validator owns."""
        raise NotImplementedError

    def execute_validation(self, manifest: "WorkbookManifest") -> list[GateResult]:
        """Public entry point used by the orchestrator.  Never raises."""
        try:
            results = self._run(manifest)
        except Exception as exc:  # noqa: BLE001 -- contained on purpose
            gate_id = self.gate_ids[0] if self.gate_ids else 0
            return [GateResult(
                gate_id=gate_id,
                gate_name=self.gate_name,
                status=GateStatus.ERROR,
                detail=f"Validator raised: {type(exc).__name__}: {exc}",
            )]
        if not results:
            gate_id = self.gate_ids[0] if self.gate_ids else 0
            return [GateResult(gate_id=gate_id, gate_name=self.gate_name,
                               status=GateStatus.SKIPPED,
                               detail="Validator produced no result.")]
        return results
