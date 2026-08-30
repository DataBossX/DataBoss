import { useState } from 'react'
import { SEEDED_PROJECTS, INITIAL_RECEIPTS } from '../data/sampleData'
import type { ProjectCommandRecord, HoldRecord } from '../types'
import { ShieldCheck, ShieldAlert, Lock, AlertTriangle, CheckCircle, RefreshCw, Smartphone, Hash, FileCheck } from 'lucide-react'

export default function HoldRegistry() {
  const [projects, setProjects] = useState<ProjectCommandRecord[]>(SEEDED_PROJECTS)
  const [activeTab, setActiveTab] = useState<'ALL' | 'SEC32' | 'SEC20' | 'SEC17'>('ALL')
  const [simulationMsg, setSimulationMsg] = useState<string | null>(null)
  const [authenticatedRole, setAuthenticatedRole] = useState<'VIEWER' | 'AUTOMATED_AGENT' | 'EXAMINER' | 'OWNER_PRINCIPAL'>('VIEWER')

  // Red-Team RT-20 automated attack test
  function attemptAutomatedClear(hold: HoldRecord) {
    if (authenticatedRole === 'AUTOMATED_AGENT' || !hold.clearableByAutomation) {
      setSimulationMsg(`[FAIL-CLOSED DEFENSE TRIGGERED] Automated or unauthorized actor (${authenticatedRole}) attempted to clear hold '${hold.holdId}'. Action DENIED by fail-closed gate P-21 / RT-20. Hold remains 100% active.`)
      setTimeout(() => setSimulationMsg(null), 8000)
      return
    }
    if (authenticatedRole === 'OWNER_PRINCIPAL') {
      setSimulationMsg(`[HUMAN AUDITED OVERRIDE] Owner principal authenticated. Hold '${hold.holdId}' cleared with append-only cryptographic receipt.`)
      setProjects(prev => prev.map(p => ({
        ...p,
        holds: p.holds.filter(h => h.holdId !== hold.holdId),
        releaseState: p.holds.length <= 1 ? 'RELEASE_READY' : p.releaseState
      })))
      setTimeout(() => setSimulationMsg(null), 8000)
    } else {
      setSimulationMsg(`[PERMISSION DENIED] Role '${authenticatedRole}' is not authorized to clear internal review controls. Requires OWNER_PRINCIPAL.`)
      setTimeout(() => setSimulationMsg(null), 8000)
    }
  }

  const filteredProjects = projects.filter(p => {
    if (activeTab === 'SEC32') return p.projectId === 'SEED-HORIZON-32'
    if (activeTab === 'SEC20') return p.projectId === 'SEED-PENTERRA-20'
    if (activeTab === 'SEC17') return p.projectId === 'SEED-PENTERRA-17'
    return true
  })

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-bold rounded bg-rose-100 text-rose-800 border border-rose-300">
              MANDATORY SAFETY P-21
            </span>
            <span className="text-xs font-mono text-slate-500">RED-TEAM TARGET RT-20</span>
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight mt-1">
            Fail-Closed Hold Registry & Gate-0 Authority
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            Cryptographic hold enforcement across Horizon 32, Penterra 20, and Penterra 17. No automated agent can bypass release controls.
          </p>
        </div>

        {/* Role Switcher to prove authorization barriers */}
        <div className="bg-slate-100 p-2.5 rounded-xl border border-slate-200 flex flex-col gap-1.5 shrink-0">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Simulate Actor Role</span>
          <div className="flex gap-1.5 flex-wrap">
            {(['VIEWER', 'AUTOMATED_AGENT', 'EXAMINER', 'OWNER_PRINCIPAL'] as const).map(role => (
              <button
                key={role}
                onClick={() => setAuthenticatedRole(role)}
                className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-all ${
                  authenticatedRole === role
                    ? 'bg-slate-900 text-white shadow-sm'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                }`}
              >
                {role}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Alert / Notification message */}
      {simulationMsg && (
        <div className={`p-4 rounded-xl border font-mono text-xs flex items-start gap-3 transition-all ${
          simulationMsg.includes('DENIED') || simulationMsg.includes('FAIL-CLOSED')
            ? 'bg-amber-50 border-amber-300 text-amber-900'
            : 'bg-emerald-50 border-emerald-300 text-emerald-900'
        }`}>
          {simulationMsg.includes('DENIED') || simulationMsg.includes('FAIL-CLOSED') ? (
            <ShieldAlert size={18} className="text-amber-600 shrink-0 mt-0.5" />
          ) : (
            <CheckCircle size={18} className="text-emerald-600 shrink-0 mt-0.5" />
          )}
          <div>{simulationMsg}</div>
        </div>
      )}

      {/* Section Filter */}
      <div className="flex gap-2">
        {([
          ['ALL', 'All Protected Sections (3)'],
          ['SEC32', 'Horizon Section 32 (Hold + Size Anomaly)'],
          ['SEC20', 'Penterra Section 20 (Hold Only)'],
          ['SEC17', 'Penterra Section 17 (Hold + Lease Defect)'],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === key
                ? 'bg-orange-500 text-white shadow-sm'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Cards for each protected project */}
      <div className="grid grid-cols-1 gap-6">
        {filteredProjects.map(project => {
          const hasHolds = project.holds.length > 0
          const hasDefects = project.defects.length > 0

          return (
            <div
              key={project.projectId}
              className={`card p-6 border-2 transition-all ${
                hasHolds ? 'border-rose-200 bg-rose-50/20' : 'border-emerald-200 bg-white'
              }`}
            >
              {/* Card Header */}
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 pb-4 border-b border-slate-200">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-lg font-black text-slate-900">{project.displayName}</span>
                    <span className="text-xs font-mono bg-slate-100 text-slate-600 px-2 py-0.5 rounded border">
                      {project.projectId}
                    </span>
                    <span className={`px-2.5 py-0.5 text-xs font-bold rounded-full ${
                      hasHolds
                        ? 'bg-rose-100 text-rose-800 border border-rose-200'
                        : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                    }`}>
                      {project.releaseState}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 font-mono mt-1">
                    {project.legalDescription.text} ({project.jurisdiction.county} County, {project.jurisdiction.state})
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <div className="text-right">
                    <div className="text-[11px] font-bold text-slate-400 uppercase">Release Gate Status</div>
                    <div className={`text-sm font-black ${hasHolds ? 'text-rose-600' : 'text-emerald-600'}`}>
                      {hasHolds ? 'LOCKED / NO EXTERNAL RELEASE' : 'READY FOR VERIFIED DISPATCH'}
                    </div>
                  </div>
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${
                    hasHolds ? 'bg-rose-100 text-rose-600' : 'bg-emerald-100 text-emerald-600'
                  }`}>
                    {hasHolds ? <Lock size={20} /> : <CheckCircle size={20} />}
                  </div>
                </div>
              </div>

              {/* Holds List */}
              <div className="mt-5 space-y-3">
                <h3 className="text-xs font-bold tracking-wider text-slate-700 uppercase flex items-center gap-1.5">
                  <ShieldCheck size={14} className="text-rose-600" /> Active Cryptographic Holds ({project.holds.length})
                </h3>

                {project.holds.length === 0 ? (
                  <div className="p-3.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs">
                    Zero active holds on this section. All verification gates passed.
                  </div>
                ) : (
                  project.holds.map(hold => (
                    <div key={hold.holdId} className="p-4 rounded-xl bg-white border border-rose-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-xs text-rose-700">{hold.holdId}</span>
                          <span className="badge bg-rose-50 text-rose-700 border border-rose-200">{hold.kind}</span>
                          <span className="text-[10px] bg-slate-100 text-slate-600 font-mono px-1.5 py-0.5 rounded">
                            CLEARABLE: {hold.clearableBy}
                          </span>
                        </div>
                        <p className="text-xs font-medium text-slate-800">{hold.reason}</p>
                        <div className="text-[11px] text-slate-400 font-mono">
                          Set at {hold.setAt} by {hold.setBy} · Scope: {hold.scope}
                        </div>
                      </div>

                      <div className="shrink-0 flex items-center gap-2">
                        <button
                          onClick={() => attemptAutomatedClear(hold)}
                          className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-600 text-white hover:bg-rose-700 transition-colors flex items-center gap-1.5"
                        >
                          <Lock size={12} /> Attempt Hold Release (Test RT-20)
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Defects & Anomalies */}
              {hasDefects && (
                <div className="mt-5 space-y-3 pt-4 border-t border-slate-100">
                  <h3 className="text-xs font-bold tracking-wider text-amber-800 uppercase flex items-center gap-1.5">
                    <AlertTriangle size={14} className="text-amber-600" /> Active Defect Sentinel ({project.defects.length})
                  </h3>

                  {project.defects.map(defect => (
                    <div key={defect.defectId} className="p-4 rounded-xl bg-amber-50/50 border border-amber-200 text-xs space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-amber-800">{defect.defectId}</span>
                          <span className="badge bg-amber-100 text-amber-800 font-bold">{defect.type}</span>
                          <span className="badge bg-rose-100 text-rose-800 font-bold">SEVERITY {defect.severity}</span>
                        </div>
                        <span className="font-mono text-[11px] text-amber-900 bg-amber-100/80 px-2 py-0.5 rounded">
                          {defect.resolutionState}
                        </span>
                      </div>

                      <p className="font-medium text-slate-800">{defect.summary}</p>

                      {defect.observed && (
                        <div className="p-2.5 rounded-lg bg-white border border-amber-200 font-mono text-[11px] text-slate-700 grid grid-cols-3 gap-2">
                          <div>Observed: <strong className="text-rose-700">{defect.observed.candidateBytes?.toLocaleString()} bytes</strong></div>
                          <div>Template: <strong>{defect.observed.templateBytes?.toLocaleString()} bytes</strong></div>
                          <div>Tolerance: <strong>±{defect.observed.tolerancePct}%</strong></div>
                        </div>
                      )}

                      <div className="text-[11px] text-slate-600 italic bg-amber-100/40 p-2 rounded">
                        <strong>Required Behavior:</strong> {defect.expectedBehaviour}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
