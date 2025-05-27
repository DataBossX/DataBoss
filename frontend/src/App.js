import React, { useState, useEffect } from 'react';
import './App.css';

const App = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [documents, setDocuments] = useState([]);
  const [systemLogs, setSystemLogs] = useState([]);
  const [analytics, setAnalytics] = useState({});
  const [systemHealth, setSystemHealth] = useState({});
  const [uploadStatus, setUploadStatus] = useState(null);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [documentDetails, setDocumentDetails] = useState(null);

  const backendUrl = process.env.REACT_APP_BACKEND_URL;

  // Fetch data functions
  const fetchDocuments = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/documents`);
      const data = await response.json();
      setDocuments(data);
    } catch (error) {
      console.error('Error fetching documents:', error);
    }
  };

  const fetchSystemLogs = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/logs`);
      const data = await response.json();
      setSystemLogs(data);
    } catch (error) {
      console.error('Error fetching logs:', error);
    }
  };

  const fetchAnalytics = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/analytics`);
      const data = await response.json();
      setAnalytics(data);
    } catch (error) {
      console.error('Error fetching analytics:', error);
    }
  };

  const fetchSystemHealth = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/health`);
      const data = await response.json();
      setSystemHealth(data);
    } catch (error) {
      console.error('Error fetching system health:', error);
    }
  };

  const fetchDocumentDetails = async (documentId) => {
    try {
      const response = await fetch(`${backendUrl}/api/documents/${documentId}`);
      const data = await response.json();
      setDocumentDetails(data);
    } catch (error) {
      console.error('Error fetching document details:', error);
    }
  };

  // Upload file function
  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploadStatus('uploading');

    try {
      const response = await fetch(`${backendUrl}/api/documents/upload`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setUploadStatus('success');
        fetchDocuments();
        setTimeout(() => setUploadStatus(null), 3000);
      } else {
        setUploadStatus('error');
        setTimeout(() => setUploadStatus(null), 3000);
      }
    } catch (error) {
      console.error('Error uploading file:', error);
      setUploadStatus('error');
      setTimeout(() => setUploadStatus(null), 3000);
    }

    event.target.value = '';
  };

  // Auto-refresh data
  useEffect(() => {
    fetchDocuments();
    fetchSystemLogs();
    fetchAnalytics();
    fetchSystemHealth();

    const interval = setInterval(() => {
      fetchDocuments();
      fetchSystemLogs();
      fetchAnalytics();
      fetchSystemHealth();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // Refresh document details when selected document changes
  useEffect(() => {
    if (selectedDocument) {
      fetchDocumentDetails(selectedDocument.id);
    }
  }, [selectedDocument]);

  const StatusBadge = ({ status }) => {
    const statusColors = {
      uploaded: 'bg-blue-500',
      processing: 'bg-yellow-500 animate-pulse',
      completed: 'bg-green-500',
      failed: 'bg-red-500'
    };

    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium text-white ${statusColors[status] || 'bg-gray-500'}`}>
        {status.toUpperCase()}
      </span>
    );
  };

  const ServiceStatus = ({ serviceName, isAvailable }) => (
    <div className="flex items-center space-x-2">
      <div className={`w-3 h-3 rounded-full ${isAvailable ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
      <span className="text-cyan-300">{serviceName}</span>
      <span className={`text-xs ${isAvailable ? 'text-green-400' : 'text-red-400'}`}>
        {isAvailable ? 'ONLINE' : 'OFFLINE'}
      </span>
    </div>
  );

  const renderDashboard = () => (
    <div className="space-y-6">
      {/* System Health Panel */}
      <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
        <h3 className="text-xl font-bold text-cyan-400 mb-4 flex items-center">
          <span className="mr-2">⚡</span> SYSTEM STATUS
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <ServiceStatus serviceName="OCR Engine" isAvailable={true} />
          <ServiceStatus serviceName="OpenAI GPT" isAvailable={systemHealth.services?.openai === 'available'} />
          <ServiceStatus serviceName="Anthropic Claude" isAvailable={systemHealth.services?.anthropic === 'available'} />
          <ServiceStatus serviceName="Google Gemini" isAvailable={systemHealth.services?.gemini === 'available'} />
        </div>
      </div>

      {/* Analytics Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
          <h4 className="text-lg font-bold text-cyan-400 mb-2">📊 TOTAL DOCUMENTS</h4>
          <div className="text-3xl font-bold text-white">
            {Object.values(analytics.document_stats || {}).reduce((a, b) => a + b, 0)}
          </div>
        </div>
        
        <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
          <h4 className="text-lg font-bold text-cyan-400 mb-2">🎯 AVG CONFIDENCE</h4>
          <div className="text-3xl font-bold text-white">
            {((analytics.ocr_metrics?.avg_confidence || 0) * 100).toFixed(1)}%
          </div>
        </div>
        
        <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
          <h4 className="text-lg font-bold text-cyan-400 mb-2">📈 24H UPLOADS</h4>
          <div className="text-3xl font-bold text-white">
            {analytics.recent_activity?.uploads_24h || 0}
          </div>
        </div>
      </div>

      {/* Recent Documents */}
      <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
        <h3 className="text-xl font-bold text-cyan-400 mb-4">📋 RECENT DOCUMENTS</h3>
        <div className="space-y-2">
          {documents.slice(0, 5).map(doc => (
            <div key={doc.id} className="flex items-center justify-between p-3 bg-gray-700 rounded border border-gray-600">
              <div className="flex items-center space-x-4">
                <span className="text-white font-medium">{doc.filename}</span>
                <StatusBadge status={doc.status} />
              </div>
              <div className="text-sm text-gray-400">
                {new Date(doc.upload_time).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderOCRControl = () => (
    <div className="space-y-6">
      {/* Upload Area */}
      <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
        <h3 className="text-xl font-bold text-cyan-400 mb-4">🔍 OCR DOCUMENT PROCESSOR</h3>
        
        <div className="border-2 border-dashed border-cyan-500 rounded-lg p-8 text-center">
          <input
            type="file"
            onChange={handleFileUpload}
            accept=".pdf,.png,.jpg,.jpeg,.bmp,.tiff"
            className="hidden"
            id="fileUpload"
          />
          <label htmlFor="fileUpload" className="cursor-pointer">
            <div className="text-4xl text-cyan-400 mb-4">📁</div>
            <div className="text-lg text-white mb-2">DROP FILES OR CLICK TO UPLOAD</div>
            <div className="text-sm text-gray-400">Supports: PDF, PNG, JPG, JPEG, BMP, TIFF</div>
          </label>
          
          {uploadStatus && (
            <div className={`mt-4 p-3 rounded ${
              uploadStatus === 'uploading' ? 'bg-yellow-800 text-yellow-200' :
              uploadStatus === 'success' ? 'bg-green-800 text-green-200' :
              'bg-red-800 text-red-200'
            }`}>
              {uploadStatus === 'uploading' && '⏳ Processing...'}
              {uploadStatus === 'success' && '✅ Upload successful!'}
              {uploadStatus === 'error' && '❌ Upload failed!'}
            </div>
          )}
        </div>
      </div>

      {/* Document List */}
      <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
        <h3 className="text-xl font-bold text-cyan-400 mb-4">📄 PROCESSED DOCUMENTS</h3>
        <div className="space-y-2">
          {documents.map(doc => (
            <div
              key={doc.id}
              onClick={() => setSelectedDocument(doc)}
              className="flex items-center justify-between p-4 bg-gray-700 rounded border border-gray-600 cursor-pointer hover:border-cyan-400 transition-colors"
            >
              <div className="flex items-center space-x-4">
                <span className="text-white font-medium">{doc.filename}</span>
                <StatusBadge status={doc.status} />
                <span className="text-sm text-gray-400">{(doc.file_size / 1024).toFixed(1)} KB</span>
              </div>
              <div className="text-sm text-gray-400">
                {new Date(doc.upload_time).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Document Details Modal */}
      {selectedDocument && documentDetails && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6 max-w-4xl max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-bold text-cyan-400">📋 {selectedDocument.filename}</h3>
              <button
                onClick={() => {setSelectedDocument(null); setDocumentDetails(null);}}
                className="text-red-400 hover:text-red-300 text-2xl"
              >
                ✕
              </button>
            </div>
            
            {/* OCR Results */}
            {documentDetails.ocr_results?.map(ocr => (
              <div key={ocr.id} className="mb-6">
                <h4 className="text-lg font-bold text-cyan-400 mb-2">🔍 OCR RESULTS</h4>
                <div className="bg-gray-700 p-4 rounded border border-gray-600">
                  <div className="mb-2 text-sm text-gray-400">
                    Confidence: {(ocr.confidence_score * 100).toFixed(1)}% | 
                    Processing Time: {ocr.processing_time.toFixed(2)}s
                  </div>
                  <div className="text-white max-h-40 overflow-y-auto">
                    {ocr.cleaned_text}
                  </div>
                </div>
              </div>
            ))}

            {/* LLM Analysis */}
            {documentDetails.llm_analysis?.map(analysis => (
              <div key={analysis.id} className="mb-4">
                <h4 className="text-lg font-bold text-cyan-400 mb-2">🤖 {analysis.model_name.toUpperCase()} ANALYSIS</h4>
                <div className="bg-gray-700 p-4 rounded border border-gray-600">
                  <div className="mb-2 text-sm text-gray-400">
                    Processing Time: {analysis.processing_time.toFixed(2)}s
                  </div>
                  <div className="text-white">
                    {analysis.analysis_result.analysis}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  const renderLogs = () => (
    <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
      <h3 className="text-xl font-bold text-cyan-400 mb-4">📊 SYSTEM LOGS</h3>
      <div className="space-y-2 max-h-[600px] overflow-y-auto">
        {systemLogs.map(log => (
          <div key={log.id} className={`p-3 rounded border ${
            log.level === 'ERROR' ? 'bg-red-900 border-red-600' :
            log.level === 'WARNING' ? 'bg-yellow-900 border-yellow-600' :
            'bg-gray-700 border-gray-600'
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  log.level === 'ERROR' ? 'bg-red-600 text-white' :
                  log.level === 'WARNING' ? 'bg-yellow-600 text-white' :
                  'bg-blue-600 text-white'
                }`}>
                  {log.level}
                </span>
                <span className="text-cyan-400 font-medium">{log.component}</span>
              </div>
              <span className="text-sm text-gray-400">
                {new Date(log.created_at).toLocaleString()}
              </span>
            </div>
            <div className="text-white mt-2">{log.message}</div>
            {log.details && (
              <div className="text-gray-400 text-sm mt-1">
                {JSON.stringify(log.details, null, 2)}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );

  const renderDataViewer = () => (
    <div className="space-y-6">
      <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
        <h3 className="text-xl font-bold text-cyan-400 mb-4">📈 DATA ANALYTICS</h3>
        
        {/* Document Status Distribution */}
        <div className="mb-6">
          <h4 className="text-lg font-bold text-cyan-400 mb-2">Document Status Distribution</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(analytics.document_stats || {}).map(([status, count]) => (
              <div key={status} className="bg-gray-700 p-4 rounded border border-gray-600">
                <div className="text-2xl font-bold text-white">{count}</div>
                <div className="text-sm text-gray-400">{status.toUpperCase()}</div>
              </div>
            ))}
          </div>
        </div>

        {/* LLM Usage Stats */}
        <div className="mb-6">
          <h4 className="text-lg font-bold text-cyan-400 mb-2">AI Model Usage</h4>
          <div className="space-y-2">
            {Object.entries(analytics.llm_usage || {}).map(([model, count]) => (
              <div key={model} className="flex items-center justify-between p-3 bg-gray-700 rounded border border-gray-600">
                <span className="text-white font-medium">{model.toUpperCase()}</span>
                <span className="text-cyan-400 font-bold">{count} analyses</span>
              </div>
            ))}
          </div>
        </div>

        {/* Performance Metrics */}
        <div>
          <h4 className="text-lg font-bold text-cyan-400 mb-2">Performance Metrics</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-gray-700 p-4 rounded border border-gray-600">
              <div className="text-lg font-bold text-white">
                {((analytics.ocr_metrics?.avg_confidence || 0) * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-gray-400">Average OCR Confidence</div>
            </div>
            <div className="bg-gray-700 p-4 rounded border border-gray-600">
              <div className="text-lg font-bold text-white">
                {(analytics.ocr_metrics?.avg_processing_time || 0).toFixed(2)}s
              </div>
              <div className="text-sm text-gray-400">Average Processing Time</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const tabs = [
    { id: 'dashboard', label: '🏠 Dashboard', component: renderDashboard },
    { id: 'ocr', label: '🔍 OCR Control', component: renderOCRControl },
    { id: 'logs', label: '📊 Logs Viewer', component: renderLogs },
    { id: 'data', label: '📈 Data Viewer', component: renderDataViewer },
  ];

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header */}
      <header className="bg-gray-900 border-b-2 border-cyan-500 p-4">
        <div className="container mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="text-3xl font-bold text-cyan-400">⚡ DATABOSSX</div>
            <div className="text-sm text-gray-400">AI-Powered Offline Control Center</div>
          </div>
          <div className="flex items-center space-x-2">
            <div className={`w-3 h-3 rounded-full ${systemHealth.status === 'healthy' ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
            <span className="text-cyan-300">{systemHealth.status?.toUpperCase() || 'UNKNOWN'}</span>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-gray-800 border-b border-cyan-500">
        <div className="container mx-auto">
          <div className="flex space-x-0">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-6 py-4 font-medium border-r border-gray-700 transition-colors ${
                  activeTab === tab.id
                    ? 'bg-cyan-500 text-black'
                    : 'text-cyan-400 hover:bg-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="container mx-auto p-6">
        {tabs.find(tab => tab.id === activeTab)?.component()}
      </main>

      {/* Footer */}
      <footer className="bg-gray-900 border-t border-cyan-500 p-4 mt-auto">
        <div className="container mx-auto text-center text-gray-400">
          <div>DataBossX v1.0.0 | Offline-First AI Document Processing | 
            <span className="text-cyan-400 ml-2">
              {new Date().toLocaleString()}
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;