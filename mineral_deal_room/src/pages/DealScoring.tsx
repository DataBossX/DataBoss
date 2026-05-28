import { useState } from 'react'
import { SAMPLE_TARGETS, SAMPLE_DEAL_SCORES } from '../data/sampleData'
import type { DealScore, ScoreComponent } from '../types'
import ScoreBadge from '../components/ScoreBadge'
import { BarChart2, TrendingUp, TrendingDown } from 'lucide-react'

const RECOMMENDATION_COLOR: Record<string, string> = {
  'Strong Buy': 'bg-green-100 text-green-800 border-green-200',
  'Buy':        'bg-blue-100 text-blue-800 border-blue-200',
  'Hold':       'bg-yellow-100 text-yellow-800 border-yellow-200',
  'Pass':       'bg-red-100 text-red-800 border-red-200',
}

function ScoreBar({ component }: { component: ScoreComponent }) {
  const pct = Math.round((component.score / component.maxScore) * 100)
  const color = pct >= 80 ? 'bg-green-400' : pct >= 55 ? 'bg-yellow-400' : 'bg-red-400'
  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <span className="text-sm font-medium text-slate-700">{component.name}</span>
        <span className="text-sm font-bold text-slate-900">{component.score}/{component.maxScore}</span>
      </div>
      <div className="bg-slate-100 rounded-full h-2.5">
        <div className={`${color} h-2.5 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-slate-500">{component.rationale}</p>
    </div>
  )
}

export default function DealScoring() {
  const [selectedId, setSelectedId] = useState<string>(SAMPLE_DEAL_SCORES[0].targetId)
  const score = SAMPLE_DEAL_SCORES.find(s => s.targetId === selectedId) ?? null
  const target = score ? SAMPLE_TARGETS.find(t => t.id === score.targetId) : null

  // Scoreable targets (those with existing scores shown; real app would allow creating new)
  const scoredIds = new Set(SAMPLE_DEAL_SCORES.map(s => s.targetId))
  const unscoredTargets = SAMPLE_TARGETS.filter(t => !scoredIds.has(t.id))

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Deal Scoring</h1>
        <p className="text-sm text-slate-500">Weighted scorecard for each acquisition target</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Score list */}
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-700">Scored Targets</h2>
          {SAMPLE_DEAL_SCORES.map(s => {
            const t = SAMPLE_TARGETS.find(x => x.id === s.targetId)
            return (
              <button
                key={s.targetId}
                onClick={() => setSelectedId(s.targetId)}
                className={`w-full text-left card p-4 transition-all hover:border-orange-300 ${selectedId === s.targetId ? 'border-orange-400 ring-1 ring-orange-300' : ''}`}
              >
                <div className="flex justify-between items-start">
                  <div className="text-sm font-semibold text-slate-800 leading-tight">{t?.ownerName}</div>
                  <ScoreBadge score={s.overallScore} />
                </div>
                <div className="text-xs text-slate-500 mt-1">{t?.county} Co.</div>
                <div className={`mt-2 text-xs font-semibold px-2 py-0.5 rounded border inline-block ${RECOMMENDATION_COLOR[s.recommendation]}`}>
                  {s.recommendation}
                </div>
              </button>
            )
          })}

          {unscoredTargets.length > 0 && (
            <>
              <h2 className="text-sm font-semibold text-slate-500 pt-2">Not Yet Scored</h2>
              {unscoredTargets.map(t => (
                <div key={t.id} className="card p-4 opacity-60">
                  <div className="text-sm font-semibold text-slate-700">{t.ownerName}</div>
                  <div className="text-xs text-slate-500">{t.county} Co. · {t.status}</div>
                  <div className="text-xs text-slate-400 mt-1 italic">Score pending</div>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Score detail */}
        <div className="lg:col-span-2">
          {score && target ? (
            <div className="card p-6 space-y-6">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">{target.ownerName}</h2>
                  <p className="text-sm text-slate-500">
                    {target.county} Co. · {target.section}-{target.township}-{target.range} · {target.nma} NMA
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    Scored by {score.scoredBy} on {score.scoredAt}
                  </p>
                </div>
                <div className="text-center">
                  <div className="text-4xl font-black text-slate-900">{score.overallScore}</div>
                  <div className="text-xs text-slate-400">/ 100</div>
                  <div className={`mt-1 text-xs font-bold px-3 py-1 rounded-full border ${RECOMMENDATION_COLOR[score.recommendation]}`}>
                    {score.recommendation}
                  </div>
                </div>
              </div>

              {/* Overall score bar */}
              <div>
                <div className="flex justify-between text-xs text-slate-500 mb-1">
                  <span>Overall Score</span>
                  <span>{score.overallScore}/100</span>
                </div>
                <div className="bg-slate-100 rounded-full h-4">
                  <div
                    className={`h-4 rounded-full ${score.overallScore >= 85 ? 'bg-green-500' : score.overallScore >= 65 ? 'bg-yellow-500' : 'bg-red-500'}`}
                    style={{ width: `${score.overallScore}%` }}
                  />
                </div>
              </div>

              {/* Component breakdown */}
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
                  <BarChart2 size={14} /> Score Breakdown
                </h3>
                <div className="space-y-5">
                  {score.components.map((c, i) => <ScoreBar key={i} component={c} />)}
                </div>
              </div>

              {/* Scorecard table */}
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-2">Scorecard Summary</h3>
                <table className="w-full text-sm border border-slate-200 rounded-lg overflow-hidden">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="table-th">Factor</th>
                      <th className="table-th">Score</th>
                      <th className="table-th">Max</th>
                      <th className="table-th">%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {score.components.map((c, i) => {
                      const pct = Math.round((c.score / c.maxScore) * 100)
                      return (
                        <tr key={i} className="border-t border-slate-100">
                          <td className="table-td">{c.name}</td>
                          <td className="table-td font-semibold">{c.score}</td>
                          <td className="table-td text-slate-400">{c.maxScore}</td>
                          <td className="table-td">
                            <span className={`badge ${pct >= 80 ? 'bg-green-100 text-green-700' : pct >= 55 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'}`}>
                              {pct}%
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                    <tr className="border-t-2 border-slate-300 bg-slate-50 font-bold">
                      <td className="table-td">TOTAL</td>
                      <td className="table-td">{score.overallScore}</td>
                      <td className="table-td">100</td>
                      <td className="table-td">{score.overallScore}%</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {score.notes && (
                <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
                  <div className="text-xs font-semibold text-blue-700 mb-1">Analyst Notes</div>
                  <div className="text-sm text-blue-800">{score.notes}</div>
                </div>
              )}
            </div>
          ) : (
            <div className="card p-12 text-center text-slate-400">
              Select a target to view its deal score.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
