import { SAMPLE_TARGETS, SAMPLE_AUDIT } from '../data/sampleData'
import StatCard from '../components/StatCard'
import StatusBadge from '../components/StatusBadge'
import ScoreBadge from '../components/ScoreBadge'
import { TrendingUp, AlertTriangle, CheckCircle, Clock, Flame } from 'lucide-react'

const STATUS_ORDER = ['Identified','Contacted','Under Review','Offer Sent','Signed','On Hold','Passed']

export default function DealDashboard() {
  const targets = SAMPLE_TARGETS
  const totalNMA = targets.reduce((s, t) => s + t.nma, 0)
  const totalValue = targets.reduce((s, t) => s + t.estimatedValue, 0)
  const avgScore = Math.round(targets.reduce((s, t) => s + t.dealScore, 0) / targets.length)
  const signed = targets.filter(t => t.status === 'Signed')
  const needsCurative = targets.filter(t => t.titleClearance === 'Needs Curative' || t.titleClearance === 'Probate Pending')
  const topDeals = [...targets].filter(t => t.status !== 'Passed' && t.status !== 'Signed')
    .sort((a, b) => b.dealScore - a.dealScore).slice(0, 5)

  const pipeline = STATUS_ORDER.map(s => ({
    status: s,
    count: targets.filter(t => t.status === s).length,
    nma: targets.filter(t => t.status === s).reduce((sum, t) => sum + t.nma, 0),
  }))

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-2 mb-1">
        <Flame className="text-orange-400" size={20} />
        <h1 className="text-xl font-bold text-white tracking-wide">MINERAL DEAL ROOM</h1>
        <span className="text-nx-muted text-sm ml-2">Target Factory v1 · Oklahoma</span>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Active Targets" value={targets.filter(t => t.status !== 'Passed').length} sub={`of ${targets.length} total`} cyan />
        <StatCard label="Pipeline NMA" value={totalNMA.toFixed(1)} sub="net mineral acres" accent />
        <StatCard label="Pipeline Value" value={`$${(totalValue / 1000).toFixed(0)}K`} sub="estimated" accent />
        <StatCard label="Avg Deal Score" value={avgScore} sub="out of 100" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Deals Signed" value={signed.length} sub={`${signed.reduce((s,t) => s+t.nma,0)} NMA closed`} />
        <StatCard label="Offers Outstanding" value={targets.filter(t => t.status === 'Offer Sent').length} sub="awaiting response" />
        <StatCard label="Needs Curative" value={needsCurative.length} sub="title work required" warn />
        <StatCard label="Evidence Docs" value={targets.reduce((s,t) => s+t.evidenceCount,0)} sub="across all targets" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pipeline Funnel */}
        <div className="nx-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="text-orange-400" size={16} />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">DEAL PIPELINE</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-nx-border">
                <th className="text-left py-2 text-xs text-nx-muted uppercase">Stage</th>
                <th className="text-left py-2 text-xs text-nx-muted uppercase">Count</th>
                <th className="text-left py-2 text-xs text-nx-muted uppercase">NMA</th>
                <th className="text-left py-2 text-xs text-nx-muted uppercase">Progress</th>
              </tr>
            </thead>
            <tbody>
              {pipeline.map(p => (
                <tr key={p.status} className="border-b border-nx-border/30">
                  <td className="py-2.5"><StatusBadge status={p.status} /></td>
                  <td className="py-2.5 font-bold text-white">{p.count}</td>
                  <td className="py-2.5 text-nx-muted">{p.nma.toFixed(1)}</td>
                  <td className="py-2.5 w-28">
                    <div className="h-1.5 bg-nx-bg rounded-full">
                      <div
                        className="bg-orange-400 h-1.5 rounded-full"
                        style={{ width: `${Math.round((p.count / targets.length) * 100)}%` }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Top Scored Active */}
        <div className="nx-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle className="text-green-400" size={16} />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">TOP ACTIVE TARGETS</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-nx-border">
                <th className="text-left py-2 text-xs text-nx-muted uppercase">Owner</th>
                <th className="text-left py-2 text-xs text-nx-muted uppercase">County</th>
                <th className="text-left py-2 text-xs text-nx-muted uppercase">NMA</th>
                <th className="text-left py-2 text-xs text-nx-muted uppercase">Score</th>
              </tr>
            </thead>
            <tbody>
              {topDeals.map(t => (
                <tr key={t.id} className="border-b border-nx-border/30 hover:bg-nx-card/60">
                  <td className="py-2.5 font-medium text-white">{t.ownerName}</td>
                  <td className="py-2.5 text-nx-muted">{t.county}</td>
                  <td className="py-2.5 text-nx-muted">{t.nma}</td>
                  <td className="py-2.5"><ScoreBadge score={t.dealScore} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="nx-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Clock className="text-cyan-400" size={16} />
          <h2 className="text-sm font-bold text-white uppercase tracking-wider">RECENT ACTIVITY</h2>
        </div>
        <div className="space-y-3">
          {SAMPLE_AUDIT.slice(0, 8).map(entry => (
            <div key={entry.id} className="flex gap-4 border-b border-nx-border/30 pb-3 last:border-0">
              <div className="text-xs text-nx-muted w-24 shrink-0 pt-0.5 font-mono">
                {entry.timestamp.split('T')[0]}
              </div>
              <div>
                <div className="text-sm font-semibold text-nx-text">{entry.action}</div>
                <div className="text-xs text-nx-muted mt-0.5 line-clamp-1">{entry.details}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Curative Alerts */}
      {needsCurative.length > 0 && (
        <div className="nx-card p-5 border-yellow-500/30 bg-yellow-500/5">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="text-yellow-400" size={16} />
            <h2 className="text-sm font-bold text-yellow-300 uppercase tracking-wider">TITLE CURATIVE ALERTS</h2>
          </div>
          <div className="space-y-3">
            {needsCurative.map(t => (
              <div key={t.id} className="bg-nx-bg rounded-lg p-4 border border-yellow-500/20">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="text-sm font-semibold text-white">{t.ownerName}</div>
                    <div className="text-xs text-nx-muted">{t.county} Co. · {t.section}-{t.township}-{t.range}</div>
                  </div>
                  <StatusBadge status={t.titleClearance} />
                </div>
                {t.curativesNeeded.length > 0 && (
                  <ul className="mt-2 text-xs text-yellow-300/80 list-disc list-inside space-y-0.5">
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
