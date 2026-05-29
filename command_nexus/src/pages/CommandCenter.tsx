import { useState, useEffect } from 'react'
import { api, HealthStatus, Analytics, Document } from '../api/client'
import { Zap, Activity, Upload, FileText, Brain, AlertCircle, CheckCircle, Clock } from 'lucide-react'
import StatCard from '../components/StatCard'

function ServiceRow({ name, status }: { name: string; status: string }) {
  const online = status === 'available'
  return (
    <div className="flex items-center justify-between py-2 border-b border-nx-border/50 last:border-0">
      <span className="text-sm text-nx-text">{name}</span>
      <div className="flex items-center gap-2">
        <span className={online ? 'dot-online' : 'dot-offline'} />
        <span className={`text-xs font-bold ${online ? 'text-green-400' : 'text-red-400'}`}>
          {online ? 'ONLINE' : 'OFFLINE'}
        </span>
      </div>
    </div>
  )
}

export default function CommandCenter() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [analytics, setAnalytics] = useState<Analytics | null>(null)
  const [docs, setDocs] = useState<Document[]>([])
  const [error, setError] = useState<string | null>(null)

  async function load() {
    try {
      const [h, a, d] = await Promise.all([api.health(), api.analytics(), api.documents()])
      setHealth(h); setAnalytics(a); setDocs(d); setError(null)
    } catch {
      setError('Backend offline — start the API server on port 8001')
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 6000)
    return () => clearInterval(t)
  }, [])

  const totalDocs = Object.values(analytics?.document_stats ?? {}).reduce((a, b) => a + b, 0)
  const avgConf = ((analytics?.ocr_metrics?.avg_confidence ?? 0) * 100).toFixed(1)
  const uploads24h = analytics?.recent_activity?.uploads_24h ?? 0

  const docStatusBg: Record<string, string> = {
    uploaded:   'bg-blue-500/20 text-blue-300',
    processing: 'bg-yellow-500/20 text-yellow-300 animate-pulse',
    completed:  'bg-green-500/20 text-green-300',
    failed:     'bg-red-500/20 text-red-300',
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Zap className="text-cyan-400" size={20} />
            <h1 className="text-xl font-bold text-white tracking-wide">HQ DASHBOARD</h1>
          </div>
          <p className="text-sm text-nx-muted mt-0.5">DataBossX Command Nexus · Local Instance</p>
        </div>
        <div className="flex items-center gap-2 nx-card px-4 py-2">
          <span className={health?.status === 'healthy' ? 'dot-online' : 'dot-offline'} />
          <span className={`text-sm font-bold ${health?.status === 'healthy' ? 'text-green-400' : 'text-red-400'}`}>
            {health?.status?.toUpperCase() ?? 'CONNECTING'}
          </span>
        </div>
      </div>

      {error && (
        <div className="nx-card border-red-500/40 p-4 flex items-center gap-3">
          <AlertCircle className="text-red-400 shrink-0" size={18} />
          <p className="text-red-300 text-sm">{error}</p>
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Documents" value={totalDocs} sub="in database" cyan />
        <StatCard label="OCR Confidence" value={`${avgConf}%`} sub="avg accuracy" />
        <StatCard label="24h Uploads" value={uploads24h} sub="recent activity" accent />
        <StatCard label="API Version" value={health?.version ?? '—'} sub="backend" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Services */}
        <div className="nx-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="text-cyan-400" size={16} />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">SYSTEM SERVICES</h2>
          </div>
          {health ? (
            <div>
              <ServiceRow name="OCR Engine"      status={health.services.ocr} />
              <ServiceRow name="OpenAI GPT"      status={health.services.openai} />
              <ServiceRow name="Anthropic Claude" status={health.services.anthropic} />
              <ServiceRow name="Google Gemini"   status={health.services.gemini} />
            </div>
          ) : (
            <div className="text-nx-muted text-sm animate-pulse">Connecting to backend…</div>
          )}
        </div>

        {/* Document Status Distribution */}
        <div className="nx-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <FileText className="text-cyan-400" size={16} />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">DOCUMENT PIPELINE</h2>
          </div>
          {analytics ? (
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(analytics.document_stats).map(([status, count]) => (
                <div key={status} className={`rounded-lg p-3 ${docStatusBg[status] ?? 'bg-slate-500/20 text-slate-300'}`}>
                  <div className="text-2xl font-bold font-mono">{count}</div>
                  <div className="text-xs uppercase tracking-wider mt-0.5 opacity-80">{status}</div>
                </div>
              ))}
              {Object.keys(analytics.document_stats).length === 0 && (
                <div className="col-span-2 text-nx-muted text-sm">No documents yet</div>
              )}
            </div>
          ) : (
            <div className="text-nx-muted text-sm animate-pulse">Loading…</div>
          )}
        </div>
      </div>

      {/* AI Model Usage */}
      {analytics && Object.keys(analytics.llm_usage).length > 0 && (
        <div className="nx-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Brain className="text-cyan-400" size={16} />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">AI MODEL USAGE</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {Object.entries(analytics.llm_usage).map(([model, count]) => (
              <div key={model} className="flex items-center justify-between nx-card px-4 py-3">
                <span className="text-sm font-semibold text-nx-text uppercase">{model}</span>
                <span className="text-cyan-400 font-bold font-mono">{count} calls</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Documents */}
      <div className="nx-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Clock className="text-cyan-400" size={16} />
          <h2 className="text-sm font-bold text-white uppercase tracking-wider">RECENT DOCUMENTS</h2>
        </div>
        {docs.length === 0 ? (
          <div className="text-nx-muted text-sm py-6 text-center">No documents yet — upload one in the OCR Lab</div>
        ) : (
          <div className="space-y-2">
            {docs.slice(0, 6).map(doc => (
              <div key={doc.id} className="flex items-center justify-between p-3 rounded-lg bg-nx-bg border border-nx-border/50 hover:border-cyan-500/30 transition-colors">
                <div className="flex items-center gap-3">
                  <FileText className="text-cyan-400/60" size={14} />
                  <span className="text-sm text-nx-text font-medium">{doc.filename}</span>
                  <span className={`badge text-xs ${docStatusBg[doc.status] ?? ''}`}>
                    {doc.status.toUpperCase()}
                  </span>
                </div>
                <span className="text-xs text-nx-muted">{new Date(doc.upload_time).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
