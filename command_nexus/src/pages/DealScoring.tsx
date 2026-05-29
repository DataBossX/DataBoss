import { useState } from 'react'
import { SAMPLE_TARGETS, SAMPLE_DEAL_SCORES } from '../data/sampleData'
import type { ScoreComponent } from '../types'
import ScoreBadge from '../components/ScoreBadge'
import StatusBadge from '../components/StatusBadge'
import { BarChart2 } from 'lucide-react'

const REC_STYLE: Record<string, string> = {
  'Strong Buy': 'bg-green-500/20 text-green-300 border border-green-500/30',
  'Buy':        'bg-blue-500/20 text-blue-300 border border-blue-500/30',
  'Hold':       'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30',
  'Pass':       'bg-red-500/20 text-red-300 border border-red-500/30',
}

function ScoreBar({ c }: { c: ScoreComponent }) {
  const pct = Math.round((c.score / c.maxScore) * 100)
  const barColor = pct >= 80 ? 'bg-green-400' : pct >= 55 ? 'bg-yellow-400' : 'bg-red-400'
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between">
        <span className="text-sm text-nx-text">{c.name}</span>
        <span className="text-sm font-bold font-mono text-white">{c.score}<span className="text-nx-muted">/{c.maxScore}</span></span>
      </div>
      <div className="h-2 bg-nx-bg rounded-full">
        <div className={`${barColor} h-2 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-nx-muted">{c.rationale}</p>
    </div>
  )
}

export default function DealScoring() {
  const [selectedId, setSelectedId] = useState<string>(SAMPLE_DEAL_SCORES[0].targetId)
  const score = SAMPLE_DEAL_SCORES.find(s => s.targetId === selectedId) ?? null
  const target = score ? SAMPLE_TARGETS.find(t => t.id === score.targetId) : null
  const scoredIds = new Set(SAMPLE_DEAL_SCORES.map(s => s.targetId))

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-2 mb-1">
        <BarChart2 className="text-cyan-400" size={20} />
        <h1 className="text-xl font-bold text-white tracking-wide">DEAL SCORING</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Score list */}
        <div className="space-y-3">
          <h2 className="text-xs font-bold text-nx-muted uppercase tracking-widest">Scored Targets</h2>
          {SAMPLE_DEAL_SCORES.map(s => {
            const t = SAMPLE_TARGETS.find(x => x.id === s.targetId)
            return (
              <button
                key={s.targetId}
                onClick={() => setSelectedId(s.targetId)}
                className={`w-full text-left nx-card p-4 hover:border-cyan-500/40 transition-all ${selectedId === s.targetId ? 'border-cyan-500/50 bg-cyan-500/5' : ''}`}
              >
                <div className="flex justify-between items-start">
                  <div className="text-sm font-semibold text-white leading-tight">{t?.ownerName}</div>
                  <ScoreBadge score={s.overallScore} />
                </div>
                <div className="text-xs text-nx-muted mt-1">{t?.county} Co.</div>
                <div className={`mt-2 badge text-xs ${REC_STYLE[s.recommendation]}`}>{s.recommendation}</div>
              </button>
            )
          })}

          {SAMPLE_TARGETS.filter(t => !scoredIds.has(t.id)).length > 0 && (
            <>
              <h2 className="text-xs font-bold text-nx-muted/50 uppercase tracking-widest pt-2">Not Yet Scored</h2>
              {SAMPLE_TARGETS.filter(t => !scoredIds.has(t.id)).map(t => (
                <div key={t.id} className="nx-card p-4 opacity-50">
                  <div className="text-sm font-semibold text-nx-text">{t.ownerName}</div>
                  <div className="text-xs text-nx-muted">{t.county} Co. · {t.status}</div>
                  <div className="text-xs text-nx-muted/50 mt-1 italic">Score pending</div>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Score Detail */}
        {score && target && (
          <div className="lg:col-span-2 space-y-5">
            <div className="nx-card p-5">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="text-lg font-bold text-white">{target.ownerName}</div>
                  <div className="text-sm text-nx-muted">{target.county} Co. · {target.section}-{target.township}-{target.range}</div>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-bold font-mono text-white">{score.overallScore}<span className="text-nx-muted text-lg">/100</span></div>
                  <div className={`badge mt-1 ${REC_STYLE[score.recommendation]}`}>{score.recommendation}</div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 text-xs mb-4">
                <div><div className="text-nx-muted uppercase">Status</div><div className="mt-1"><StatusBadge status={target.status} /></div></div>
                <div><div className="text-nx-muted uppercase">Scored By</div><div className="text-nx-text mt-1">{score.scoredBy}</div></div>
                <div><div className="text-nx-muted uppercase">Scored</div><div className="text-nx-text mt-1">{score.scoredAt}</div></div>
              </div>
              {score.notes && (
                <div className="bg-nx-bg border border-nx-border rounded-lg p-3 text-sm text-nx-muted">{score.notes}</div>
              )}
            </div>

            <div className="nx-card p-5">
              <h3 className="text-sm font-bold text-cyan-400 uppercase tracking-wider mb-4">SCORE BREAKDOWN</h3>
              <div className="space-y-5">
                {score.components.map(c => <ScoreBar key={c.name} c={c} />)}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
