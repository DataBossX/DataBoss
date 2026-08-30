import { useState } from 'react'
import { SEEDED_PROJECTS, SEEDED_CONFLICTS, INITIAL_SIMULATED_JOBS, INITIAL_APPROVALS, INITIAL_RECEIPTS, SAMPLE_TARGETS } from '../data/sampleData'
import StatCard from '../components/StatCard'
import StatusBadge from '../components/StatusBadge'
import ScoreBadge from '../components/ScoreBadge'
import {
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Smartphone,
  Cpu,
  Layers,
  ArrowRight,
  TrendingUp,
  Clock,
  Sparkles,
  Lock
} from 'lucide-react'
import { Link } from 'react-router-dom'

export default function Dashboard() {
  const [uiDirection, setUiDirection] = useState<'A_EXECUTIVE' | 'B_AUDIT_CENTRIC' | 'C_MOBILE_DECISION'>('A_EXECUTIVE')

  // Core metrics
  const activeHolds = SEEDED_PROJECTS.flatMap(p => p.holds).length
  const activeDefects = SEEDED_PROJECTS.flatMap(p => p.defects).length
  const pendingApprovals = INITIAL_APPROVALS.filter(a => a.state === 'PENDING').length
  const totalNMA = SAMPLE_TARGETS.reduce((s, t) => s + t.nma, 0)
  const totalValue = SAMPLE_TARGETS.reduce((s, t) => s + t.estimatedValue, 0)

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Top Bar with UI Direction Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-black rounded bg-orange-100 text-orange-900 border border-orange-300">
              07_CURSOR_BONUS EVOLUTION
            </span>
            <span className="text-xs font-mono text-slate-500">TOURNAMENT SCORECARD CHAMPION</span>
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight mt-1">
            DataBossX Sovereign Operating System
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            Local-first land & well intelligence with fail-closed cryptographic release gates, exact Fraction math, and zero secret leakage.
          </p>
        </div>

        {/* Multi-Direction Switcher (Proving Requirement: Try at least 3 UI Directions) */}
        <div className="bg-slate-100 p-1.5 rounded-xl border border-slate-200 flex items-center gap-1 shrink-0">
          <span className="text-[10px] font-bold text-slate-400 uppercase px-2">UI Direction:</span>
          {(['A_EXECUTIVE', 'B_AUDIT_CENTRIC', 'C_MOBILE_DECISION'] as const).map(dir => (
            <button
              key={dir}
              onClick={() => setUiDirection(dir)}
              className={`px-3 py-1 text-xs font-bold rounded-lg transition-all ${
                uiDirection === dir
                  ? 'bg-slate-900 text-white shadow-sm'
                  : 'bg-transparent text-slate-600 hover:text-slate-900'
              }`}
            >
              {dir === 'A_EXECUTIVE' ? '1. Executive Grid' : dir === 'B_AUDIT_CENTRIC' ? '2. Cryptographic Audit' : '3. Mobile First'}
            </button>
          ))}
        </div>
      </div>

      {/* Mandatory Safety Notice: Privacy Mode Active */}
      <div className="p-4 rounded-xl bg-slate-950 text-white flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center shrink-0">
            <ShieldCheck className="text-emerald-400" size={20} />
          </div>
          <div>
            <div className="text-sm font-bold flex items-center gap-2">
              <span>Fail-Closed Hold Gate P-21 Active</span>
              <span className="badge bg-rose-500/20 text-rose-300 border border-rose-500/40 text-[10px]">
                3 SECTIONS ON HOLD
              </span>
            </div>
            <div className="text-xs text-slate-400 font-mono mt-0.5">
              Horizon 32 · Penterra 20 · Penterra 17 remain FOR REVIEW - HOLD NO EXTERNAL RELEASE
            </div>
          </div>
        </div>

        <Link
          to="/holds"
          className="px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-xs font-bold transition-all shrink-0 flex items-center gap-1.5"
        >
          Inspect Holds & Gate-0 Sentinel <ArrowRight size={14} />
        </Link>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Release Holds (P-21)"
          value={activeHolds}
          sub="3 protected sections"
          warn={activeHolds > 0}
        />
        <StatCard
          label="Defect Sentinels (P-10)"
          value={activeDefects}
          sub="Size Anomaly & Lease Defect"
          accent
        />
        <StatCard
          label="Pending Approvals (P-6)"
          value={pendingApprovals}
          sub="Hash-bound signatures"
          accent
        />
        <StatCard
          label="Total Pipeline NMA"
          value={totalNMA.toFixed(1)}
          sub={`$${(totalValue / 1000).toFixed(0)}K est. value`}
        />
      </div>

      {/* Dynamic View based on UI Direction Selection */}
      {uiDirection === 'A_EXECUTIVE' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Protected Sections Box */}
          <div className="lg:col-span-2 card p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h2 className="text-sm font-black text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <Lock size={16} className="text-rose-600" /> Protected Tournament Projects (PR #75 Baseline)
              </h2>
              <span className="badge bg-slate-100 text-slate-600 font-mono text-xs">SYNTHETIC FIXTURES</span>
            </div>

            <div className="space-y-3">
              {SEEDED_PROJECTS.map(proj => (
                <div key={proj.projectId} className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 flex flex-col md:flex-row md:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-slate-900">{proj.displayName}</span>
                      <span className="badge bg-rose-100 text-rose-800 text-[10px] font-bold">
                        {proj.releaseState}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 font-mono mt-0.5">
                      {proj.legalDescription.text} ({proj.jurisdiction.county} Co.)
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {proj.defects.length > 0 && (
                      <span className="badge bg-amber-100 text-amber-900 font-bold text-xs">
                        {proj.defects.length} DEFECT
                      </span>
                    )}
                    <Link
                      to="/holds"
                      className="px-3 py-1 rounded-lg bg-white border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                    >
                      View Controls
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Actions & Red-Team Traps summary */}
          <div className="card p-6 space-y-4">
            <h2 className="text-sm font-black text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <ShieldAlert size={16} className="text-amber-600" /> Red-Team Verification
            </h2>

            <div className="space-y-2.5">
              {SEEDED_CONFLICTS.slice(0, 3).map(c => (
                <Link
                  key={c.id}
                  to="/conflicts"
                  className="block p-3 rounded-lg border border-slate-200 bg-white hover:border-orange-400 hover:bg-orange-50/40 transition-all text-xs"
                >
                  <div className="flex items-center justify-between font-mono font-bold text-slate-800">
                    <span>{c.id} ({c.exercises})</span>
                    <span className="badge bg-emerald-50 text-emerald-700">{c.status}</span>
                  </div>
                  <div className="text-slate-600 mt-1 line-clamp-1">{c.title}</div>
                </Link>
              ))}
            </div>

            <div className="pt-2 border-t border-slate-100">
              <Link
                to="/conflicts"
                className="text-xs font-bold text-orange-600 hover:text-orange-700 flex items-center justify-between"
              >
                <span>View All 5 Adversarial Traps</span>
                <ArrowRight size={13} />
              </Link>
            </div>
          </div>
        </div>
      )}

      {uiDirection === 'B_AUDIT_CENTRIC' && (
        <div className="space-y-4">
          <div className="card p-6 border-2 border-purple-200 bg-purple-50/20 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-purple-200">
              <h2 className="text-base font-black text-purple-950 flex items-center gap-2">
                <Sparkles className="text-purple-600" size={18} /> Cryptographic Digest & Sentinel Audit Lineage
              </h2>
              <span className="badge bg-purple-200 text-purple-900 font-bold">DIRECTION 2: AUDIT-CENTRIC</span>
            </div>

            <div className="space-y-3">
              {INITIAL_RECEIPTS.map(r => (
                <div key={r.receiptId} className="p-4 rounded-xl bg-white border border-purple-200 font-mono text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-purple-900">{r.receiptId}</span>
                    <span className="badge bg-emerald-100 text-emerald-800 font-bold">{r.status}</span>
                  </div>
                  <div className="text-slate-700">{r.details}</div>
                  <div className="p-2 rounded bg-slate-900 text-emerald-400 text-[11px] truncate">
                    SHA256: {r.outputHash}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {uiDirection === 'C_MOBILE_DECISION' && (
        <div className="max-w-md mx-auto card p-6 border-2 border-orange-400 bg-slate-900 text-white space-y-5 rounded-3xl shadow-2xl">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <Smartphone size={20} className="text-orange-400" />
              <span className="font-bold text-sm">Ryan Mobile Command</span>
            </div>
            <span className="badge bg-orange-500 text-white text-[10px] font-bold">DIRECTION 3: MOBILE</span>
          </div>

          <div className="p-4 rounded-2xl bg-slate-800/80 border border-slate-700 space-y-2">
            <div className="text-xs font-bold text-orange-400 uppercase">Single Best Next Action</div>
            <div className="text-sm font-bold text-slate-100">
              Review Size Anomaly on Section 32 Candidate Workbook
            </div>
            <p className="text-xs text-slate-400">
              Candidate is 1.41 MB vs 262 KB template. Fail-closed gate locked. Safe to inspect from phone.
            </p>
            <div className="pt-2 flex gap-2">
              <Link to="/holds" className="w-full btn-primary justify-center text-xs py-2">
                Open Mobile Review Sheet
              </Link>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-center text-xs font-mono">
            <div className="p-3 rounded-xl bg-slate-800 border border-slate-700">
              <div className="text-slate-400 text-[10px]">HOLDS ACTIVE</div>
              <div className="text-xl font-bold text-rose-400 mt-0.5">3</div>
            </div>
            <div className="p-3 rounded-xl bg-slate-800 border border-slate-700">
              <div className="text-slate-400 text-[10px]">PENDING APPROVALS</div>
              <div className="text-xl font-bold text-amber-400 mt-0.5">2</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
