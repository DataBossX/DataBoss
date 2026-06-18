import { useState } from 'react'
import { SAMPLE_EVIDENCE, SAMPLE_TARGETS } from '../data/sampleData'
import type { Evidence, EvidenceStatus } from '../types'
import StatusBadge from '../components/StatusBadge'
import { CheckCircle, Flag, Clock, X } from 'lucide-react'

export default function ReviewQueue() {
  const [statusFilter, setStatusFilter] = useState<EvidenceStatus | 'all'>('Pending Review')
  const [selected, setSelected] = useState<Evidence | null>(null)
  const [localStatus, setLocalStatus] = useState<Record<string, EvidenceStatus>>({})

  const getStatus = (e: Evidence): EvidenceStatus => localStatus[e.id] ?? e.status

  const evidence = SAMPLE_EVIDENCE.filter(e =>
    statusFilter === 'all' || getStatus(e) === statusFilter
  )

  const counts = {
    pending: SAMPLE_EVIDENCE.filter(e => getStatus(e) === 'Pending Review').length,
    reviewed: SAMPLE_EVIDENCE.filter(e => getStatus(e) === 'Reviewed').length,
    flagged: SAMPLE_EVIDENCE.filter(e => getStatus(e) === 'Flagged').length,
  }

  function markStatus(id: string, status: EvidenceStatus) {
    setLocalStatus(prev => ({ ...prev, [id]: status }))
    if (selected?.id === id) setSelected(prev => prev ? { ...prev, status } : null)
  }

  function getTargetName(targetId: string) {
    return SAMPLE_TARGETS.find(t => t.id === targetId)?.ownerName ?? targetId
  }

  function ConfBar({ score }: { score: number }) {
    const color = score >= 0.9 ? 'bg-green-400' : score >= 0.7 ? 'bg-yellow-400' : 'bg-red-400'
    return (
      <div className="flex items-center gap-2">
        <div className="bg-slate-100 rounded-full h-2 w-24">
          <div className={`${color} h-2 rounded-full`} style={{ width: `${score * 100}%` }} />
        </div>
        <span className="text-xs font-semibold">{Math.round(score * 100)}%</span>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Parsed-Results Review Queue</h1>
        <p className="text-sm text-slate-500">Review OCR-extracted document fields before they enter the title chain</p>
      </div>

      {/* Status tabs */}
      <div className="flex gap-3">
        {([
          ['all', 'All', counts.pending + counts.reviewed + counts.flagged, ''],
          ['Pending Review', 'Pending', counts.pending, 'text-yellow-600'],
          ['Reviewed', 'Reviewed', counts.reviewed, 'text-green-600'],
          ['Flagged', 'Flagged', counts.flagged, 'text-red-600'],
        ] as [string, string, number, string][]).map(([val, label, count, cls]) => (
          <button
            key={val}
            onClick={() => setStatusFilter(val as EvidenceStatus | 'all')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              statusFilter === val ? 'bg-orange-500 text-white' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            {label}
            <span className={`text-xs font-bold ${statusFilter === val ? 'text-orange-100' : cls}`}>{count}</span>
          </button>
        ))}
      </div>

      {/* Evidence cards */}
      <div className="space-y-3">
        {evidence.map(e => (
          <div
            key={e.id}
            className="card p-4 cursor-pointer hover:border-orange-300 transition-all"
            onClick={() => setSelected(e)}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-900 truncate">{e.fileName}</span>
                  <span className="badge bg-indigo-100 text-indigo-700">{e.type}</span>
                  <StatusBadge status={getStatus(e)} />
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  Target: <span className="font-medium text-slate-700">{getTargetName(e.targetId)}</span>
                  &nbsp;·&nbsp;{e.county} Co. Book {e.book} Pg {e.page}
                  &nbsp;·&nbsp;Inst. {e.instrumentNumber}
                </div>
                <div className="flex gap-6 mt-2">
                  <div>
                    <div className="text-xs text-slate-400">Grantors</div>
                    <div className="text-xs text-slate-700">{e.grantors.join(', ')}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400">Grantees</div>
                    <div className="text-xs text-slate-700">{e.grantees.join(', ')}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400">Recorded</div>
                    <div className="text-xs text-slate-700">{e.recordingDate}</div>
                  </div>
                </div>
                <div className="mt-2">
                  <div className="text-xs text-slate-400 mb-1">AI Confidence</div>
                  <ConfBar score={e.confidence} />
                </div>
              </div>
              <div className="flex flex-col gap-2 shrink-0">
                <button
                  className="btn-secondary text-xs py-1.5"
                  onClick={ev => { ev.stopPropagation(); markStatus(e.id, 'Reviewed') }}
                >
                  <CheckCircle size={12} className="text-green-500" /> Approve
                </button>
                <button
                  className="btn-secondary text-xs py-1.5 text-red-600"
                  onClick={ev => { ev.stopPropagation(); markStatus(e.id, 'Flagged') }}
                >
                  <Flag size={12} /> Flag
                </button>
                <button
                  className="btn-secondary text-xs py-1.5"
                  onClick={ev => { ev.stopPropagation(); markStatus(e.id, 'Pending Review') }}
                >
                  <Clock size={12} /> Reset
                </button>
              </div>
            </div>

            {e.notes && (
              <div className={`mt-3 text-xs p-2 rounded ${getStatus(e) === 'Flagged' ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-slate-50 text-slate-600'}`}>
                {e.notes}
              </div>
            )}
          </div>
        ))}
        {evidence.length === 0 && (
          <div className="card p-12 text-center text-slate-400">
            No documents in this queue.
          </div>
        )}
      </div>

      {/* Detail modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/40 z-40 flex items-center justify-center p-4" onClick={() => setSelected(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full p-6 overflow-y-auto max-h-[90vh]" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-4">
              <div>
                <div className="font-bold text-slate-900">{selected.fileName}</div>
                <div className="text-sm text-slate-500">{selected.type} · {selected.county} Co.</div>
              </div>
              <button onClick={() => setSelected(null)}><X size={18} className="text-slate-400" /></button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm mb-4">
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
                  <div className="text-xs text-slate-400 uppercase">{l}</div>
                  <div className="font-medium">{v || '—'}</div>
                </div>
              ))}
            </div>

            <div className="mb-3">
              <div className="text-xs text-slate-400 uppercase mb-1">Grantors</div>
              <div className="text-sm">{selected.grantors.join('; ')}</div>
            </div>
            <div className="mb-3">
              <div className="text-xs text-slate-400 uppercase mb-1">Grantees</div>
              <div className="text-sm">{selected.grantees.join('; ')}</div>
            </div>
            <div className="mb-4">
              <div className="text-xs text-slate-400 uppercase mb-1">Legal Description</div>
              <div className="text-sm bg-slate-50 p-2 rounded border">{selected.legalDescription}</div>
            </div>

            <div className="flex gap-2">
              <button className="btn-primary" onClick={() => { markStatus(selected.id, 'Reviewed'); setSelected(null) }}>
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
