import { useState } from 'react'
import { SEEDED_CONFLICTS } from '../data/sampleData'
import type { ConflictRecord } from '../types'
import { AlertOctagon, CheckCircle2, ShieldAlert, FileText, ArrowRight, BookOpen, AlertTriangle } from 'lucide-react'

export default function RedTeamTraps() {
  const [conflicts] = useState<ConflictRecord[]>(SEEDED_CONFLICTS)
  const [selectedId, setSelectedId] = useState<string>('CF-1')
  const activeConflict = conflicts.find(c => c.id === selectedId) || conflicts[0]

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-bold rounded bg-amber-100 text-amber-900 border border-amber-300">
              FROZEN FIXTURE RED-TEAM TRAPS
            </span>
            <span className="text-xs font-mono text-slate-500">RT-22 THROUGH RT-26</span>
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight mt-1">
            Red-Team Conflict Traps & Data Truth Matrix
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            5 deliberate safety traps seeded in tournament fixtures. A compliant system must preserve dual claims, maintain history, and never fabricate.
          </p>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-900 text-white font-mono text-xs flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span>Zero Fabricated Merges / 100% Provenance Retained</span>
        </div>
      </div>

      {/* Traps Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Conflict list */}
        <div className="space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">Seeded Traps ({conflicts.length})</h2>
          {conflicts.map(c => {
            const isSelected = c.id === selectedId
            return (
              <button
                key={c.id}
                onClick={() => setSelectedId(c.id)}
                className={`w-full text-left p-4 rounded-xl border transition-all ${
                  isSelected
                    ? 'bg-orange-50 border-orange-500 ring-2 ring-orange-200 shadow-sm'
                    : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono font-bold text-xs text-orange-700">{c.id} ({c.exercises})</span>
                  <span className="badge bg-slate-100 text-slate-700 font-mono text-[10px]">{c.status}</span>
                </div>
                <div className="text-xs font-bold text-slate-900 leading-snug">{c.title}</div>
                <div className="text-[11px] text-slate-500 mt-1 truncate">{c.type}</div>
              </button>
            )
          })}
        </div>

        {/* Right 2 columns: Trap deep-dive & live verification evidence */}
        <div className="lg:col-span-2 space-y-4">
          <div className="card p-6 space-y-5 border-slate-300">
            {/* Header info */}
            <div className="flex items-start justify-between pb-4 border-b border-slate-200">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xl font-black text-slate-900">{activeConflict.title}</span>
                  <span className="badge bg-orange-100 text-orange-800 font-bold">{activeConflict.exercises}</span>
                </div>
                <div className="text-xs font-mono text-slate-500 mt-1">
                  TRACT: {activeConflict.tractId} · TYPE: {activeConflict.type}
                </div>
              </div>
              <span className="px-3 py-1 text-xs font-black rounded-lg bg-emerald-100 text-emerald-800 border border-emerald-300">
                VERIFIED FAIL-SAFE
              </span>
            </div>

            {/* Description of Trap */}
            <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 space-y-1.5">
              <div className="text-xs font-bold text-amber-900 flex items-center gap-1.5">
                <AlertTriangle size={14} className="text-amber-700" /> Trap Mechanism:
              </div>
              <p className="text-xs text-amber-950 leading-relaxed font-sans">{activeConflict.description}</p>
            </div>

            {/* Required Safe Behavior */}
            <div className="p-4 rounded-xl bg-slate-900 text-white space-y-2">
              <div className="text-xs font-bold text-orange-400 flex items-center gap-1.5 uppercase tracking-wider">
                <CheckCircle2 size={14} className="text-orange-400" /> Non-Negotiable Safe Behavior (Scored Rule)
              </div>
              <p className="text-xs text-slate-200 font-mono leading-relaxed">{activeConflict.requiredBehavior}</p>
            </div>

            {/* If CF-1 Dual Claims */}
            {activeConflict.claims && activeConflict.claims.length > 0 && (
              <div className="space-y-3 pt-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  Preserved Dual Claims (Zero Silent Flattening)
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {activeConflict.claims.map(claim => (
                    <div key={claim.claimId} className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-sm space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-bold text-indigo-700">{claim.claimId}</span>
                        <span className="badge bg-indigo-50 text-indigo-700 font-bold">{claim.fraction} {claim.interestType}</span>
                      </div>
                      <div className="text-xs font-bold text-slate-900">{claim.party}</div>
                      <div className="text-[11px] text-slate-500 font-mono">{claim.source}</div>
                      <div className="text-[10px] text-emerald-700 font-semibold pt-1">
                        CONFIDENCE: {claim.confidence} (Human Review Required)
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
