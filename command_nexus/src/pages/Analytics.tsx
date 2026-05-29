import { useState, useEffect } from 'react'
import { api, Analytics as AnalyticsData } from '../api/client'
import { Activity, AlertCircle } from 'lucide-react'
import StatCard from '../components/StatCard'

export default function Analytics() {
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    api.analytics().then(setData).catch(() => setError(true))
    const t = setInterval(() => api.analytics().then(setData).catch(() => {}), 10000)
    return () => clearInterval(t)
  }, [])

  if (error) return (
    <div className="p-6">
      <div className="nx-card border-red-500/40 p-6 flex gap-3 items-center">
        <AlertCircle className="text-red-400" size={18} />
        <span className="text-red-300 text-sm">Backend unavailable — start the API server</span>
      </div>
    </div>
  )

  const totalDocs = Object.values(data?.document_stats ?? {}).reduce((a, b) => a + b, 0)

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-2 mb-1">
        <Activity className="text-cyan-400" size={20} />
        <h1 className="text-xl font-bold text-white tracking-wide">ANALYTICS</h1>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Documents" value={totalDocs} sub="in database" cyan />
        <StatCard label="Avg OCR Confidence" value={`${((data?.ocr_metrics?.avg_confidence ?? 0) * 100).toFixed(1)}%`} />
        <StatCard label="Avg Processing Time" value={`${(data?.ocr_metrics?.avg_processing_time ?? 0).toFixed(2)}s`} />
        <StatCard label="24h Uploads" value={data?.recent_activity?.uploads_24h ?? 0} accent />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="nx-card p-5">
          <h2 className="text-sm font-bold text-cyan-400 uppercase tracking-wider mb-4">DOCUMENT STATUS BREAKDOWN</h2>
          {data ? (
            <div className="space-y-3">
              {Object.entries(data.document_stats).map(([status, count]) => {
                const pct = totalDocs ? Math.round((count / totalDocs) * 100) : 0
                return (
                  <div key={status}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="uppercase text-nx-muted tracking-wider">{status}</span>
                      <span className="font-bold text-white">{count} <span className="text-nx-muted font-normal">({pct}%)</span></span>
                    </div>
                    <div className="h-2 bg-nx-bg rounded-full">
                      <div className="h-2 bg-cyan-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
              {Object.keys(data.document_stats).length === 0 && (
                <div className="text-nx-muted text-sm">No data yet</div>
              )}
            </div>
          ) : (
            <div className="animate-pulse text-nx-muted text-sm">Loading…</div>
          )}
        </div>

        <div className="nx-card p-5">
          <h2 className="text-sm font-bold text-cyan-400 uppercase tracking-wider mb-4">AI MODEL USAGE</h2>
          {data ? (
            <div className="space-y-3">
              {Object.entries(data.llm_usage).map(([model, count]) => (
                <div key={model} className="flex items-center justify-between p-3 bg-nx-bg rounded-lg border border-nx-border">
                  <span className="text-sm font-semibold text-nx-text uppercase tracking-wider">{model}</span>
                  <span className="font-bold font-mono text-cyan-400">{count}</span>
                </div>
              ))}
              {Object.keys(data.llm_usage).length === 0 && (
                <div className="text-nx-muted text-sm">No AI analyses yet</div>
              )}
            </div>
          ) : (
            <div className="animate-pulse text-nx-muted text-sm">Loading…</div>
          )}
        </div>
      </div>
    </div>
  )
}
