"""Isolated document-parser benchmark specification and runner.

Candidates are recorded, not installed. MinerU stays blocked unless both
enabled=true and LICENSE_ACCEPTED=true. Outputs stay inside an isolated root.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .constants import (
    CURRENT_PARSER_REF,
    CURRENT_PARSER_VERSION,
    DEFAULT_RUNTIME_RD,
    DOCLING_PINNED_VERSION,
    MANIFEST_ROOT,
    MINERU_LICENSE_ENV,
    MINERU_PINNED_VERSION,
    REPO_ROOT,
    UNKNOWN,
)
from .writer import assert_isolated_target, exclusive_writer

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None  # type: ignore[assignment]


REQUIRED_RESULT_FIELDS = (
    "input_sha256",
    "source_page_count",
    "source_start_count",
    "extracted_page_count",
    "extracted_block_count",
    "extracted_table_count",
    "page_provenance",
    "source_provenance",
    "elapsed_ms",
    "peak_memory_kb",
    "errors",
    "unknown_fields",
    "missing_or_dropped_pages",
    "missing_or_dropped_blocks",
    "output_sha256",
    "deterministic_output_expected",
)

PAGE_MARK_RE = re.compile(r"\[PAGE\s+(\d+)\]")
ExtractFn = Callable[[Path], tuple[str, str, bool, str]]


class BenchSpecError(Exception):
    """Raised when the bench specification is incomplete or inconsistent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _peak_memory_kb() -> Any:
    if resource is None:
        return UNKNOWN
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(usage) if usage else UNKNOWN


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BenchSpecError(message)


def load_bench_spec(path: Optional[Path] = None) -> dict[str, Any]:
    spec_path = path or (MANIFEST_ROOT / "parser_bench_spec.v1.json")
    try:
        payload = json.loads(spec_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BenchSpecError(f"spec_missing:{spec_path}") from exc
    except json.JSONDecodeError as exc:
        raise BenchSpecError(f"spec_unreadable:{spec_path}") from exc
    validate_bench_spec(payload, spec_path=spec_path)
    return payload


def validate_bench_spec(spec: dict[str, Any], *, spec_path: Optional[Path] = None) -> None:
    _require(spec.get("schema_id") == "databossx.rd.parser_bench", "schema_id_invalid")
    _require(spec.get("install_policy") == "never_automatic", "install_policy_must_be_never_automatic")
    _require(
        spec.get("network_policy", {}).get("allowed_hosts") == ["127.0.0.1"],
        "network_policy_must_be_loopback_only",
    )
    candidates = spec.get("candidates")
    _require(isinstance(candidates, list) and len(candidates) == 3, "candidates_must_be_current_docling_mineru")
    ids = [item.get("id") for item in candidates]
    _require(ids == ["databossx_current", "docling", "mineru"], "candidate_order_or_ids_invalid")
    current, docling, mineru = candidates
    _require(current.get("implementation") == CURRENT_PARSER_REF, "current_parser_ref_mismatch")
    _require(current.get("version") == CURRENT_PARSER_VERSION, "current_parser_version_mismatch")
    _require(docling.get("version") == DOCLING_PINNED_VERSION, "docling_version_mismatch")
    _require(docling.get("install") == "never_automatic", "docling_must_not_auto_install")
    _require(mineru.get("version") == MINERU_PINNED_VERSION, "mineru_version_mismatch")
    _require(mineru.get("enabled") is False, "mineru_must_default_disabled")
    _require(mineru.get("license_accepted") is False, "mineru_license_must_default_false")
    _require(mineru.get("install") == "never_automatic", "mineru_must_not_auto_install")
    _require(
        spec.get("required_result_fields") == list(REQUIRED_RESULT_FIELDS),
        "required_result_fields_mismatch",
    )
    sources = spec.get("test_sources")
    _require(isinstance(sources, list) and bool(sources), "test_sources_missing")
    for source in sources:
        rel = source.get("path")
        expected = source.get("input_sha256")
        _require(bool(rel) and bool(expected), "test_source_requires_path_and_sha256")
        source_path = Path(rel) if Path(rel).is_absolute() else (REPO_ROOT / rel).resolve()
        if spec_path is not None and not source_path.exists():
            raise BenchSpecError(f"test_source_missing:{rel}")
        if source_path.exists() and sha256_file(source_path) != expected:
            raise BenchSpecError(f"test_source_sha256_mismatch:{rel}")


def mineru_license_accepted(environ: Optional[dict[str, str]] = None) -> bool:
    env = environ if environ is not None else os.environ
    return env.get(MINERU_LICENSE_ENV, "false").strip().lower() == "true"


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _page_numbers_from_text(text: str) -> Any:
    marks = [int(match) for match in PAGE_MARK_RE.findall(text)]
    return marks if marks else UNKNOWN


def _block_count(text: str) -> int:
    return len([block for block in re.split(r"\n\s*\n", text) if block.strip()])


def _pdf_page_count(path: Path) -> Any:
    try:
        import pdfplumber  # type: ignore
    except Exception:
        pdfplumber = None
    if pdfplumber is not None:
        try:
            with pdfplumber.open(str(path)) as pdf:
                return len(pdf.pages)
        except Exception:
            pass
    try:
        import fitz  # type: ignore
    except Exception:
        fitz = None
    if fitz is not None:
        try:
            doc = fitz.open(str(path))
            count = doc.page_count
            doc.close()
            return int(count)
        except Exception:
            return UNKNOWN
    return UNKNOWN


def _source_unknowns(start_count: Any = 1) -> dict[str, Any]:
    return {
        "source_start_count": start_count,
        "source_page_count": UNKNOWN,
        "source_page_numbers": UNKNOWN,
        "source_block_count": UNKNOWN,
    }


def source_counts(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".pdf":
        pages = _pdf_page_count(path)
        return {
            "source_start_count": 1,
            "source_page_count": pages,
            "source_page_numbers": list(range(1, pages + 1)) if isinstance(pages, int) else UNKNOWN,
            "source_block_count": UNKNOWN,
        }
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return _source_unknowns()
    numbers = _page_numbers_from_text(text)
    return {
        "source_start_count": 1,
        "source_page_count": len(numbers) if isinstance(numbers, list) else UNKNOWN,
        "source_page_numbers": numbers,
        "source_block_count": _block_count(text),
    }


def _drop_status(expected: Any, observed: Any) -> Any:
    if expected is UNKNOWN or observed is UNKNOWN:
        return UNKNOWN
    if not isinstance(expected, list) or not isinstance(observed, list):
        return UNKNOWN
    return [item for item in expected if item not in observed]


def unknown_fields_of(result: dict[str, Any]) -> list[str]:
    return [key for key in REQUIRED_RESULT_FIELDS if result.get(key) is UNKNOWN]


def _empty_result(source: Path, digest: Any, errors: list[str]) -> dict[str, Any]:
    result = {
        "input_sha256": digest,
        "source_page_count": UNKNOWN,
        "source_start_count": UNKNOWN,
        "extracted_page_count": UNKNOWN,
        "extracted_block_count": UNKNOWN,
        "extracted_table_count": UNKNOWN,
        "page_provenance": UNKNOWN,
        "source_provenance": {
            "path": str(source),
            "sha256": digest,
        },
        "elapsed_ms": UNKNOWN,
        "peak_memory_kb": UNKNOWN,
        "errors": errors,
        "unknown_fields": [],
        "missing_or_dropped_pages": UNKNOWN,
        "missing_or_dropped_blocks": UNKNOWN,
        "output_sha256": UNKNOWN,
        "deterministic_output_expected": False,
    }
    result["unknown_fields"] = unknown_fields_of(result)
    return result


def extract_with_current_pipeline(path: Path) -> tuple[str, str, bool, str]:
    repo = str(REPO_ROOT)
    if repo not in sys.path:
        sys.path.insert(0, repo)
    import grocery_report_pipeline as grp

    suffix = path.suffix.lower()
    extractors = (
        (grp.TEXT_EXT, grp._extract_txt),
        (grp.CSV_EXT, grp._extract_csv),
        (grp.EXCEL_EXT, grp._extract_xlsx),
        (grp.WORD_EXT, grp._extract_docx),
        (grp.PDF_EXT, grp._extract_pdf),
        (grp.IMAGE_EXT, grp._extract_image),
    )
    for extensions, extract in extractors:
        if suffix in extensions:
            return extract(path)
    return "", "skip", False, "unsupported extension"


def measure_extractor(
    path: Path,
    extractor: ExtractFn,
    *,
    deterministic_expected: bool,
) -> dict[str, Any]:
    digest = sha256_file(path)
    source = source_counts(path)
    started = time.perf_counter()
    try:
        text, method, ocr_used, note = extractor(path)
        errors = [note] if note else []
    except Exception as exc:
        result = _empty_result(path, digest, [f"extractor_error:{type(exc).__name__}"])
        result["source_page_count"] = source["source_page_count"]
        result["source_start_count"] = source["source_start_count"]
        result["unknown_fields"] = unknown_fields_of(result)
        return result
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    extracted_pages = _page_numbers_from_text(text)
    extracted_blocks = _block_count(text) if text.strip() else 0
    if isinstance(extracted_pages, list):
        page_provenance: Any = [
            {
                "page": page,
                "source_sha256": digest,
                "source_path": path.name,
                "extractor": method,
            }
            for page in extracted_pages
        ]
    elif text.strip():
        page_provenance = UNKNOWN
    else:
        page_provenance = []
    dropped_blocks: Any = UNKNOWN
    if source["source_block_count"] is not UNKNOWN:
        dropped_blocks = max(source["source_block_count"] - extracted_blocks, 0)
    result = {
        "input_sha256": digest,
        "source_page_count": source["source_page_count"],
        "source_start_count": source["source_start_count"],
        "extracted_page_count": (
            len(extracted_pages) if isinstance(extracted_pages, list) else UNKNOWN
        ),
        "extracted_block_count": extracted_blocks,
        "extracted_table_count": UNKNOWN,
        "page_provenance": page_provenance,
        "source_provenance": {
            "path": path.name,
            "sha256": digest,
            "extractor": method,
            "ocr_used": ocr_used,
        },
        "elapsed_ms": elapsed_ms,
        "peak_memory_kb": _peak_memory_kb(),
        "errors": errors,
        "unknown_fields": [],
        "missing_or_dropped_pages": _drop_status(source["source_page_numbers"], extracted_pages),
        "missing_or_dropped_blocks": dropped_blocks,
        "output_sha256": sha256_text(text) if text else UNKNOWN,
        "deterministic_output_expected": deterministic_expected and not ocr_used,
    }
    result["unknown_fields"] = unknown_fields_of(result)
    return result


def _candidate_status_base(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": candidate.get("id"),
        "version": candidate.get("version"),
        "enabled": candidate.get("enabled"),
        "install": candidate.get("install"),
        "available": False,
        "blocked": False,
        "block_reason": UNKNOWN,
        "ran": False,
    }


def _block(status: dict[str, Any], reason: str) -> dict[str, Any]:
    status["blocked"] = True
    status["block_reason"] = reason
    return status


def _candidate_gate(candidate: dict[str, Any], environ: Optional[dict[str, str]]) -> dict[str, Any]:
    status = _candidate_status_base(candidate)
    ident = candidate.get("id")
    if ident == "databossx_current":
        status["available"] = True
        return status
    if candidate.get("install") != "never_automatic":
        return _block(status, "install_policy_violation")
    if ident == "docling":
        status["available"] = _module_available("docling")
        if not status["available"]:
            return _block(status, "candidate_not_installed")
        if not candidate.get("enabled", False):
            return _block(status, "disabled_by_spec")
        return status
    if ident == "mineru":
        license_ok = mineru_license_accepted(environ)
        status["license_accepted"] = license_ok
        if not license_ok:
            return _block(status, "LICENSE_ACCEPTED=false")
        if not candidate.get("enabled", False):
            return _block(status, "disabled_by_spec")
        status["available"] = _module_available("mineru")
        if not status["available"]:
            return _block(status, "candidate_not_installed")
        return status
    return _block(status, "unknown_candidate")


def _resolve_source(rel: str) -> Path:
    path = Path(rel)
    if path.is_absolute():
        return path
    return (REPO_ROOT / rel).resolve()


def _mark_current_ran(candidate_status: list[dict[str, Any]]) -> None:
    for status in candidate_status:
        if status["id"] == "databossx_current" and not status["blocked"]:
            status["ran"] = True


def _apply_current_source_gates(
    measured: dict[str, Any],
    source_spec: dict[str, Any],
) -> bool:
    failed = False
    if measured["input_sha256"] != source_spec["input_sha256"]:
        measured["errors"].append("input_sha256_mismatch")
        failed = True
    pages = measured["missing_or_dropped_pages"]
    if pages not in (UNKNOWN, []):
        measured["errors"].append("dropped_pages")
        failed = True
    if pages is UNKNOWN:
        measured["errors"].append("drop_detection_unknown")
        failed = True
    if measured["missing_or_dropped_blocks"] not in (UNKNOWN, 0):
        measured["errors"].append("dropped_blocks")
        failed = True
    return failed


def _run_current_sources(
    loaded: dict[str, Any],
    extractor: ExtractFn,
    errors: list[str],
) -> tuple[list[dict[str, Any]], str]:
    verdict = "pass"
    sources_out: list[dict[str, Any]] = []
    for source_spec in loaded["test_sources"]:
        path = _resolve_source(source_spec["path"])
        if not path.exists():
            errors.append(f"source_missing:{source_spec['path']}")
            verdict = "fail"
            sources_out.append(_empty_result(path, UNKNOWN, ["source_missing"]))
            continue
        measured = measure_extractor(
            path,
            extractor,
            deterministic_expected=bool(source_spec.get("deterministic_output_expected", True)),
        )
        if _apply_current_source_gates(measured, source_spec):
            verdict = "fail"
        sources_out.append(measured)
    return sources_out, verdict


def _run_spec_only_sources(loaded: dict[str, Any]) -> list[dict[str, Any]]:
    sources_out: list[dict[str, Any]] = []
    for source_spec in loaded["test_sources"]:
        path = _resolve_source(source_spec["path"])
        digest = source_spec.get("input_sha256", UNKNOWN)
        if path.exists():
            digest = sha256_file(path)
        placeholder = _empty_result(path, digest, ["spec_only_no_extract"])
        placeholder["source_start_count"] = 1
        if path.exists():
            counts = source_counts(path)
            placeholder["source_page_count"] = counts["source_page_count"]
            placeholder["source_start_count"] = counts["source_start_count"]
        placeholder["unknown_fields"] = unknown_fields_of(placeholder)
        sources_out.append(placeholder)
    return sources_out


def _enforce_mineru_license(
    candidate_status: list[dict[str, Any]],
    environ: Optional[dict[str, str]],
    errors: list[str],
) -> bool:
    failed = False
    for status in candidate_status:
        if status["id"] != "mineru" or status.get("block_reason") == "LICENSE_ACCEPTED=false":
            continue
        if mineru_license_accepted(environ):
            continue
        status["blocked"] = True
        status["block_reason"] = "LICENSE_ACCEPTED=false"
        errors.append("mineru_license_gate_failed")
        failed = True
    return failed


def run_parser_bench(
    *,
    spec: Optional[dict[str, Any]] = None,
    spec_path: Optional[Path] = None,
    output_root: Optional[Path] = None,
    allowed_roots: Optional[list[Path]] = None,
    mode: str = "spec_only",
    environ: Optional[dict[str, str]] = None,
    current_extractor: Optional[ExtractFn] = None,
    writer_id: str = "databossx-rd-parser-bench",
) -> dict[str, Any]:
    loaded = spec if spec is not None else load_bench_spec(spec_path)
    if spec is not None:
        validate_bench_spec(loaded, spec_path=spec_path)
    if mode not in {"spec_only", "current_only"}:
        raise BenchSpecError(f"unsupported_mode:{mode}")
    target = Path(output_root or (DEFAULT_RUNTIME_RD / "bench"))
    roots = allowed_roots or [DEFAULT_RUNTIME_RD]
    assert_isolated_target(target, roots)

    candidate_status = [_candidate_gate(item, environ) for item in loaded["candidates"]]
    errors: list[str] = []
    if mode == "current_only":
        sources_out, verdict = _run_current_sources(
            loaded,
            current_extractor or extract_with_current_pipeline,
            errors,
        )
        _mark_current_ran(candidate_status)
    else:
        sources_out = _run_spec_only_sources(loaded)
        verdict = "pass"

    if _enforce_mineru_license(candidate_status, environ, errors):
        verdict = "fail"

    payload = {
        "schema_id": "databossx.rd.parser_bench_run",
        "schema_version": "1.0",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "verdict": verdict if not errors else "fail",
        "errors": errors,
        "installs_attempted": False,
        "cloud_calls_attempted": False,
        "candidates": candidate_status,
        "sources": sources_out,
        "required_result_fields": list(REQUIRED_RESULT_FIELDS),
    }
    if any(status["id"] in {"docling", "mineru"} and status.get("ran") for status in candidate_status):
        payload["verdict"] = "fail"
        payload["errors"].append("candidate_ran_without_authorization")

    with exclusive_writer(target, writer_id, roots) as writer:
        writer.write_json("run.json", payload)
        payload["output_path"] = str(writer.target / "run.json")
    return payload
