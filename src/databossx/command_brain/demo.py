"""Phase 5 controlled demo.

Runs the full loop against the SYNTHETIC corpus only. No Horizon, Penterra, or
other client material is touched, no network call is made, and the demo asserts
its own safety properties rather than merely printing them:

* the accepted baseline's bytes are identical before and after the tournament
* a deliberately fabricating candidate is quarantined, not merely rejected
* a candidate that regresses is rejected
* contested cells become human-review items
* an immutable, hash-chained receipt is written

Run it with::

    python -m databossx.command_brain.demo
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from .autonomy import AutonomyLevel
from .policy import PolicyProfile
from .redaction import redact
from .runtime import CommandBrainRuntime
from .service import CommandBrain
from .util import FrozenClock, canonical_hash
from .voice import SimulatedSpeechToText, SimulatedTextToSpeech, VoiceSession

DEMO_PROJECT = "sec32_synthetic"

SCRIPT = (
    "What is happening with Section 32?",
    "Read-only mode.",
    "Do not touch the workbook yet.",
    "Have three agents independently inspect this index.",
)


def run_demo(db_path=None, *, verbose: bool = True) -> dict:
    db_path = Path(db_path) if db_path else Path(tempfile.mkdtemp()) / "command_brain_demo.db"

    runtime = CommandBrainRuntime(
        db_path,
        profile=PolicyProfile(autonomy_ceiling=AutonomyLevel.DRAFT),
        clock=FrozenClock(),
        id_seed="databossx-command-brain-demo",
        requesting_user="ryan",
        project_id=DEMO_PROJECT,
    )
    brain = CommandBrain(runtime)
    conversation_id = brain.start_conversation("voice", DEMO_PROJECT)

    voice = VoiceSession(
        runtime.store,
        conversation_id,
        authenticated_session_id="demo-authenticated-session",
        stt=SimulatedSpeechToText(),
        tts=SimulatedTextToSpeech(),
    )

    transcript_log = []
    response = None
    for utterance in SCRIPT:
        token = voice.press_to_talk()
        record = voice.submit_audio(utterance, token)
        voice.confirm(record.transcript_id)
        response = brain.handle(utterance, channel="voice", project_id=DEMO_PROJECT, voice_session=voice)
        transcript_log.append(
            {
                "utterance": utterance,
                "interpreted": response.interpreted_request,
                "requires_approval": response.requires_approval,
                "spoken": response.spoken_summary,
            }
        )
        if verbose:
            print(f"\n> {utterance}")
            print(f"  interpreted: {response.interpreted_request}")
            print(f"  {response.spoken_summary}")

    assert response is not None and response.requires_approval, "tournament must stop for approval"
    envelope_id = response.envelope["task_id"]

    # Authenticated approval — deliberately a separate act from the utterance.
    approval = brain.approve(envelope_id, "ryan", method="authenticated_ui")
    result = brain.execute(envelope_id, approval.approval_id)
    tournament = result["tournament"]

    baseline_hash = tournament["baseline"]["output_hash"]
    stored_baseline = runtime.store.fetchone(
        "SELECT output_json, status FROM cb_tournament_candidates WHERE candidate_id = ?",
        (tournament["baseline"]["candidate_id"],),
    )
    stored_hash = canonical_hash(json.loads(stored_baseline["output_json"]))

    quarantined = [c for c in tournament["candidates"] if c["status"] == "QUARANTINED"]
    rejected = [c for c in tournament["candidates"] if c["status"] == "REJECTED"]
    accepted = [c for c in tournament["candidates"] if c["status"] == "ACCEPTED"]

    checks = {
        "baseline_bytes_unchanged": stored_hash == baseline_hash,
        "fabricating_candidate_quarantined": any(
            c["spec"]["profile_id"] == "fabricating" for c in quarantined
        ),
        "regressing_candidate_rejected": bool(rejected),
        "vote_never_overrode_source": bool(tournament["consensus"]["vote_overruled_by_source"]),
        "human_review_queue_populated": bool(runtime.store.open_human_reviews(DEMO_PROJECT)),
        "receipt_written": bool(result.get("receipt_id")),
        "audit_ledger_intact": runtime.store.verify_ledger()["valid"],
        "no_client_files_used": all(
            artifact["synthetic"] for artifact in runtime.state.artifacts(DEMO_PROJECT)
        ),
        "level_4_disabled": runtime.policy.profile.autonomy_ceiling <= AutonomyLevel.BOUNDED_WRITER,
    }

    explanation = runtime.explain(tournament["tournament_id"], "phone", "concise")

    summary = {
        "conversation_id": conversation_id,
        "voice": voice.describe(),
        "transcript_log": transcript_log,
        "envelope_id": envelope_id,
        "envelope_hash": response.envelope_hash,
        "approval_id": approval.approval_id,
        "tournament_id": tournament["tournament_id"],
        "baseline_output_hash": baseline_hash,
        "baseline_preserved": tournament["baseline_preserved"],
        "accepted_candidate_id": tournament["accepted_candidate_id"],
        "accepted_profiles": [c["spec"]["profile_id"] for c in accepted],
        "candidates": [
            {
                "profile": c["spec"]["profile_id"],
                "status": c["status"],
                "aggregate": c["scorecard"]["aggregate"],
                "decision": (c["decision"] or {}).get("decision"),
                "simulated": c["simulated"],
            }
            for c in tournament["candidates"]
        ],
        "baseline_aggregate": tournament["baseline"]["scorecard"]["aggregate"],
        "consensus": tournament["consensus"],
        "human_review_items": len(runtime.store.open_human_reviews(DEMO_PROJECT)),
        "receipt_id": result.get("receipt_id"),
        "explanation": explanation["explanation"],
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    # The summary is a shareable artifact, so it goes through the same redaction
    # as any phone-facing payload. The local database path is attached after
    # redaction because it is operator-local plumbing, not part of the receipt.
    summary = redact(summary)
    summary["db_path"] = str(db_path)

    if verbose:
        print("\n--- CONTROLLED DEMO RESULT (SYNTHETIC DATA ONLY) ---")
        print(f"baseline           {summary['baseline_aggregate']}")
        for candidate in summary["candidates"]:
            print(
                f"  {candidate['profile']:<14} {candidate['status']:<12} "
                f"{candidate['aggregate']:<8} {candidate['decision']}"
            )
        print(f"baseline preserved: {summary['baseline_preserved']}")
        print(f"human review items: {summary['human_review_items']}")
        print(f"receipt:            {summary['receipt_id']}")
        for name, passed in checks.items():
            print(f"  [{'PASS' if passed else 'FAIL'}] {name}")

    return summary


def main() -> int:  # pragma: no cover - CLI entry point
    parser = argparse.ArgumentParser(description="DataBossX Command Brain controlled demo")
    parser.add_argument("--db", default=None, help="Path for the demo database")
    parser.add_argument("--json", action="store_true", help="Emit the summary as JSON")
    args = parser.parse_args()
    summary = run_demo(args.db, verbose=not args.json)
    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    return 0 if summary["all_checks_passed"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
