import { useState, useMemo } from 'react'
import { SAMPLE_TARGETS } from '../data/sampleData'
import type { Target, TargetStatus } from '../types'
import StatusBadge from '../components/StatusBadge'
import ScoreBadge from '../components/ScoreBadge'
import { Search, Download, ChevronDown, ChevronUp, X, Target as TargetIcon } from 'lucide-react'

const STATUSES: TargetStatus[] = ['Identified','Contacted','Under Review','Offer Sent','Signed','Passed','On Hold']
const COUNTIES = [...new Set(SAMPLE_TARGETS.map(t => t.county))].sort()

function exportCSV(targets: Target[]) {
  const headers = ['ID','Owner','County','Section','Township','Range','Interest Type','NMA','Deal Score','Status','Title Clearance','Est. Value ($)','Wells','Royalty Rate','Assigned To','Last Contact','Curatives','Notes']
  const rows = targets.map(t => [
    t.id, t.ownerName, t.county, t.section, t.township, t.range,
    t.interestType, t.nma, t.dealScore, t.status, t.titleClearance,
    t.estimatedValue, t.wellsProducing, t.royaltyRate,
    t.assignedTo, t.lastContact,
    `"${t.curativesNeeded.join('; ')}"`,
    `"${t.notes.replace(/"/g, "'")}"`,
  ])
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
  a.download = `target_factory_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
}

export default function TargetFactory() {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [countyFilter, setCountyFilter] = useState('all')
  const [sortKey, setSortKey] = useState<keyof Target>('dealScore')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [selected, setSelected] = useState<Target | null>(null)

  const filtered = useMemo(() => {
    let list = SAMPLE_TARGETS.filter(t => {
      const q = search.toLowerCase()
      const ok = !q || t.ownerName.toLowerCase().includes(q) || t.county.toLowerCase().includes(q)
      return ok && (statusFilter === 'all' || t.status === statusFilter) && (countyFilter === 'all' || t.county === countyFilter)
    })
    return [...list].sort((a, b) => {
      const av = a[sortKey] as string | number
      const bv = b[sortKey] as string | number
      if (av < bv) return sortDir === 'asc' ? -1 : 1
      if (av > bv) return sortDir === 'asc' ? 1 : -1
      return 0
    })
  }, [search, statusFilter, countyFilter, sortKey, sortDir])

  function toggleSort(key: keyof Target) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const SortIcon = ({ col }: { col: keyof Target }) => {
    if (sortKey !== col) return null
    return sortDir === 'asc' ? <ChevronUp size={11} /> : <ChevronDown size={11} />
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <TargetIcon className="text-orange-400" size={20} />
            <h1 className="text-xl font-bold text-white tracking-wide">TARGET FACTORY</h1>
          </div>
          <p className="text-sm text-nx-muted">{filtered.length} targets · {filtered.reduce((s,t) => s+t.nma,0).toFixed(1)} NMA</p>
        </div>
        <button className="btn-ghost" onClick={() => exportCSV(filtered)}>
          <Download size={14} /> Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-nx-muted" />
          <input className="nx-input pl-8 w-56" placeholder="Search owner, county…" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <select className="nx-select w-44" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="all">All Statuses</option>
          {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="nx-select w-40" value={countyFilter} onChange={e => setCountyFilter(e.target.value)}>
          <option value="all">All Counties</option>
          {COUNTIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        {(search || statusFilter !== 'all' || countyFilter !== 'all') && (
          <button className="btn-ghost text-xs" onClick={() => { setSearch(''); setStatusFilter('all'); setCountyFilter('all') }}>
            <X size={12} /> Clear
          </button>
        )}
      </div>

      <div className="nx-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                {([
                  ['ownerName','Owner'], ['county','County'], ['interestType','Type'],
                  ['nma','NMA'], ['dealScore','Score'], ['status','Status'],
                  ['titleClearance','Title'], ['estimatedValue','Value'],
                  ['wellsProducing','Wells'], ['lastContact','Last Contact'],
                ] as [keyof Target, string][]).map(([k, label]) => (
                  <th key={k} className="nx-th cursor-pointer select-none hover:text-white" onClick={() => toggleSort(k)}>
                    <span className="inline-flex items-center gap-1">{label}<SortIcon col={k} /></span>
                  </th>
                ))}
                <th className="nx-th">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(t => (
                <tr key={t.id} className="hover:bg-nx-card/60 cursor-pointer" onClick={() => setSelected(t)}>
                  <td className="nx-td font-medium text-white">{t.ownerName}</td>
                  <td className="nx-td text-nx-muted">{t.county}</td>
                  <td className="nx-td"><span className="badge bg-nx-border/60 text-nx-muted">{t.interestType}</span></td>
                  <td className="nx-td font-bold text-white">{t.nma}</td>
                  <td className="nx-td"><ScoreBadge score={t.dealScore} /></td>
                  <td className="nx-td"><StatusBadge status={t.status} /></td>
                  <td className="nx-td"><StatusBadge status={t.titleClearance} /></td>
                  <td className="nx-td text-nx-muted">${t.estimatedValue.toLocaleString()}</td>
                  <td className="nx-td text-nx-muted">{t.wellsProducing}</td>
                  <td className="nx-td text-nx-muted">{t.lastContact || '—'}</td>
                  <td className="nx-td">
                    <button className="text-xs text-cyan-400 hover:underline" onClick={e => { e.stopPropagation(); setSelected(t) }}>Detail</button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={11} className="nx-td text-center text-nx-muted py-10">No targets match filters</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/70 z-40 flex items-center justify-center p-4" onClick={() => setSelected(null)}>
          <div className="bg-nx-card border border-nx-bordHi/40 rounded-xl p-6 max-w-xl w-full overflow-y-auto max-h-[90vh] shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-5">
              <div>
                <div className="text-lg font-bold text-white">{selected.ownerName}</div>
                <div className="text-sm text-nx-muted">{selected.county} Co. · {selected.section}-{selected.township}-{selected.range}</div>
              </div>
              <button onClick={() => setSelected(null)} className="text-nx-muted hover:text-white"><X size={20} /></button>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm mb-5">
              {[
                ['Interest Type', selected.interestType],
                ['NMA', String(selected.nma)],
                ['Est. Value', `$${selected.estimatedValue.toLocaleString()}`],
                ['Wells Producing', String(selected.wellsProducing)],
                ['Royalty Rate', selected.royaltyRate],
                ['Assigned To', selected.assignedTo || 'Unassigned'],
                ['Last Contact', selected.lastContact || '—'],
                ['Created', selected.createdAt],
              ].map(([l, v]) => (
                <div key={l}>
                  <div className="text-xs text-nx-muted uppercase tracking-wide">{l}</div>
                  <div className="font-medium text-nx-text mt-0.5">{v}</div>
                </div>
              ))}
            </div>
            <div className="flex gap-3 mb-4">
              <div><div className="text-xs text-nx-muted uppercase mb-1">Status</div><StatusBadge status={selected.status} /></div>
              <div><div className="text-xs text-nx-muted uppercase mb-1">Title</div><StatusBadge status={selected.titleClearance} /></div>
              <div><div className="text-xs text-nx-muted uppercase mb-1">Score</div><ScoreBadge score={selected.dealScore} /></div>
            </div>
            {selected.curativesNeeded.length > 0 && (
              <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3 mb-4">
                <div className="text-xs font-bold text-yellow-300 mb-2 uppercase">Curatives Needed</div>
                <ul className="text-xs text-yellow-200/80 list-disc list-inside space-y-0.5">
                  {selected.curativesNeeded.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              </div>
            )}
            {selected.notes && (
              <div className="bg-nx-bg border border-nx-border rounded-lg p-3">
                <div className="text-xs font-semibold text-nx-muted uppercase mb-1">Notes</div>
                <div className="text-sm text-nx-text">{selected.notes}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
