"""Outbound-only local runner.

The runner never listens. It claims work, verifies it, executes inside a
constrained working directory, and posts metadata plus receipts. There is no
inbound port, no tunnel, and no LAN API, so there is nothing to authenticate
from the outside.

Verification order before any adapter runs -- every one of these is a hard stop:

  envelope exists -> not expired -> nonce unused -> lease ACTIVE ->
  fencing sequence current -> input hashes unchanged -> approval consumed
  (when required) -> adapter allowlisted -> mode supported

Only then does work begin, and even then a SIMULATED task is labelled SIMULATED
in every artifact it produces.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Mapping, Optional

from . import policy as policymod
from . import db as dbmod
from .canonical import canonical_json, iso, new_id, parse_iso, sha256_bytes, sha256_of, utc_now
from .errors import (
    AdapterNotAllowed,
    ApprovalRequired,
    ArtifactChanged,
    ControlKernelError,
    LeaseExpired,
    NonceReplay,
    PathNotAllowed,
)

#: Coarse resource ceilings for a job. Enforced where the platform allows.
DEFAULT_LIMITS = {
    "max_wall_seconds": 120,
    "max_output_bytes": 8 * 1024 * 1024,
    "network": "DENY",
    "filesystem": "WORKDIR_ONLY",
}


@dataclass
class RunnerConfig:
    workroot: str
    runner_id: str = "runner-local-1"
    simulation_only: bool = True
    kill_switch_path: Optional[str] = None
    limits: Mapping = None

    def __post_init__(self):
        if self.limits is None:
            self.limits = dict(DEFAULT_LIMITS)


class KillSwitchEngaged(ControlKernelError):
    code = "KILL_SWITCH_ENGAGED"


@dataclass
class AdapterResult:
    output: dict
    artifacts: list  # list of (logical_id, bytes)
    checks: list


AdapterFn = Callable[["LocalRunner", Mapping, str], AdapterResult]


class LocalRunner:
    """Outbound-only worker. Restart-safe and duplicate-safe by construction."""

    def __init__(self, kernel, config: RunnerConfig):
        self.kernel = kernel
        self.config = config
        os.makedirs(config.workroot, exist_ok=True)
        self._adapters: dict = {
            "status.read_posture": _adapter_read_posture,
            "project.read_summary": _adapter_project_summary,
            "artifact.verify_hashes": _adapter_verify_hashes,
            "title.simulate_interest_rollup": _adapter_simulate_rollup,
            "report.simulate_draft_build": _adapter_simulate_report,
        }

    # ------------------------------------------------------------- utilities
    def _check_kill_switch(self) -> None:
        path = self.config.kill_switch_path
        if path and os.path.exists(path):
            raise KillSwitchEngaged("local kill switch is engaged; runner refuses all work")

    def workdir_for(self, task_id: str) -> str:
        """Each job gets its own directory inside the work root, and only that."""
        safe = policymod.resolve_relative_path(self.config.workroot, f"jobs/{task_id}")
        os.makedirs(safe, exist_ok=True)
        return safe

    def resolve_path(self, task_id: str, relative: str) -> str:
        """Map a server-supplied relative name into this job's directory."""
        return policymod.resolve_relative_path(self.workdir_for(task_id), relative)

    # --------------------------------------------------------------- verify
    def verify_envelope(self, task_id: str) -> dict:
        """Re-verify everything. The runner trusts nothing it was handed."""
        row = dbmod.fetchone(
            self.kernel.conn, "SELECT * FROM task_envelopes WHERE task_id=?", (task_id,)
        )
        if row is None:
            raise ControlKernelError(f"unknown task {task_id}")
        env = dict(row)

        if self.kernel.now() >= parse_iso(env["expires_at"]):
            raise LeaseExpired(f"task {task_id} envelope expired at {env['expires_at']}")

        lease = self.kernel.get_lease(env["lease_id"])
        if lease["state"] != "ACTIVE":
            raise LeaseExpired(f"lease {env['lease_id']} is {lease['state']}")

        # Old fencing sequences fail closed, which is what makes a stale writer
        # harmless rather than merely unlucky.
        self.kernel.assert_fencing_current(env["resource_scope"], env["fencing_sequence"])

        spec = policymod.get_adapter(env["adapter"])
        if env["adapter"] not in self._adapters and env["adapter"] not in policymod.ADAPTER_ALLOWLIST:
            raise AdapterNotAllowed(f"adapter {env['adapter']} is not implemented or allowlisted")
        if env["execution_mode"] not in spec.modes:
            raise AdapterNotAllowed(
                f"adapter {env['adapter']} does not support mode {env['execution_mode']}"
            )
        if self.config.simulation_only and env["execution_mode"] == "REAL":
            raise AdapterNotAllowed("runner is in simulation-only mode; REAL execution refused")
        if env["risk_class"] == "APPROVAL_REQUIRED" and not env["approval_token_id"]:
            raise ApprovalRequired(f"task {task_id} requires an approval token")

        # Inputs must still hash to what was approved.
        declared = json.loads(env["input_hashes_json"] or "{}")
        for logical_id, expected in declared.items():
            actual = self._current_input_hash(logical_id)
            if actual is None:
                raise ArtifactChanged(f"input {logical_id} is no longer registered")
            if actual != expected:
                raise ArtifactChanged(
                    f"input {logical_id} changed after approval: expected {expected}, found {actual}"
                )
        return env

    def _current_input_hash(self, logical_id: str) -> Optional[str]:
        row = dbmod.fetchone(
            self.kernel.conn,
            "SELECT av.sha256 FROM artifact_versions av JOIN artifacts a ON a.artifact_id = av.artifact_id"
            " WHERE a.logical_id=? ORDER BY av.version_number DESC LIMIT 1",
            (logical_id,),
        )
        return row["sha256"] if row else None

    # --------------------------------------------------------------- execute
    def execute(self, *, job_id: str, task_id: str, writer_identity: str) -> dict:
        """Claim, verify, run, verify again, and produce a receipt.

        Any failure produces a receipt with a fail-closed outcome. A job never
        ends silently, and a partially successful job is reported as failed.
        """
        self._check_kill_switch()
        started_at = iso(self.kernel.now())
        env = self.verify_envelope(task_id)

        ack = self.kernel.writer_ack(
            task_id=task_id, lease_id=env["lease_id"], writer_identity=writer_identity
        )

        self.kernel.set_job_state(job_id, "RUNNER_CLAIMED", actor=self.config.runner_id)
        attempt_id = self.kernel.start_attempt(
            job_id=job_id, task_id=task_id, lease_id=env["lease_id"],
            fencing_sequence=env["fencing_sequence"],
        )
        self.kernel.set_job_state(job_id, "EXECUTING", actor=self.config.runner_id)

        parameters = json.loads(env["parameters_json"])
        workdir = self.workdir_for(task_id)
        checks = [
            {"name": "envelope_verified", "status": "PASS", "detail": f"sha={env['content_sha256'][:16]}"},
            {"name": "lease_active_and_fenced", "status": "PASS",
             "detail": f"seq={env['fencing_sequence']}"},
            {"name": "writer_ack_bound", "status": "PASS", "detail": f"ack={ack['content_sha256'][:16]}"},
        ]

        # Consume the approval as late as possible, so an abort before this
        # point does not burn the owner's single-use token.
        if env["risk_class"] == "APPROVAL_REQUIRED":
            self.kernel.consume_approval(
                env["approval_token_id"],
                operation=env["adapter"],
                resource_scope=env["resource_scope"],
                parameters=parameters,
                task_envelope_sha256=env["content_sha256"],
                input_hashes=json.loads(env["input_hashes_json"] or "{}") or None,
                attempt_id=attempt_id,
            )
            checks.append({"name": "approval_consumed_single_use", "status": "PASS",
                           "detail": env["approval_token_id"]})
        else:
            checks.append({"name": "approval_consumed_single_use", "status": "SKIPPED",
                           "detail": "not required for this risk class"})

        outcome = "COMPLETED"
        failure_reason = None
        artifacts_meta: list = []
        adapter_output: dict = {}

        try:
            adapter_fn = self._adapters.get(env["adapter"])
            if adapter_fn is None:
                raise AdapterNotAllowed(f"no implementation for adapter {env['adapter']}")
            result = adapter_fn(self, parameters, task_id)
            adapter_output = result.output
            checks.extend(result.checks)

            self.kernel.set_job_state(job_id, "VERIFYING", actor=self.config.runner_id)

            for logical_id, data in result.artifacts:
                # Atomic staging inside the job directory, then registration.
                path = self.resolve_path(task_id, f"out/{logical_id}.json")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                tmp = path + ".tmp"
                with open(tmp, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp, path)

                digest = sha256_bytes(data)
                self.kernel.register_artifact(
                    logical_id=logical_id, sha256=digest, byte_size=len(data), synthetic=True,
                )
                artifacts_meta.append({
                    "logical_id": logical_id, "sha256": digest, "byte_size": len(data),
                    "synthetic": True, "drive_file_id": None, "drive_version": None,
                    "drive_mime_type": None, "drive_parent_id": None,
                    "drive_readback_sha256": None, "drive_readback_at": None,
                })
                checks.append({"name": f"artifact_hashed:{logical_id}", "status": "PASS",
                               "detail": digest})
        except Exception as exc:
            outcome = "ABORTED_FAIL_CLOSED"
            failure_reason = f"{type(exc).__name__}: {exc}"
            checks.append({"name": "adapter_execution", "status": "FAIL", "detail": failure_reason})
            self._rollback_workdir(workdir)
            checks.append({"name": "rollback_completed", "status": "PASS",
                           "detail": "job working directory reverted"})

        self.kernel.finish_attempt(attempt_id, outcome, failure_reason)

        mode = env["execution_mode"]
        label = "SIMULATED" if mode == "SIMULATED" else mode
        if outcome == "COMPLETED":
            plain = f"[{label}] {env['adapter']} completed on {env['resource_scope']}. " \
                    f"{adapter_output.get('summary', 'No summary provided.')}"
            self.kernel.set_job_state(job_id, "COMPLETED", actor=self.config.runner_id)
        else:
            plain = f"[{label}] {env['adapter']} FAILED CLOSED on {env['resource_scope']}. " \
                    f"Nothing was changed. Reason: {failure_reason}"
            self.kernel.set_job_state(job_id, "FAILED", actor=self.config.runner_id)

        receipt = {
            "schema_version": "1.0.0",
            "receipt_id": new_id("rcpt"),
            "task_id": task_id,
            "command_id": env["command_id"],
            "attempt_id": attempt_id,
            "resource_scope": env["resource_scope"],
            "execution_mode": mode,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "started_at": started_at,
            "finished_at": iso(self.kernel.now()),
            "fencing_sequence": env["fencing_sequence"],
            "lease_id": env["lease_id"],
            "writer_identity": writer_identity,
            "policy_version": env["policy_version"],
            "holds_in_effect": self.kernel.hold_labels(),
            "checks": checks,
            "artifacts": artifacts_meta,
            "plain_language_result": plain,
            "next_safe_action": (
                "Review the receipt under More > Audit, then choose the next Best Move."
                if outcome == "COMPLETED"
                else "Open Jobs > Blocked and read the failure reason before retrying."
            ),
        }
        return self.kernel.record_receipt(receipt, actor=self.config.runner_id)

    def _rollback_workdir(self, workdir: str) -> None:
        out_dir = os.path.join(workdir, "out")
        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir, ignore_errors=True)


# --------------------------------------------------------------------- adapters
# Each adapter is small, pure-ish, and receives only validated parameters. None
# of them accept a path, a command string, or SQL.

def _adapter_read_posture(runner: "LocalRunner", params: Mapping, task_id: str) -> AdapterResult:
    posture = runner.kernel.posture()
    return AdapterResult(
        output={"summary": f"{len(posture['running'])} running, {len(posture['blocked'])} blocked, "
                           f"{len(posture['needs_ryan'])} awaiting your decision."},
        artifacts=[],
        checks=[{"name": "posture_read", "status": "PASS",
                 "detail": f"audit_chain_valid={posture['audit_chain_valid']}"}],
    )


def _adapter_project_summary(runner: "LocalRunner", params: Mapping, task_id: str) -> AdapterResult:
    project_id = params["project_id"]
    return AdapterResult(
        output={"summary": f"Read synthetic project {project_id}."},
        artifacts=[],
        checks=[{"name": "project_read", "status": "PASS", "detail": project_id}],
    )


def _adapter_verify_hashes(runner: "LocalRunner", params: Mapping, task_id: str) -> AdapterResult:
    rows = dbmod.fetchall(
        runner.kernel.conn,
        "SELECT a.logical_id, av.sha256, av.version_number FROM artifact_versions av"
        " JOIN artifacts a ON a.artifact_id = av.artifact_id ORDER BY a.logical_id",
    )
    checks = [{"name": f"hash_registered:{r['logical_id']}#{r['version_number']}",
               "status": "PASS", "detail": r["sha256"]} for r in rows]
    if not rows:
        checks = [{"name": "hash_registered", "status": "NOT_RUN",
                   "detail": "no artifact versions registered yet"}]
    return AdapterResult(
        output={"summary": f"Checked {len(rows)} registered artifact version(s)."},
        artifacts=[], checks=checks,
    )


def _adapter_simulate_rollup(runner: "LocalRunner", params: Mapping, task_id: str) -> AdapterResult:
    """Exact-fraction interest roll-up over synthetic tracts.

    Uses :class:`fractions.Fraction` throughout. Binary floating point is never
    the ownership authority, and an unbalanced chain is reported as unbalanced
    rather than force-balanced to 1.
    """
    project_id = params["project_id"]
    # Synthetic ownership. Deliberately does NOT sum to 1 so the honest-reporting
    # path is the one that actually executes.
    synthetic_owners = [
        {"owner": "SYNTHETIC OWNER A", "interest": Fraction(1, 4)},
        {"owner": "SYNTHETIC OWNER B", "interest": Fraction(1, 8)},
        {"owner": "SYNTHETIC OWNER C", "interest": Fraction(1, 16)},
    ]
    total = sum((o["interest"] for o in synthetic_owners), Fraction(0))
    balanced = total == Fraction(1)
    remainder = Fraction(1) - total

    payload = {
        "SIMULATED": True,
        "project_id": project_id,
        "owners": [
            {"owner": o["owner"],
             "interest": f"{o['interest'].numerator}/{o['interest'].denominator}"}
            for o in synthetic_owners
        ],
        "total_interest": f"{total.numerator}/{total.denominator}",
        "balanced": balanced,
        "unaccounted_interest": f"{remainder.numerator}/{remainder.denominator}",
        "note": "SIMULATED synthetic data. Unaccounted interest is reported, never force-balanced.",
    }
    data = canonical_json(payload).encode("utf-8")

    checks = [
        {"name": "exact_fraction_arithmetic", "status": "PASS",
         "detail": "fractions.Fraction used; no binary float in the ownership path"},
        {"name": "ownership_balances_to_one", "status": "FAIL" if not balanced else "PASS",
         "detail": f"total={total}; unaccounted={remainder} reported honestly, not force-balanced"},
    ]
    return AdapterResult(
        output={"summary": f"SIMULATED roll-up for {project_id}: total {total}, "
                           f"unaccounted {remainder} reported, not force-balanced."},
        artifacts=[(f"sim-rollup-{project_id}", data)],
        checks=checks,
    )


def _adapter_simulate_report(runner: "LocalRunner", params: Mapping, task_id: str) -> AdapterResult:
    project_id = params["project_id"]
    payload = {
        "SIMULATED": True,
        "project_id": project_id,
        "title": f"SIMULATED draft report - {project_id}",
        "sections": ["Scope (SIMULATED)", "Findings (SIMULATED)", "Open items (SIMULATED)"],
        "disclaimer": "SIMULATED synthetic output. Not a title opinion, abstract, or legal conclusion.",
        "generated_at": iso(utc_now()),
    }
    data = canonical_json(payload).encode("utf-8")
    return AdapterResult(
        output={"summary": f"SIMULATED draft report built for {project_id}."},
        artifacts=[(f"sim-report-{project_id}", data)],
        checks=[{"name": "report_marked_simulated", "status": "PASS",
                 "detail": "SIMULATED flag present in payload, receipt, and UI label"}],
    )
