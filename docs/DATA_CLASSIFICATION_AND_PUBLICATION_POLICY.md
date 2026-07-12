# Data Classification and Publication Policy

## Public

Allowed only after review:

- application source code
- synthetic fixtures and fictional examples
- generic architecture and operating procedures
- approved product documentation
- non-reversible aggregate metrics
- public marketing assets

## Internal

Keep in an approved private repository or controlled cloud workspace:

- real project manifests and work orders
- exact legal descriptions tied to a client assignment
- owner names, addresses, title chains, calculations, and exceptions
- source images, OCR, evidence links, hashes, file IDs, folder IDs, and paths
- API queues, spend logs, Cursor jobs/results, QA reports, and release receipts
- candidate and final workbooks

## Publication gate

A public artifact must be generated from an allowlist, not from a blacklist. It must pass automated checks for credentials, cloud IDs, private paths, client/project identifiers, title data, and evidence links, followed by human review.

Removing a file from the current tree does not erase Git history, forks, clones, or caches. Rotate exposed credentials first and coordinate any history rewrite.
