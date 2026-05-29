interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  accent?: boolean
  warn?: boolean
  cyan?: boolean
}

export default function StatCard({ label, value, sub, accent, warn, cyan }: StatCardProps) {
  const border = cyan ? 'border-cyan-500/40' : accent ? 'border-orange-500/30' : warn ? 'border-yellow-500/30' : 'border-nx-border'
  const valColor = cyan ? 'text-cyan-400' : accent ? 'text-orange-400' : warn ? 'text-yellow-400' : 'text-white'
  return (
    <div className={`nx-card p-5 ${border}`}>
      <div className="text-xs font-semibold text-nx-muted uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-2xl font-bold font-mono ${valColor}`}>{value}</div>
      {sub && <div className="text-xs text-nx-muted mt-1">{sub}</div>}
    </div>
  )
}
