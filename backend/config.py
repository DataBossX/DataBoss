"""Centralized configuration for the DataBossX backend.

All settings are read from the environment (loaded from backend/.env) so that
nothing is hard-coded. Import this module wherever configuration is needed.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# --- Database ---
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./databossx.db")

# --- LLM provider API keys (blank => provider disabled) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- LLM model ids (overridable via env) ---
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# --- LLM reliability knobs ---
LLM_TIMEOUT_SECONDS = _float("LLM_TIMEOUT_SECONDS", 60.0)
LLM_MAX_RETRIES = _int("LLM_MAX_RETRIES", 2)
LLM_MAX_TOKENS = _int("LLM_MAX_TOKENS", 1000)

# --- Upload limits ---
MAX_UPLOAD_BYTES = _int("MAX_UPLOAD_BYTES", 25 * 1024 * 1024)  # 25 MiB

# --- CORS ---
_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000")
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
# Browsers reject credentialed requests when origin is the "*" wildcard.
CORS_ALLOW_CREDENTIALS = CORS_ORIGINS != ["*"]

# --- Logging / observability ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "logs")
JSON_LOGS = os.getenv("JSON_LOGS", "true").lower() in {"1", "true", "yes"}
