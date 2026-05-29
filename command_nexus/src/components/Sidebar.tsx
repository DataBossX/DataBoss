import { NavLink } from 'react-router-dom'
import {
  Zap, LayoutDashboard, FlaskConical, FileText,
  Target, BarChart2, FileSearch, FolderOpen,
  ClipboardList, Activity, ScrollText, ChevronRight,
} from 'lucide-react'

const SECTIONS = [
  {
    title: 'COMMAND CENTER',
    items: [
      { to: '/',         icon: LayoutDashboard, label: 'HQ Dashboard' },
      { to: '/ocr',      icon: FlaskConical,    label: 'OCR Lab' },
      { to: '/docs',     icon: FileText,        label: 'Document Library' },
    ],
  },
  {
    title: 'MINERAL DEAL ROOM',
    items: [
      { to: '/deals',    icon: Target,          label: 'Deal Dashboard' },
      { to: '/targets',  icon: Target,          label: 'Target Factory' },
      { to: '/scoring',  icon: BarChart2,       label: 'Deal Scoring' },
      { to: '/review',   icon: FileSearch,      label: 'Review Queue' },
      { to: '/evidence', icon: FolderOpen,      label: 'Field Evidence' },
      { to: '/audit',    icon: ClipboardList,   label: 'Audit Trail' },
    ],
  },
  {
    title: 'SYSTEM',
    items: [
      { to: '/analytics', icon: Activity,   label: 'Analytics' },
      { to: '/logs',      icon: ScrollText, label: 'System Logs' },
    ],
  },
]

export default function Sidebar() {
  return (
    <aside className="w-64 min-h-screen bg-nx-sidebar border-r border-nx-border flex flex-col shrink-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-nx-border">
        <div className="flex items-center gap-2">
          <Zap className="text-cyan-400" size={20} />
          <div>
            <div className="text-white font-bold text-sm tracking-widest">DATABOSSX</div>
            <div className="text-cyan-500 text-xs tracking-wider">COMMAND NEXUS</div>
          </div>
        </div>
        <div className="mt-2 flex items-center gap-1.5">
          <span className="dot-online" />
          <span className="text-xs text-nx-muted">LOCAL INSTANCE · v1.0</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-5 overflow-y-auto">
        {SECTIONS.map(({ title, items }) => (
          <div key={title}>
            <div className="px-2 mb-2 text-[10px] font-bold tracking-widest text-nx-muted/60 uppercase">
              {title}
            </div>
            <div className="space-y-0.5">
              {items.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/25 shadow-[0_0_8px_rgba(6,182,212,0.1)]'
                        : 'text-nx-muted hover:bg-nx-card hover:text-nx-text'
                    }`
                  }
                >
                  <Icon size={15} />
                  {label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-nx-border">
        <div className="text-[10px] text-nx-muted/60 uppercase tracking-wider">Offline-First · No Cloud Sync</div>
        <div className="text-[10px] text-nx-muted/40 mt-0.5">Backend: localhost:8001</div>
      </div>
    </aside>
  )
}
