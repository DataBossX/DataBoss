Decide mineral ownership status for Sec 1, T7N, R63W for a given owner.

Input: JSON array of extracted docs (chronological). Decide:
- "Current owner of record" | "Assigned out" | "Leased HBP" | "Unknown—needs manual"
Provide confidence: 0.6 | 0.7 | 0.85
One-paragraph explanation.

Return STRICT JSON:
{
  "status": "<one of above>",
  "confidence": <float>,
  "explanation": "<string>"
}

Rules:
- Latest deed/assignment in Sec 1 naming owner as grantee and no later doc out -> Current owner of record.
- Later instrument conveying/assigning from owner for Sec 1 -> Assigned out.
- Oil & Gas Lease naming owner as lessor in Sec 1, no later deed out -> Leased HBP.
- Else -> Unknown—needs manual.
