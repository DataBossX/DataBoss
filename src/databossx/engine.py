"""Capability execution with routing, cache, comparison, and receipts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .batching import (
    claim_ready_tasks,
    complete_task,
    persist_cache_row,
    persist_comparison_row,
    persist_receipt_row,
)
from .cache import DerivedWorkCache, make_cache_key
from .candidates import Candidate, compare_candidates, comparison_hash
from .database import DataBossDatabase
from .hashing import sha256_bytes
from .receipts import (
    build_engine_receipt,
    canonical_dumps,
    seal_receipt,
    sha256_canonical,
    write_sealed_receipt,
)
from .routing import (
    RouteDecision,
    RoutePolicy,
    RouteRequest,
    decision_to_dict,
    persist_route_decision,
    policy_from_profile,
    route,
)


TASK_CAPABILITIES = {
    "REGISTER_SOURCES": "inventory",
    "INVENTORY_AND_LOCK": "inventory",
    "REGISTER_TEMPLATE": "hash",
    "COMPARE_CANDIDATES": "candidate_compare",
    "HASH_INPUTS": "hash",
}

ACK_CAPABILITIES = frozenset(
    {
        "inventory",
        "title_math",
        "chain_rules",
        "workbook_compare",
        "cache_lookup",
        "receipt",
    }
)


@dataclass(frozen=True)
class ExecutionResult:
    capability: str
    status: str
    cache_hit: bool
    route: RouteDecision
    receipt: dict[str, Any]
    output: dict[str, Any]
    output_hash: str | None


def _input_hash(values: Sequence[str] | Mapping[str, Any]) -> str:
    payload = values if isinstance(values, Mapping) else list(values)
    return sha256_canonical(payload)


def _candidate_from_payload(item: Mapping[str, Any]) -> Candidate:
    return Candidate(
        candidate_id=item["candidate_id"],
        producer=item["producer"],
        values=item["values"],
        evidence_hashes=item.get("evidence_hashes", {}),
        schema_valid=item.get("schema_valid", True),
    )


def _dispatch(capability: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if capability == "hash":
        parts = list(payload.get("input_hashes", []))
        return {"digest": sha256_canonical(parts), "count": len(parts)}
    if capability == "candidate_compare":
        report = compare_candidates(
            str(payload.get("subject_key", "subject")),
            [_candidate_from_payload(item) for item in payload["candidates"]],
        )
        body = report.to_dict()
        body["comparison_hash"] = comparison_hash(report)
        return body
    if capability in ACK_CAPABILITIES:
        return {"ack": capability, "payload_hash": _input_hash(payload)}
    raise ValueError(f"no local dispatcher for capability: {capability}")


def _execution_result(
    capability: str,
    status: str,
    decision: RouteDecision,
    extra: dict[str, Any],
    input_hashes: Sequence[str],
    *,
    project_id: str | None,
    receipt_path: str | Path | None,
    cache_hit: bool = False,
    output: dict[str, Any] | None = None,
    output_hash: str | None = None,
) -> ExecutionResult:
    extra["cache"]["hit"] = cache_hit
    receipt = build_engine_receipt(
        kind="capability",
        status=status,
        input_hashes=list(input_hashes),
        output_hashes=[output_hash] if output_hash else (),
        project_id=project_id,
        extra=extra,
    )
    if receipt_path is not None:
        sealed = write_sealed_receipt(receipt_path, receipt.body)
    else:
        sealed = seal_receipt(receipt.body)
    return ExecutionResult(
        capability,
        status,
        cache_hit,
        decision,
        sealed,
        output or {},
        output_hash,
    )


def execute_capability(
    capability: str,
    payload: Mapping[str, Any],
    *,
    project_id: str | None = None,
    policy: RoutePolicy | None = None,
    policy_profile: str = "local_only",
    cache: DerivedWorkCache | None = None,
    recipe_version: str = "engine.v1",
    receipt_path: str | Path | None = None,
) -> ExecutionResult:
    resolved_policy = policy or policy_from_profile(policy_profile)
    input_hashes = [str(item) for item in payload.get("input_hashes", [])]
    if not input_hashes:
        input_hashes = [_input_hash(payload)]
    decision = route(
        RouteRequest(
            capability=capability,
            input_hash=input_hashes[0],
            policy=resolved_policy,
            modality=str(payload.get("modality", "text")),
            context_bytes=int(payload.get("context_bytes", 0)),
        )
    )
    extra = {
        "cache": {"hit": False, "key": None},
        "capability": capability,
        "route": decision_to_dict(decision),
    }
    if decision.blocked:
        return _execution_result(
            capability,
            "blocked",
            decision,
            extra,
            input_hashes,
            project_id=project_id,
            receipt_path=receipt_path,
        )

    cache_key = make_cache_key(recipe_version, input_hashes, {"capability": capability})
    extra["cache"]["key"] = cache_key
    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            return _execution_result(
                capability,
                "cache_hit",
                decision,
                extra,
                input_hashes,
                project_id=project_id,
                receipt_path=receipt_path,
                cache_hit=True,
                output=cached.payload,
                output_hash=cached.output_hash,
            )

    output = _dispatch(capability, payload)
    output_hash = sha256_canonical(output)
    if cache is not None:
        cache.put(
            recipe_version=recipe_version,
            input_hashes=input_hashes,
            payload=output,
            params={"capability": capability},
            output_hash=output_hash,
        )
    return _execution_result(
        capability,
        "computed",
        decision,
        extra,
        input_hashes,
        project_id=project_id,
        receipt_path=receipt_path,
        output=output,
        output_hash=output_hash,
    )


def execute_claimed_batch(
    db: DataBossDatabase,
    *,
    project_id: str,
    worker_id: str,
    capabilities: Sequence[str],
    cache: DerivedWorkCache,
    limit: int = 8,
    policy_profile: str = "local_only",
    receipts_root: str | Path | None = None,
) -> list[ExecutionResult]:
    claimed = claim_ready_tasks(
        db,
        worker_id=worker_id,
        capabilities=capabilities,
        limit=limit,
    )
    results: list[ExecutionResult] = []
    for item in claimed:
        capability = TASK_CAPABILITIES.get(item.task_type, item.task_type.lower())
        payload = {
            "input_hashes": [sha256_bytes(item.payload_json.encode("utf-8"))],
            "task_type": item.task_type,
            "payload_json": item.payload_json,
        }
        receipt_path = None
        if receipts_root is not None:
            receipt_path = Path(receipts_root) / f"task_{item.task_id}.json"
        result = execute_capability(
            capability,
            payload,
            project_id=project_id,
            policy_profile=policy_profile,
            cache=cache,
            receipt_path=receipt_path,
        )
        complete_task(
            db,
            item,
            status="SUCCEEDED" if result.status in {"computed", "cache_hit"} else "FAILED_TERMINAL",
            error_code=result.route.blocked_reason,
        )
        _persist_batch_artifacts(db, project_id, result)
        results.append(result)
    return results


def _persist_batch_artifacts(
    db: DataBossDatabase,
    project_id: str,
    result: ExecutionResult,
) -> None:
    with db.connect() as conn:
        persist_route_decision(conn, project_id, result.route)
        persist_receipt_row(conn, project_id, result.receipt["kind"], result.status, result.receipt)
        cache_key = result.receipt.get("cache", {}).get("key")
        if result.output_hash and cache_key:
            persist_cache_row(
                conn,
                project_id,
                cache_key,
                "engine.v1",
                result.receipt["input_hashes"][0],
                result.output_hash,
                canonical_dumps(result.output),
            )
        if result.output.get("comparison_hash"):
            persist_comparison_row(
                conn,
                project_id,
                result.output.get("subject_key", ""),
                canonical_dumps(result.output),
                int(result.output.get("conflict_count", 0)),
                result.receipt["receipt_sha256"],
            )
        conn.commit()
