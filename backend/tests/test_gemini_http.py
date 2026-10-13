"""Qualify the real FastAPI/SQLite path using synthetic documents and SDK results."""
import hashlib
import importlib.util
import os
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


BACKEND = Path(__file__).resolve().parents[1]
REQUIRED = (
    "fastapi", "aiosqlite", "dotenv", "openai", "anthropic",
    "google.generativeai", "PIL", "loguru", "multipart", "httpx",
)


def runtime_dependencies_available():
    try:
        return all(importlib.util.find_spec(name) is not None for name in REQUIRED)
    except ModuleNotFoundError:
        return False


@unittest.skipUnless(runtime_dependencies_available(), "Install the documented backend HTTP test dependencies")
class GeminiHTTPTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from loguru import logger

        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        previous = os.getcwd()
        os.chdir(self.workspace.name)
        self.addCleanup(os.chdir, previous)
        env = patch.dict(os.environ, {
            "GEMINI_API_KEY": "synthetic-placeholder",
            "SQLITE_DB_PATH": str(Path(self.workspace.name) / "test.db"),
        }, clear=True)
        env.start()
        self.addCleanup(env.stop)
        # Real provider SDKs are imported, but outbound sockets are forbidden.
        self.sockets = []
        for name in ("connect", "connect_ex"):
            blocker = patch.object(socket.socket, name, side_effect=AssertionError(
                "Outbound network forbidden in qualification"
            ))
            blocker.start()
            self.addCleanup(blocker.stop)
            self.sockets.append(blocker)
        added_sinks = []
        original_add = logger.add

        def add_test_sink(*args, **kwargs):
            sink = original_add(*args, **kwargs)
            added_sinks.append(sink)
            return sink

        with (
            patch.object(sys, "path", [str(BACKEND), *sys.path]),
            patch("dotenv.load_dotenv", return_value=False),
            patch.object(logger, "add", side_effect=add_test_sink),
        ):
            spec = importlib.util.spec_from_file_location("gemini_http_server", BACKEND / "server.py")
            self.server = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.server)
        for sink in added_sinks:
            self.addCleanup(logger.remove, sink)
        sdk = patch.object(self.server.genai, "GenerativeModel")
        self.sdk = sdk.start()
        self.addCleanup(sdk.stop)
        self.sdk.return_value.generate_content.return_value = SimpleNamespace(text="synthetic-analysis")
        self.client = TestClient(self.server.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def upload(self, payload=b"synthetic-source", filename="synthetic.txt"):
        response = self.client.post("/api/documents/upload", files={"file": (filename, payload, "text/plain")})
        self.assertEqual(response.status_code, 200, response.text)
        detail = self.client.get("/api/documents/" + response.json()["document_id"])
        self.assertEqual(detail.status_code, 200, detail.text)
        return detail.json()

    def test_key_without_model_is_paused_over_http(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["services"]["gemini"], "paused")
        self.assertEqual(response.json()["provider_configuration"]["gemini"]["live_api_verification"], "NOT_RUN")
        self.sdk.assert_not_called()

    def test_paused_upload_preserves_source_hash_without_provider_analysis(self):
        payload = b"synthetic-source-no-client-data"
        result = self.upload(payload)
        self.assertEqual(result["document"]["file_hash"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(result["llm_analysis"], [])
        self.assertIn("mock OCR", result["ocr_results"][0]["raw_text"])
        duplicate = self.client.post("/api/documents/upload", files={"file": ("duplicate.txt", payload, "text/plain")})
        self.assertEqual(duplicate.status_code, 409)
        self.sdk.assert_not_called()

    def test_retiring_and_legacy_models_cannot_run_in_background(self):
        models = ("gemini-omni-flash-preview", "deep-research-pro-preview-12-2025", "gemini-pro", "gemini-1.5-flash")
        for i, model in enumerate(models):
            with self.subTest(model=model), patch.dict(os.environ, {"GEMINI_MODEL": model}):
                result = self.upload(("synthetic-" + str(i)).encode())
                self.assertEqual(result["llm_analysis"], [])
                self.assertEqual(self.client.get("/api/health").json()["services"]["gemini"], "paused")
        self.sdk.assert_not_called()

    def test_explicit_model_identity_is_persisted_and_health_stays_unverified(self):
        with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-2.5-flash"}):
            result = self.upload()
            analysis = result["llm_analysis"][0]["analysis_result"]
            self.assertEqual(analysis["model_identifier"], "gemini-2.5-flash")
            self.assertEqual(analysis["analysis"], "synthetic-analysis")
            self.assertEqual(self.client.get("/api/health").json()["services"]["gemini"], "configured_unverified")
        self.sdk.assert_called_once_with("gemini-2.5-flash")
        self.sdk.return_value.generate_content.assert_called_once()

    def test_no_key_is_unavailable_and_never_creates_an_sdk_model(self):
        self.server.GEMINI_API_KEY = None
        self.assertEqual(self.client.get("/api/health").json()["services"]["gemini"], "unavailable")
        self.assertEqual(self.upload()["llm_analysis"], [])
        self.sdk.assert_not_called()


if __name__ == "__main__":
    unittest.main()
