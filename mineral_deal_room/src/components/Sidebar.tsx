import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Target, FileSearch, FolderOpen,
  BarChart2, ClipboardList, Flame,
} from 'lucide-react'

const NAV = [
  { to: '/',             icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/targets',      icon: Target,          label: 'Target Factory' },
  { to: '/scoring',      icon: BarChart2,        label: 'Deal Scoring' },
  { to: '/review',       icon: FileSearch,       label: 'Review Queue' },
  { to: '/evidence',     icon: FolderOpen,       label: 'Field Evidence' },
  { to: '/audit',        icon: ClipboardList,    label: 'Audit Trail' },
]

export default function Sidebar() {
  return (
    <aside className="w-64 min-h-screen bg-slate-900 flex flex-col">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Flame className="text-orange-500" size={22} />
          <div>
            <div className="text-white font-bold text-sm leading-tight">DataBossX</div>
            <div className="text-orange-400 text-xs leading-tight">Mineral Deal Room</div>
          </div>
        </div>
        <div className="mt-2 text-slate-500 text-xs">Target Factory v1</div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-orange-500 text-white'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-white'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-slate-700">
        <div className="text-slate-500 text-xs">Local-only · No cloud sync</div>
        <div className="text-slate-600 text-xs mt-0.5">Sample data · No real records</div>
      </div>
    </aside>
  )
}
