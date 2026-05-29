import { useState, useMemo } from 'react'
import { SAMPLE_AUDIT } from '../data/sampleData'
import type { AuditCategory } from '../types'
import { ClipboardList, Download, Search, X } from 'lucide-react'

const CATEGORY_STYLE: Record<AuditCategory, string> = {
  Target:   'bg-blue-500/20 text-blue-300 border-blue-500/30',
  Evidence: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
  Score:    'bg-green-500/20 text-green-300 border-green-500/30',
  Export:   'bg-orange-500/20 text-orange-300 border-orange-500/30',
  System:   'bg-slate-500/20 text-slate-400 border-slate-500/30',
}

function exportCSV() {
  const headers = ['Timestamp','Category','Action','Target','User','Details']
  const rows = SAMPLE_AUDIT.map(e => [
    e.timestamp, e.category, e.action, e.targetName ?? '', e.user,
    `"${e.details.replace(/"/g, "'")}"`,
  ])
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
  a.download = `audit_trail_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
}

export default function AuditTrail() {
  const [search, setSearch] = useState('')
  const [catFilter, setCatFilter] = useState<AuditCategory | 'all'>('all')

  const entries = useMemo(() => SAMPLE_AUDIT.filter(e => {
    const q = search.toLowerCase()
    const matchSearch = !q || e.action.toLowerCase().includes(q) || e.details.toLowerCase().includes(q) || (e.targetName?.toLowerCase().includes(q) ?? false)
    return matchSearch && (catFilter === 'all' || e.category === catFilter)
  }), [search, catFilter])

  const cats: (AuditCategory | 'all')[] = ['all','Target','Evidence','Score','Export','System']

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ClipboardList className="text-cyan-400" size={20} />
            <h1 className="text-xl font-bold text-white tracking-wide">AUDIT TRAIL</h1>
          </div>
          <p className="text-sm text-nx-muted">{entries.length} entries</p>
        </div>
        <button className="btn-ghost" onClick={exportCSV}>
          <Download size={14} /> Export CSV
        </button>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-nx-muted" />
          <input className="nx-input pl-8 w-64" placeholder="Search actions, targets…" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <div className="flex gap-2">
          {cats.map(c => (
            <button
              key={c}
              onClick={() => setCatFilter(c)}
              className={`px-3 py-2 rounded-lg text-xs font-medium transition-all capitalize ${catFilter === c ? 'bg-cyan-500/20 border border-cyan-500/40 text-cyan-400' : 'nx-card text-nx-muted hover:text-nx-text'}`}
            >
              {c}
            </button>
          ))}
        </div>
        {(search || catFilter !== 'all') && (
          <button className="btn-ghost text-xs" onClick={() => { setSearch(''); setCatFilter('all') }}>
            <X size={12} /> Clear
          </button>
        )}
      </div>

      <div className="nx-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="nx-th">Timestamp</th>
                <th className="nx-th">Category</th>
                <th className="nx-th">Action</th>
                <th className="nx-th">Target</th>
                <th className="nx-th">User</th>
                <th className="nx-th">Details</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(e => (
                <tr key={e.id} className="hover:bg-nx-card/60">
                  <td className="nx-td font-mono text-xs text-nx-muted whitespace-nowrap">{e.timestamp.replace('T', ' ')}</td>
                  <td className="nx-td">
                    <span className={`badge border text-xs ${CATEGORY_STYLE[e.category]}`}>{e.category}</span>
                  </td>
                  <td className="nx-td font-semibold text-nx-text whitespace-nowrap">{e.action}</td>
                  <td className="nx-td text-nx-muted">{e.targetName || <span className="opacity-40">—</span>}</td>
                  <td className="nx-td text-cyan-400">{e.user}</td>
                  <td className="nx-td text-nx-muted max-w-xs truncate" title={e.details}>{e.details}</td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr><td colSpan={6} className="nx-td text-center text-nx-muted py-10">No entries match filters</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
