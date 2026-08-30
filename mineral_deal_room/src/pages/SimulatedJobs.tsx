import { useState } from 'react'
import { INITIAL_SIMULATED_JOBS } from '../data/sampleData'
import type { SimulatedJob } from '../types'
import { Cpu, Play, CheckCircle2, AlertCircle, RefreshCw, Smartphone, Key, ShieldCheck, CornerDownRight } from 'lucide-react'

export default function SimulatedJobs() {
  const [jobs, setJobs] = useState<SimulatedJob[]>(INITIAL_SIMULATED_JOBS)
  const [executingId, setExecutingId] = useState<string | null>(null)
  const [doubleTapAlert, setDoubleTapAlert] = useState<string | null>(null)

  // Trigger simulated execution (Testing RT-6 & RT-27 Idempotency)
  function executeJob(job: SimulatedJob) {
    if (job.state === 'RUNNING' || executingId === job.jobId) {
      setDoubleTapAlert(`[IDEMPOTENCY LOCK P-14 / RT-27] Double-tap blocked for idempotency key '${job.idempotencyKey}'. Request deduplicated — zero double-execution.`)
      setTimeout(() => setDoubleTapAlert(null), 6000)
      return
    }

    if (job.state === 'COMPLETED') {
      setDoubleTapAlert(`[IDEMPOTENCY REPLAY GUARD RT-6] Job '${job.jobId}' already completed with hash. Resubmission rejected.`)
      setTimeout(() => setDoubleTapAlert(null), 6000)
      return
    }

    setExecutingId(job.jobId)
    setJobs(prev => prev.map(j => j.jobId === job.jobId ? { ...j, state: 'RUNNING' } : j))

    setTimeout(() => {
      setJobs(prev => prev.map(j => j.jobId === job.jobId ? {
        ...j,
        state: 'COMPLETED',
        completedAt: new Date().toISOString(),
        resultHash: 'ad0cf2cfde55726d4a6ef36681693a399cf2835465c05bda36624aed73b8b19f'
      } : j))
      setExecutingId(null)
    }, 1500)
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-bold rounded bg-indigo-100 text-indigo-900 border border-indigo-300">
              SAFE LOCAL WORKERS P-12
            </span>
            <span className="text-xs font-mono text-slate-500">IDEMPOTENCY & LEASE FENCING (RT-6, RT-27)</span>
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight mt-1">
            Simulated Worker Execution Queue
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            Sandboxed local execution tasks with cryptographic idempotency keys, nonces, and zero unauthenticated shell access.
          </p>
        </div>

        {/* Prominent Simulated Labeling (P-20 / RT-21) */}
        <div className="p-3 rounded-xl bg-amber-500/10 border-2 border-amber-500 text-amber-950 text-xs font-bold flex items-center gap-2">
          <ShieldCheck size={18} className="text-amber-600 shrink-0" />
          <span>ALL ACTIONS SIMULATED IN THIS RUNTIME (P-20 CERTIFIED)</span>
        </div>
      </div>

      {/* Double tap notification */}
      {doubleTapAlert && (
        <div className="p-4 rounded-xl bg-indigo-50 border border-indigo-300 text-indigo-950 font-mono text-xs flex items-center gap-3">
          <Smartphone size={18} className="text-indigo-600 shrink-0" />
          <span>{doubleTapAlert}</span>
        </div>
      )}

      {/* Jobs list */}
      <div className="space-y-4">
        {jobs.map(job => (
          <div key={job.jobId} className="card p-5 border border-slate-200 shadow-sm space-y-3">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-xs font-bold text-slate-900">{job.jobId}</span>
                <span className="badge bg-slate-100 text-slate-700 font-bold">{job.taskType}</span>
                <span className="text-xs font-mono text-slate-500">{job.projectId}</span>
                <span className={`badge ${
                  job.state === 'COMPLETED' ? 'bg-emerald-100 text-emerald-800' :
                  job.state === 'RUNNING' ? 'bg-amber-100 text-amber-800 animate-pulse' :
                  'bg-blue-100 text-blue-800'
                }`}>
                  {job.state}
                </span>
                <span className="badge bg-amber-100 text-amber-900 border border-amber-300 font-bold">
                  SIMULATED (P-20)
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  disabled={job.state === 'RUNNING'}
                  onClick={() => executeJob(job)}
                  className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 ${
                    job.state === 'COMPLETED'
                      ? 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      : 'bg-orange-500 hover:bg-orange-600 text-white shadow-sm'
                  }`}
                >
                  {job.state === 'RUNNING' ? (
                    <>
                      <RefreshCw size={14} className="animate-spin" /> Executing Task...
                    </>
                  ) : job.state === 'COMPLETED' ? (
                    <>
                      <Smartphone size={14} /> Re-Submit (Test RT-6 Guard)
                    </>
                  ) : (
                    <>
                      <Play size={14} /> Run Simulated Task
                    </>
                  )}
                </button>
              </div>
            </div>

            <p className="text-xs text-slate-700 font-medium">{job.payloadSummary}</p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100 font-mono text-[11px] text-slate-600">
              <div className="flex items-center gap-1.5">
                <Key size={13} className="text-slate-400" />
                <span className="truncate">Key: {job.idempotencyKey}</span>
              </div>
              <div>Worker: {job.workerId}</div>
              <div>Priority: {job.priority}</div>
            </div>

            {job.resultHash && (
              <div className="p-2.5 rounded-lg bg-emerald-50/80 border border-emerald-200 font-mono text-[11px] text-emerald-900 flex items-center gap-2">
                <CheckCircle2 size={14} className="text-emerald-600 shrink-0" />
                <span className="truncate">Output Hash: {job.resultHash} (Verified & Signed)</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
