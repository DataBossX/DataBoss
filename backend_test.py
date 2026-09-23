import requests
import unittest
import os
import sys
import time
import asyncio
import tempfile
import shutil
import importlib
import importlib.util
from datetime import datetime

try:
    from fastapi.testclient import TestClient
    from fastapi import HTTPException
    _FASTAPI_TESTCLIENT_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when fastapi/httpx missing
    TestClient = None
    HTTPException = None
    _FASTAPI_TESTCLIENT_AVAILABLE = False


def _resolve_backend_url():
    """Determine the backend URL from env vars or the frontend .env file.

    Returns None when it cannot be determined (e.g. in a bare CI runner) so the
    live-integration tests below can be skipped instead of erroring out.
    """
    url = os.environ.get("BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL")
    if url:
        return url.strip().strip('"\'')
    env_path = os.environ.get("FRONTEND_ENV_PATH", "/app/frontend/.env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.strip().split("=", 1)[1].strip('"\'')
    return None


BASE_URL = _resolve_backend_url()

# These are live integration tests that require a running backend. When no
# backend URL is available (the normal case in CI), the whole class is skipped,
# so the tests are still collected and reported as skipped (a clean, passing
# run) instead of erroring on a missing .env / server.
@unittest.skipUnless(
    BASE_URL is not None,
    "No backend URL available (set BACKEND_URL, REACT_APP_BACKEND_URL, or "
    "provide frontend/.env); skipping DataBossX API integration tests.",
)
class DataBossXAPITester(unittest.TestCase):
    def setUp(self):
        self.base_url = BASE_URL
        print(f"Using backend URL: {self.base_url}")
        self.sample_file_path = os.environ.get(
            "SAMPLE_FILE_PATH",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_document.txt"),
        )

        # Create a sample document if it doesn't exist
        if not os.path.exists(self.sample_file_path):
            with open(self.sample_file_path, "w") as f:
                f.write(
                    f"This is a sample document for testing.\nCreated at: {datetime.now()}\n\n"
                    "This document contains test content for the DataBossX OCR and LLM processing pipeline.\n\n"
                    "Test data includes:\n- Legal information\n- Sample contract clauses\n- Test identifiers\n\n"
                    "This is for testing purposes only."
                )
    
    def test_01_health_check(self):
        """Test the health check endpoint"""
        print("\n🔍 Testing health check endpoint...")
        response = requests.get(f"{self.base_url}/api/health")
        
        self.assertEqual(response.status_code, 200, "Health check should return 200")
        data = response.json()
        self.assertEqual(data['status'], 'healthy', "System status should be 'healthy'")
        self.assertIn('services', data, "Response should include services information")
        self.assertIn('ocr', data['services'], "Services should include OCR status")
        
        print("✅ Health check endpoint test passed")
        return data
    
    def test_02_document_upload(self):
        """Test document upload endpoint"""
        print("\n🔍 Testing document upload endpoint...")
        
        # Check if sample file exists
        self.assertTrue(os.path.exists(self.sample_file_path), "Sample document should exist")
        
        with open(self.sample_file_path, 'rb') as f:
            files = {'file': ('sample_document.txt', f, 'text/plain')}
            response = requests.post(f"{self.base_url}/api/documents/upload", files=files)
        
        self.assertIn(response.status_code, [200, 201, 409], 
                     f"Upload should return 200, 201 or 409 (if duplicate), got {response.status_code}")
        
        data = response.json()
        if response.status_code == 409:
            self.assertIn('error', data, "Duplicate response should include error message")
            self.assertIn('document_id', data, "Duplicate response should include document_id")
            print("ℹ️ Document already exists (409), which is acceptable")
        else:
            self.assertIn('document_id', data, "Response should include document_id")
            self.assertIn('status', data, "Response should include status")
            self.assertEqual(data['status'], 'processing', "Initial status should be 'processing'")
        
        print("✅ Document upload endpoint test passed")
        return data.get('document_id')
    
    def test_03_get_documents(self):
        """Test get documents endpoint"""
        print("\n🔍 Testing get documents endpoint...")
        response = requests.get(f"{self.base_url}/api/documents")
        
        self.assertEqual(response.status_code, 200, "Get documents should return 200")
        data = response.json()
        self.assertIsInstance(data, list, "Response should be a list")
        
        if len(data) > 0:
            document = data[0]
            self.assertIn('id', document, "Document should have id")
            self.assertIn('filename', document, "Document should have filename")
            self.assertIn('status', document, "Document should have status")
        
        print(f"✅ Get documents endpoint test passed, found {len(data)} documents")
        return data
    
    def test_04_get_document_details(self):
        """Test get document details endpoint"""
        print("\n🔍 Testing get document details endpoint...")
        
        # First get the list of documents
        documents = self.test_03_get_documents()
        
        if not documents:
            print("⚠️ No documents found to test details endpoint")
            return None
        
        # Get details of the first document
        doc_id = documents[0]['id']
        response = requests.get(f"{self.base_url}/api/documents/{doc_id}")
        
        self.assertEqual(response.status_code, 200, f"Get document details should return 200, got {response.status_code}")
        data = response.json()
        
        self.assertIn('document', data, "Response should include document info")
        self.assertEqual(data['document']['id'], doc_id, "Document ID should match")
        
        # Check if OCR results exist (they might not if processing is still ongoing)
        if 'ocr_results' in data and data['ocr_results']:
            self.assertIn('raw_text', data['ocr_results'][0], "OCR results should include raw_text")
            self.assertIn('confidence_score', data['ocr_results'][0], "OCR results should include confidence_score")
        
        print("✅ Get document details endpoint test passed")
        return data
    
    def test_05_get_analytics(self):
        """Test get analytics endpoint"""
        print("\n🔍 Testing analytics endpoint...")
        response = requests.get(f"{self.base_url}/api/analytics")
        
        self.assertEqual(response.status_code, 200, "Get analytics should return 200")
        data = response.json()
        
        self.assertIn('document_stats', data, "Response should include document_stats")
        self.assertIn('ocr_metrics', data, "Response should include ocr_metrics")
        self.assertIn('llm_usage', data, "Response should include llm_usage")
        self.assertIn('recent_activity', data, "Response should include recent_activity")
        
        print("✅ Analytics endpoint test passed")
        return data
    
    def test_06_get_logs(self):
        """Test get logs endpoint"""
        print("\n🔍 Testing logs endpoint...")
        response = requests.get(f"{self.base_url}/api/logs")
        
        self.assertEqual(response.status_code, 200, "Get logs should return 200")
        data = response.json()
        
        self.assertIsInstance(data, list, "Response should be a list")
        
        if len(data) > 0:
            log = data[0]
            self.assertIn('id', log, "Log should have id")
            self.assertIn('level', log, "Log should have level")
            self.assertIn('message', log, "Log should have message")
            self.assertIn('component', log, "Log should have component")
        
        print(f"✅ Logs endpoint test passed, found {len(data)} logs")
        return data
    
    def test_07_document_processing_workflow(self):
        """Test the complete document processing workflow"""
        print("\n🔍 Testing complete document processing workflow...")
        
        # 1. Upload a document
        doc_id = self.test_02_document_upload()
        if not doc_id and isinstance(doc_id, str):
            # If we got a 409 (duplicate), get the first document from the list
            documents = self.test_03_get_documents()
            if documents:
                doc_id = documents[0]['id']
            else:
                self.fail("No document ID available for workflow test")
        
        # 2. Wait for processing to complete (max 30 seconds)
        max_attempts = 6
        for attempt in range(max_attempts):
            print(f"Checking document status (attempt {attempt+1}/{max_attempts})...")
            response = requests.get(f"{self.base_url}/api/documents/{doc_id}")
            data = response.json()
            
            if data['document']['status'] in ['completed', 'failed']:
                break
                
            time.sleep(5)
        
        # 3. Verify final document status
        response = requests.get(f"{self.base_url}/api/documents/{doc_id}")
        data = response.json()
        
        self.assertIn(data['document']['status'], ['completed', 'failed'], 
                     f"Document should be in 'completed' or 'failed' state, got {data['document']['status']}")
        
        if data['document']['status'] == 'completed':
            # 4. Check for OCR results
            self.assertTrue(len(data['ocr_results']) > 0, "Completed document should have OCR results")
            
            # 5. Check for LLM analysis (if any LLM is available)
            health = self.test_01_health_check()
            llm_available = any(status == 'available' for service, status in health['services'].items() 
                               if service in ['openai', 'anthropic', 'gemini'])
            
            if llm_available:
                self.assertTrue(len(data.get('llm_analysis', [])) > 0, 
                              "Document should have LLM analysis when LLMs are available")
        
        print("✅ Document processing workflow test completed")
        return data

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_SERVER_PATH = os.path.join(_REPO_ROOT, "backend", "server.py")

_SECURITY_ENV_KEYS = [
    "DATABOSSX_API_KEY",
    "DATABOSSX_ALLOWED_ORIGINS",
    "DATABOSSX_DEMO_MODE",
    "DATABOSSX_MAX_UPLOAD_SIZE_BYTES",
    "DATABOSSX_ALLOWED_CONTENT_TYPES",
    "DATABOSSX_HOST",
    "DATABOSSX_PORT",
]


def _load_server_module(env_overrides, db_path):
    """Import backend/server.py fresh under a controlled environment.

    A brand-new module object is returned each call, so module-level state
    (the `settings` singleton built from env vars, the FastAPI `app`) reflects
    exactly `env_overrides`, independent of any other test or the real
    process environment. Used by the issue #94 regression tests below so each
    scenario (demo mode on/off, API key set/unset, custom CORS allowlist) gets
    its own isolated backend instance.
    """
    saved = {key: os.environ.get(key) for key in _SECURITY_ENV_KEYS + ["SQLITE_DB_PATH"]}
    try:
        for key in _SECURITY_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ.update(env_overrides)
        os.environ["SQLITE_DB_PATH"] = db_path

        sys.modules.pop("server", None)
        spec = importlib.util.spec_from_file_location("server", _SERVER_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules["server"] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@unittest.skipUnless(
    _FASTAPI_TESTCLIENT_AVAILABLE,
    "fastapi/httpx TestClient not installed; skipping in-process backend "
    "security regression tests (issue #94).",
)
class DataBossXSecurityRegressionTests(unittest.TestCase):
    """In-process regression tests for issue #94 items 4-6.

    These do not depend on a live server (unlike DataBossXAPITester above):
    they import backend/server.py directly and drive it with FastAPI's
    TestClient, so they run in any environment that has the backend's own
    dependencies installed.
    """

    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp(prefix="databossx_test_")
        self.addCleanup(shutil.rmtree, self._tmp_dir, ignore_errors=True)

    def _db_path(self, name):
        return os.path.join(self._tmp_dir, name)

    # -- Test 1: every non-health data endpoint requires authentication -----
    def test_data_endpoints_reject_unauthenticated_requests(self):
        module = _load_server_module(
            {"DATABOSSX_API_KEY": "correct-horse-battery-staple"},
            self._db_path("auth.db"),
        )
        with TestClient(module.app) as client:
            # Health check stays open.
            self.assertEqual(client.get("/api/health").status_code, 200)

            protected_requests = [
                ("GET", "/api/documents"),
                ("GET", "/api/documents/does-not-exist"),
                ("GET", "/api/logs"),
                ("GET", "/api/analytics"),
            ]
            for method, path in protected_requests:
                with self.subTest(endpoint=path, auth="missing"):
                    response = client.request(method, path)
                    self.assertIn(
                        response.status_code, (401, 403),
                        f"{path} should reject an unauthenticated request, got {response.status_code}",
                    )
                with self.subTest(endpoint=path, auth="wrong"):
                    response = client.request(method, path, headers={"X-API-Key": "wrong-key"})
                    self.assertIn(
                        response.status_code, (401, 403),
                        f"{path} should reject a wrong API key, got {response.status_code}",
                    )
                with self.subTest(endpoint=path, auth="correct"):
                    response = client.request(
                        method, path, headers={"X-API-Key": "correct-horse-battery-staple"}
                    )
                    self.assertNotIn(response.status_code, (401, 403))

            # Upload endpoint: unauthenticated multipart POST must also be rejected.
            files = {"file": ("sample.txt", b"hello world", "text/plain")}
            response = client.post("/api/documents/upload", files=files)
            self.assertIn(response.status_code, (401, 403))
            response = client.post(
                "/api/documents/upload", files=files, headers={"X-API-Key": "wrong-key"}
            )
            self.assertIn(response.status_code, (401, 403))

    def test_data_endpoints_reject_when_no_api_key_configured(self):
        """Fail closed: with DATABOSSX_API_KEY unset, nothing gets in - not even a blank key."""
        module = _load_server_module({}, self._db_path("noauth.db"))
        self.assertIsNone(module.settings.api_key)
        with TestClient(module.app) as client:
            response = client.get("/api/documents", headers={"X-API-Key": ""})
            self.assertIn(response.status_code, (401, 403))
            response = client.get("/api/documents")
            self.assertIn(response.status_code, (401, 403))

    # -- Test 2: untrusted origins cannot make credentialed CORS requests ---
    def test_cors_never_combines_wildcard_with_credentials(self):
        module = _load_server_module(
            {"DATABOSSX_API_KEY": "test-key", "DATABOSSX_ALLOWED_ORIGINS": "*"},
            self._db_path("cors_wildcard.db"),
        )
        # Even if misconfigured with "*", the loaded settings must never expose
        # a wildcard origin while credentials are allowed.
        self.assertNotIn("*", module.settings.allowed_origins)

    def test_cors_rejects_untrusted_origin_for_credentialed_request(self):
        module = _load_server_module(
            {
                "DATABOSSX_API_KEY": "test-key",
                "DATABOSSX_ALLOWED_ORIGINS": "https://trusted.databossx.example",
            },
            self._db_path("cors_allowlist.db"),
        )
        self.assertNotIn("*", module.settings.allowed_origins)

        with TestClient(module.app) as client:
            # An origin not on the allowlist must not be reflected back.
            response = client.get(
                "/api/health",
                headers={"Origin": "https://evil.attacker.example"},
            )
            self.assertNotEqual(
                response.headers.get("access-control-allow-origin"),
                "https://evil.attacker.example",
            )
            self.assertIsNone(response.headers.get("access-control-allow-origin"))

            # A trusted origin is allowed through with credentials support.
            response = client.get(
                "/api/health",
                headers={"Origin": "https://trusted.databossx.example"},
            )
            self.assertEqual(
                response.headers.get("access-control-allow-origin"),
                "https://trusted.databossx.example",
            )
            self.assertEqual(response.headers.get("access-control-allow-credentials"), "true")

    # -- Test 3: outside demo mode, mock OCR fails closed and never fabricates content --
    def test_ocr_fails_closed_outside_demo_mode(self):
        module = _load_server_module(
            {"DATABOSSX_API_KEY": "test-key", "DATABOSSX_DEMO_MODE": "false"},
            self._db_path("ocr_real.db"),
        )
        self.assertFalse(module.settings.demo_mode)

        async def _run():
            return await module.process_ocr(b"real uploaded file bytes", "real_document.pdf")

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(_run())
        self.assertEqual(ctx.exception.status_code, 503)
        # The failure detail must not itself contain any fabricated document content.
        self.assertNotIn("Parties", str(ctx.exception.detail))
        self.assertNotIn("DataBossX Corp", str(ctx.exception.detail))

    def test_ocr_demo_mode_output_is_unambiguously_labeled_synthetic(self):
        module = _load_server_module(
            {"DATABOSSX_API_KEY": "test-key", "DATABOSSX_DEMO_MODE": "true"},
            self._db_path("ocr_demo.db"),
        )
        self.assertTrue(module.settings.demo_mode)

        async def _run():
            return await module.process_ocr(b"anything", "some_document.pdf")

        result = asyncio.run(_run())
        self.assertTrue(result.get("is_synthetic"))
        self.assertIn("SYNTHETIC", result["raw_text"])
        # No invented legal-sounding facts (the original defect's fabricated
        # parties/summary text) should ever appear, even in demo mode.
        for fabricated_fact in ("Parties:", "DataBossX Corp", "Client ABC", "Sample Legal Document"):
            self.assertNotIn(fabricated_fact, result["raw_text"])
        # The old defect returned a fixed high confidence (0.95) for fabricated
        # output; the synthetic placeholder must not masquerade as confident.
        self.assertNotEqual(result["confidence_score"], 0.95)

    # -- Regression: PR review findings on the above fixes ------------------
    def test_health_check_reports_ocr_unavailable_outside_demo_mode(self):
        """/api/health must not claim OCR is available when it will fail closed."""
        module = _load_server_module(
            {"DATABOSSX_API_KEY": "test-key", "DATABOSSX_DEMO_MODE": "false"},
            self._db_path("health_real.db"),
        )
        with TestClient(module.app) as client:
            body = client.get("/api/health").json()
            self.assertNotEqual(body["services"]["ocr"], "available")

        module = _load_server_module(
            {"DATABOSSX_API_KEY": "test-key", "DATABOSSX_DEMO_MODE": "true"},
            self._db_path("health_demo.db"),
        )
        with TestClient(module.app) as client:
            body = client.get("/api/health").json()
            self.assertIn("demo", body["services"]["ocr"].lower())

    def test_upload_rejects_synchronously_when_ocr_unavailable(self):
        """An upload must not be accepted (200/"processing") only to fail
        invisibly in the background once OCR rejects it - the client should
        get the real 503 immediately, before any document record is created."""
        module = _load_server_module(
            {"DATABOSSX_API_KEY": "test-key", "DATABOSSX_DEMO_MODE": "false"},
            self._db_path("upload_no_ocr.db"),
        )
        with TestClient(module.app) as client:
            files = {"file": ("sample.pdf", b"%PDF-1.4 fake", "application/pdf")}
            response = client.post(
                "/api/documents/upload", files=files, headers={"X-API-Key": "test-key"}
            )
            self.assertEqual(response.status_code, 503)
            documents = client.get(
                "/api/documents", headers={"X-API-Key": "test-key"}
            ).json()
            self.assertEqual(documents, [], "no document record should be created for a rejected upload")


def run_tests():
    """Run all API tests"""
    print("🚀 Starting DataBossX API Tests")
    
    # Create a test suite
    suite = unittest.TestSuite()
    tester = DataBossXAPITester()
    
    # Add tests in order
    suite.addTest(DataBossXAPITester('test_01_health_check'))
    suite.addTest(DataBossXAPITester('test_02_document_upload'))
    suite.addTest(DataBossXAPITester('test_03_get_documents'))
    suite.addTest(DataBossXAPITester('test_04_get_document_details'))
    suite.addTest(DataBossXAPITester('test_05_get_analytics'))
    suite.addTest(DataBossXAPITester('test_06_get_logs'))
    suite.addTest(DataBossXAPITester('test_07_document_processing_workflow'))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n📊 Test Summary:")
    print(f"Total tests: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    return len(result.failures) + len(result.errors) == 0

if __name__ == "__main__":
    run_tests()
