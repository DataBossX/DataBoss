interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  accent?: boolean
  warn?: boolean
}

export default function StatCard({ label, value, sub, accent, warn }: StatCardProps) {
  return (
    <div className={`card p-5 ${accent ? 'border-orange-200 bg-orange-50' : warn ? 'border-yellow-200 bg-yellow-50' : ''}`}>
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-2xl font-bold ${accent ? 'text-orange-600' : warn ? 'text-yellow-700' : 'text-slate-900'}`}>
        {value}
      </div>
      {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
    </div>
  )
}
