import { useState, useMemo } from 'react'
import { SAMPLE_AUDIT } from '../data/sampleData'
import type { AuditEntry, AuditCategory } from '../types'
import { Download, Search, X } from 'lucide-react'

const CATEGORY_COLORS: Record<AuditCategory, string> = {
  Target:   'bg-blue-100 text-blue-700',
  Evidence: 'bg-indigo-100 text-indigo-700',
  Score:    'bg-green-100 text-green-700',
  Export:   'bg-orange-100 text-orange-700',
  System:   'bg-slate-100 text-slate-500',
}

const ACTION_ICONS: Record<string, string> = {
  'Target Added':      '＋',
  'Status Changed':    '↔',
  'Note Added':        '✏️',
  'Evidence Uploaded': '📎',
  'Score Recorded':    '📊',
  'CSV Export':        '⬇️',
  'System':            '⚙️',
}

function exportAuditCSV(entries: AuditEntry[]) {
  const headers = ['Timestamp','Category','Action','Target','User','Details']
  const rows = entries.map(e => [
    e.timestamp, e.category, e.action,
    e.targetName ?? '', e.user,
    `"${e.details.replace(/"/g, "'")}"`,
  ])
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `audit_trail_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
}

export default function AuditTrail() {
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<AuditCategory | 'all'>('all')

  const entries = useMemo(() => {
    return SAMPLE_AUDIT.filter(e => {
      const q = search.toLowerCase()
      const matchSearch = !q ||
        e.action.toLowerCase().includes(q) ||
        e.details.toLowerCase().includes(q) ||
        (e.targetName?.toLowerCase().includes(q) ?? false)
      const matchCat = categoryFilter === 'all' || e.category === categoryFilter
      return matchSearch && matchCat
    })
  }, [search, categoryFilter])

  const categories: (AuditCategory | 'all')[] = ['all','Target','Evidence','Score','Export','System']

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Audit Trail</h1>
          <p className="text-sm text-slate-500">{entries.length} entries · full activity history</p>
        </div>
        <button className="btn-secondary" onClick={() => exportAuditCSV(entries)}>
          <Download size={14} /> Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            className="input pl-8 w-64"
            placeholder="Search actions, targets, details..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                categoryFilter === cat
                  ? 'bg-orange-500 text-white'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {cat === 'all' ? 'All' : cat}
            </button>
          ))}
        </div>
        {(search || categoryFilter !== 'all') && (
          <button className="btn-secondary text-xs" onClick={() => { setSearch(''); setCategoryFilter('all') }}>
            <X size={12} /> Clear
          </button>
        )}
      </div>

      {/* Timeline */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="table-th">Timestamp</th>
                <th className="table-th">Category</th>
                <th className="table-th">Action</th>
                <th className="table-th">Target</th>
                <th className="table-th">User</th>
                <th className="table-th">Details</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(e => (
                <tr key={e.id} className="border-b border-slate-100 hover:bg-slate-50 align-top">
                  <td className="table-td whitespace-nowrap text-slate-500 font-mono text-xs">
                    {e.timestamp.replace('T', ' ')}
                  </td>
                  <td className="table-td">
                    <span className={`badge ${CATEGORY_COLORS[e.category]}`}>
                      {e.category}
                    </span>
                  </td>
                  <td className="table-td font-medium whitespace-nowrap">
                    <span className="mr-1">{ACTION_ICONS[e.action] ?? ''}</span>
                    {e.action}
                  </td>
                  <td className="table-td text-slate-600">
                    {e.targetName ?? <span className="text-slate-300">—</span>}
                  </td>
                  <td className="table-td whitespace-nowrap text-slate-600">{e.user}</td>
                  <td className="table-td text-slate-600 max-w-sm">{e.details}</td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={6} className="table-td text-center text-slate-400 py-10">
                    No audit entries match the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Summary counts */}
      <div className="grid grid-cols-5 gap-3">
        {(['Target','Evidence','Score','Export','System'] as AuditCategory[]).map(cat => (
          <div key={cat} className="card p-3 text-center">
            <div className="text-lg font-bold text-slate-900">
              {SAMPLE_AUDIT.filter(e => e.category === cat).length}
            </div>
            <div className={`badge mt-1 ${CATEGORY_COLORS[cat]}`}>{cat}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
