"""The first working vertical slice, end to end, on synthetic data only.

Runs the exact story the directive requires: authenticate, see the hold, speak,
confirm transcript and intent, rank moves, create an envelope, claim a lease,
review with watchers, execute an allowlisted simulated task, verify, publish a
receipt through the Drive protocol, prove idempotency, and prove the Section 32
hold cannot be removed.

Everything here is synthetic. No client evidence, no real Drive write, no
production data.
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from . import best_moves as bm
from . import voice as voicemod
from . import watchers as watchmod
from .canonical import canonical_json, sha256_of
from .drive_bridge import DriveBridge, InMemoryDriveClient, plan_control_room
from .errors import HoldRemovalForbidden
from .kernel import Actor, ControlKernel
from .runner import LocalRunner, RunnerConfig

SYNTHETIC_PROJECT = "synthetic-alpha"


def run_slice(workdir: Optional[str] = None, *, verbose: bool = False) -> dict:
    """Execute the full slice and return a structured trace."""
    workdir = workdir or tempfile.mkdtemp(prefix="dbx-cc-slice-")
    os.makedirs(workdir, exist_ok=True)
    trace: dict = {"workdir": workdir, "steps": []}

    def step(name: str, **detail):
        trace["steps"].append({"step": name, **detail})
        if verbose:
            print(f"  [{len(trace['steps']):2d}] {name}: {detail}")

    kernel = ControlKernel.open(os.path.join(workdir, "command_center.db"))

    # 1-2. Authenticate and observe the global hold.
    kernel.upsert_user("ryan", "Ryan Gille", "OWNER")
    ryan = Actor("ryan", "OWNER", session_id="sess-demo", device_id="iphone-demo", stepped_up=True)
    posture = kernel.posture()
    step("authenticated_and_saw_hold", holds=[h["label"] for h in posture["holds"]],
         banner=posture["hold_banner"])

    # 3-5. Speak, then confirm transcript AND parsed intent before anything exists.
    intake = voicemod.intake("What should I do next?", provider="local-stub-v1", confidence=0.0)
    step("voice_intake_awaiting_confirmation",
         transcript=intake.transcript.text,
         transcript_sha256=intake.transcript.sha256,
         parsed_operation=intake.intent.operation,
         audio_retained=intake.transcript.audio_retained,
         requires_confirmation=intake.requires_confirmation)

    # 6. Confirmed request becomes an immutable CommandEnvelope.
    command = kernel.create_command(
        ryan, idempotency_key="demo-key-001",
        transcript_text=intake.transcript.text, intent=intake.intent.to_dict(),
        channel="VOICE", provider=intake.transcript.provider, confirmed=True,
    )
    step("command_envelope_created", command_id=command["command_id"],
         content_sha256=command["content_sha256"])

    # 7. Deterministic policy classification.
    classified = kernel.classify_command(command["command_id"], ryan)
    step("policy_classified", risk_class=classified["decision"].risk_class,
         allowed=classified["decision"].allowed)

    # 8. Best Moves ranking with explanations.
    ranked = bm.rank_for(kernel.posture(), role="OWNER")
    best = bm.best_next_move(ranked)
    vetoed = [r.to_dict() for r in ranked if not r.eligible]
    step("best_moves_ranked", best_move=best.candidate.move_id, score=round(best.score, 4),
         eligible=sum(1 for r in ranked if r.eligible),
         vetoed=[(v["move_id"], v["vetoes"]) for v in vetoed])

    # 9. Ryan picks a low-risk SIMULATED action.
    chosen = next(r for r in ranked if r.candidate.move_id == "mv_sim_rollup")
    step("owner_selected_move", move_id=chosen.candidate.move_id,
         risk_class=chosen.risk_class, approval_required=chosen.requires_approval)

    # 10. Sole writer claims a lease and receives a fresh fencing sequence.
    scope = chosen.candidate.resource_scope
    lease = kernel.claim_lease(ryan, scope)
    step("writer_lease_claimed", lease_id=lease["lease_id"],
         fencing_sequence=lease["fencing_sequence"], writer=lease["writer_identity"])

    envelope = kernel.build_task_envelope(
        command_id=command["command_id"], resource_scope=scope,
        adapter=chosen.candidate.operation, parameters=chosen.candidate.parameters,
        execution_mode="SIMULATED", risk_class=chosen.risk_class, lease=lease,
    )
    persisted = kernel.persist_task_envelope(envelope, ryan)
    job_id = persisted["job_id"]
    kernel.set_job_state(job_id, "QUEUED")
    kernel.set_job_state(job_id, "APPROVED")
    step("task_envelope_issued", task_id=envelope["task_id"], job_id=job_id,
         content_sha256=envelope["content_sha256"])

    # 11. Independent read-only watchers review. They cannot mutate anything.
    pre_reviews = watchmod.run_watchers(kernel.conn, "task", envelope["task_id"])
    step("watchers_reviewed_read_only",
         watchers=[(r["watcher_name"], r["verdict"]) for r in pre_reviews])

    # 12. Runner executes the allowlisted simulated task.
    runner = LocalRunner(kernel, RunnerConfig(workroot=os.path.join(workdir, "runner"),
                                              simulation_only=True))
    receipt = runner.execute(job_id=job_id, task_id=envelope["task_id"],
                             writer_identity=lease["writer_identity"])
    step("runner_executed", outcome=receipt["outcome"], mode=receipt["execution_mode"],
         receipt_id=receipt["receipt_id"], artifacts=[a["logical_id"] for a in receipt["artifacts"]])

    # 13. Drive bridge: stage, hash, upload, read back, verify, advance pointer.
    drive = InMemoryDriveClient()
    bridge = DriveBridge(drive, staging_dir=os.path.join(workdir, "staging"))
    plan = plan_control_room({"00_COMMAND_INBOX": "id1", "receipts": "id2"}, "PARENT_VERIFIED")
    receipt_bytes = canonical_json(receipt).encode("utf-8")
    published = bridge.publish(
        logical_id=receipt["receipt_id"], data=receipt_bytes,
        parent_id="PARENT_VERIFIED", name=f"{receipt['receipt_id']}.json",
    )
    step("drive_receipt_published_and_read_back",
         local_sha256=published.local_sha256, readback_sha256=published.readback_sha256,
         verified=published.verified, pointer_updated=published.manifest_pointer_updated,
         folder_plan_created=plan["created"], folder_authority=plan["authority"],
         client="InMemoryDriveClient (no real Drive write - authorization not active)")

    # 14. Duplicate command and double tap do not execute twice.
    dup = kernel.create_command(
        ryan, idempotency_key="demo-key-001", transcript_text=intake.transcript.text,
        intent=intake.intent.to_dict(), channel="VOICE", confirmed=True,
    )
    step("idempotency_proven", same_command=dup["command_id"] == command["command_id"],
         command_id=dup["command_id"])

    # 15. Section 32 hold removal fails closed and is audited.
    hold_denied = False
    try:
        kernel.attempt_remove_hold(ryan, "hold_section32")
    except HoldRemovalForbidden:
        hold_denied = True
    deny_events = [e for e in kernel.audit_tail(200) if e["event_type"] == "HOLD_REMOVAL_ATTEMPT"]
    step("section32_hold_removal_failed_closed", refused=hold_denied,
         audit_events=len(deny_events), outcome=deny_events[0]["outcome"] if deny_events else None)

    # 16. Post-run watcher pass over the finished work.
    post_reviews = watchmod.run_watchers(kernel.conn, "receipt", receipt["receipt_id"])
    step("watchers_verified_result",
         verdicts=[(r["watcher_name"], r["verdict"]) for r in post_reviews])

    kernel.release_lease(ryan, lease["lease_id"])
    final = kernel.posture()
    step("final_posture", audit_chain_valid=final["audit_chain_valid"],
         holds=len(final["holds"]), recent_changes=len(final["changed"]))

    trace["summary"] = {
        "command_id": command["command_id"],
        "task_id": envelope["task_id"],
        "job_id": job_id,
        "receipt_id": receipt["receipt_id"],
        "receipt_sha256": receipt["content_sha256"],
        "execution_mode": receipt["execution_mode"],
        "outcome": receipt["outcome"],
        "drive_readback_verified": published.verified,
        "idempotent": dup["command_id"] == command["command_id"],
        "hold_removal_refused": hold_denied,
        "audit_chain_valid": final["audit_chain_valid"],
        "holds_preserved": [h["label"] for h in final["holds"]],
        "watcher_verdicts": [(r["watcher_name"], r["verdict"]) for r in post_reviews],
    }
    trace["kernel"] = kernel
    return trace


if __name__ == "__main__":  # pragma: no cover
    import json

    result = run_slice(verbose=True)
    result.pop("kernel", None)
    print(json.dumps(result["summary"], indent=2))
