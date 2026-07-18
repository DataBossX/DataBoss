import React, { useState, useEffect } from 'react';
import './App.css';

const App = () => {
  const [activeTab, setActiveTab] = useState('landman');
  const [documents, setDocuments] = useState([]);
  const [systemLogs, setSystemLogs] = useState([]);
  const [analytics, setAnalytics] = useState({});
  const [systemHealth, setSystemHealth] = useState({});
  const [uploadStatus, setUploadStatus] = useState(null);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [documentDetails, setDocumentDetails] = useState(null);

  // Landman Title Intelligence state
  const [landmanProjects, setLandmanProjects] = useState([]);
  const [landmanView, setLandmanView] = useState('list');
  const [currentProject, setCurrentProject] = useState(null);
  const [landmanStatus, setLandmanStatus] = useState(null);
  const [npName, setNpName] = useState('');
  const [npSection, setNpSection] = useState('');
  const [deedText, setDeedText] = useState('');

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

  // ----- Landman Title Intelligence actions -----
  const fetchLandmanProjects = async () => {
    try {
      const r = await fetch(`${backendUrl}/api/landman/projects`);
      setLandmanProjects(await r.json());
    } catch (error) {
      console.error('Error fetching title projects:', error);
    }
  };

  const openProject = async (projectId) => {
    try {
      const r = await fetch(`${backendUrl}/api/landman/projects/${projectId}`);
      setCurrentProject(await r.json());
      setLandmanView('detail');
    } catch (error) {
      console.error('Error opening project:', error);
    }
  };

  const createDemoProject = async () => {
    setLandmanStatus('Seeding demo corpus & reconciling chain of title…');
    try {
      const r = await fetch(`${backendUrl}/api/landman/demo`, { method: 'POST' });
      const data = await r.json();
      await fetchLandmanProjects();
      await openProject(data.project.project_id);
    } catch (error) {
      console.error('Demo failed:', error);
    }
    setLandmanStatus(null);
  };

  const createProject = async () => {
    if (!npName.trim()) return;
    setLandmanStatus('Creating title project…');
    try {
      const r = await fetch(`${backendUrl}/api/landman/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: npName, section: npSection || null }),
      });
      const p = await r.json();
      setNpName('');
      setNpSection('');
      await fetchLandmanProjects();
      await openProject(p.project_id);
    } catch (error) {
      console.error('Create failed:', error);
    }
    setLandmanStatus(null);
  };

  const uploadLandmanDoc = async (event) => {
    const file = event.target.files[0];
    if (!file || !currentProject) return;
    const fd = new FormData();
    fd.append('file', file);
    setLandmanStatus(`Vaulting & extracting ${file.name}…`);
    try {
      await fetch(`${backendUrl}/api/landman/projects/${currentProject.project.project_id}/documents`, {
        method: 'POST',
        body: fd,
      });
      await openProject(currentProject.project.project_id);
    } catch (error) {
      console.error('Upload failed:', error);
    }
    setLandmanStatus(null);
    event.target.value = '';
  };

  const addDeedText = async () => {
    if (!deedText.trim() || !currentProject) return;
    setLandmanStatus('Extracting conveyance from pasted text…');
    try {
      await fetch(`${backendUrl}/api/landman/projects/${currentProject.project.project_id}/documents/text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: `pasted_deed_${Date.now()}.txt`, text: deedText }),
      });
      setDeedText('');
      await openProject(currentProject.project.project_id);
    } catch (error) {
      console.error('Add failed:', error);
    }
    setLandmanStatus(null);
  };

  const runAnalysis = async () => {
    if (!currentProject) return;
    setLandmanStatus('Reconciling chain of title with exact fraction math…');
    try {
      await fetch(`${backendUrl}/api/landman/projects/${currentProject.project.project_id}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      await openProject(currentProject.project.project_id);
      await fetchLandmanProjects();
    } catch (error) {
      console.error('Analysis failed:', error);
    }
    setLandmanStatus(null);
  };

  const deleteProject = async (projectId) => {
    try {
      await fetch(`${backendUrl}/api/landman/projects/${projectId}`, { method: 'DELETE' });
      setCurrentProject(null);
      setLandmanView('list');
      await fetchLandmanProjects();
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  // Auto-refresh data
  useEffect(() => {
    fetchDocuments();
    fetchSystemLogs();
    fetchAnalytics();
    fetchSystemHealth();
    fetchLandmanProjects();

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

  const OverallBadge = ({ status }) => {
    const ok = status === 'CLEAR';
    return (
      <span className={`px-3 py-1 rounded-full text-xs font-bold ${ok ? 'bg-green-600 text-white' : 'bg-yellow-500 text-black'}`}>
        {status || 'PENDING'}
      </span>
    );
  };

  const renderLandmanList = () => (
    <div className="space-y-6">
      <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
        <h3 className="text-xl font-bold text-cyan-400 mb-2">⚖️ LANDMAN TITLE INTELLIGENCE</h3>
        <p className="text-gray-400 mb-4 text-sm">
          Upload title documents → deterministic extraction (grantor/grantee/interest/legal) →
          exact fraction chain-of-title reconciliation → current mineral ownership, net acres, and an
          examiner worklist. Evidence-vaulted and audited. Nothing is fabricated: unsupported balances
          are flagged <span className="text-yellow-400">Needs Examiner Review</span>.
        </p>
        <div className="flex flex-wrap gap-3 items-end">
          <button
            onClick={createDemoProject}
            className="bg-cyan-500 text-black font-bold px-4 py-2 rounded hover:bg-cyan-400 transition-colors"
          >
            🚀 Load Demo Project
          </button>
          <div className="flex-1 min-w-[240px]">
            <label className="block text-xs text-gray-400 mb-1">New project name</label>
            <input
              value={npName}
              onChange={(e) => setNpName(e.target.value)}
              placeholder="e.g. Section 14 Acquisition"
              className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-cyan-500 outline-none"
            />
          </div>
          <div className="min-w-[180px]">
            <label className="block text-xs text-gray-400 mb-1">Section (optional)</label>
            <input
              value={npSection}
              onChange={(e) => setNpSection(e.target.value)}
              placeholder="Section 14, T3N, R5W"
              className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-cyan-500 outline-none"
            />
          </div>
          <button
            onClick={createProject}
            className="border border-cyan-500 text-cyan-400 font-medium px-4 py-2 rounded hover:bg-gray-700 transition-colors"
          >
            + Create
          </button>
        </div>
      </div>

      <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
        <h3 className="text-lg font-bold text-cyan-400 mb-4">📁 TITLE PROJECTS</h3>
        {landmanProjects.length === 0 ? (
          <div className="text-gray-500 text-sm">No projects yet. Load the demo or create one above.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {landmanProjects.map((p) => (
              <div
                key={p.project_id}
                onClick={() => openProject(p.project_id)}
                className="bg-gray-700 border border-gray-600 rounded-lg p-4 cursor-pointer hover:border-cyan-400 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-white font-bold">{p.name}</span>
                  {p.latest_summary && <OverallBadge status={p.latest_summary.overall_status} />}
                </div>
                <div className="text-xs text-gray-400">{p.section || 'Section not set'}</div>
                <div className="text-xs text-gray-500 mt-2">
                  {p.document_count} document{p.document_count === 1 ? '' : 's'}
                  {p.latest_summary ? ` · ${p.latest_summary.tracts} tract(s)` : ' · not analyzed'}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  const activityLabels = {
    'project.created': '🆕 Project created',
    'run.seeded': '🧩 Workflow seeded',
    'source.registered': '🔌 Source registered',
    'source.inventory.completed': '🔒 Evidence inventoried',
    'document.registered': '📄 Document registered',
    'template.registered': '📐 Template registered',
    'title.analyzed': '⚙️ Title analyzed',
    'report.exported': '⬇️ Report exported',
  };

  const renderLandmanDetail = () => {
    const proj = currentProject.project;
    const analysis = currentProject.analysis;
    const documentsList = currentProject.documents || [];
    const activity = currentProject.activity || [];
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <button
            onClick={() => { setLandmanView('list'); setCurrentProject(null); }}
            className="text-cyan-400 hover:text-cyan-300 text-sm"
          >
            ← Back to projects
          </button>
          <button
            onClick={() => deleteProject(proj.project_id)}
            className="text-red-400 hover:text-red-300 text-sm"
          >
            Delete project
          </button>
        </div>

        <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="text-xl font-bold text-cyan-400">{proj.name}</h3>
              <div className="text-sm text-gray-400">
                {proj.section || 'Section not set'} · {proj.jurisdiction_code} · project {proj.project_id}
              </div>
            </div>
            {analysis && <OverallBadge status={analysis.summary.overall_status} />}
          </div>
        </div>

        {/* Workflow controls */}
        <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
          <h4 className="text-lg font-bold text-cyan-400 mb-4">📥 ADD DOCUMENTS & RECONCILE</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border-2 border-dashed border-cyan-500 rounded-lg p-4 text-center">
              <input type="file" onChange={uploadLandmanDoc} accept=".txt,.md,.csv,.pdf,.docx,.png,.jpg,.jpeg,.tiff,.tif,.bmp" className="hidden" id="landmanUpload" />
              <label htmlFor="landmanUpload" className="cursor-pointer">
                <div className="text-3xl text-cyan-400 mb-1">📄</div>
                <div className="text-sm text-white">UPLOAD TITLE DOCUMENT</div>
                <div className="text-xs text-gray-400">deed, assignment, lease — PDF / Word / scanned image (OCR) / text</div>
              </label>
            </div>
            <div>
              <textarea
                value={deedText}
                onChange={(e) => setDeedText(e.target.value)}
                placeholder="…or paste deed text here (e.g. 'Grantor: A  Grantee: B  conveys an undivided 1/2 interest … Section 14, T3N, R5W, 320 gross acres. Instrument No. 12345')"
                className="w-full h-24 bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white text-xs focus:border-cyan-500 outline-none"
              />
              <button onClick={addDeedText} className="mt-2 border border-cyan-500 text-cyan-400 text-sm px-3 py-1 rounded hover:bg-gray-700">
                + Add pasted document
              </button>
            </div>
          </div>
          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={runAnalysis}
              className="bg-cyan-500 text-black font-bold px-5 py-2 rounded hover:bg-cyan-400 transition-colors"
            >
              ⚙️ Run Title Analysis
            </button>
            <span className="text-xs text-gray-400">{documentsList.length} document(s) in project</span>
          </div>
        </div>

        {!analysis ? (
          <div className="bg-gray-800 border border-gray-600 rounded-lg p-6 text-gray-400 text-sm">
            No analysis yet. Add title documents, then run the analysis to reconcile the chain of title.
            {documentsList.length > 0 && (
              <ul className="mt-3 space-y-1">
                {documentsList.map((d, i) => (
                  <li key={i} className="text-gray-300">• {d.filename}</li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                ['DOCUMENTS', analysis.summary.documents],
                ['TRACTS', analysis.summary.tracts],
                ['CHAIN ROWS', analysis.summary.chain_rows],
                ['OVER-CONVEYANCES', analysis.summary.over_conveyances],
              ].map(([label, val]) => (
                <div key={label} className="bg-gray-800 border border-cyan-500 rounded-lg p-4">
                  <div className="text-xs text-gray-400">{label}</div>
                  <div className={`text-2xl font-bold ${label === 'OVER-CONVEYANCES' && val > 0 ? 'text-yellow-400' : 'text-white'}`}>{val}</div>
                </div>
              ))}
            </div>

            {/* Ownership ledger */}
            <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
              <h4 className="text-lg font-bold text-cyan-400 mb-3">🏆 CURRENT MINERAL OWNERSHIP</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-cyan-400 text-left border-b border-gray-600">
                      <th className="py-2 pr-4">Tract</th>
                      <th className="py-2 pr-4">Current owner</th>
                      <th className="py-2 pr-4">Interest</th>
                      <th className="py-2 pr-4">Net mineral acres</th>
                      <th className="py-2 pr-4">Ties out</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.ownership.map((o, i) => (
                      <tr key={i} className="border-b border-gray-700">
                        <td className="py-2 pr-4 text-gray-300">{o.tract_legal}</td>
                        <td className="py-2 pr-4 text-white font-medium">{o.current_owner}</td>
                        <td className="py-2 pr-4 text-cyan-300">{o.current_interest || '—'}</td>
                        <td className="py-2 pr-4 text-cyan-300">{o.net_mineral_acres || '—'}</td>
                        <td className="py-2 pr-4">
                          <span className={o.ties_out ? 'text-green-400' : 'text-yellow-400'}>
                            {o.ties_out ? 'yes' : 'REVIEW'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Chain of title */}
            <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
              <h4 className="text-lg font-bold text-cyan-400 mb-3">🔗 CHAIN OF TITLE</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-cyan-400 text-left border-b border-gray-600">
                      <th className="py-2 pr-3">Instrument</th>
                      <th className="py-2 pr-3">Grantor</th>
                      <th className="py-2 pr-3">Grantee</th>
                      <th className="py-2 pr-3">Conveyed</th>
                      <th className="py-2 pr-3">Retained</th>
                      <th className="py-2 pr-3">Net acres</th>
                      <th className="py-2 pr-3">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.chain_rows.map((r, i) => (
                      <tr key={i} className="border-b border-gray-700">
                        <td className="py-2 pr-3 text-gray-300">{r.instrument_number || '—'}</td>
                        <td className="py-2 pr-3 text-gray-300">{r.grantor || '—'}</td>
                        <td className="py-2 pr-3 text-gray-300">{r.grantee || '—'}</td>
                        <td className="py-2 pr-3 text-cyan-300">{r.conveyed_interest || '—'}</td>
                        <td className="py-2 pr-3 text-cyan-300">{r.retained_interest || '—'}</td>
                        <td className="py-2 pr-3 text-cyan-300">{r.net_mineral_acres || '—'}</td>
                        <td className={`py-2 pr-3 ${r.status === 'ok' ? 'text-green-400' : 'text-yellow-400'}`}>{r.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {analysis.chain_rows.some((r) => r.remarks) && (
                <div className="mt-3 text-xs text-gray-400 space-y-1">
                  {analysis.chain_rows.filter((r) => r.remarks).map((r, i) => (
                    <div key={i}>⚠️ <span className="text-yellow-400">{r.instrument_number}</span>: {r.remarks}</div>
                  ))}
                </div>
              )}
            </div>

            {/* Extracted documents */}
            <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
              <h4 className="text-lg font-bold text-cyan-400 mb-3">📑 EXTRACTED DOCUMENTS</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-cyan-400 text-left border-b border-gray-600">
                      <th className="py-2 pr-3">Document</th>
                      <th className="py-2 pr-3">Type</th>
                      <th className="py-2 pr-3">Grantor → Grantee</th>
                      <th className="py-2 pr-3">Interest</th>
                      <th className="py-2 pr-3">Confidence</th>
                      <th className="py-2 pr-3">Role</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documentsList.map((d, i) => (
                      <tr key={i} className="border-b border-gray-700">
                        <td className="py-2 pr-3 text-gray-300">
                          {d.filename}
                          {d.ocr_used && <span className="ml-2 px-1.5 py-0.5 rounded bg-purple-700 text-purple-100 text-[10px] font-bold">OCR</span>}
                        </td>
                        <td className="py-2 pr-3 text-gray-300">{d.doc_type || '—'}</td>
                        <td className="py-2 pr-3 text-gray-300">
                          {d.grantor || '?'} → {d.grantee || '?'}
                        </td>
                        <td className="py-2 pr-3 text-cyan-300">{d.conveyed_interest || '—'}</td>
                        <td className="py-2 pr-3 text-gray-300">{d.confidence != null ? `${Math.round(d.confidence * 100)}%` : '—'}</td>
                        <td className="py-2 pr-3">
                          <span className={d.is_conveyance ? 'text-green-400' : 'text-gray-500'}>
                            {d.is_conveyance ? 'conveyance' : 'supporting'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Validation / worklist */}
            <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
              <h4 className="text-lg font-bold text-cyan-400 mb-3">✅ VALIDATION & EXAMINER WORKLIST</h4>
              <div className="text-sm text-gray-300 mb-2">
                Golden-source gate: <span className={analysis.validation.passed ? 'text-green-400' : 'text-yellow-400'}>{analysis.validation.summary}</span>
              </div>
              {analysis.validation.issues.length === 0 ? (
                <div className="text-green-400 text-sm">No validation issues.</div>
              ) : (
                <ul className="space-y-1 text-xs">
                  {analysis.validation.issues.map((iss, i) => (
                    <li key={i} className="text-gray-300">
                      <span className={iss.severity === 'error' ? 'text-red-400' : 'text-yellow-400'}>[{iss.severity}]</span>{' '}
                      row {iss.row_index} · {iss.field}: {iss.message}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Generated report */}
            <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
              <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
                <h4 className="text-lg font-bold text-cyan-400">📝 CURSORY TITLE REPORT (DRAFT)</h4>
                <div className="flex gap-2">
                  <a
                    href={`${backendUrl}/api/landman/projects/${proj.project_id}/report.xlsx`}
                    className="border border-cyan-500 text-cyan-400 text-xs px-3 py-1 rounded hover:bg-gray-700"
                  >
                    ⬇️ Excel report
                  </a>
                  <a
                    href={`${backendUrl}/api/landman/projects/${proj.project_id}/worklist.csv`}
                    className="border border-cyan-500 text-cyan-400 text-xs px-3 py-1 rounded hover:bg-gray-700"
                  >
                    ⬇️ Examiner worklist (CSV)
                  </a>
                </div>
              </div>
              <pre className="bg-gray-900 border border-gray-700 rounded p-4 text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">{analysis.report_markdown}</pre>
            </div>
          </>
        )}

        {/* Project activity / audit trail */}
        <div className="bg-gray-800 border border-cyan-500 rounded-lg p-6">
          <h4 className="text-lg font-bold text-cyan-400 mb-3">🧾 PROJECT ACTIVITY (AUDIT TRAIL)</h4>
          {activity.length === 0 ? (
            <div className="text-gray-500 text-sm">No activity recorded yet.</div>
          ) : (
            <ul className="space-y-1 text-xs">
              {activity.map((ev, i) => (
                <li key={i} className="flex items-start gap-3 border-b border-gray-700 pb-1">
                  <span className="text-gray-500 whitespace-nowrap">{ev.created_at}</span>
                  <span className="text-cyan-300 whitespace-nowrap">{activityLabels[ev.event_type] || ev.event_type}</span>
                  <span className="text-gray-400 break-all">{ev.entity_type}:{ev.entity_id}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    );
  };

  const renderLandman = () => (
    <div className="space-y-4">
      {landmanStatus && (
        <div className="bg-cyan-900 border border-cyan-500 text-cyan-200 rounded-lg p-3 text-sm animate-pulse">
          ⏳ {landmanStatus}
        </div>
      )}
      {landmanView === 'detail' && currentProject ? renderLandmanDetail() : renderLandmanList()}
    </div>
  );

  const tabs = [
    { id: 'landman', label: '⚖️ Landman', component: renderLandman },
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