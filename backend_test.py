import requests
import unittest
import os
import time
from datetime import datetime

class DataBossXAPITester(unittest.TestCase):
    BASE_URL_DEFAULT = "http://localhost:8001"

    def __init__(self, *args, **kwargs):
        super(DataBossXAPITester, self).__init__(*args, **kwargs)
        self.base_url = self._resolve_base_url()
        print(f"Using backend URL: {self.base_url}")

        # Keep the sample document next to this test so it works outside the
        # original /app Docker layout (e.g. CI runners), where /app is absent.
        self.sample_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'sample_document.txt')
        if not os.path.exists(self.sample_file_path):
            with open(self.sample_file_path, 'w') as f:
                f.write(f"This is a sample document for testing.\nCreated at: {datetime.now()}\n\nThis document contains test content for the DataBossX OCR and LLM processing pipeline.\n\nTest data includes:\n- Legal information\n- Sample contract clauses\n- Test identifiers\n\nThis is for testing purposes only.")

    @staticmethod
    def _resolve_base_url():
        # Prefer the frontend .env (original Docker layout), then an env var,
        # then a localhost default — never crash if none are present.
        env_path = '/app/frontend/.env'
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if line.startswith('REACT_APP_BACKEND_URL='):
                        return line.strip().split('=')[1].strip('"\'')
        return os.environ.get('REACT_APP_BACKEND_URL',
                              DataBossXAPITester.BASE_URL_DEFAULT)

    def setUp(self):
        # These are live integration tests. When no backend is reachable
        # (e.g. CI without a running server) skip cleanly instead of erroring.
        try:
            requests.get(f"{self.base_url}/api/health", timeout=2)
        except requests.exceptions.RequestException:
            self.skipTest(f"backend not reachable at {self.base_url}; "
                          "skipping live integration test")

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
