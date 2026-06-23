// Typed client for the EvoSwarm API (see ../../evoswarm). Mirrors the Pydantic
// v2 schemas in evoswarm/src/evoswarm/schemas.py. Note: the backend serializes
// Decimal fields as JSON strings, so numeric amounts arrive as strings here.

const BASE_URL: string =
  (import.meta as { env?: Record<string, string> }).env?.VITE_EVOSWARM_API ??
  'http://localhost:8080'

export interface Money {
  amount: string
  currency: 'USD'
}

export interface RoyaltyInput {
  net_mineral_acres: string
  spacing_unit_acres: string
  royalty_rate: string
  monthly_production_bbl: string
  price_per_bbl: Money
}

export interface RoyaltyResult {
  decimal_interest: string
  gross_monthly: Money
  net_monthly: Money
  explanation: string
}

export class EvoSwarmError extends Error {}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (e) {
    throw new EvoSwarmError(
      `Cannot reach EvoSwarm API at ${BASE_URL}. Is it running? (${String(e)})`,
    )
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText)
    throw new EvoSwarmError(`EvoSwarm ${path} failed (${res.status}): ${detail}`)
  }
  return res.json() as Promise<T>
}

// Parse a human royalty rate ("3/16", "1/8", "0.1875", "18.75%") into a decimal
// string the API's strict schema accepts (0 < rate <= 0.5).
export function parseRoyaltyRate(raw: string): string {
  const s = raw.trim()
  if (s.includes('/')) {
    const [num, den] = s.split('/').map(Number)
    if (!den) throw new EvoSwarmError(`Invalid royalty fraction: "${raw}"`)
    return (num / den).toString()
  }
  if (s.endsWith('%')) return (Number(s.slice(0, -1)) / 100).toString()
  return Number(s).toString()
}

export function computeRoyalty(input: RoyaltyInput): Promise<RoyaltyResult> {
  return postJSON<RoyaltyResult>('/v1/royalty', input)
}
