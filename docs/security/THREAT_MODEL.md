# Threat Model

Protected assets are source evidence, credentials, provenance, calculated interests, review decisions, and generated reports. Relevant threats include path traversal or symlink escape, source mutation after inventory, malicious ZIP/OOXML content, spreadsheet formula injection, forged model provenance, stale PID reuse, unauthorized local access, accidental publication, and external-provider disclosure.

Implemented mitigations include allow-listed canonical paths, signatures and archive limits, before-use hashes, immutable candidate archives, source-ledger provenance rebuilding, conflict quarantine, local authentication/RBAC/audit, loopback binding, exact-template comparison, and public-repository boundaries.

Residual risks remain: Tesseract and document parsers process untrusted files; local administrators can bypass application controls; antivirus and sandboxing are deployment responsibilities; OCR can be wrong; legal descriptions and chains can be incomplete; and no production penetration test is represented here. Human source review is mandatory for material facts.
