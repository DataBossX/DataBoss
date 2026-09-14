"""Capability execution with routing, cache, comparison, and receipts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .batching import ClaimedTask, claim_ready_tasks, complete_task, persist_cache_row, persist_receipt_row
from .cache import DerivedWorkCache, make_cache_key
from .candidates import Candidate, compare_candidates, comparison_hash
from .database import DataBossDatabase
from .hashing import sha256_bytes
from .receipts import EngineReceipt, build_engine_receipt, canonical_dumps, seal_receipt, write_sealed_receipt
from .routing import RouteDecision, RoutePolicy, RouteRequest, decision_to_dict, persist_route_decision, policy_from_profile, route


TASK_CAPABILITIES = {
    "REGISTER_SOURCES": "inventory",
    "INVENTORY_AND_LOCK": "inventory",
    "REGISTER_TEMPLATE": "hash",
    "COMPARE_CANDIDATES": "candidate_compare",
    "HASH_INPUTS": "hash",
}


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
    if isinstance(values, Mapping):
        return sha256_bytes(canonical_dumps(values).encode("utf-8"))
    return sha256_bytes(canonical_dumps(list(values)).encode("utf-8"))


def _dispatch(capability: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if capability == "hash":
        parts = list(payload.get("input_hashes", []))
        return {"digest": sha256_bytes(canonical_dumps(parts).encode("utf-8")), "count": len(parts)}
    if capability == "candidate_compare":
        candidates = [
            Candidate(
                candidate_id=item["candidate_id"],
                producer=item["producer"],
                values=item["values"],
                evidence_hashes=item.get("evidence_hashes", {}),
                schema_valid=item.get("schema_valid", True),
            )
            for item in payload["candidates"]
        ]
        report = compare_candidates(str(payload.get("subject_key", "subject")), candidates)
        body = report.to_dict()
        body["comparison_hash"] = comparison_hash(report)
        return body
    if capability in {"inventory", "title_math", "chain_rules", "workbook_compare", "cache_lookup", "receipt"}:
        return {"ack": capability, "payload_hash": _input_hash(payload)}
    raise ValueError(f"no local dispatcher for capability: {capability}")


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
    request = RouteRequest(
        capability=capability,
        input_hash=input_hashes[0],
        policy=resolved_policy,
        modality=str(payload.get("modality", "text")),
        context_bytes=int(payload.get("context_bytes", 0)),
    )
    decision = route(request)
    extra = {
        "cache": {"hit": False, "key": None},
        "capability": capability,
        "route": decision_to_dict(decision),
    }
    if decision.blocked:
        receipt = build_engine_receipt(
            kind="capability",
            status="blocked",
            input_hashes=input_hashes,
            project_id=project_id,
            extra=extra,
        )
        sealed = _persist_receipt(receipt, receipt_path)
        return ExecutionResult(capability, "blocked", False, decision, sealed, {}, None)

    cache_key = make_cache_key(recipe_version, input_hashes, {"capability": capability})
    extra["cache"]["key"] = cache_key
    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            extra["cache"]["hit"] = True
            receipt = build_engine_receipt(
                kind="capability",
                status="cache_hit",
                input_hashes=input_hashes,
                output_hashes=[cached.output_hash],
                project_id=project_id,
                extra=extra,
            )
            sealed = _persist_receipt(receipt, receipt_path)
            return ExecutionResult(
                capability,
                "cache_hit",
                True,
                decision,
                sealed,
                cached.payload,
                cached.output_hash,
            )

    output = _dispatch(capability, payload)
    output_hash = sha256_bytes(canonical_dumps(output).encode("utf-8"))
    if cache is not None:
        cache.put(
            recipe_version=recipe_version,
            input_hashes=input_hashes,
            payload=output,
            params={"capability": capability},
            output_hash=output_hash,
        )
    extra["cache"]["hit"] = False
    receipt = build_engine_receipt(
        kind="capability",
        status="computed",
        input_hashes=input_hashes,
        output_hashes=[output_hash],
        project_id=project_id,
        extra=extra,
    )
    sealed = _persist_receipt(receipt, receipt_path)
    return ExecutionResult(capability, "computed", False, decision, sealed, output, output_hash)


def _persist_receipt(receipt: EngineReceipt, receipt_path: str | Path | None) -> dict[str, Any]:
    if receipt_path is not None:
        return write_sealed_receipt(receipt_path, receipt.body)
    return seal_receipt(receipt.body)


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
        with db.connect() as conn:
            persist_route_decision(conn, project_id, result.route)
            persist_receipt_row(conn, project_id, result.receipt["kind"], result.status, result.receipt)
            if result.output_hash and result.receipt.get("cache", {}).get("key"):
                persist_cache_row(
                    conn,
                    project_id,
                    result.receipt["cache"]["key"],
                    "engine.v1",
                    result.receipt["input_hashes"][0],
                    result.output_hash,
                    canonical_dumps(result.output),
                )
            conn.commit()
        results.append(result)
    return results
