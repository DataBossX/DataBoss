import { useState, useEffect } from 'react'
import { api, SystemLog } from '../api/client'
import { ScrollText, RefreshCw } from 'lucide-react'

const LEVEL_STYLE: Record<string, string> = {
  INFO:    'bg-blue-500/20 text-blue-300 border-blue-500/30',
  WARNING: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  ERROR:   'bg-red-500/20 text-red-300 border-red-500/30',
}

const ROW_BG: Record<string, string> = {
  INFO:    '',
  WARNING: 'bg-yellow-500/5 border-yellow-500/10',
  ERROR:   'bg-red-500/5 border-red-500/10',
}

export default function SystemLogs() {
  const [logs, setLogs] = useState<SystemLog[]>([])
  const [filter, setFilter] = useState<'ALL' | 'INFO' | 'WARNING' | 'ERROR'>('ALL')
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      const l = await api.logs(200)
      setLogs(l)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [])

  const filtered = filter === 'ALL' ? logs : logs.filter(l => l.level === filter)
  const counts = {
    ALL: logs.length,
    INFO: logs.filter(l => l.level === 'INFO').length,
    WARNING: logs.filter(l => l.level === 'WARNING').length,
    ERROR: logs.filter(l => l.level === 'ERROR').length,
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ScrollText className="text-cyan-400" size={20} />
            <h1 className="text-xl font-bold text-white tracking-wide">SYSTEM LOGS</h1>
          </div>
          <p className="text-sm text-nx-muted">Live feed · auto-refreshes every 5s</p>
        </div>
        <button onClick={load} className="btn-cyan">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Level filter */}
      <div className="flex gap-2">
        {(['ALL', 'INFO', 'WARNING', 'ERROR'] as const).map(level => (
          <button
            key={level}
            onClick={() => setFilter(level)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              filter === level
                ? 'bg-cyan-500/20 border border-cyan-500/40 text-cyan-400'
                : 'nx-card text-nx-muted hover:text-nx-text'
            }`}
          >
            {level} <span className="ml-1 text-xs opacity-70">{counts[level]}</span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-nx-muted text-sm animate-pulse">Loading logs…</div>
      ) : filtered.length === 0 ? (
        <div className="nx-card p-12 text-center text-nx-muted">No log entries</div>
      ) : (
        <div className="space-y-2 max-h-[650px] overflow-y-auto">
          {filtered.map(log => (
            <div
              key={log.id}
              className={`rounded-lg border border-nx-border/50 p-4 ${ROW_BG[log.level] ?? ''}`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-3">
                  <span className={`badge border text-xs font-bold ${LEVEL_STYLE[log.level] ?? ''}`}>
                    {log.level}
                  </span>
                  <span className="text-cyan-400 text-sm font-semibold">{log.component}</span>
                </div>
                <span className="text-xs text-nx-muted">{new Date(log.created_at).toLocaleString()}</span>
              </div>
              <div className="text-sm text-nx-text mt-1">{log.message}</div>
              {log.details && (
                <pre className="text-xs text-nx-muted mt-2 bg-black/20 p-2 rounded overflow-x-auto">
                  {JSON.stringify(log.details, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
