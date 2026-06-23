// Deno test for the EvoSwarm royalty-rate parser. Gives the repo's `deno test`
// CI step a real module to run, and pins the "3/16" | "%" | decimal parsing the
// Target Factory UI relies on before POSTing to /v1/royalty. Intentionally has
// no remote imports so it runs offline and without third-party availability.
import { parseRoyaltyRate, EvoSwarmError } from './evoswarm.ts'

function assertEquals(actual: string, expected: string) {
  if (actual !== expected) {
    throw new Error(`expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`)
  }
}

Deno.test('parseRoyaltyRate handles fractions', () => {
  assertEquals(parseRoyaltyRate('3/16'), '0.1875')
  assertEquals(parseRoyaltyRate('1/8'), '0.125')
})

Deno.test('parseRoyaltyRate handles percent and decimal', () => {
  assertEquals(parseRoyaltyRate('18.75%'), '0.1875')
  assertEquals(parseRoyaltyRate('0.1875'), '0.1875')
})

Deno.test('parseRoyaltyRate rejects a zero denominator', () => {
  let threw = false
  try {
    parseRoyaltyRate('3/0')
  } catch (e) {
    threw = e instanceof EvoSwarmError
  }
  if (!threw) throw new Error('expected EvoSwarmError for a zero denominator')
})
