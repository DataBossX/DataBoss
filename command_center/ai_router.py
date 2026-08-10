"""Provider-neutral model/provider registry and routing hierarchy.

Deterministic -> local model -> cheap cloud -> premium cloud.
Default mode is SAVE_CREDITS. No unbounded agent loops, no automatic
download of large local models -- only detection of what's already
reachable.
"""
import os
import urllib.request

MODES = ("LOCAL_ONLY", "SAVE_CREDITS", "NORMAL", "DEEP_QA")
DEFAULT_MODE = "SAVE_CREDITS"

REGISTRY = [
    {
        "provider": "deterministic", "model": "python-stdlib", "purpose": "inventory/QA/transform",
        "location": "local", "cost_class": "FREE", "latency_class": "instant",
        "task_types": ["scan", "qa", "worklist", "summarize"], "data_egress": False, "max_attempts": 2,
    },
    {
        "provider": "ollama", "model": "auto-detect", "purpose": "classification/summarization/drafting",
        "location": "local", "cost_class": "LOCAL", "latency_class": "seconds",
        "task_types": ["classify", "summarize", "extract", "triage"], "data_egress": False, "max_attempts": 2,
    },
    {
        "provider": "cheap-cloud", "model": "configured-via-env", "purpose": "bounded high-value tasks",
        "location": "cloud", "cost_class": "LOW", "latency_class": "seconds", "task_types": ["draft", "extract"],
        "data_egress": True, "max_attempts": 1,
    },
    {
        "provider": "premium-cloud", "model": "configured-via-env", "purpose": "hard reasoning/final QA",
        "location": "cloud", "cost_class": "PREMIUM", "latency_class": "slow", "task_types": ["hard_qa", "hard_code"],
        "data_egress": True, "max_attempts": 1,
    },
]


def detect_local_model() -> dict:
    """Check for an already-running local model endpoint. Never triggers
    a download."""
    endpoint = os.environ.get("DATABOSSX_LOCAL_MODEL_URL", "http://127.0.0.1:11434")
    try:
        req = urllib.request.Request(endpoint + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.0):
            return {"available": True, "endpoint": endpoint, "runtime": "ollama"}
    except Exception:
        return {
            "available": False, "endpoint": endpoint, "runtime": None,
            "setup_hint": (
                "No local model endpoint detected. Install Ollama and run "
                "`ollama pull llama3.1:8b` when convenient -- this is optional "
                "and never triggered automatically."
            ),
        }


def route(task_type: str, mode: str = DEFAULT_MODE) -> dict:
    if mode not in MODES:
        mode = DEFAULT_MODE
    candidates = [r for r in REGISTRY if task_type in r["task_types"]] or REGISTRY[:1]
    if mode == "LOCAL_ONLY":
        candidates = [c for c in candidates if not c["data_egress"]] or candidates[:1]
    elif mode == "SAVE_CREDITS":
        candidates = sorted(candidates, key=lambda c: {"FREE": 0, "LOCAL": 1, "LOW": 2, "PREMIUM": 3}[c["cost_class"]])
    elif mode == "DEEP_QA":
        candidates = sorted(candidates, key=lambda c: {"PREMIUM": 0, "LOW": 1, "LOCAL": 2, "FREE": 3}[c["cost_class"]])
    return candidates[0]
