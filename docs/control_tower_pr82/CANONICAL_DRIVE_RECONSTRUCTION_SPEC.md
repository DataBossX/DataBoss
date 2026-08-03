# Canonical Drive Reconstruction Specification

FOR REVIEW - HOLD NO EXTERNAL RELEASE

Every live entry path requires startup reconstruction from a non-empty explicit pin set. Each pin binds parent folder, Drive object ID, name, byte count, SHA-256, schema, and semantic identity. The reconstructor rejects missing objects, changed bytes, parent/name mismatches, schema or semantic mismatches, duplicate same-name objects, duplicate retirement identities, and a missing permanent-retirement pin before durable reconciliation.

The original Gate 0 command and its Drive identity are also pinned in the code-level permanent-retirement registry. This is defense in depth, not replacement authority. It makes the terminalized identity unclaimable before reconstruction and after a fresh clone, spool deletion, or complete local-state loss. The verified Drive pin supplies the canonical evidentiary record required for any live startup.

Recognized reconstruction facts are retired commands and verified receipt records. The exact noncanonical Section 32 SHA-256 fixture is preserved as an observation but rejected before claim, ACK consumption, lease/fence issuance, spool, Drive write, or authority mutation.

Local cache state is not a substitute for exact pinned remote bytes. Live activation remains separately controlled.
