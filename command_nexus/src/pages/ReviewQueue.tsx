import { useState } from 'react'
import { SAMPLE_EVIDENCE, SAMPLE_TARGETS } from '../data/sampleData'
import type { Evidence, EvidenceStatus } from '../types'
import StatusBadge from '../components/StatusBadge'
import { FileSearch, CheckCircle, Flag, Clock, X } from 'lucide-react'

export default function ReviewQueue() {
  const [statusFilter, setStatusFilter] = useState<EvidenceStatus | 'all'>('Pending Review')
  const [selected, setSelected] = useState<Evidence | null>(null)
  const [localStatus, setLocalStatus] = useState<Record<string, EvidenceStatus>>({})

  const getStatus = (e: Evidence): EvidenceStatus => localStatus[e.id] ?? e.status
  const evidence = SAMPLE_EVIDENCE.filter(e => statusFilter === 'all' || getStatus(e) === statusFilter)

  const counts = {
    pending:  SAMPLE_EVIDENCE.filter(e => getStatus(e) === 'Pending Review').length,
    reviewed: SAMPLE_EVIDENCE.filter(e => getStatus(e) === 'Reviewed').length,
    flagged:  SAMPLE_EVIDENCE.filter(e => getStatus(e) === 'Flagged').length,
  }

  function markStatus(id: string, status: EvidenceStatus) {
    setLocalStatus(prev => ({ ...prev, [id]: status }))
  }

  function getTargetName(tid: string) {
    return SAMPLE_TARGETS.find(t => t.id === tid)?.ownerName ?? tid
  }

  function ConfBar({ score }: { score: number }) {
    const color = score >= 0.9 ? 'bg-green-400' : score >= 0.7 ? 'bg-yellow-400' : 'bg-red-400'
    return (
      <div className="flex items-center gap-2">
        <div className="h-1.5 w-24 bg-nx-bg rounded-full">
          <div className={`${color} h-1.5 rounded-full`} style={{ width: `${score * 100}%` }} />
        </div>
        <span className="text-xs font-bold text-nx-text">{Math.round(score * 100)}%</span>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-5">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <FileSearch className="text-cyan-400" size={20} />
          <h1 className="text-xl font-bold text-white tracking-wide">REVIEW QUEUE</h1>
        </div>
        <p className="text-sm text-nx-muted">Review OCR-extracted document fields before they enter the title chain</p>
      </div>

      <div className="flex gap-2">
        {([
          ['all', 'All', counts.pending + counts.reviewed + counts.flagged],
          ['Pending Review', 'Pending', counts.pending],
          ['Reviewed', 'Reviewed', counts.reviewed],
          ['Flagged', 'Flagged', counts.flagged],
        ] as [string, string, number][]).map(([val, label, count]) => (
          <button
            key={val}
            onClick={() => setStatusFilter(val as EvidenceStatus | 'all')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              statusFilter === val
                ? 'bg-cyan-500/20 border border-cyan-500/40 text-cyan-400'
                : 'nx-card text-nx-muted hover:text-nx-text'
            }`}
          >
            {label} <span className="ml-1 text-xs opacity-70">{count}</span>
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {evidence.map(e => (
          <div key={e.id} className="nx-card p-4 hover:border-cyan-500/30 cursor-pointer transition-all" onClick={() => setSelected(e)}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-white">{e.fileName}</span>
                  <span className="badge bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs">{e.type}</span>
                  <StatusBadge status={getStatus(e)} />
                </div>
                <div className="text-xs text-nx-muted mt-1">
                  Target: <span className="text-nx-text">{getTargetName(e.targetId)}</span>
                  &nbsp;·&nbsp;{e.county} Co. Book {e.book} Pg {e.page}
                </div>
                <div className="flex gap-6 mt-2 text-xs">
                  <div><span className="text-nx-muted">Grantors: </span><span className="text-nx-text">{e.grantors.join(', ')}</span></div>
                  <div><span className="text-nx-muted">Grantees: </span><span className="text-nx-text">{e.grantees.join(', ')}</span></div>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-xs text-nx-muted">AI Confidence:</span>
                  <ConfBar score={e.confidence} />
                </div>
              </div>
              <div className="flex flex-col gap-2 shrink-0">
                <button className="btn-cyan text-xs py-1.5 px-3" onClick={ev => { ev.stopPropagation(); markStatus(e.id, 'Reviewed') }}>
                  <CheckCircle size={11} /> Approve
                </button>
                <button className="btn-danger text-xs py-1.5 px-3" onClick={ev => { ev.stopPropagation(); markStatus(e.id, 'Flagged') }}>
                  <Flag size={11} /> Flag
                </button>
                <button className="btn-ghost text-xs py-1.5 px-3" onClick={ev => { ev.stopPropagation(); markStatus(e.id, 'Pending Review') }}>
                  <Clock size={11} /> Reset
                </button>
              </div>
            </div>
            {e.notes && (
              <div className={`mt-3 text-xs p-2 rounded ${getStatus(e) === 'Flagged' ? 'bg-red-500/10 text-red-300 border border-red-500/20' : 'bg-nx-bg text-nx-muted border border-nx-border/50'}`}>
                {e.notes}
              </div>
            )}
          </div>
        ))}
        {evidence.length === 0 && (
          <div className="nx-card p-12 text-center text-nx-muted">No documents in this queue</div>
        )}
      </div>

      {selected && (
        <div className="fixed inset-0 bg-black/70 z-40 flex items-center justify-center p-4" onClick={() => setSelected(null)}>
          <div className="bg-nx-card border border-nx-bordHi/40 rounded-xl p-6 max-w-2xl w-full overflow-y-auto max-h-[90vh] shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-5">
              <div>
                <div className="font-bold text-white">{selected.fileName}</div>
                <div className="text-sm text-nx-muted">{selected.type} · {selected.county} Co.</div>
              </div>
              <button onClick={() => setSelected(null)} className="text-nx-muted hover:text-white"><X size={18} /></button>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm mb-5">
              {[
                ['Book', selected.book], ['Page', selected.page],
                ['Instrument #', selected.instrumentNumber],
                ['Recording Date', selected.recordingDate],
                ['Instrument Date', selected.instrumentDate],
                ['Section', selected.section], ['Township', selected.township], ['Range', selected.range],
                ['Interest Conveyed', selected.interestConveyed],
                ['AI Confidence', `${Math.round(selected.confidence * 100)}%`],
              ].map(([l, v]) => (
                <div key={String(l)}>
                  <div className="text-xs text-nx-muted uppercase tracking-wide">{l}</div>
                  <div className="font-medium text-nx-text mt-0.5">{v || '—'}</div>
                </div>
              ))}
            </div>
            <div className="mb-3">
              <div className="text-xs text-nx-muted uppercase mb-1">Grantors</div>
              <div className="text-sm text-nx-text">{selected.grantors.join('; ')}</div>
            </div>
            <div className="mb-3">
              <div className="text-xs text-nx-muted uppercase mb-1">Grantees</div>
              <div className="text-sm text-nx-text">{selected.grantees.join('; ')}</div>
            </div>
            <div className="mb-5">
              <div className="text-xs text-nx-muted uppercase mb-1">Legal Description</div>
              <div className="text-sm text-nx-text bg-nx-bg border border-nx-border p-2 rounded font-mono">{selected.legalDescription}</div>
            </div>
            <div className="flex gap-2">
              <button className="btn-cyan" onClick={() => { markStatus(selected.id, 'Reviewed'); setSelected(null) }}>
                <CheckCircle size={14} /> Approve
              </button>
              <button className="btn-danger" onClick={() => { markStatus(selected.id, 'Flagged'); setSelected(null) }}>
                <Flag size={14} /> Flag
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
