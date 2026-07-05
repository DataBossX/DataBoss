"""Pipeline orchestration and the self-healing loop.

This module ties the deterministic engine (:mod:`chaining`, :mod:`verifier`) to
the CrewAI agents (:mod:`agents`) and drives the per-tract self-healing loop:

    1. Extract structured rows        (chaining.ingest_runsheet)
    2. Chain ownership                (chaining.chain_tract)
    3. Deterministic math verify      (verifier.verify_tract)
    4. If total != tract acres, send the delta + owner table back to the
       TitleAuditorAgent for a corrected chain.
    5. Retry up to 5 times.
    6. If still unbalanced, keep the best result and close the tract with a
       NOTED assumption + yellow review flag -- never a silent force-balance.

The CrewAI ``Task`` objects are also defined here (``ingest_task``,
``audit_task``, ``verify_task``) to satisfy the required architecture; they are
built lazily so importing this module never needs an LLM.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from chaining import chain_tract, discover_tracts, ingest_runsheet
from schemas import (
    ACRE_QUANT,
    Conveyance,
    OwnerInterest,
    RunsheetInstrument,
    TractChainResult,
    VerificationResult,
    quantize_acres,
)
from verifier import verify_tract

MAX_RETRIES = 5

LogFn = Callable[[str], None]


def _noop(_: str) -> None:  # default telemetry sink
    pass


# --------------------------------------------------------------------------
# CrewAI Task builders (lazy -- require crewai + an LLM only when invoked)
# --------------------------------------------------------------------------


def build_tasks(agents: Dict[str, Any]) -> Dict[str, Any]:
    """Construct the three CrewAI Tasks bound to the given agents."""
    from crewai import Task

    ingest_task = Task(
        description=(
            "Read the provided runsheet extraction and confirm every instrument "
            "is captured with its tract, parties, conveyance type, book/page, "
            "date, legal, notes and OGL reference. OGL fields must hold OGL "
            "numbers only -- never a book/page."
        ),
        expected_output="A confirmed JSON list of runsheet instruments.",
        agent=agents["ingestion"],
    )
    audit_task = Task(
        description=(
            "Chain title for the tract using the deterministic owner table and "
            "conveyances provided. Apply ASSN logic, deduct ownership, carry OGL "
            "numbers beside leased owners, and return FINAL owners only as JSON: "
            '{"owners": [{"owner": str, "acres": str, "ogl": str|null, '
            '"assumption_note": str}]}. The owners must total exactly to the '
            "tract acreage or include an explicit, noted assumption."
        ),
        expected_output="JSON object with a final 'owners' list for the tract.",
        agent=agents["auditor"],
    )
    verify_task = Task(
        description=(
            "Given the deterministic Decimal verification result, confirm the "
            "tract totals to its acreage. If not, report the exact delta and the "
            "precise correction needed. Never force-balance without a note."
        ),
        expected_output="A verification verdict with exact delta and feedback.",
        agent=agents["mathematician"],
    )
    return {"ingest": ingest_task, "audit": audit_task, "verify": verify_task}


# --------------------------------------------------------------------------
# LLM-assisted correction (best-effort; deterministic path is the guarantee)
# --------------------------------------------------------------------------


def _llm_rechain(
    agents: Dict[str, Any],
    tract: str,
    tract_acres: Decimal,
    owners: List[OwnerInterest],
    conveyances: List[Conveyance],
    feedback: str,
    log: LogFn,
) -> Optional[List[OwnerInterest]]:
    """Ask the TitleAuditorAgent for a corrected owner table.

    Returns a parsed list of :class:`OwnerInterest` if the agent produces a
    usable JSON table, else ``None``. All failures are swallowed (logged) so a
    flaky model never breaks the pipeline -- the deterministic path still runs.
    """
    try:
        from crewai import Crew, Task

        conv_lines = "\n".join(
            f"  {c.date or '?'} | {c.conv_type} | {c.grantor} -> {c.grantee} | "
            f"acres={c.acres} | ogl={c.ogl or ''}"
            for c in conveyances
        )
        owner_lines = "\n".join(f"  {o.owner}: {o.acres} ac (OGL {o.ogl or '-'})" for o in owners)
        prompt = (
            f"Tract {tract} must total EXACTLY {tract_acres} net mineral acres.\n"
            f"Current final owners:\n{owner_lines}\n\n"
            f"Ordered conveyances:\n{conv_lines}\n\n"
            f"Verifier feedback:\n{feedback}\n\n"
            "Re-chain the tract. Deduct ownership correctly, never let anyone "
            "convey more than they own, never allow negative ownership, carry "
            "OGL numbers beside leased owners, and return FINAL owners only as "
            'strict JSON: {"owners":[{"owner":str,"acres":str,"ogl":str|null,'
            '"assumption_note":str}]}. If the runsheet cannot close the total, '
            "add an explicit assumption owner and describe it in "
            "assumption_note. Return ONLY the JSON object."
        )
        task = Task(
            description=prompt,
            expected_output='JSON: {"owners":[...]}',
            agent=agents["auditor"],
        )
        crew = Crew(agents=[agents["auditor"]], tasks=[task], verbose=False)
        raw = str(crew.kickoff())
        parsed = _parse_owner_json(raw, tract)
        if parsed:
            log(f"    LLM proposed {len(parsed)} corrected owner(s) for tract {tract}.")
        return parsed
    except Exception as exc:  # pragma: no cover - model/runtime failures
        log(f"    LLM correction unavailable ({type(exc).__name__}); using deterministic repair.")
        return None


def _parse_owner_json(raw: str, tract: str) -> Optional[List[OwnerInterest]]:
    """Defensively parse an LLM ``{"owners": [...]}`` blob into OwnerInterests."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    rows = data.get("owners")
    if not isinstance(rows, list) or not rows:
        return None
    owners: List[OwnerInterest] = []
    for r in rows:
        try:
            name = str(r["owner"]).strip()
            acres = quantize_acres(r["acres"])
            if not name or acres < 0:
                return None
            note = str(r.get("assumption_note") or "").strip()
            owners.append(
                OwnerInterest(
                    owner=name,
                    tract=tract,
                    acres=acres,
                    ogl=(r.get("ogl") or None),
                    leased=bool(r.get("ogl")),
                    is_assumption=bool(note),
                    assumption_note=note,
                )
            )
        except (KeyError, TypeError, ValueError):
            return None
    return owners


# --------------------------------------------------------------------------
# Deterministic assumption balance (the honest last resort)
# --------------------------------------------------------------------------


def _apply_assumption_balance(
    result: TractChainResult,
    verification: VerificationResult,
    log: LogFn,
) -> TractChainResult:
    """Close a still-unbalanced tract with an explicit, flagged assumption.

    * Shortfall (owners total < tract): add an ``UNIDENTIFIED / UNLEASED
      INTEREST`` owner for the residual so the tract totals exactly, marked as
      an assumption and painted yellow by the writer.
    * Overage (owners total > tract): we refuse to fabricate a negative
      holding; the tract is left at its best value with a yellow review flag and
      a note. Rule 16/12 forbid inventing negative ownership to force a total.

    Either way an assumption note is recorded -- never a silent force-balance.
    """
    delta = verification.delta  # calculated_total - expected
    if delta < 0:
        residual = (-delta).quantize(ACRE_QUANT)
        note = (
            f"Tract {result.tract}: runsheet does not account for "
            f"{residual} ac after {result.attempts} chaining attempts; "
            "allocated to UNIDENTIFIED / UNLEASED INTEREST as a noted "
            "assumption pending examiner review."
        )
        result.final_owners.append(
            OwnerInterest(
                owner="UNIDENTIFIED / UNLEASED INTEREST",
                tract=result.tract,
                acres=residual,
                is_assumption=True,
                assumption_note=note,
            )
        )
        result.assumption_notes.append(note)
        result.review_flags.append(note)
        log(f"    Assumption-balanced tract {result.tract}: +{residual} ac to suspense (flagged).")
    else:
        note = (
            f"Tract {result.tract}: final owners exceed tract acreage by "
            f"{delta} ac after {result.attempts} attempts. Left as best result "
            "with review flag; not force-balanced (rule 12/16). Examiner must "
            "resolve the over-conveyance."
        )
        result.assumption_notes.append(note)
        result.review_flags.append(note)
        # Flag the largest owner for examiner attention without altering acres.
        if result.final_owners:
            biggest = max(result.final_owners, key=lambda o: o.acres)
            biggest.is_assumption = True
            if not biggest.assumption_note:
                biggest.assumption_note = note
        log(f"    Tract {result.tract} over by {delta} ac; flagged for review (not forced).")
    result.balanced = False
    return result


# --------------------------------------------------------------------------
# The self-healing loop
# --------------------------------------------------------------------------


def process_tract(
    tract: str,
    instruments: List[RunsheetInstrument],
    tract_acres: Optional[Decimal],
    agents: Optional[Dict[str, Any]],
    log: LogFn = _noop,
    max_retries: int = MAX_RETRIES,
) -> tuple[TractChainResult, VerificationResult]:
    """Run the full self-healing loop for one tract and return (result, verdict)."""
    log(f"[Tract {tract}] extracting rows and chaining ownership...")
    result, conveyances = chain_tract(tract, instruments, tract_acres)
    verification = verify_tract(
        result.final_owners, result.tract_acres, tract=tract, conveyances=conveyances
    )
    log(
        f"[Tract {tract}] attempt 1: total {verification.calculated_total} vs "
        f"tract {verification.expected_acres} (delta {verification.delta})."
    )

    attempt = 1
    while not verification.passed and attempt < max_retries:
        attempt += 1
        result.attempts = attempt
        log(f"[Tract {tract}] attempt {attempt}: sending delta + owner table back to auditor...")

        corrected: Optional[List[OwnerInterest]] = None
        if agents is not None:
            corrected = _llm_rechain(
                agents,
                tract,
                result.tract_acres,
                result.final_owners,
                conveyances,
                verification.correction_suggestion,
                log,
            )

        if corrected:
            candidate = verify_tract(
                corrected, result.tract_acres, tract=tract, conveyances=conveyances
            )
            # Accept the LLM chain only if it strictly improves the delta.
            if abs(candidate.delta) < abs(verification.delta) or candidate.passed:
                result.final_owners = corrected
                verification = candidate
                log(
                    f"[Tract {tract}] attempt {attempt}: LLM chain improved delta to "
                    f"{verification.delta}."
                )
                continue

        # No LLM, or no improvement: the deterministic chain is already optimal.
        # Break out to the assumption-balance stage rather than spin.
        log(f"[Tract {tract}] attempt {attempt}: no improving re-chain; moving to assumption close.")
        break

    if verification.passed:
        result.balanced = True
        log(f"[Tract {tract}] BALANCED cleanly at {verification.calculated_total} ac.")
    else:
        result = _apply_assumption_balance(result, verification, log)
        # Re-verify after the assumption so the reported total reflects reality.
        verification = verify_tract(
            result.final_owners, result.tract_acres, tract=tract, conveyances=conveyances
        )

    return result, verification


def run_pipeline(
    runsheet_path: str | Path,
    tract_acres_map: Optional[Dict[str, Any]] = None,
    log: LogFn = _noop,
    max_retries: int = MAX_RETRIES,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Run the whole pipeline over a runsheet and return structured results.

    Returns a dict with keys: ``results`` (tract -> TractChainResult),
    ``verifications`` (tract -> VerificationResult), and ``summary`` (counts).
    The Excel writer consumes ``results`` directly.
    """
    tract_acres_map = {str(k): quantize_acres(v) for k, v in (tract_acres_map or {}).items()}

    log("Ingesting runsheet...")
    instruments = ingest_runsheet(runsheet_path)
    log(f"Ingested {len(instruments)} instrument(s).")

    tracts = discover_tracts(instruments)
    log(f"Discovered {len(tracts)} tract(s): {', '.join(tracts)}")

    agents: Optional[Dict[str, Any]] = None
    if use_llm:
        try:
            from agents import build_agents, try_get_llm

            llm = try_get_llm()
            if llm is not None:
                agents = build_agents(llm)
                log("LLM agents online; self-healing loop will use the TitleAuditorAgent.")
            else:
                log("No LLM configured; running deterministic-only self-healing loop.")
        except Exception as exc:
            log(f"Agent setup skipped ({type(exc).__name__}); deterministic-only mode.")

    results: Dict[str, TractChainResult] = {}
    verifications: Dict[str, VerificationResult] = {}
    for tract in tracts:
        res, ver = process_tract(
            tract,
            instruments,
            tract_acres_map.get(tract),
            agents,
            log=log,
            max_retries=max_retries,
        )
        results[tract] = res
        verifications[tract] = ver

    balanced = sum(1 for r in results.values() if r.balanced)
    review = sum(1 for r in results.values() if r.needs_review)
    summary = {
        "tracts_processed": len(results),
        "balanced_tracts": balanced,
        "review_flags": review,
    }
    log(
        f"Done: {summary['tracts_processed']} tract(s), {balanced} balanced, "
        f"{review} flagged for review."
    )
    return {
        "results": results,
        "verifications": verifications,
        "summary": summary,
        "instruments": instruments,
    }
