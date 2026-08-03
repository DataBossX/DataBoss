# Canonical Drive Reconstruction Specification

FOR REVIEW - HOLD NO EXTERNAL RELEASE

Every live entry path requires startup reconstruction from an explicit pin set. Each pin binds parent folder, Drive object ID, name, byte count, SHA-256, schema, and semantic identity. The reconstructor rejects missing objects, changed bytes, parent/name mismatches, schema or semantic mismatches, and duplicate same-name objects before durable reconciliation.

Recognized reconstruction facts are retired commands and verified receipt records. The exact noncanonical Section 32 SHA-256 fixture is preserved as an observation but rejected before claim, ACK consumption, lease/fence issuance, spool, Drive write, or authority mutation.

Local cache state is not a substitute for exact pinned remote bytes. Live activation remains separately controlled.
