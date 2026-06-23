import { useState, useMemo } from 'react'
import { SAMPLE_TARGETS } from '../data/sampleData'
import type { Target, TargetStatus } from '../types'
import StatusBadge from '../components/StatusBadge'
import ScoreBadge from '../components/ScoreBadge'
import RoyaltyAnalysis from '../components/RoyaltyAnalysis'
import { Search, Download, ChevronDown, ChevronUp, X } from 'lucide-react'

const STATUSES: TargetStatus[] = ['Identified','Contacted','Under Review','Offer Sent','Signed','Passed','On Hold']
const COUNTIES = [...new Set(SAMPLE_TARGETS.map(t => t.county))].sort()

function exportCSV(targets: Target[]) {
  const headers = [
    'ID','Owner','County','Section','Township','Range','Interest Type',
    'NMA','Deal Score','Status','Title Clearance','Est. Value ($)',
    'Wells Producing','Royalty Rate','Assigned To','Last Contact',
    'Curatives Needed','Notes',
  ]
  const rows = targets.map(t => [
    t.id, t.ownerName, t.county, t.section, t.township, t.range,
    t.interestType, t.nma, t.dealScore, t.status, t.titleClearance,
    t.estimatedValue, t.wellsProducing, t.royaltyRate,
    t.assignedTo, t.lastContact,
    `"${t.curativesNeeded.join('; ')}"`,
    `"${t.notes.replace(/"/g, "'")}"`,
  ])
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `target_factory_export_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export default function TargetFactory() {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [countyFilter, setCountyFilter] = useState<string>('all')
  const [sortKey, setSortKey] = useState<keyof Target>('dealScore')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [selected, setSelected] = useState<Target | null>(null)

  const filtered = useMemo(() => {
    let list = SAMPLE_TARGETS.filter(t => {
      const q = search.toLowerCase()
      const matchSearch = !q || t.ownerName.toLowerCase().includes(q) ||
        t.county.toLowerCase().includes(q) || t.instrumentType?.toLowerCase().includes(q)
      const matchStatus = statusFilter === 'all' || t.status === statusFilter
      const matchCounty = countyFilter === 'all' || t.county === countyFilter
      return matchSearch && matchStatus && matchCounty
    })
    list = [...list].sort((a, b) => {
      const av = a[sortKey] as string | number
      const bv = b[sortKey] as string | number
      if (av < bv) return sortDir === 'asc' ? -1 : 1
      if (av > bv) return sortDir === 'asc' ? 1 : -1
      return 0
    })
    return list
  }, [search, statusFilter, countyFilter, sortKey, sortDir])

  function toggleSort(key: keyof Target) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  function SortIcon({ col }: { col: keyof Target }) {
    if (sortKey !== col) return null
    return sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Target Factory</h1>
          <p className="text-sm text-slate-500">{filtered.length} targets · {filtered.reduce((s,t) => s+t.nma,0).toFixed(1)} NMA</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => exportCSV(filtered)}>
            <Download size={14} /> Export CSV
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            className="input pl-8 w-56"
            placeholder="Search owner, county..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <select className="input w-44" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="all">All Statuses</option>
          {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="input w-40" value={countyFilter} onChange={e => setCountyFilter(e.target.value)}>
          <option value="all">All Counties</option>
          {COUNTIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        {(search || statusFilter !== 'all' || countyFilter !== 'all') && (
          <button className="btn-secondary text-xs" onClick={() => { setSearch(''); setStatusFilter('all'); setCountyFilter('all') }}>
            <X size={12} /> Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                {([
                  ['ownerName','Owner'],
                  ['county','County'],
                  ['interestType','Type'],
                  ['nma','NMA'],
                  ['dealScore','Score'],
                  ['status','Status'],
                  ['titleClearance','Title'],
                  ['estimatedValue','Est. Value'],
                  ['wellsProducing','Wells'],
                  ['lastContact','Last Contact'],
                ] as [keyof Target, string][]).map(([k, label]) => (
                  <th
                    key={k}
                    className="table-th cursor-pointer select-none hover:text-slate-800"
                    onClick={() => toggleSort(k)}
                  >
                    <span className="inline-flex items-center gap-1">
                      {label}<SortIcon col={k} />
                    </span>
                  </th>
                ))}
                <th className="table-th">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(t => (
                <tr
                  key={t.id}
                  className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer"
                  onClick={() => setSelected(t)}
                >
                  <td className="table-td font-medium text-slate-900">{t.ownerName}</td>
                  <td className="table-td">{t.county}</td>
                  <td className="table-td">
                    <span className="badge bg-slate-100 text-slate-600">{t.interestType}</span>
                  </td>
                  <td className="table-td font-semibold">{t.nma}</td>
                  <td className="table-td"><ScoreBadge score={t.dealScore} /></td>
                  <td className="table-td"><StatusBadge status={t.status} /></td>
                  <td className="table-td"><StatusBadge status={t.titleClearance} /></td>
                  <td className="table-td">${t.estimatedValue.toLocaleString()}</td>
                  <td className="table-td">{t.wellsProducing}</td>
                  <td className="table-td text-slate-500">{t.lastContact || '—'}</td>
                  <td className="table-td">
                    <button
                      className="text-xs text-orange-600 hover:underline"
                      onClick={e => { e.stopPropagation(); setSelected(t) }}
                    >
                      Detail
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={11} className="table-td text-center text-slate-400 py-10">
                    No targets match the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail panel */}
      {selected && (
        <div className="fixed inset-0 bg-black/40 z-40 flex items-center justify-center p-4" onClick={() => setSelected(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-xl w-full p-6 overflow-y-auto max-h-[90vh]" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-4">
              <div>
                <div className="text-lg font-bold text-slate-900">{selected.ownerName}</div>
                <div className="text-sm text-slate-500">{selected.county} Co. · {selected.section}-{selected.township}-{selected.range}</div>
              </div>
              <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-slate-700">
                <X size={20} />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm mb-4">
              {[
                ['Interest Type', selected.interestType],
                ['NMA', selected.nma],
                ['Deal Score', <ScoreBadge score={selected.dealScore} />],
                ['Status', <StatusBadge status={selected.status} />],
                ['Title', <StatusBadge status={selected.titleClearance} />],
                ['Est. Value', `$${selected.estimatedValue.toLocaleString()}`],
                ['Wells Producing', selected.wellsProducing],
                ['Royalty Rate', selected.royaltyRate],
                ['Assigned To', selected.assignedTo || 'Unassigned'],
                ['Last Contact', selected.lastContact || '—'],
              ].map(([label, val]) => (
                <div key={String(label)}>
                  <div className="text-xs text-slate-400 uppercase tracking-wide">{label}</div>
                  <div className="font-medium mt-0.5">{val}</div>
                </div>
              ))}
            </div>

            <RoyaltyAnalysis target={selected} />

            {selected.curativesNeeded.length > 0 && (
              <div className="bg-yellow-50 rounded-lg p-3 mb-3 border border-yellow-200">
                <div className="text-xs font-semibold text-yellow-800 mb-1">Curatives Needed</div>
                <ul className="text-xs text-yellow-700 list-disc list-inside space-y-0.5">
                  {selected.curativesNeeded.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              </div>
            )}

            {selected.notes && (
              <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                <div className="text-xs font-semibold text-slate-500 mb-1">Notes</div>
                <div className="text-sm text-slate-700">{selected.notes}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
