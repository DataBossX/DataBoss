import { useState } from 'react'
import { SEEDED_WELLS } from '../data/sampleData'
import type { WellRecord } from '../types'
import { Activity, Droplet, Flame, AlertCircle, History, CheckCircle2, ShieldAlert } from 'lucide-react'

export default function WellBrain() {
  const [wells] = useState<WellRecord[]>(SEEDED_WELLS)
  const [selectedWellId, setSelectedWellId] = useState<string>('W-SEED-0001')
  const activeWell = wells.find(w => w.wellId === selectedWellId) || wells[0]

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-bold rounded bg-cyan-100 text-cyan-900 border border-cyan-300">
              WELL BRAIN & PRODUCTION INTELLIGENCE
            </span>
            <span className="text-xs font-mono text-slate-500">OCC FEEDS & TIME-AWARE RESTATEMENTS (RT-23, RT-24)</span>
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight mt-1">
            Well Intelligence & Regulatory Feed Monitor
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            Real-time tracking of Oklahoma OCC regulatory filings, producing horizontal wellbores, and time-aware amended reports.
          </p>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-900 text-white font-mono text-xs flex items-center gap-2">
          <Activity size={16} className="text-cyan-400" />
          <span>3 Monitored Wells · Sandhill Basin</span>
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Well selector */}
        <div className="space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">Active Wellbores</h2>
          {wells.map(w => {
            const isSelected = w.wellId === selectedWellId
            return (
              <button
                key={w.wellId}
                onClick={() => setSelectedWellId(w.wellId)}
                className={`w-full text-left p-4 rounded-xl border transition-all ${
                  isSelected
                    ? 'bg-cyan-50 border-cyan-500 ring-2 ring-cyan-200 shadow-sm'
                    : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono font-bold text-xs text-cyan-800">{w.api}</span>
                  <span className={`badge text-[10px] ${
                    w.status === 'PRODUCING' ? 'bg-emerald-100 text-emerald-800' :
                    w.status === 'SHUT_IN' ? 'bg-amber-100 text-amber-800' :
                    'bg-blue-100 text-blue-800'
                  }`}>
                    {w.status}
                  </span>
                </div>
                <div className="text-xs font-bold text-slate-900">{w.name}</div>
                <div className="text-[11px] text-slate-500 mt-0.5">{w.operatorName}</div>
                <div className="text-[10px] font-mono text-slate-400 mt-1">{w.surfaceLocation}</div>
              </button>
            )
          })}
        </div>

        {/* Right 2 columns: Well detail & monthly production */}
        <div className="lg:col-span-2 space-y-5">
          <div className="card p-6 border-slate-300 space-y-5">
            {/* Header info */}
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 pb-4 border-b border-slate-200">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-black text-slate-900">{activeWell.name}</h2>
                  <span className="badge bg-slate-100 text-slate-700 font-bold">{activeWell.wellboreType}</span>
                </div>
                <div className="text-xs font-mono text-slate-600 mt-1">
                  API: {activeWell.api} · Operator: {activeWell.operatorName} · Formation: {activeWell.formation}
                </div>
              </div>

              <div className="text-right">
                <span className={`badge font-bold px-3 py-1 ${
                  activeWell.linkConfidence === 'HIGH'
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                    : 'bg-amber-100 text-amber-900 border border-amber-300'
                }`}>
                  TRACT LINK: {activeWell.linkConfidence}
                </span>
              </div>
            </div>

            {/* Ambiguity notice for W-SEED-0003 */}
            {activeWell.ambiguityNote && (
              <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-950 flex items-start gap-3">
                <AlertCircle size={18} className="text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <strong className="font-bold">Unit Boundary & Lateral Allocation Ambiguity (RT-24):</strong>
                  <p className="mt-0.5">{activeWell.ambiguityNote}</p>
                </div>
              </div>
            )}

            {/* Monthly Production Table (Time-aware and Restatements RT-23) */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                <History size={14} className="text-cyan-600" /> Historical Monthly Production (OCC Data Feed)
              </h3>

              {activeWell.monthlyProduction && activeWell.monthlyProduction.length > 0 ? (
                <div className="overflow-x-auto border border-slate-200 rounded-xl">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-50 border-b border-slate-200">
                      <tr>
                        <th className="table-th">Period</th>
                        <th className="table-th">Oil (Bbl)</th>
                        <th className="table-th">Gas (Mcf)</th>
                        <th className="table-th">Water (Bbl)</th>
                        <th className="table-th">Source</th>
                        <th className="table-th">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeWell.monthlyProduction.map((p, idx) => (
                        <tr key={idx} className={`border-b border-slate-100 ${p.restated ? 'bg-amber-50/60' : 'hover:bg-slate-50'}`}>
                          <td className="table-td font-mono font-bold">{p.period}</td>
                          <td className="table-td font-mono">{p.oilBbl.toLocaleString()}</td>
                          <td className="table-td font-mono">{p.gasMcf.toLocaleString()}</td>
                          <td className="table-td font-mono">{p.waterBbl.toLocaleString()}</td>
                          <td className="table-td font-mono text-slate-500">{p.source}</td>
                          <td className="table-td">
                            {p.restated ? (
                              <div>
                                <span className="badge bg-amber-100 text-amber-900 border border-amber-300 font-bold">
                                  RESTATED / SUPERSEDED
                                </span>
                                {p.restatementNote && (
                                  <div className="text-[10px] text-amber-800 font-sans mt-0.5">
                                    {p.restatementNote}
                                  </div>
                                )}
                              </div>
                            ) : (
                              <span className="badge bg-emerald-100 text-emerald-800">ORIGINAL</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-500 text-center">
                  No historical production records yet (Permitted / Not Spud).
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
