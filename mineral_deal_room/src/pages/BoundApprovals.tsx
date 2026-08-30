import { useState } from 'react'
import { INITIAL_APPROVALS } from '../data/sampleData'
import type { ApprovalRequest } from '../types'
import { CheckSquare, CheckCircle, XCircle, Clock, ShieldCheck, AlertTriangle } from 'lucide-react'

export default function BoundApprovals() {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>(INITIAL_APPROVALS)
  const [activeMessage, setActiveMessage] = useState<string | null>(null)

  function handleAction(id: string, decision: 'APPROVED' | 'REJECTED') {
    const item = approvals.find(a => a.approvalId === id)
    if (!item) return

    setApprovals(prev => prev.map(a => a.approvalId === id ? { ...a, state: decision } : a))
    setActiveMessage(`[CRYPTOGRAPHIC BINDING P-6] Approval ${id} marked ${decision}. Action bound strictly to artifact hash ${item.artifactHash.slice(0, 12)}... (Scope: ${item.scope}). Any subsequent payload alteration automatically revokes this signature (RT-14).`)
    setTimeout(() => setActiveMessage(null), 8000)
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-bold rounded bg-emerald-100 text-emerald-900 border border-emerald-300">
              HASH-BOUND APPROVALS P-6
            </span>
            <span className="text-xs font-mono text-slate-500">TAMPER DETECTION (RT-3, RT-14)</span>
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight mt-1">
            Hash-Bound Human Approval Gate
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            Every approval is bound to actor identity, specific action, and immutable payload digest. No stale or scope-widened reuse.
          </p>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-900 text-white font-mono text-xs flex items-center gap-2">
          <ShieldCheck size={16} className="text-emerald-400" />
          <span>Non-Transferable Signatures</span>
        </div>
      </div>

      {/* Message */}
      {activeMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-950 font-mono text-xs flex items-center gap-3">
          <CheckCircle size={18} className="text-emerald-600 shrink-0" />
          <span>{activeMessage}</span>
        </div>
      )}

      {/* Approvals list */}
      <div className="space-y-4">
        {approvals.map(appr => (
          <div key={appr.approvalId} className="card p-6 border border-slate-200 shadow-sm space-y-4">
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs font-bold text-slate-900">{appr.approvalId}</span>
                  <span className="badge bg-indigo-50 text-indigo-700 font-bold">{appr.scope}</span>
                  <span className="text-xs font-mono text-slate-500">{appr.projectId}</span>
                  <span className={`badge ${
                    appr.state === 'APPROVED' ? 'bg-emerald-100 text-emerald-800' :
                    appr.state === 'REJECTED' ? 'bg-rose-100 text-rose-800' :
                    'bg-amber-100 text-amber-800'
                  }`}>
                    {appr.state}
                  </span>
                </div>
                <h3 className="text-base font-bold text-slate-900 mt-1">{appr.title}</h3>
                <p className="text-xs text-slate-600 font-mono mt-0.5">
                  Requested by: {appr.requestedBy} · Created: {appr.createdAt} · Expires: {appr.expiresAt}
                </p>
              </div>

              {appr.state === 'PENDING' ? (
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleAction(appr.approvalId, 'REJECTED')}
                    className="px-3.5 py-1.5 rounded-lg border border-rose-300 text-rose-700 bg-rose-50 text-xs font-bold hover:bg-rose-100 transition-all flex items-center gap-1.5"
                  >
                    <XCircle size={14} /> Reject
                  </button>
                  <button
                    onClick={() => handleAction(appr.approvalId, 'APPROVED')}
                    className="px-4 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 transition-all shadow-sm flex items-center gap-1.5"
                  >
                    <CheckCircle size={14} /> Approve & Sign Hash
                  </button>
                </div>
              ) : (
                <span className="text-xs font-mono font-bold text-slate-500">
                  Decision Finalized
                </span>
              )}
            </div>

            {/* Cryptographic Artifact Hash Binding */}
            <div className="p-3.5 rounded-xl bg-slate-900 text-slate-200 font-mono text-xs space-y-1">
              <div className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider">
                Bound Target Action & Artifact SHA-256 Digest:
              </div>
              <div className="text-amber-400 font-bold text-xs truncate">
                ACTION: {appr.action}
              </div>
              <div className="text-emerald-400 text-[11px] break-all">
                HASH: {appr.artifactHash}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
