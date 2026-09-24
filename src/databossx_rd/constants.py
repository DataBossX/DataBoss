"""Shared R&D constants. No secrets live here."""

from __future__ import annotations

from pathlib import Path

UNKNOWN = "UNKNOWN"

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]
RD_ROOT = REPO_ROOT / "rd"
MANIFEST_ROOT = RD_ROOT / "manifests"
DEFAULT_RUNTIME_RD = REPO_ROOT / "runtime" / "rd"

LOOPBACK_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
N8N_PORT = 5678

# Minimum recommended n8n stable named by the safe-slice contract.
# Used only as an upgrade-candidate label. Never triggers an upgrade.
N8N_MIN_STABLE = (2, 40, 5)
N8N_MIN_STABLE_LABEL = "2.40.5"
N8N_AGENTS_REVIEW_MINOR = (2, 41)

# Read-only Ollama paths. Pull/create/push/delete/copy are rejected.
OLLAMA_ALLOWED_PATHS = {
    ("GET", "/api/version"),
    ("GET", "/api/tags"),
    ("POST", "/api/show"),
}

# Read-only n8n paths. Workflows and credentials are not requested.
N8N_ALLOWED_PATHS = {
    ("GET", "/healthz"),
    ("GET", "/healthz/readiness"),
    ("GET", "/rest/settings"),
}

FORBIDDEN_PRODUCTION_PREFIXES = (
    "output/",
    "projects/",
    "private_projects/",
    "client_work/",
    "evidence/",
    "website/",
    "backend/",
    "frontend/",
    "horizon/",
)

# Environment keys that may be recorded as already-observable n8n config.
# Values that look like secrets are redacted even if a key is listed here.
N8N_OBSERVABLE_ENV_KEYS = (
    "N8N_VERSION",
    "N8N_RELEASE_TYPE",
    "N8N_DISABLED_MODULES",
    "N8N_ENABLED_MODULES",
    "N8N_AI_ENABLED",
    "N8N_PORT",
    "N8N_HOST",
    "N8N_PROTOCOL",
    "N8N_PERSONALIZATION_ENABLED",
    "N8N_DIAGNOSTICS_ENABLED",
    "N8N_TEMPLATES_ENABLED",
    "N8N_HIDE_USAGE_PAGE",
)

N8N_PRERELEASE_ALLOWLIST_ENV = "DATABOSSX_RD_N8N_PRERELEASE_ALLOWLIST"
MINERU_LICENSE_ENV = "DATABOSSX_RD_MINERU_LICENSE_ACCEPTED"

DOCLING_PINNED_VERSION = "2.130.0"
MINERU_PINNED_VERSION = "4.0.7"
CURRENT_PARSER_REF = "grocery_report_pipeline.extract_text"
CURRENT_PARSER_VERSION = "1.0.0"
