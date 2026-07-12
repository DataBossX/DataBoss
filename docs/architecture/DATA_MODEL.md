# Data Model

The source inventory records relative and absolute path, SHA-256, size, timestamp, type, page count, support status, and duplicate group. OCR citations bind text and word geometry to a source hash, source locator, derived image, preprocessing recipe, engine, and confidence.

Instrument candidates retain every engine result and raw imported candidate. Reconciliation emits field decisions, source-support provenance, conflicts, confidence, and review status. A runsheet is only a chronological draft over reconciled instruments; missing-document rows identify unsupported or unrepresented sources.

SQLite tracks runs, stages, artifact paths and hashes, plus separate authentication tables and audit events. JSON/JSONL is the authoritative machine-readable artifact format; CSV and XLSX are review views. Evidence values in exact-interest calculations carry a value, evidence references, and an explicit evidence status.

No schema field proves legal ownership by itself. Empty, conflicted, inferred, or unsupported facts remain review items rather than being silently completed.
