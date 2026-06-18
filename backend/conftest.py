"""Pytest configuration: isolate the app from real config and make it importable.

Environment is set BEFORE importing the app so ``config`` (which reads env at
import time) picks up the test values: a throwaway SQLite DB, a small upload
limit, and no provider keys (so LLM analysis is skipped deterministically).
"""

import os
import sys
import tempfile

# Make `import server`, `import config`, ... resolve when running from anywhere.
sys.path.insert(0, os.path.dirname(__file__))

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

os.environ["SQLITE_DB_PATH"] = _tmp_db.name
os.environ["MAX_UPLOAD_BYTES"] = "100000"  # 100 KB, keeps the "too large" test cheap
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="databossx-logs-")
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)

import pytest
from fastapi.testclient import TestClient

import server


@pytest.fixture(scope="session")
def client():
    with TestClient(server.app) as c:
        yield c


def teardown_module():  # best-effort cleanup
    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass
