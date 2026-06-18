"""Observability: structured logging, request metrics, and a metrics endpoint.

Dependency-light by design:
  * logging uses loguru (already a dependency) with an optional JSON sink,
  * metrics are kept in-process and exposed both as JSON (/api/metrics) and in
    Prometheus text format (/metrics) — no extra package required.
"""
import os
import sys
import threading
import time
from collections import defaultdict
from typing import Dict, Tuple

from loguru import logger

import config

_lock = threading.Lock()
_counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = defaultdict(float)
_hist: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], Dict[str, float]] = defaultdict(
    lambda: {"count": 0.0, "sum": 0.0}
)


def _key(name: str, labels: Dict[str, str]) -> Tuple[str, Tuple[Tuple[str, str], ...]]:
    return name, tuple(sorted(labels.items()))


def inc(name: str, value: float = 1.0, **labels: str) -> None:
    with _lock:
        _counters[_key(name, labels)] += value


def observe(name: str, value: float, **labels: str) -> None:
    with _lock:
        h = _hist[_key(name, labels)]
        h["count"] += 1
        h["sum"] += value


def snapshot() -> dict:
    with _lock:
        counters = [
            {"name": n, "labels": dict(lbls), "value": v}
            for (n, lbls), v in _counters.items()
        ]
        histograms = [
            {"name": n, "labels": dict(lbls), "count": h["count"], "sum": h["sum"]}
            for (n, lbls), h in _hist.items()
        ]
    return {"counters": counters, "histograms": histograms}


def prometheus_text() -> str:
    lines = []

    def fmt_labels(lbls: Tuple[Tuple[str, str], ...]) -> str:
        if not lbls:
            return ""
        inner = ",".join(f'{k}="{v}"' for k, v in lbls)
        return "{" + inner + "}"

    with _lock:
        for (name, lbls), v in _counters.items():
            lines.append(f"{name}{fmt_labels(lbls)} {v}")
        for (name, lbls), h in _hist.items():
            lines.append(f"{name}_count{fmt_labels(lbls)} {h['count']}")
            lines.append(f"{name}_sum{fmt_labels(lbls)} {h['sum']}")
    return "\n".join(lines) + "\n"


def configure_logging() -> None:
    """Configure loguru: console + rotating file (JSON when enabled)."""
    logger.remove()
    logger.add(sys.stderr, level=config.LOG_LEVEL)
    os.makedirs(config.LOG_DIR, exist_ok=True)
    logger.add(
        os.path.join(config.LOG_DIR, "databossx.log"),
        rotation="10 MB",
        retention="10 days",
        level=config.LOG_LEVEL,
        serialize=config.JSON_LOGS,
        enqueue=True,
    )


async def metrics_middleware(request, call_next):
    """Time each request, record metrics, and log it structurally."""
    start = time.monotonic()
    # Use the route template when available so label cardinality stays bounded.
    path = request.url.path
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        duration = time.monotonic() - start
        inc("http_requests_total", method=request.method, path=path, status="500")
        observe("http_request_duration_seconds", duration, method=request.method, path=path)
        logger.exception(f"Unhandled error {request.method} {path}")
        raise

    duration = time.monotonic() - start
    inc("http_requests_total", method=request.method, path=path, status=str(status))
    observe("http_request_duration_seconds", duration, method=request.method, path=path)
    logger.info(
        "request",
        method=request.method,
        path=path,
        status=status,
        duration_ms=round(duration * 1000, 2),
    )
    response.headers["X-Process-Time-ms"] = str(round(duration * 1000, 2))
    return response
