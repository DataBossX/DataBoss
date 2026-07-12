# Processing Pipeline

1. Inventory creates a new run, hashes every non-output source, identifies duplicates, and records workbook candidates.
2. OCR renders copies of image/PDF pages, tries local preprocessing variants, uses embedded PDF text when adequate, and writes page/row/cell citations. Originals are not altered.
3. Extraction creates or imports candidates. Imported candidates cannot supply trusted provenance; support is rebuilt from the current OCR ledger.
4. Reconciliation resolves only source-supported fields, preserves all candidates, and quarantines weak, conflicting, or unsupported results.
5. Runsheet assembly sorts dates and emits missing-document, lease, and tract drafts.
6. Review-package export copies the template exactly and puts audit/control data in a separate workbook. Client-cell population is not implemented because no approved writable-range map exists.

Stages are resumable only when recorded artifact hashes still match. A successful pipeline means “ready for human review,” not clear title or approval for delivery.
