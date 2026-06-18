"""Tests for backend helper functions.

backend/server.py pulls in heavy optional deps (fastapi, openai, anthropic,
google.generativeai, aiosqlite, PIL, loguru). When those are not installed the
whole module is skipped rather than failing the suite.
"""
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

# Skip cleanly if the backend's runtime deps are not installed.
for mod in ("fastapi", "openai", "anthropic", "google.generativeai",
            "aiosqlite", "PIL", "loguru", "dotenv"):
    pytest.importorskip(mod)

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
server = importlib.import_module("server")


@pytest.mark.parametrize("dirty,expected_safe", [
    ("../../etc/passwd", "passwd"),
    ("..\\..\\windows\\system32\\cmd.exe", "cmd.exe"),
    ("report.pdf", "report.pdf"),
    ("", "unnamed"),
    (None, "unnamed"),
])
def test_sanitize_filename_strips_paths(dirty, expected_safe):
    assert server.sanitize_filename(dirty) == expected_safe


def test_sanitize_filename_removes_null_bytes():
    assert "\x00" not in server.sanitize_filename("a\x00b.txt")


def test_calculate_file_hash_is_stable_sha256():
    h1 = server.calculate_file_hash(b"hello")
    h2 = server.calculate_file_hash(b"hello")
    assert h1 == h2
    assert len(h1) == 64  # sha-256 hex digest
    assert h1 != server.calculate_file_hash(b"world")


def test_cors_origins_not_wildcard_by_default(monkeypatch):
    # Default config must not be wildcard-with-credentials.
    assert "*" not in server._cors_origins or server._allow_credentials is False
