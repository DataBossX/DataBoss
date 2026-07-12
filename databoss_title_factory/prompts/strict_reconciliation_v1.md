# Strict source-controlled reconciliation — version 1

Reconcile independent extractions against the original source image. The image
controls; model agreement is supporting evidence only.

1. Match records using visible location, bounding boxes, identifiers, parties,
   dates, and legal description. Do not force uncertain matches.
2. For each field, verify visible support, completeness, punctuation, row
   isolation, inference status, region consistency, and OCR support.
3. Weight direct image fidelity above all other factors. Two agreeing models
   cannot win without source support.
4. Use only these decisions: `ACCEPT_A`, `ACCEPT_B`, `ACCEPT_C`,
   `ACCEPT_COMBINED`, `UNRESOLVED`, `NOT_PRESENT`, `ROW_MATCH_UNCERTAIN`.
5. Any unresolved party, instrument type/number, book/page, date, legal,
   interest, reservation, exception, depth, term, or royalty requires human review.
6. Preserve every candidate and field value. Never delete or omit a conflict.
7. Return valid JSON only with matched records, field decisions, unmatched
   candidates, possible missing source rows, material conflicts, human-review
   queue, and reconciliation counts.
