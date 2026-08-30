import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  ShieldCheck,
  AlertOctagon,
  Cpu,
  CheckSquare,
  Activity,
  Target,
  BarChart2,
  FileSearch,
  FolderOpen,
  ClipboardList,
  Flame,
  Layers,
  FileCode2
} from 'lucide-react'

const TOURNAMENT_NAV = [
  { to: '/',             icon: LayoutDashboard, label: 'Executive Cockpit' },
  { to: '/holds',        icon: ShieldCheck,     label: 'Fail-Closed Holds (P-21)' },
  { to: '/conflicts',    icon: AlertOctagon,    label: 'Red-Team Traps (RT-22)' },
  { to: '/jobs',         icon: Cpu,             label: 'Simulated Workers (P-12)' },
  { to: '/approvals',    icon: CheckSquare,     label: 'Bound Approvals (P-6)' },
  { to: '/wells',        icon: Activity,        label: 'Well Brain & OCC (RT-23)' },
  { to: '/receipts',     icon: FileCode2,       label: 'Audit Receipts (P-18)' },
]

const CLASSIC_NAV = [
  { to: '/targets',      icon: Target,          label: 'Target Factory' },
  { to: '/scoring',      icon: BarChart2,        label: 'Deal Scoring' },
  { to: '/review',       icon: FileSearch,       label: 'Review Queue' },
  { to: '/evidence',     icon: FolderOpen,       label: 'Field Evidence' },
  { to: '/audit',        icon: ClipboardList,    label: 'Audit Trail' },
]

export default function Sidebar() {
  return (
    <aside className="w-64 min-h-screen bg-slate-900 border-r border-slate-800 flex flex-col shrink-0">
      {/* Brand Header */}
      <div className="px-5 py-4 border-b border-slate-800 bg-slate-950/60">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center shadow-md shadow-orange-500/20">
            <Flame className="text-white" size={18} />
          </div>
          <div>
            <div className="text-white font-bold text-sm tracking-tight flex items-center gap-1.5">
              DataBossX <span className="text-[10px] bg-orange-500/20 text-orange-400 font-mono px-1.5 py-0.2 rounded border border-orange-500/30">CHALLENGER</span>
            </div>
            <div className="text-slate-400 text-xs">Autonomous Command OS</div>
          </div>
        </div>
      </div>

      {/* Navigation Sections */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        <div>
          <div className="px-3 text-[11px] font-semibold tracking-wider text-slate-400 uppercase mb-2 flex items-center gap-1.5">
            <Layers size={12} className="text-orange-400" /> Command Center
          </div>
          <nav className="space-y-1">
            {TOURNAMENT_NAV.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-gradient-to-r from-orange-500 to-amber-600 text-white font-semibold shadow-sm'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`
                }
              >
                <Icon size={15} />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div>
          <div className="px-3 text-[11px] font-semibold tracking-wider text-slate-400 uppercase mb-2">
            Mineral Deal Room
          </div>
          <nav className="space-y-1">
            {CLASSIC_NAV.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-slate-800 text-orange-400 font-semibold border-l-2 border-orange-500'
                      : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                  }`
                }
              >
                <Icon size={15} />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </div>

      {/* Safety & Environment Status Badge */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/70">
        <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 space-y-1">
          <div className="flex items-center justify-between text-[11px] font-bold">
            <span>PRIVACY MODE</span>
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          </div>
          <div className="text-[10px] text-emerald-400/80 leading-tight font-mono">
            Synthetic-Only · PR #75 Frozen Fixture · Zero Secret Leaks
          </div>
        </div>
      </div>
    </aside>
  )
}
