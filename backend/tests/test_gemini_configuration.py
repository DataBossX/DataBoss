"""Exercise actual route functions without importing SDKs or starting a service."""
import ast
import asyncio
from datetime import datetime
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from typing import Any, Dict


BACKEND = Path(__file__).resolve().parents[1]


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def route_namespace():
    sdk = MagicMock()
    sdk.GenerativeModel.return_value.generate_content.return_value = SimpleNamespace(
        text="synthetic-result"
    )
    namespace = {
        "os": os, "datetime": datetime, "Dict": Dict, "Any": Any,
        "HTTPException": HTTPException, "GEMINI_API_KEY": "synthetic-placeholder",
        "openai_client": None, "anthropic_client": None,
        "genai": sdk, "logger": MagicMock(),
    }
    policy_path = BACKEND / "gemini_model_policy.py"
    if policy_path.exists():
        spec = importlib.util.spec_from_file_location("backend_gemini_policy", policy_path)
        policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy)
        namespace.update(resolve_text_model=policy.resolve_text_model,
                         GeminiModelConfigurationError=policy.GeminiModelConfigurationError)
    source = ast.parse((BACKEND / "server.py").read_text())
    names = {"health_check", "analyze_with_llm", "gemini_configuration_status"}
    nodes = [node for node in source.body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    for node in nodes:
        node.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "server.py", "exec"), namespace)
    return namespace, sdk


class BackendGeminiConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.ns, self.sdk = route_namespace()

    def health(self):
        return asyncio.run(self.ns["health_check"]())

    def analyze(self):
        return asyncio.run(self.ns["analyze_with_llm"]("synthetic", "gemini", "general_summary"))

    def test_key_without_model_is_paused_not_available(self):
        self.assertEqual(self.health()["services"]["gemini"], "paused")
        self.sdk.GenerativeModel.assert_not_called()

    def test_configured_model_does_not_claim_live_api_verification(self):
        os.environ["GEMINI_MODEL"] = "gemini-2.5-flash"
        result = self.health()
        self.assertEqual(result["services"]["gemini"], "configured_unverified")
        self.assertEqual(result["provider_configuration"]["gemini"]["live_api_verification"], "NOT_RUN")

    def test_absent_key_is_unavailable(self):
        self.ns["GEMINI_API_KEY"] = None
        self.assertEqual(self.health()["services"]["gemini"], "unavailable")

    def test_missing_model_refuses_transport_with_configuration_error(self):
        with self.assertRaises(HTTPException) as cm:
            self.analyze()
        self.assertEqual(cm.exception.status_code, 503)
        self.sdk.GenerativeModel.assert_not_called()

    def test_explicit_configuration_reaches_only_that_model(self):
        os.environ["GEMINI_MODEL"] = "gemini-2.5-flash"
        result = self.analyze()
        self.assertEqual(result["analysis"], "synthetic-result")
        self.assertEqual(result.get("model_identifier"), "gemini-2.5-flash")
        self.sdk.GenerativeModel.assert_called_once_with("gemini-2.5-flash")

    def test_retiring_or_incompatible_identifier_is_paused(self):
        for model in ["gemini-omni-flash-preview", "deep-research-pro-preview-12-2025",
                      "gemini-omni-1.1-flash", "gemini-1.5-flash"]:
            with self.subTest(model=model):
                os.environ["GEMINI_MODEL"] = model
                self.assertEqual(self.health()["services"]["gemini"], "paused")
                with self.assertRaises(HTTPException) as cm:
                    self.analyze()
                self.assertEqual(cm.exception.status_code, 503)
        self.sdk.GenerativeModel.assert_not_called()

    def test_other_provider_health_fields_are_preserved(self):
        result = self.health()
        self.assertEqual(result["services"]["openai"], "unavailable")
        self.assertEqual(result["services"]["anthropic"], "unavailable")
        self.assertEqual(result["services"]["ocr"], "available")


if __name__ == "__main__":
    unittest.main()
