# Multi-engine vision adjudication workflow (generic)

Reusable procedure for adjudicating scanned record images (title runsheets, index pages, recorded
instruments) with multiple independent "AI passes," producing per-field best guesses with stated
confidence instead of a single opaque OCR output.

## Passes

- **PASS A — server-side OCR** (e.g., the cloud storage provider's OCR of the image). Strong on
  clean typed text; weak on handwritten recording stamps, fractions, and aliquot letters.
- **PASS B — LLM pixel vision** reading the raw scan. Strong on layout, stamps, and context-aware
  disambiguation; flag any uncertain single characters (day digits, initials) explicitly.
- **PASS C — prior record** (existing workbook rows, county metadata, prior audits). Strong on
  record identity; weak on operative effect.

## Adjudication rules

1. Score each **field**, not each document: parties, dates (execution / effective / recorded),
   book/page, legal description, fractions, reservations.
2. Record every pass's raw reading, an agreement flag, and one adjudicated best guess with a
   confidence percentage and an evidence tier (D direct image / M metadata / O OCR / A assumption).
3. Each engine states its own estimated accuracy for the document class, calibrated from observed
   errors on the same set (e.g., OCR reading "N/2" as "1/2" or an impossible day "33").
4. OCR is never elevated over the image. Metadata proves facial identity only. Blank never means
   zero. Anything above direct-image tier is an expressly labeled assumption with its basis.
5. Gap fills go into the working report only with a source note ("vision-abstracted <date>, image
   <n>, confidence <p>%"); uncertain digits stay flagged until a certified copy settles them.

## Template conformance gate

Before delivery, run a structural comparison of the populated workbook against the clean template:
sheet names and order, sheet visibility, merged-range counts, print areas, formula counts, defined
names, and a `#REF!`/external-link scan. Every intentional variance must be individually disclosed;
anything else is drift and must be fixed. See `scripts/compare_workbook_to_template.py`.

## Large-binary transfer note (remote sessions)

Connector downloads that exceed the tool-result token limit are written to a local tool-results
file as JSON with a base64 `content` field; decode from that file to reconstruct exact binaries
(verify with SHA-256) without flooding the model context. Uploads have no such path — deliver large
binaries via session file delivery and keep an exact regeneration recipe (base workbook hash + delta
script) in the controlled workspace.
