import { useState } from 'react'
import { Calculator, Loader2, AlertTriangle } from 'lucide-react'
import type { Target } from '../types'
import {
  computeRoyalty,
  parseRoyaltyRate,
  EvoSwarmError,
  type RoyaltyResult,
} from '../lib/evoswarm'

// Oklahoma statutory gas spacing unit (1 section). Operators can override.
const DEFAULT_SPACING_ACRES = '640'

export default function RoyaltyAnalysis({ target }: { target: Target }) {
  const [spacing, setSpacing] = useState(DEFAULT_SPACING_ACRES)
  const [production, setProduction] = useState('1000') // bbl / month
  const [price, setPrice] = useState('70.00')          // $ / bbl
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<RoyaltyResult | null>(null)

  async function run() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await computeRoyalty({
        net_mineral_acres: String(target.nma),
        spacing_unit_acres: spacing,
        royalty_rate: parseRoyaltyRate(target.royaltyRate),
        monthly_production_bbl: production,
        price_per_bbl: { amount: price, currency: 'USD' },
      })
      setResult(res)
    } catch (e) {
      setError(e instanceof EvoSwarmError ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const usd = (m: { amount: string }) =>
    `$${Number(m.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}`

  return (
    <div className="card p-3 mb-3">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs font-semibold text-slate-600 flex items-center gap-1">
          <Calculator size={13} /> DOI Royalty Analysis
          <span className="text-slate-400 font-normal">· EvoSwarm</span>
        </div>
        <button className="btn-primary text-xs py-1 px-3" onClick={run} disabled={loading}>
          {loading ? <Loader2 size={12} className="animate-spin" /> : <Calculator size={12} />}
          {loading ? 'Computing…' : 'Run'}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-2">
        <label className="text-xs text-slate-500">
          Spacing unit (ac)
          <input className="input mt-0.5 py-1" value={spacing}
                 onChange={e => setSpacing(e.target.value)} inputMode="decimal" />
        </label>
        <label className="text-xs text-slate-500">
          Production (bbl/mo)
          <input className="input mt-0.5 py-1" value={production}
                 onChange={e => setProduction(e.target.value)} inputMode="decimal" />
        </label>
        <label className="text-xs text-slate-500">
          Price ($/bbl)
          <input className="input mt-0.5 py-1" value={price}
                 onChange={e => setPrice(e.target.value)} inputMode="decimal" />
        </label>
      </div>
      <div className="text-[11px] text-slate-400 mb-2">
        Using {target.nma} NMA · royalty {target.royaltyRate}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-2 text-xs text-red-700 flex gap-1.5">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" /> {error}
        </div>
      )}

      {result && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-sm space-y-1">
          <div className="flex justify-between">
            <span className="text-slate-500">DOI decimal</span>
            <span className="font-mono font-semibold">{result.decimal_interest}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Gross / month</span>
            <span className="font-medium">{usd(result.gross_monthly)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Net royalty / month</span>
            <span className="font-bold text-orange-600">{usd(result.net_monthly)}</span>
          </div>
          <div className="text-[11px] text-slate-400 pt-1 border-t border-slate-200 mt-1">
            {result.explanation}
          </div>
        </div>
      )}
    </div>
  )
}
