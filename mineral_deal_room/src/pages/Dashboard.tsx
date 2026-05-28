import { SAMPLE_TARGETS, SAMPLE_AUDIT } from '../data/sampleData'
import StatCard from '../components/StatCard'
import StatusBadge from '../components/StatusBadge'
import ScoreBadge from '../components/ScoreBadge'
import { TrendingUp, AlertTriangle, CheckCircle, Clock } from 'lucide-react'

const STATUS_ORDER = ['Identified','Contacted','Under Review','Offer Sent','Signed','On Hold','Passed']

export default function Dashboard() {
  const targets = SAMPLE_TARGETS
  const totalNMA = targets.reduce((s, t) => s + t.nma, 0)
  const totalValue = targets.reduce((s, t) => s + t.estimatedValue, 0)
  const avgScore = Math.round(targets.reduce((s, t) => s + t.dealScore, 0) / targets.length)
  const signed = targets.filter(t => t.status === 'Signed')
  const needsCurative = targets.filter(t => t.titleClearance === 'Needs Curative' || t.titleClearance === 'Probate Pending')
  const topDeals = [...targets].filter(t => t.status !== 'Passed' && t.status !== 'Signed').sort((a, b) => b.dealScore - a.dealScore).slice(0, 5)

  const pipeline = STATUS_ORDER.map(s => ({
    status: s,
    count: targets.filter(t => t.status === s).length,
    nma: targets.filter(t => t.status === s).reduce((sum, t) => sum + t.nma, 0),
  }))

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Mineral Deal Intelligence Room</h1>
        <p className="text-sm text-slate-500 mt-0.5">Target Factory v1 · Oklahoma · Local Instance</p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Active Targets" value={targets.filter(t => t.status !== 'Passed').length} sub={`of ${targets.length} total`} />
        <StatCard label="Total NMA in Pipeline" value={totalNMA.toFixed(1)} sub="net mineral acres" accent />
        <StatCard label="Pipeline Value Est." value={`$${(totalValue / 1000).toFixed(0)}K`} sub="all statuses" accent />
        <StatCard label="Avg Deal Score" value={avgScore} sub="out of 100" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Deals Signed" value={signed.length} sub={`${signed.reduce((s,t) => s + t.nma, 0)} NMA closed`} />
        <StatCard label="Offers Outstanding" value={targets.filter(t => t.status === 'Offer Sent').length} sub="awaiting response" />
        <StatCard label="Needs Curative" value={needsCurative.length} sub="title work required" warn />
        <StatCard label="Evidence Docs" value={targets.reduce((s,t) => s + t.evidenceCount, 0)} sub="across all targets" />
      </div>

      {/* Pipeline funnel */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
          <TrendingUp size={16} className="text-orange-500" /> Deal Pipeline
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100">
                <th className="table-th">Stage</th>
                <th className="table-th">Count</th>
                <th className="table-th">NMA</th>
                <th className="table-th">Bar</th>
              </tr>
            </thead>
            <tbody>
              {pipeline.map(p => (
                <tr key={p.status} className="border-b border-slate-50">
                  <td className="table-td"><StatusBadge status={p.status} /></td>
                  <td className="table-td font-semibold">{p.count}</td>
                  <td className="table-td">{p.nma.toFixed(1)}</td>
                  <td className="table-td w-48">
                    <div className="bg-slate-100 rounded-full h-2">
                      <div
                        className="bg-orange-400 h-2 rounded-full"
                        style={{ width: `${Math.round((p.count / targets.length) * 100)}%` }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top deals */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <CheckCircle size={16} className="text-green-500" /> Top Scored Active Targets
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100">
                <th className="table-th">Owner</th>
                <th className="table-th">County</th>
                <th className="table-th">NMA</th>
                <th className="table-th">Score</th>
              </tr>
            </thead>
            <tbody>
              {topDeals.map(t => (
                <tr key={t.id} className="border-b border-slate-50 hover:bg-slate-50">
                  <td className="table-td font-medium">{t.ownerName}</td>
                  <td className="table-td">{t.county}</td>
                  <td className="table-td">{t.nma}</td>
                  <td className="table-td"><ScoreBadge score={t.dealScore} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Recent activity */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <Clock size={16} className="text-indigo-500" /> Recent Activity
          </h2>
          <div className="space-y-3">
            {SAMPLE_AUDIT.slice(0, 6).map(entry => (
              <div key={entry.id} className="flex gap-3">
                <div className="text-xs text-slate-400 w-20 shrink-0 pt-0.5">
                  {entry.timestamp.split('T')[0]}
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-700">{entry.action}</div>
                  <div className="text-xs text-slate-500 line-clamp-1">{entry.details}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Curative alerts */}
      {needsCurative.length > 0 && (
        <div className="card p-5 border-yellow-200 bg-yellow-50">
          <h2 className="text-sm font-semibold text-yellow-800 mb-3 flex items-center gap-2">
            <AlertTriangle size={16} /> Title Curative Alerts
          </h2>
          <div className="space-y-2">
            {needsCurative.map(t => (
              <div key={t.id} className="bg-white rounded-lg p-3 border border-yellow-200">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="text-sm font-semibold text-slate-800">{t.ownerName}</div>
                    <div className="text-xs text-slate-500">{t.county} Co. · {t.section}-{t.township}-{t.range}</div>
                  </div>
                  <StatusBadge status={t.titleClearance} />
                </div>
                {t.curativesNeeded.length > 0 && (
                  <ul className="mt-2 text-xs text-slate-600 list-disc list-inside space-y-0.5">
                    {t.curativesNeeded.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
