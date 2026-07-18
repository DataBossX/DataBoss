# DataBossX Production Engineering Blueprint

Status: build authority  
Horizon: six-month production build  
Supersedes: architecture-only recommendations for the title-production system  
Primary outcome: a reproducible, evidence-backed, professionally formatted title report from real petroleum land records

## 1. Executive decision

DataBossX will be one title-production platform, not a collection of scripts and
not an autonomous title examiner. It will turn immutable source records into
reviewed legal facts, a temporal title graph, exact ownership calculations, and
a hash-bound report release.

The production authority is:

```text
Google Drive and county sources
        |
        v
bounded read-only connectors
        |
        v
immutable SHA-256 object vault + PostgreSQL evidence ledger
        |
        v
durable task graph -> document/OCR/extraction/title workers
        |
        v
field claims + source geometry + conflicts
        |
        v
qualified examiner review
        |
        v
exact title/interest ledger
        |
        v
surgical Excel template population + native Excel verification
        |
        v
hash-bound release + verified Drive delivery
```

The database and vault, not a folder name or spreadsheet, are the canonical
system of record. Google Drive remains the operator-facing intake and delivery
surface. Original Drive files are never silently renamed, moved, converted, or
overwritten.

### Hard decisions

1. Use a Python modular monolith, one React application, PostgreSQL with
   PostGIS, and S3-compatible immutable object storage. Do not begin with
   microservices, Kafka, Kubernetes, a vector database, or an agent framework.
2. Use PostgreSQL rather than the existing SQLite databases for production.
   Concurrent reviewers, worker leases, spatial land queries, row-level
   security, and durable Drive synchronization justify it. SQLite remains
   supported only for disconnected field capture and tests.
3. Keep `horizon/interest.py` as the seed for exact rational arithmetic and
   port Horizon chaining tests, but replace row-order title logic with a
   tract/depth/time-aware graph.
4. Split `grocery_report_pipeline.py` into typed workers. It is useful workflow
   scaffolding, not the canonical domain model.
5. Migrate DOTO acquisition into the common task graph. Retire its independent
   database and queue after parity.
6. Retire `backend/` and `frontend/`; the mock OCR may never enter a production
   path. Keep `mineral_deal_room/` as the UI seed and remove sample runtime data.
7. Never save an arbitrary approved workbook through `openpyxl`. Populate it by
   surgical OOXML edits, then verify it in licensed Microsoft Excel on a
   dedicated Windows worker.
8. LLMs create candidates and draft prose. They never mutate canonical facts,
   merge parties, calculate ownership, resolve defects, or approve a report.
9. A report is a draft until a qualified examiner—and an attorney where the
   jurisdiction or engagement requires one—approves the exact artifact hash.
10. Unknown, absent, illegible, inapplicable, inferred, and source-confirmed are
    different data states. Blank text is not a data model.

## 2. Production acceptance definition

DataBossX is production-ready only when two representative real projects pass
all of the following:

- 100% of in-scope source occurrences are inventoried; every byte has custody
  metadata and a SHA-256.
- Every material report value opens its source page and highlighted region in
  two user actions or fewer.
- No unsupported model value is promoted to a legal fact.
- All material conflicts are explicitly resolved by a qualified reviewer.
- Ownership, mineral interest, WI, NRI, burdens, and net acres use reduced
  rational numbers and pass conservation checks.
- Every chain gap, over-conveyance, duplicate, legal mismatch, depth mismatch,
  and missing instrument is visible as a defect or reviewed disposition.
- The approved Excel template loses no protected feature.
- The output reopens and recalculates in native Excel without new errors.
- The released workbook and rendered PDF are reproducible from a locked input
  manifest and versioned recipes.
- Release approval binds source manifest, accepted claims, title graph, rule
  set, template, write plan, tool versions, Office build, and output hashes.
- Delivery is not complete until the uploaded file is downloaded again and its
  SHA-256 matches.

Accuracy is reported per field and document class. “Overall accuracy” alone is
not an acceptance metric because an incorrect reservation or fraction matters
more than a missed return address.

## 3. Runtime topology and software

### 3.1 Private control plane

Run the first production deployment on a dedicated encrypted Linux server or
private-cloud VM:

| Component | Production choice | Responsibility |
| --- | --- | --- |
| API | Python, FastAPI, Pydantic | authenticated commands and read models |
| Orchestrator | Python process | sole task state-transition authority |
| Database | PostgreSQL 17 | canonical metadata, title facts, task graph, audit |
| Spatial | PostGIS | tract geometries, overlap, parcel search |
| Object vault | versioned S3-compatible storage with object lock | originals and derived artifacts |
| UI | Vite, React, TypeScript | projects, evidence, title graph, review, releases |
| Image pipeline | MuPDF, OpenCV, libvips | safe render, quality analysis, variants |
| OCR | registered native PDF text, PaddleOCR, Tesseract, pinned handwriting model | geometry-preserving text candidates |
| Document layout | pinned local layout/table models | reading order, regions, rows, cells |
| Search | PostgreSQL full-text and trigram | cited lexical and structured search |
| Metrics | OpenTelemetry and Prometheus-compatible collector | latency, quality, cost, failures |
| Logs | structured JSON to encrypted local retention | operational diagnostics without evidence text |
| Secrets | OS/key-management service | credential references only |

Pin every production image by digest. Pin Python lockfiles, model weights,
language packs, OCR dictionaries, fonts, and the Office update channel. A
version is not “latest”; it is an approved artifact hash.

Use Docker Compose for the Linux processes during the first six months. One
database and one deployment simplify transactions and incident response. Split
a worker into a service only after measurements prove resource isolation or
independent scaling is needed.

### 3.2 Windows Excel worker

A dedicated Windows 11 VM runs a signed DataBossX worker under a non-admin
interactive desktop identity. It:

- receives only a candidate workbook, workbook profile, and task receipt;
- has macros disabled and external-link refresh disabled;
- has network access denied except to the private task API and vault;
- opens, fully recalculates, saves, and exports PDF through installed Microsoft
  Excel;
- returns the Office build, formula errors, PDF, final workbook, and hashes;
- is recycled after each workbook and restored from a known image on failure.

Do not run Excel automation as a Windows service. Do not use LibreOffice as the
release authority for Microsoft Excel templates. A headless parser can inspect
OOXML, but only native Excel proves native calculation and pagination.

### 3.3 Trust and network boundaries

- TLS is required even on the private network.
- UI users authenticate through OIDC with MFA.
- Database roles are `migration_owner`, `api_reader`, `orchestrator_writer`,
  `worker_none`, and `backup_operator`. Workers cannot connect to PostgreSQL.
- Workers lease tasks over authenticated HTTPS and return immutable envelopes.
- Tenant and project row-level security is forced in PostgreSQL.
- Remote OCR/model workers have allowlisted egress. Local-only projects have no
  route to a remote worker, making accidental egress technically impossible.
- Source bytes never appear in logs, traces, exception trackers, or prompts
  unless a project policy explicitly permits that provider.

### 3.4 Approved software bill of materials

The first qualified build uses the following named baseline. The release BOM
records the exact package lock, container digest, model-weight SHA-256,
language-pack SHA-256, configuration hash, and license receipt; no mutable model
or `latest` container tag is accepted.

| Capability | Baseline product |
| --- | --- |
| Linux host | Ubuntu Server 24.04 LTS, CIS-hardened |
| Container runtime | Docker Engine 27 and Compose v2 |
| Application | CPython 3.12, FastAPI, Pydantic v2, psycopg 3 |
| Database/GIS | PostgreSQL 17 and matching PostGIS 3 image |
| Object vault | MinIO Enterprise or AWS S3 Object Lock, selected before Day 4 |
| PDF | MuPDF/PyMuPDF plus qpdf validation |
| Images | OpenCV 4, libvips, Pillow |
| Printed OCR | PaddleOCR PP-OCRv5 server model |
| OCR challenger | Tesseract 5 with explicit English language pack |
| Layout/tables | PaddleOCR PP-StructureV3 |
| Handwriting | `microsoft/trocr-large-handwritten`, locally hosted |
| Model runtime | ONNX Runtime where export is benchmark-equivalent; otherwise pinned framework runtime |
| UI | Node.js 22 LTS, Vite, React, TypeScript |
| Telemetry | OpenTelemetry Collector, Prometheus, Grafana |
| Windows verifier | Windows 11 Enterprise 24H2 and Microsoft 365 Apps Current Channel pinned to a qualified build |

MinIO versus AWS S3 is the one deployment-specific choice: on-premises work
uses MinIO; private-cloud work uses S3. Both must pass the same
`ObjectVault` contract, retention, hash, object-lock, backup, and restore suite.
The week-one `bom.lock.json` supplies exact patches and digests after the target
hardware is known. A BOM change invalidates qualification and runs the relevant
golden suites.

## 4. Canonical repository

The current repository becomes one monorepo:

```text
src/databossx/
  api/                     # FastAPI routes and query services
  control/                 # orchestration, leases, policy, outbox
  domain/                  # immutable contracts and value objects
  persistence/             # repositories and transaction boundaries
  vault/                   # content-addressed object storage
  connectors/
    local/
    drive/
    county/
  workers/
    documents/
    imaging/
    ocr/
    layout/
    extraction/
    normalization/
  products/title/
    instruments/
    parties/
    land/
    graph/
    interests/
    defects/
    notes/
    workbooks/
  observability/
ui/                        # only operational frontend
migrations/                # numbered forward SQL migrations
schemas/                   # JSON Schema/OpenAPI/event contracts
config/
  policies/
  jurisdictions/
  document_types/
  template_profiles/
tests/
  unit/
  integration/
  property/
  adversarial/
  golden/
  performance/
  windows_excel/
ops/                       # non-secret local deployment examples
website/                   # independent public static site
```

Migration policy:

| Existing asset | Decision |
| --- | --- |
| `horizon/interest.py` | port with its tests; expand to typed interest bases |
| `horizon/chaining.py` | retain normalization regression tests; replace engine |
| Horizon controlled loop and workbook QA | port concepts into release gates |
| PR #26 Title Factory | review immediately; port source hashing, OCR geometry, candidate archive, resume, control workbook, and integrity tests through a feature/test parity matrix; reject any competing domain authority |
| `grocery_report_pipeline.py` | split stages into workers, then remove file |
| `doto_image_commander/` | port county connector, cost controls, and audit |
| `mineral_deal_room/` | move to `ui/`, replace static data with API |
| `backend/`, `frontend/` | delete after migration; never deploy |
| Roger Mills builder | convert mappings into a versioned template profile |
| root dependency files | replace with one locked Python project plus UI lockfile |
| client files | never commit; migrate to vault/Drive records |

Keep private deployment settings in a private operations repository. Keep
credentials only in a secret manager. Do not create a repository per county,
client, report, worker, or model.

Before any new build is deployable, quarantine the current root `Dockerfile`,
`entrypoint.sh`, and `run.bat` paths that launch `backend/server.py`. CI uses an
explicit production-image allowlist and fails if `backend/`, `frontend/`, mock
OCR symbols, sample data, or development CORS enter an image. Month 5 removes
legacy source after parity; Day 1 removes its ability to deploy.

Plugins are limited to stable external boundaries:

- `SourceConnector`
- `OcrProvider`
- `LayoutProvider`
- `ExtractionProvider`
- `JurisdictionRuleSet`
- `TemplateAdapter`
- `DeliveryConnector`

Title arithmetic, evidence, claims, workflow, audit, and release logic are core
modules, not plugins.

## 5. Files and immutable artifacts

Object keys are implementation details; database IDs are references. The vault
uses:

```text
objects/sha256/ab/cd/<64-hex-hash>
manifests/<tenant>/<project>/<artifact-version>.json
quarantine/<reason>/<uuid>
backups/database/<timestamp>.dump.enc
```

Every artifact manifest contains:

```json
{
  "schema_version": "1.0",
  "artifact_id": "uuid",
  "artifact_kind": "ocr_page_result",
  "sha256": "hex",
  "size_bytes": 123,
  "media_type": "application/json",
  "inputs": [{"artifact_version_id": "uuid", "sha256": "hex"}],
  "recipe": {"name": "printed-ocr", "version": "3", "sha256": "hex"},
  "toolchain": [{"name": "engine", "version": "pinned", "digest": "hex"}],
  "policy_sha256": "hex",
  "created_at": "RFC3339",
  "task_attempt_id": "uuid"
}
```

Created artifact kinds include:

- source occurrence metadata and source byte;
- custody receipt and locked source manifest;
- rendered page and thumbnail;
- page-quality profile;
- preprocessing variant and homography;
- native-text, OCR, handwriting, layout, and consensus results;
- classification and extraction candidate archives;
- evidence spans and reconciliation manifests;
- title graph snapshot, calculation trace, and defect set;
- review worklist and decision receipt;
- template authority/profile, write plan, candidate workbook;
- pre/post-Excel package inventories and diffs;
- rendered PDF, release manifest, and delivery receipt.

Original, OCR, claim, title, and report versions are append-only. A correction
creates a new revision linked to the prior one. Released files are never
overwritten; a defect produces a superseding release and an incident record.

## 6. Durable workflow

### 6.1 Project state

```text
DRAFT
 -> INVENTORY_REVIEW
 -> EVIDENCE_LOCKED
 -> PROCESSING
 -> EXAMINER_REVIEW
 -> READY_FOR_EXPORT
 -> CANDIDATE_VERIFIED
 -> APPROVED
 -> RELEASED
 -> SUPERSEDED (optional terminal successor)
```

Transitions are commands with preconditions. There is no generic “set status”
endpoint.

### 6.2 Logical queues

Queues are rows in PostgreSQL selected with `FOR UPDATE SKIP LOCKED`, not
separate brokers:

```text
ingest.inventory.v1
ingest.copy_and_verify.v1
document.inspect.v1
document.render.v1
page.assess.v1
page.preprocess.v1
ocr.native.v1
ocr.printed.v1
ocr.handwriting.v1
ocr.remote.v1
layout.analyze.v1
ocr.consensus.v1
document.classify.v1
instrument.extract.v1
claim.reconcile.v1
entity.resolve.v1
land.normalize.v1
title.graph.v1
interest.project.v1
defect.evaluate.v1
review.materialize.v1
report.plan.v1
report.patch.v1
report.static_audit.v1
report.excel_verify.v1
report.visual_audit.v1
release.publish.v1
feedback.curate.v1
deadletter.v1
```

Priority is: release blockers, material conflicts affecting downstream title,
missing pages, low-confidence operative clauses, then normal throughput.

### 6.3 Task contract

Each task has:

- UUID, run, queue, capability, priority, and current state;
- immutable input manifest hash;
- idempotency key;
- required policy and confidentiality partition;
- dependency conditions;
- lease owner, expiry, heartbeat, and bounded attempt budget;
- cost, token, page, time, and remote-egress budgets;
- correlation and causation IDs.

The idempotency key is:

```text
SHA256(
  queue + contract_version + canonical_input_json +
  ordered_input_hashes + recipe_hash + tool_or_model_digest +
  policy_hash + jurisdiction_rules_hash
)
```

Workers return `TaskOutcome` with status, output receipts, typed candidate
records, diagnostics, metrics, input hash, and output manifest hash. They cannot
claim success with prose and cannot write canonical rows. The orchestrator
validates the envelope and commits canonical state, audit event, and outbox row
in one transaction.

Task states:

```text
PLANNED -> BLOCKED | READY -> LEASED -> RUNNING
RUNNING -> SUCCEEDED | WAITING_HUMAN | FAILED_RETRYABLE | FAILED_TERMINAL
FAILED_RETRYABLE -> READY
```

Retries use the same idempotency key. Stale leases are reclaimed. Poison tasks
retain every attempt and enter `deadletter.v1`.

## 7. End-to-end production workflow

### Stage 0 — project and scope

An operator creates a project with client, jurisdiction, confidentiality,
search dates, tract/depth scope, estate types, report template, required
document classes, and reviewer roles. A jurisdiction ruleset and policy version
are frozen. Search scope is reviewed before processing.

Output: project, search-scope revision, policy snapshot, template authority
reference.

### Stage 1 — inherited-data inventory

Connectors scan bounded Drive roots, local folders, SQLite databases, existing
reports, and repositories in read-only mode. For every occurrence they record
provider ID, path/name, revision, MIME from bytes, size, timestamps, owner,
permissions, available checksum, and relationship to a project.

Content is streamed to a temporary file, hashed, malware-scanned, fsynced,
copied to the object vault, read back, and hash-verified. Identical bytes share
one blob within a tenant but retain separate occurrences.

Existing SQLite rows are imported into staging tables with source database
hash, table, primary key, and raw JSON. Nothing becomes a canonical title fact
until it has source evidence.

The inventory UI groups:

- exact duplicates by SHA-256;
- likely duplicate scans by perceptual page hashes and OCR similarity;
- prior reports and templates;
- missing expected classes;
- unreadable/encrypted/unsupported items;
- conflicting versions and unknown provenance.

No automatic deletion or quarantine move occurs. “Quarantine” is a database
state and isolated copied byte, not a mutation of the inherited folder.

Gate: a human approves the source manifest hash. Any later source revision
invalidates downstream approval.

### Stage 2 — document inspection and decomposition

The document worker:

1. identifies media type from bytes;
2. validates ZIP/PDF/image structure, limits, encryption, signatures, page
   count, dimensions, compression ratio, and embedded payloads;
3. extracts native PDF text, glyph coordinates, annotations, page boxes,
   rotation, embedded images, and font metadata;
4. renders each page to a lossless image at an effective 300 DPI, escalating
   material fine print to 400 or 600 DPI;
5. creates page records and page-image hashes;
6. validates rendered page count against the container.

Native text is accepted only if it has sane Unicode, adequate glyph coverage,
correct spatial registration, and visual spot-check agreement. A text layer
from a bad prior OCR is just another candidate.

### Stage 3 — page quality and preprocessing

For every page, deterministic measurements and pinned classifiers produce:

- DPI, orientation, skew, perspective, clipping;
- blur, contrast, illumination, background variance, compression artifacts;
- speckle, faded ink, bleed-through, front/back correlation;
- printed/handwritten/cursive probabilities;
- language/script candidates;
- column, table, ruling-line, form, stamp, seal, signature, and marginalia
  regions;
- native-text coverage and reading-order ambiguity.

Preprocessing never alters the source page and never uses generative image
enhancement. It creates at most three normal variants and six escalated
variants:

| Condition | Generated variants |
| --- | --- |
| clean scan | grayscale, deskewed grayscale, adaptive threshold |
| faded | channel-separated, background-subtracted, CLAHE/Sauvola |
| bleed-through | channel separation, conservative bilateral suppression, paired-side cancellation when known |
| blurred | denoise plus mild unsharp mask; no invented super-resolution |
| cursive | high-resolution grayscale, contrast-only, channel-separated |
| table/index | line-preserving image and line-removed text image |
| multicolumn | full page plus layout-derived column crops |
| perspective photo | conservative dewarp with stored homography |

Every crop and variant maps back to source coordinates with a recorded 3x3
homography.

### Stage 4 — OCR and layout

OCR is region-routed:

1. Registered native text is primary for a clean born-digital region.
2. The pinned local printed engine runs on ordinary scans.
3. Tesseract is an independent challenger on weak or material regions.
4. A pinned handwriting recognizer runs on segmented handwritten lines.
5. Table/layout models detect index rows and cells before cell OCR.
6. Mixed pages route printed, cursive, stamp, margin, and table regions
   independently.
7. A policy-approved remote document/vision provider runs only on unresolved
   material regions, not automatically on the entire document.
8. If no allowed route clears the evidence threshold, the region goes to human
   transcription.

Old county indexes are processed as tables: detect column boundaries and row
baselines, preserve headings, OCR each cell, associate continuation rows, and
store a row object with cell polygons. Multiple-column pages are segmented
before reading order. Stamps and marginal notations remain independent regions
so they do not corrupt body text.

There is no page cap. Large documents are page-sharded and assembled from an
ordered page manifest.

OCR output stores token, line, block, cell, raw/normalized text, source polygon,
reading order, engine/version, variant hash, raw confidence, calibrated
probability, and alternatives.

Consensus aligns overlapping tokens geometrically. It builds a confusion
network and retains alternatives such as `1/8` versus `1/6`. Majority agreement
cannot resolve a material legal value.

Confidence is calibrated against reviewed private gold data by engine, version,
quality band, document class, field class, and printed/handwritten mode.
Measure character error rate, word error rate, exact-field rate, Brier score,
and expected calibration error. Confidence prioritizes routing and review; it
does not establish title.

OCR qualification is per stratum, not one aggregate:

| Stratum | Primary route | Required fallback | Production gate |
| --- | --- | --- | --- |
| born-digital | registered native text | Paddle visual spot-check | zero material glyph-registration errors in locked holdout |
| clean printed scan | PP-OCRv5 | Tesseract challenger | material-field lower 95% confidence bound >= 99% |
| low-DPI/fax/compressed | 400/600 DPI bounded variants + both printed engines | remote region or human | never auto-accept a fraction/name below calibrated threshold |
| faded/bleed-through | channel/background variants + both engines | human if material alternatives remain | per-condition CER/WER and material exact rate reported |
| handwriting/cursive | line segmentation + TrOCR | approved remote handwriting route or human | no material field auto-accept until at least 500 reviewed lines in that hand/quality family |
| index/table | PP-Structure row/cell detection + cell OCR | human row reconstruction | row/column association lower 95% bound >= 99% |
| columns/mixed/stamps/margins | region segmentation and independent routes | full-page human comparison | reading order and region attribution lower 95% bound >= 99% |
| clipped/occluded/unreadable | no reconstruction | request better source or human `UNREADABLE` decision | automatic release prohibited |

Each major degradation stratum needs at least 1,000 held-out material fields
before general auto-accept is enabled; handwriting needs 500 held-out lines and
200 material fields. Until then, the route may assist but all material values
are reviewed. Wilson lower confidence bounds, not point estimates, control
promotion.

### Stage 5 — document classification

Classification produces page role, document family, operative subtype,
jurisdiction, likely title effects, supporting heading span, and alternatives.

Deterministic headings and layout rules run first; a trained classifier runs
second; an LLM may challenge. The controlling heading, not a referenced
instrument in a “subject to” clause, determines document type.

Supported initial families:

- warranty, quitclaim, mineral, royalty, correction, and trustee deeds;
- oil and gas leases, memoranda, amendments, ratifications, releases;
- assignments, bills of sale, farmouts, pooling/unit orders;
- mortgages, liens, releases, judgments;
- probate petitions, wills, decrees, heirship affidavits, death records;
- corporate merger, conversion, name-change, dissolution records;
- plats, surveys, tract maps, county indexes, court dockets;
- prior title/ownership reports and spreadsheets.

Low-confidence or mixed-document bundles are split only through a reviewed
page-range proposal.

### Stage 6 — field extraction

Extraction is document-family-specific and produces candidates, never facts.
Independent passes include:

- deterministic date, recording reference, fraction, money, PLSS, and citation
  parsers;
- layout-aware schema extraction;
- family-specific rules/models;
- optional LLM structured extraction from selected source regions;
- cross-page exhibit and continuation assembly.

The canonical field catalog covers:

- grantors, grantees, lessors, lessees, assignors, assignees, heirs, devisees,
  executors, trustees, corporate capacities, spouses, and signatories;
- execution, effective, acknowledgment, recording, death, decree, and merger
  dates;
- instrument/reception number, book, page, case number, recording office;
- consideration and tax/documentary values;
- complete verbatim and parsed legal descriptions, acreage, exceptions,
  easements, and excluded tracts;
- estate conveyed, fraction language, fraction basis, reservations,
  exceptions, subject-to clauses, depth and formation limitations;
- primary term, extension, royalty, shut-in, pooling, continuous-development,
  Pugh, retained-acreage, and habendum terms;
- assignment scope, WI, NRI, ORRI, NPRI, overriding burdens, proportionate
  reduction, effective time;
- probate distributions, life estates, remainders, heirship claims;
- corporate predecessor/successor language and filing references;
- correction, release, ratification, and related-instrument references.

Every candidate has a typed value, verbatim value, value state, source spans,
extractor/version, probability, materiality, and validation findings.

### Stage 7 — claims and reconciliation

Candidates become claims only if the evidence polygon covers the complete
semantic value.

- Matching normalized candidates with compatible evidence are one claim with
  multiple supports.
- A deterministic normalization rule may unify equivalent dates, fractions, or
  recording references while preserving verbatim text.
- Material disagreement opens a conflict. No score or model vote selects it.
- Unsupported output is retained in the candidate archive but cannot become a
  claim.
- Missing, illegible, absent, and not-applicable values are explicit states.
- Losing candidates and reviewer corrections remain immutable.

### Stage 8 — normalization and identity

Party names retain:

1. verbatim source text;
2. conservative search key;
3. canonical party identity.

Search normalization standardizes case, Unicode, punctuation, whitespace,
suffix formatting, and known OCR confusions. It never discards a suffix or
legal capacity in the canonical value.

Entity resolution proposes links using names, addresses, co-parties, spouse
context, signature capacity, probate case, corporate registration identifiers,
dates, jurisdictions, and predecessor documents. Only a deterministic unique
identifier or human review may merge parties. Merge and split decisions are
reversible events; source mentions are never rewritten.

Aliases, former names, DBAs, trusts, personal representatives, heirs, mergers,
conversions, and name changes are typed relationships with effective dates and
source support. Similar names alone do not establish succession.

### Stage 9 — land normalization and GIS

The legal-description parser emits an AST, not a cleaned string.

PLSS components include state/county, principal meridian, township number and
direction, range number and direction, section, nested aliquot path,
government lot, subdivision, stated acreage, exceptions, and verbatim text.

Example:

```text
NE/4 of SW/4, Section 31, T10N R20W
-> Section(31, Aliquot(NE, Aliquot(SW)), Township(10,N), Range(20,W))
```

Metes-and-bounds descriptions store point of beginning, ordered calls, exact
bearing, exact distance/unit, monuments, curve parameters, exclusions, and
parent tract. Decimal calculations produce closure vector and closure ratio.
The system flags nonclosure; it does not silently repair a call.

GIS imports authoritative cadastral layers with source, publication date,
coordinate reference system, and license. A parsed description can be linked
to geometry only with an explicit derivation version and quality status.
PostGIS detects overlap, gaps, wrong section, wrong county, impossible acreage,
and report-map mismatches. OCR/LLM output never draws a legally authoritative
boundary by itself.

Depth is a first-class interval with top/bottom boundary type, numeric depth,
unit, datum, measured-depth versus TVD basis, formation marker, inclusive
language, and verbatim source. Incompatible datums are not compared.

### Stage 10 — title graph and calculations

Accepted claims produce a temporal multigraph.

Nodes:

- parties and corporate identities;
- instruments and recording events;
- tracts and estate slices;
- depth intervals and effective-time intervals;
- mineral, royalty, leasehold, WI, NRI, ORRI, and NPRI positions;
- probate estates and corporate events.

Edges:

- conveys, reserves, excepts, leases, assigns, burdens, mortgages, releases;
- devises, distributes, claims-heirship;
- merges-into, converts-to, changes-name-to;
- corrects, ratifies, terminates, and references.

Every edge cites accepted claim revisions and evidence. Ordering distinguishes
execution, effective, recording, death, decree, and merger dates. Recording
priority is evaluated by a versioned jurisdiction rule, not by naïve date sort.

Each conveyance is decomposed by tract, estate, depth interval, effective
interval, and interest basis. One instrument may produce multiple ledger
transactions. Duplicate recordings point to one logical legal effect unless a
reviewed rule says otherwise.

Probate is explicit:

```text
decedent -> death -> estate -> will/intestacy evidence
          -> representative authority -> decree/distribution -> successors
```

A will or heirship affidavit is evidence, not automatically a decree.
Unresolved heirs, missing ancillary probate, life estates, remainders, and
inconsistent names open defects.

Corporate succession requires an authoritative filing, explicit assignment, or
reviewed determination. Merger, name change, conversion, dissolution,
reinstatement, bankruptcy transfer, and asset assignment are distinct events.

### Stage 11 — defects and examiner notes

Deterministic, jurisdiction-versioned rules detect:

- source drift, missing pages, unreadable operative clauses;
- unsupported material claims and unresolved conflicts;
- chain gaps and grantors without supported ownership;
- duplicate instruments with incompatible contents;
- tract, acreage, PLSS, geometry, or depth mismatch;
- over-conveyance, negative balance, and interest conservation failure;
- ambiguous fraction/burden basis;
- lease assignment beyond assignor holdings;
- missing probate distribution or unsupported corporate successor;
- unreleased liens/mortgages within search scope;
- correction instruments without originals;
- stale approvals, policy drift, and workbook integrity failures.

Each result contains rule/version, severity, affected graph nodes, evidence,
calculation trace, suggested curative action, and disposition. The system
generates factual draft notes from structured results, for example:

```text
System finding: Instrument 2024-1234 purports to convey 1/2 of the minerals in
Tract A. The accepted ledger shows the grantor holding 1/4 immediately before
the effective date. Apparent over-conveyance: 1/4. Sources: [links].
Examiner disposition: [required].
```

An LLM may rewrite an approved structured finding into the client template's
house style. It may not add facts, legal conclusions, or citations. A
deterministic verifier ensures every number/entity/citation in prose exists in
the structured input.

### Stage 12 — human review

Humans review material ambiguity and legal judgment, not file conversion or
copying.

Always human-reviewed:

- unreadable operative language;
- material candidate conflict;
- party merge/split without unique identity;
- chain gap, over-conveyance, legal/depth mismatch;
- probate/heirship and corporate succession determinations;
- exception/defect disposition and curative recommendation;
- title graph and final ownership projection;
- generated notes;
- first qualification of each template;
- exact final artifact hash.

Normally automated:

- hashing, custody, rendering, safe preprocessing;
- clear nonmaterial OCR;
- exact parsers and schema validation;
- duplicate detection, conservation tests, workbook diffs;
- backup, sync cursor processing, and release receipt creation.

The review screen shows source image with highlight, variants, OCR alternatives,
verbatim/normalized candidate, competing candidates, affected chain edges,
exact calculations, and rule findings together.

Review actions are accept, correct, reject, mark illegible, request source,
resolve conflict, merge/split entity, disposition defect, or escalate. A
correction appends a claim revision and reason code. Two qualified reviewers
must resolve high-impact disagreement; persistent disagreement goes to the
designated senior examiner or attorney. Confidence never breaks a tie.

### Stage 13 — report and release

The report model is a versioned projection of accepted claims and ledger
results. Each report field carries its claim revision IDs, format rule, target
cell, and display value. Export cannot begin with unresolved material blockers.

The workbook system follows Section 12 below. The release service verifies all
gates. Report approval and delivery approval are separate. Delivery approval is
short-lived and binds tenant, connector identity, destination root/file
identity, operation (`CREATE_RELEASE` only), exact payload hash, policy hash,
approver, and expiry. The executor cannot be the delivery approver. The service
uploads a new immutable release, downloads it again, compares hashes, and
writes a release/delivery receipt.

## 8. Canonical database

### 8.1 Conventions

- UUIDv7 application-generated keys.
- `timestamptz` for instants; `date` for legal dates without time.
- Every project table includes `tenant_id` and `project_id`; foreign keys carry
  both to prevent cross-tenant/project references.
- Every listed `id` is a non-null UUIDv7 primary key unless a composite `PK` is
  shown. Every `tenant_id` references `iam.tenants(id)`. Every project-scoped
  row has `FK (tenant_id,project_id) -> core.projects(tenant_id,id)`.
- Every named `*_id` has a same-tenant composite foreign key to the named table;
  project-domain references also include `project_id`. All canonical foreign
  keys use `ON UPDATE RESTRICT ON DELETE RESTRICT`. Retention is state/event
  based, not cascading deletion.
- Columns are `NOT NULL` unless marked `NULL` or their value state makes absence
  explicit. State/type codes have lookup-table foreign keys or versioned check
  constraints in the migration.
- SHA-256 is `bytea CHECK (octet_length(value)=32)`.
- Exact fractions are `numerator numeric(100,0)` and
  `denominator numeric(100,0) CHECK (denominator > 0)`, reduced by a constraint
  trigger.
- Frequently queried legal values are typed columns. `jsonb` is for bounded
  extensions, not a substitute for a schema.
- Immutable tables reject `UPDATE` and `DELETE` with triggers.
- “Current” values are views over append-only events/revisions.
- Row-level security is forced using transaction-local tenant/user context.

### 8.2 Tables

The initial migration creates these schemas and tables. Columns listed are the
required core, not optional prose.

#### Identity and policy

- `iam.tenants(id PK, slug UNIQUE, name, status, created_at)`
- `iam.users(id PK, email citext UNIQUE, display_name, disabled_at)`
- `iam.tenant_memberships(tenant_id FK, user_id FK, role_code, valid_during,
  PK(tenant_id,user_id))`
- `iam.project_memberships(tenant_id, project_id, user_id, role_code,
  valid_during, PK(...))`
- `iam.service_accounts(tenant_id, id, name, credential_ref, disabled_at,
  UNIQUE(tenant_id,name))`
- `iam.policy_sets(tenant_id, id, name, classification, egress_policy jsonb,
  retention_policy jsonb, created_at)`
- `iam.policy_versions(tenant_id, id, policy_set_id FK, version_no, policy_json,
  policy_hash, approved_by, approved_at, UNIQUE(policy_set_id,version_no))`

#### Projects, sources, and vault

- `core.projects(tenant_id, id, name, jurisdiction_id, policy_version_id,
  classification, state, row_version, created_at, released_at)`
- `core.project_state_events(tenant_id, project_id, id, from_state, to_state,
  actor_id, reason, occurred_at)`
- `core.search_scope_revisions(tenant_id, project_id, id, revision_no,
  effective_start, effective_end, estates, scope_json, scope_hash, approved_at)`
- `core.source_connections(tenant_id, id, provider_code, bounded_root_id,
  credential_ref, capabilities, status, created_at)`
- `core.source_snapshots(tenant_id, project_id, id, connection_id,
  provider_cursor, manifest_hash, completeness_status, scanned_at, locked_at)`
- `core.source_occurrences(tenant_id, project_id, id, snapshot_id,
  connection_id, provider_id,
  provider_revision, display_name, locator_ciphertext, mime_type, size_bytes,
  provider_checksum, metadata_json, discovered_at,
  UNIQUE(snapshot_id,connection_id,provider_id))`
- `core.blob_objects(tenant_id, id, sha256, size_bytes, media_type, storage_uri,
  verified_at, created_at, UNIQUE(tenant_id,sha256))`
- `core.assets(tenant_id, project_id, id, asset_kind, logical_name,
  source_connection_id, created_at)`
- `core.asset_versions(tenant_id, project_id, id, asset_id, version_no, blob_id,
  occurrence_id, previous_version_id, custody_at, manifest_json,
  UNIQUE(asset_id,version_no))`
- `core.artifacts(tenant_id, project_id, id, artifact_kind, logical_name)`
- `core.artifact_versions(tenant_id, project_id, id, artifact_id, version_no,
  blob_id, recipe_name, recipe_version, recipe_hash, task_attempt_id,
  manifest_hash, created_at, UNIQUE(artifact_id,version_no))`
- `core.artifact_inputs(tenant_id, project_id, artifact_version_id,
  input_asset_version_id NULL, input_artifact_version_id NULL, input_role,
  CHECK(exactly one input), PK(...))`
- `core.import_records(tenant_id, project_id, id, source_blob_id, source_table,
  source_pk, raw_json, import_status, canonical_target_type,
  canonical_target_id)`

#### Documents, OCR, and evidence

- `evidence.documents(tenant_id, project_id, id, asset_version_id,
  document_family, page_count, inspection_status, UNIQUE(asset_version_id))`
- `evidence.document_pages(tenant_id, project_id, id, document_id, page_no,
  width, height, rotation, rendered_artifact_version_id,
  UNIQUE(document_id,page_no))`
- `evidence.page_quality_profiles(tenant_id, project_id, id, page_id,
  recipe_version, metrics_json, route_flags, profile_hash)`
- `evidence.image_variants(tenant_id, project_id, id, page_id, artifact_version_id,
  recipe_name, recipe_version, homography, quality_purpose)`
- `evidence.processing_runs(tenant_id, project_id, id, run_kind, provider,
  model_name, model_version, prompt_version, input_hash, output_hash,
  parameters_json, token_usage_json, cost_microunits, status, started_at,
  completed_at)`
- `evidence.ocr_page_results(tenant_id, project_id, id, processing_run_id,
  page_id, variant_id, full_text_artifact_id, mean_probability, language_codes,
  result_hash, UNIQUE(processing_run_id,page_id,variant_id))`
- `evidence.ocr_nodes(tenant_id, project_id, id, page_result_id, parent_id,
  node_kind, ordinal, raw_text, normalized_text, raw_confidence,
  calibrated_probability, x0, y0, x1, y1, polygon, char_start, char_end)`
- `evidence.layout_regions(tenant_id, project_id, id, page_id, parent_id,
  region_kind, reading_order, polygon, row_no, column_no, model_run_id)`
- `evidence.classification_candidates(tenant_id, project_id, id, document_id,
  page_range, family, subtype, probability, heading_span_id, processing_run_id,
  candidate_hash)`
- `evidence.evidence_spans(tenant_id, project_id, id, asset_version_id, page_id,
  ocr_node_id NULL, char_start, char_end, polygon, quoted_text, span_hash)`
- `evidence.claim_subjects(tenant_id, project_id, id, subject_kind,
  canonical_entity_id NULL, created_at)`
- `evidence.claim_predicates(tenant_id, id, code, value_type, materiality,
  validation_schema, UNIQUE(tenant_id,code))`
- `evidence.claims(tenant_id, project_id, id, subject_id, predicate_id,
  logical_key, created_at, UNIQUE(subject_id,predicate_id,logical_key))`
- `evidence.claim_revisions(tenant_id, project_id, id, claim_id, revision_no,
  value_state, value_type, value_text, value_date, value_num, value_den,
  value_entity_id, value_json, verbatim_text, method, processing_run_id,
  supersedes_id, recorded_at, UNIQUE(claim_id,revision_no))`
- `evidence.claim_supports(tenant_id, project_id, claim_revision_id,
  evidence_span_id, support_role, rule_version, support_probability, PK(...))`
- `evidence.claim_acceptance_events(tenant_id, project_id, id, claim_id,
  claim_revision_id, action, review_decision_id, recorded_at)`
- `evidence.conflicts(tenant_id, project_id, id, subject_id, predicate_id,
  materiality, status, opened_at)`
- `evidence.conflict_members(tenant_id, project_id, conflict_id,
  claim_revision_id, PK(...))`
- `evidence.conflict_resolution_events(tenant_id, project_id, id, conflict_id,
  selected_revision_id, review_decision_id, action, recorded_at)`

#### Parties, tracts, and instruments

- `title.jurisdictions(id PK, country_code, state_code, county_name,
  recording_office_code, ruleset_code,
  UNIQUE(country_code,state_code,county_name,recording_office_code))`
- `title.parties(tenant_id, id, party_kind, canonical_name, status, created_at)`
- `title.party_names(tenant_id, id, party_id, name_text, name_kind, valid_during,
  source_claim_revision_id)`
- `title.party_mentions(tenant_id, project_id, id, party_id NULL,
  evidence_span_id, verbatim_name, role_hint, resolution_status)`
- `title.party_identifiers(tenant_id, id, party_id, identifier_type,
  identifier_hash, jurisdiction_id,
  UNIQUE(tenant_id,party_id,identifier_type,identifier_hash,jurisdiction_id))`
- `title.party_relationships(tenant_id, project_id, id, from_party_id,
  to_party_id, relationship_kind, effective_during, source_instrument_id,
  source_claim_revision_id)`
- `title.tracts(tenant_id, project_id, id, tract_code, gross_acres_num,
  gross_acres_den, geom geometry(MultiPolygon,4326), geometry_status, status,
  UNIQUE(project_id,tract_code))`
- `title.legal_descriptions(tenant_id, project_id, id, verbatim_text,
  normalized_text, description_kind, parse_ast_json, source_claim_revision_id)`
- `title.plss_components(tenant_id, project_id, legal_description_id,
  principal_meridian, section, township_no, township_dir, range_no, range_dir,
  aliquot_path, government_lot, subdivision, stated_acres_num,
  stated_acres_den)`
- `title.metes_bounds_calls(tenant_id, project_id, id, legal_description_id,
  ordinal, call_kind, bearing_json, distance_num, distance_den, unit,
  monument_text, curve_json)`
- `title.tract_legal_descriptions(tenant_id, project_id, tract_id,
  legal_description_id, relationship_kind, PK(...))`
- `title.formations(tenant_id, id, canonical_name, basin, aliases)`
- `title.depth_intervals(tenant_id, project_id, id, datum_code, basis_code,
  top_depth, bottom_depth, unit, top_formation_id, bottom_formation_id,
  top_inclusive, bottom_inclusive, verbatim_text)`
- `title.property_scopes(tenant_id, project_id, id, tract_id, depth_interval_id,
  estate_kind, effective_during,
  UNIQUE(project_id,tract_id,depth_interval_id,estate_kind,effective_during))`
- `title.instruments(tenant_id, project_id, id, subject_id, instrument_type,
  execution_date, effective_date, acknowledgment_date, status, created_at)`
- `title.instrument_revisions(tenant_id, project_id, id, instrument_id,
  revision_no, accepted_claim_set_hash, supersedes_id, recorded_at)`
- `title.recording_references(tenant_id, project_id, id, instrument_id,
  jurisdiction_id, instrument_number, book, page, reception_number, case_number,
  recorded_date, recording_office)`
- `title.instrument_parties(tenant_id, project_id, id, instrument_id, party_id,
  role_code, capacity_text, ordinal, source_claim_revision_id)`
- `title.instrument_scopes(tenant_id, project_id, instrument_id,
  property_scope_id, scope_role, source_claim_revision_id, PK(...))`
- `title.instrument_relations(tenant_id, project_id, id, from_instrument_id,
  to_instrument_id, relation_kind, source_claim_revision_id)`

#### Title ledger and domain events

- `title.ledger_transactions(tenant_id, project_id, id, event_kind,
  instrument_id, effective_date, sequence_no, idempotency_key,
  reverses_transaction_id, status, created_at, UNIQUE(project_id,idempotency_key))`
- `title.interest_postings(tenant_id, project_id, id, transaction_id,
  property_scope_id, party_id, interest_kind, basis_code, quantity_num,
  quantity_den, posting_role)`
- `title.leases(tenant_id, project_id, id, instrument_id, lessor_party_id,
  lessee_party_id, property_scope_id, status)`
- `title.lease_term_revisions(tenant_id, project_id, id, lease_id, revision_no,
  primary_term, option_term, royalty_num, royalty_den, terms_json,
  supersedes_id)`
- `title.lease_burdens(tenant_id, project_id, id, lease_id,
  beneficiary_party_id, burden_kind, basis_code, quantity_num, quantity_den,
  property_scope_id, source_claim_revision_id)`
- `title.assignments(tenant_id, project_id, id, ledger_transaction_id, lease_id,
  assignor_party_id, assignee_party_id, assignment_kind)`
- `title.probate_cases(tenant_id, project_id, id, decedent_party_id,
  jurisdiction_id, case_number, filed_date, closed_date, status)`
- `title.probate_events(tenant_id, project_id, id, probate_case_id, event_kind,
  event_date, instrument_id, source_claim_revision_id)`
- `title.probate_distributions(tenant_id, project_id, id, probate_case_id,
  ledger_transaction_id, successor_party_id, property_scope_id, quantity_num,
  quantity_den, distribution_kind)`
- `title.corporate_events(tenant_id, project_id, id, event_kind, effective_date,
  predecessor_party_id, successor_party_id, instrument_id,
  source_claim_revision_id)`
- `title.graph_revisions(tenant_id, project_id, id, revision_no,
  accepted_claim_manifest_hash, ruleset_hash, graph_artifact_version_id,
  status, created_at)`
- `title.chain_edges(tenant_id, project_id, id, graph_revision_id, edge_kind,
  from_subject_id, to_subject_id, property_scope_id, instrument_id,
  effective_date, evidence_manifest_hash)`
- `title.projection_runs(tenant_id, project_id, id, graph_revision_id,
  input_ledger_hash, formula_version, as_of_date, status, trace_artifact_id)`
- `title.interest_snapshots(tenant_id, project_id, projection_run_id, party_id,
  property_scope_id, mi_num, mi_den, royalty_num, royalty_den, wi_num, wi_den,
  nri_num, nri_den, orri_num, orri_den, npri_num, npri_den, PK(...))`
- `title.defect_results(tenant_id, project_id, id, graph_revision_id, rule_code,
  rule_version, severity, materiality, subject_id, status, details_json,
  evidence_manifest_hash)`
- `title.note_revisions(tenant_id, project_id, id, logical_note_id, revision_no,
  note_type, subject_type, subject_id, author_type, author_id, text,
  evidence_manifest_hash, supersedes_id, created_at)`

#### Workflow, review, reporting, and audit

- `workflow.definitions(tenant_id, id, name, created_at)`
- `workflow.definition_versions(tenant_id, id, definition_id, version_no,
  specification_json, spec_hash, UNIQUE(definition_id,version_no))`
- `workflow.runs(tenant_id, project_id, id, definition_version_id,
  input_manifest_hash, status, started_at, completed_at)`
- `workflow.tasks(tenant_id, project_id, id, run_id, queue_name, capability,
  status, idempotency_key, priority, available_at, input_manifest_hash,
  current_attempt_no, UNIQUE(run_id,idempotency_key))`
- `workflow.task_dependencies(tenant_id, project_id, task_id,
  depends_on_task_id, condition_code, PK(...))`
- `workflow.task_attempts(tenant_id, project_id, id, task_id, attempt_no,
  worker_id, input_hash, output_hash, status, failure_json, started_at,
  completed_at, UNIQUE(task_id,attempt_no))`
- `workflow.task_leases(tenant_id, project_id, id, task_id, attempt_id,
  worker_id, leased_at, expires_at, heartbeat_at, released_at)`
- `workflow.task_state_events(tenant_id, project_id, id, task_id, from_state,
  to_state, reason, occurred_at)`
- `workflow.outbox(tenant_id, project_id, id, event_type, aggregate_type,
  aggregate_id, payload_json, payload_hash, available_at, attempt_count,
  dispatched_at, last_error, created_at)`
- `review.cases(tenant_id, project_id, id, case_kind, subject_id, materiality,
  status, opened_by_task_id, due_at)`
- `review.assignments(tenant_id, project_id, id, case_id, reviewer_id,
  assigned_at, released_at)`
- `review.decisions(tenant_id, project_id, id, case_id, decision_code,
  rationale, reviewer_id, input_manifest_hash, decided_at)`
- `review.corrections(tenant_id, project_id, id, decision_id,
  old_claim_revision_id, new_claim_revision_id, correction_kind, reason_code)`
- `review.approvals(tenant_id, project_id, id, approval_kind, subject_id,
  input_manifest_hash, output_hash, policy_hash, reviewer_id, expires_at,
  revoked_at)`
- `review.external_write_approvals(tenant_id, project_id, id, release_id,
  connector_id, destination_root_ciphertext, destination_object_ciphertext,
  operation_code, payload_hash, policy_hash, approved_by, approved_at,
  expires_at, executed_by, executed_at, revoked_at)`
- `review.training_examples(tenant_id, project_id, id, correction_id,
  input_artifact_id, expected_claim_revision_id, consent_status,
  deidentification_status, dataset_split, example_hash)`
- `review.evaluation_runs(tenant_id, id, capability, provider_version,
  recipe_version, dataset_manifest_hash, metrics_json, promotion_decision,
  created_at)`
- `review.dataset_versions(tenant_id, id, name, version_no, manifest_artifact_id,
  manifest_hash, split_policy_hash, consent_snapshot_hash, locked_at,
  UNIQUE(tenant_id,name,version_no))`
- `review.training_runs(tenant_id, id, dataset_version_id, base_model_artifact_id,
  code_artifact_id, config_artifact_id, environment_hash, output_model_artifact_id,
  metrics_artifact_id, status, started_at, completed_at)`
- `review.model_versions(tenant_id, id, capability, model_name, version_no,
  model_artifact_id, training_run_id, license_code, status,
  UNIQUE(tenant_id,capability,model_name,version_no))`
- `review.model_promotion_events(tenant_id, id, model_version_id, from_state,
  to_state, evaluation_run_id, approved_by, policy_hash, occurred_at)`
- `review.model_deployments(tenant_id, id, model_version_id, environment,
  deployment_manifest_hash, enabled_at, disabled_at, approved_by)`
- `reporting.templates(tenant_id, id, name, file_format, status)`
- `reporting.template_versions(tenant_id, id, template_id, version_no,
  artifact_version_id, fingerprint_hash, office_build, approved_at,
  UNIQUE(template_id,version_no))`
- `reporting.template_profiles(tenant_id, id, template_version_id, version_no,
  profile_json, profile_hash, approved_by, approved_at)`
- `reporting.report_runs(tenant_id, project_id, id, graph_revision_id,
  projection_run_id, template_profile_id, input_manifest_hash, status)`
- `reporting.write_plans(tenant_id, project_id, id, report_run_id,
  write_plan_artifact_id, plan_hash, approved_at)`
- `reporting.report_artifacts(tenant_id, project_id, id, report_run_id,
  artifact_version_id, artifact_role, integrity_hash)`
- `reporting.integrity_audits(tenant_id, project_id, id, report_artifact_id,
  gate_code, result, details_json, audited_at)`
- `reporting.releases(tenant_id, project_id, id, release_no,
  report_artifact_id, input_manifest_hash, artifact_hash, approval_id,
  released_by, released_at, UNIQUE(project_id,release_no))`
- `reporting.release_events(tenant_id, project_id, id, release_id, event_kind,
  reason, occurred_at)`
- `reporting.delivery_receipts(tenant_id, project_id, id, release_id,
  connection_id, remote_file_id_ciphertext, uploaded_hash, verified_hash,
  delivered_at)`
- `audit.events(tenant_id, project_id, id, stream_id, stream_seq, actor_type,
  actor_id, action, entity_type, entity_id, request_id, correlation_id,
  causation_id, details_json, occurred_at, previous_hash, event_hash,
  UNIQUE(tenant_id,stream_id,stream_seq))`
- `audit.anchors(tenant_id, id, period_start, period_end, root_hash, signature,
  anchored_at)`

### 8.3 Critical constraints and indexes

- Unique partial recording references on `(tenant_id,jurisdiction_id,
  instrument_number)` and `(tenant_id,jurisdiction_id,book,page)` when present.
- Unique active task lease on `task_id WHERE released_at IS NULL`.
- B-tree task dequeue index on `(status, available_at, priority DESC)`.
- B-tree indexes on asset/claim/template version descending.
- Trigram GIN on party names and OCR normalized text.
- Full-text GIN on OCR page text and approved notes.
- GiST on tract geometry, party relationship date ranges, property effective
  ranges, and comparable depth ranges.
- Ledger index on `(project_id, property_scope_id, effective_date, sequence_no)`.
- Posting index on `(project_id, party_id, property_scope_id, interest_kind)`.
- B-tree indexes on every foreign-key column tuple and RLS-leading
  `(tenant_id,project_id)` path.
- BRIN on high-volume append timestamps.

Do not partition initially. Introduce measured hash partitions for OCR nodes and
claim supports, and monthly range partitions for audit/outbox, only before a
table exceeds the tested maintenance threshold. Premature partitions complicate
foreign keys and unique constraints.

### 8.4 Transaction boundaries

- Ingest: vault write first; one DB transaction inserts blob/version, custody
  event, audit, and outbox. An orphaned blob is safe and garbage-collectable.
- OCR: one page result and all its nodes commit atomically. A run completes only
  when expected page manifests validate.
- Extraction: processing run, candidate archive, claim revisions, support,
  conflicts, review cases, audit, and outbox commit together.
- Review: lock the case/claim; append decision, correction, acceptance event,
  resulting title task, and audit together.
- Ledger: `SERIALIZABLE`; advisory-lock the property scope; insert transaction
  and postings; run deferred exact-balance constraints.
- Release: `SERIALIZABLE`; lock project, recheck all gates and approval hashes,
  then create release/audit/outbox atomically.

### 8.5 Migration and deployment rollback

Every schema change uses expand/contract:

1. restore the latest production backup into staging and run migration
   preflight, integrity checks, and representative query plans;
2. take and verify a new backup plus WAL replay point;
3. deploy additive schema compatible with both old and new application builds;
4. backfill through idempotent, checkpointed tasks;
5. deploy readers/writers for the new schema and hold a compatibility window;
6. prove backup restore, event/outbox replay, and application rollback;
7. remove old columns/constraints only in a later release.

Abort on migration lock budget, data-count/hash mismatch, failed invariant,
unexpected query-plan regression, or failed restore drill. The release manager
owns the decision. Before contract phase, rollback redeploys the prior
application. After contract phase, recovery restores the verified backup and
replays audited events; releases remain paused until reconciliation passes.

## 9. Exact title and ownership engine

### 9.1 Quantity model

Every fraction has a basis:

```text
OF_EIGHT_EIGHTHS
OF_GRANTOR_INTEREST
OF_ASSIGNED_INTEREST
OF_LEASEHOLD
OF_PRODUCTION
NET_ACRES
UNIT_PARTICIPATION
```

“1/16 royalty” without a supported basis remains ambiguous. Display decimals
never feed calculations.

Ledger postings are signed and double-entry by property scope and interest
kind. Except for an approved opening balance, every transaction must sum to
zero exactly. A conveyance debits the grantor and credits the grantee; a
reservation creates retained and conveyed positions explicitly.

### 9.2 Algorithms

1. Sort applicable legal events by jurisdiction rule using effective,
   execution, recording, decree, death, and corporate-event dates.
2. Expand each instrument into affected tract/depth/estate/time scopes.
3. Resolve party capacity at the event date without merging identities.
4. Read the grantor's immediately prior exact balance.
5. Convert the conveyed language using its explicit basis.
6. Post debit/credit entries and retained/reserved burdens.
7. Reject or flag a negative balance; never clamp it to zero.
8. Recompute affected descendants incrementally.
9. Snapshot the projection at the requested as-of date.
10. Emit a human-readable calculation trace citing every source edge.

Typed effect rules extend that loop:

- Reservation/exception: split the source scope first; post the conveyed slice
  and retained/reserved slice separately. An exception removes property from
  the grant, while a reservation creates the stated retained interest/burden;
  ambiguous wording opens review.
- Partial assignment: multiply only the assignor's supported leasehold/WI/NRI
  in each included scope; excluded depths/tracts and retained ORRI become
  separate postings.
- Correction: link to the corrected instrument, reverse only the reviewed legal
  effects being replaced as of the jurisdiction-approved effective rule, then
  post corrected effects. Never delete the original.
- Ratification: create a confirmation/estoppel edge and any explicitly stated
  effective consequence; do not fabricate a new conveyance.
- Lease/amendment/release: create a leasehold interval; amendments supersede
  only identified terms; release/expiration closes the supported scopes at the
  supported time. HBP status is a reviewed fact, not inferred from age alone.
- Depth split: intersect the incoming scope with conveyed and retained depth
  intervals; incompatible datum/basis stops calculation.
- Probate: opening estate postings equal the decedent's supported positions.
  Decree/distribution postings transfer exact scopes to devisees/heirs; life
  estate and remainder are distinct temporal positions. Unknown heirs poison
  only affected downstream scopes.
- Corporate merger/conversion: after a supported effective event, move the
  predecessor's positions to the successor without changing quantity.
  Name-change events change identity presentation, not ownership.
- Reversal: a compensating transaction references the reversed transaction and
  has equal/opposite postings. Projections always retain both histories.

Each effect handler declares accepted instrument types, required claim
predicates, allowed bases, jurisdiction hook, postings, unknown propagation,
defect outputs, and property-based examples. An absent precondition produces
`WAITING_HUMAN`, never a partial posting.

Core formulas:

```text
retained = prior_grantor_interest - absolute_conveyance
absolute_conveyance =
  stated_fraction                         [OF_EIGHT_EIGHTHS]
  prior_grantor_interest * stated_fraction [OF_GRANTOR_INTEREST]

net_mineral_acres = gross_acres * mineral_interest
assigned_WI = assignor_WI * assignment_fraction
retained_WI = assignor_WI - assigned_WI
tract_participation = credited_tract_acres / unit_acres
unit_WI = leasehold_fraction * tract_participation
NRI = WI - burdens_expressed_in_eight_eighths
NRI = WI * (1 - relative_burdens)          [relative burden basis]
```

Mixed burden bases are converted only through explicit source-supported
relationships.

### 9.3 Invariants

For each estate/depth/time slice:

- incoming equals outgoing plus retained;
- aggregate ownership does not exceed 1/1;
- assigned WI does not exceed assignor WI;
- `0 <= NRI <= WI`;
- burdens do not exceed the affected interest;
- duplicate instruments apply once;
- unit participation reconciles to approved unit acreage;
- disjoint depths conserve separately;
- an unknown opening balance makes downstream balances unknown, not 8/8;
- no float is accepted at a domain boundary.

## 10. API contract

All endpoints are `/api/v1`, use OIDC, cursor pagination, UTC timestamps,
RFC 9457 problem responses, request IDs, optimistic row versions, and
`Idempotency-Key` on commands. Mutations return `202` plus a run/task URL.

```text
POST /projects
GET  /projects/{id}
POST /projects/{id}/transitions
POST /projects/{id}/search-scope-revisions

POST /connections/drive/authorizations
POST /connections/{id}/scans
GET  /connections/{id}/coverage
POST /source-snapshots/{id}/lock

GET  /assets
GET  /assets/{id}/versions
GET  /asset-versions/{id}/pages
GET  /pages/{id}/image
GET  /pages/{id}/ocr

POST /workflow-runs
GET  /workflow-runs/{id}
GET  /workflow-runs/{id}/tasks
POST /tasks/{id}/retry
POST /tasks/{id}/cancel

GET  /claims
GET  /claims/{id}/revisions
GET  /conflicts
POST /review-cases/{id}/decisions
POST /parties/{id}/merge-proposals
POST /party-merge-proposals/{id}/decisions

GET  /title-graphs/{revision}
GET  /title-graphs/{revision}/chains
GET  /interest-projections/{id}
GET  /interest-projections/{id}/trace
GET  /defects
POST /defects/{id}/dispositions

POST /templates
POST /templates/{id}/qualifications
GET  /template-versions/{id}/profile
POST /report-runs
GET  /report-runs/{id}/integrity
POST /report-runs/{id}/approvals
POST /releases/{id}/external-write-approvals
POST /report-runs/{id}/release

GET  /search
GET  /audit-events
GET  /health/live
GET  /health/ready
GET  /metrics
```

Evidence image endpoints use short-lived signed URLs and range requests.
Downloaded originals require an explicit permission and are audited.

## 11. Caching and versioning

Caches are immutable derivations, separated by tenant and confidentiality:

| Cache | Complete key |
| --- | --- |
| render | source hash + renderer digest + page + DPI + colorspace |
| quality | page image hash + quality recipe/model digest |
| preprocess | page image hash + recipe/version/parameters |
| OCR | variant hash + engine/model digest + full config |
| layout | page hash + OCR manifest + layout digest |
| consensus | ordered OCR hashes + consensus version |
| classification | evidence manifest + classifier/prompt digest |
| extraction | evidence manifest + schema + extractor/model/prompt digest |
| normalization | verbatim hash + jurisdiction rules hash |
| title graph | accepted claim manifest + rules hash |
| interest | graph revision + scope + as-of date + formula version |
| report | projection + template/profile/write-plan hashes |

A source, tool, model, prompt, mapping, policy, ruleset, reviewer decision, or
template change creates a new key. Cache reuse records a new derivation receipt;
it does not conceal the original run.

Database migrations are forward-only and tested against restored production
snapshots. Domain schemas, prompts, rules, templates, model catalog entries,
calibrators, and workbook profiles all use semantic version plus content hash.

## 12. Excel report engine

### 12.1 Template qualification

Each approved `.xlsx`/`.xlsm` is registered as immutable bytes and inventoried:

- ZIP members, content types, relationships, unknown extensions;
- sheet order, IDs, hidden and very-hidden states;
- cells, styles, number formats, formulas, arrays, spills, tables;
- merged cells, names, data validation, conditional formatting;
- print areas/titles, page setup, margins, breaks, headers/footers;
- drawings, images, charts, pivots, slicers, embeddings, custom XML;
- external links, connections, macros, ActiveX, digital signatures.

A template administrator approves a `WorkbookProfile` containing semantic
field mappings, exact writable cells/ranges, expected old values/types,
maximum rows, protected parts, formula policies, native Office build, print
expectations, and unsupported features.

Initial production permits writes only to pre-existing cells. Row insertion,
sheet creation, merge changes, table resizing, formula edits, or drawing
changes need a separately qualified template-specific transform.

### 12.2 Write plan

Every planned cell operation contains:

```text
sheet stable identity
cell reference
expected old-value digest
new typed value
preserved style index
source claim revision IDs
format rule
approval/rule reference
```

Writes to formula cells, merged-cell followers, spill/array ranges, protected
cells, or unapproved ranges are rejected.

### 12.3 Surgical OOXML patch

The package editor:

1. validates ZIP/OPC safety;
2. copies the authority bytes to staging and verifies the hash;
3. resolves a sheet through workbook relationships, never position alone;
4. edits only approved `<c>` elements;
5. uses explicit OOXML number/date/boolean types and inline strings;
6. preserves style IDs and untouched part bytes;
7. preserves unknown namespaces and relationship IDs;
8. writes a new archive atomically;
9. emits raw-part and canonical semantic diffs.

`openpyxl` may inspect simple workbook semantics and create control workbooks.
It is not allowed to save the client authority or candidate.

### 12.4 Blocking gates

- X0 authority hashes and approvals match.
- X1 ZIP/OPC safety passes.
- X2 every feature is classified as preserve/qualified-transform/unsupported.
- X3 every write is typed, evidence-backed, in range, and not stale.
- X4 only planned worksheet cells change.
- X5 protected parts and relationship graph remain intact.
- X6 native Excel opens, recalculates, saves, and renders without new errors.
- X7 Excel-induced changes match a qualified allowlist.
- X8 PDF page count, print areas, headers, footers, images, charts, clipping,
  and visual comparison pass.
- X9 title/evidence/domain gates still pass.
- X10 qualified reviewer approves exact final hash.
- X11 Drive re-download hash matches.

For `.xlsm`, `vbaProject.bin`, VBA signatures, ActiveX, controls, embeddings,
and relationships must remain byte-identical. A package digital signature that
cannot survive modification blocks export unless an approved re-sign workflow
exists.

The control workbook is separate from the client workbook and contains
provenance, claim IDs, calculations, defects, write plan, diffs, and approvals.

## 13. Google Drive design

Use a DataBossX-managed Shared Drive:

```text
DataBossX Records/
  00_System/
    Template Registry/
    Policy Registry/
    Recovery Catalog/
  Projects/
    <PROJECT-ID>/
      00_Project Control/
      10_Intake/
      20_Locked Source Manifests/
      30_Working Candidates/
      40_Examiner Review/
      50_Approved Releases/
      60_Delivery Receipts/
      90_Archive/
  Templates/
    Approved/
    Superseded/
    Qualification Receipts/
```

Naming is presentation, not identity:

```text
<PROJECT-ID>__<ARTIFACT-TYPE>__v0003__<YYYYMMDD>__<HASH8>.xlsx
```

Rules:

- Prefer interactive OAuth `drive.file` for selected and app-created files.
- Separate read connector and release connector identities.
- Folder and file IDs are encrypted in the database and never logged.
- Persist a Drive start-page token before enumeration.
- Notifications trigger change-feed polling; they are not the change record.
- Occurrence identity is `(connection_id, drive_file_id)`.
- Version identity is provider revision plus downloaded SHA-256.
- Advance the cursor in the same transaction that accepts the changes.
- Run a daily bounded reconciliation for missed notifications and permission
  drift.
- Google-native files are metadata-only unless an approved export MIME is
  defined; exports are derived artifacts.
- Never convert Office templates to Google Sheets.
- SHA-256 is exact dedupe authority; Drive MD5 is only an optimization hint.
- Near duplicates create a review proposal and are never auto-deleted.
- Upload idempotency is destination root + release ID + SHA-256.
- A release is successful only after re-download hash verification.
- Offline work uses a signed snapshot bundle and later imports append-only
  results; it does not use bidirectional folder mirroring.

Retention labels are `ACTIVE`, `LOCKED`, `RELEASED`, `SUPERSEDED`,
`LEGAL_HOLD`, and `ARCHIVE_ELIGIBLE`. No permanent automated deletion is
allowed during the initial six months.

Backups:

- continuous PostgreSQL WAL archive;
- nightly encrypted database backup and vault manifest;
- weekly encrypted off-site object backup;
- monthly Drive inventory export;
- monthly restore drill of database, source, template, candidate, release, and
  receipt.

## 14. AI, rules, OCR, and GIS boundaries

| Capability | Technology | May decide canonical state? |
| --- | --- | --- |
| hash, MIME, custody, dedupe | deterministic code | yes |
| rendering and preprocessing | deterministic image code | yes, as derivation |
| OCR/layout/handwriting | specialized OCR/ML | candidate text only |
| classification | rules + classifier + optional LLM | reviewed/thresholded class |
| dates/references/fractions/PLSS | deterministic parser first | yes when source-supported and unambiguous |
| complex clause extraction | schema model/LLM challenger | candidate only |
| party resolution | deterministic identifiers + scored proposals | human merge unless unique identifier |
| legal geometry | parser + authoritative GIS + deterministic math | qualified derivation, never LLM geometry |
| title graph effects | versioned deterministic rules from accepted claims | yes, with review gates |
| ownership/WI/NRI | exact deterministic ledger | yes |
| defect detection | deterministic jurisdiction rules | finding only |
| note prose | structured templates; optional LLM rewrite | human-reviewed draft |
| workbook writes/diffs | deterministic OOXML | yes within approved plan |
| release | policy engine + human approval | human only |

Models are selected by a versioned capability benchmark, privacy policy,
availability, latency, and cost. Provider names are catalog configuration, not
workflow code. A provider upgrade runs in shadow against the golden set and
requires explicit promotion.

Do not use embeddings until a versioned retrieval benchmark beats PostgreSQL
structured/full-text search on citation precision and recall. Never use a
chatbot answer as evidence.

## 15. Training memory

Every human correction creates an immutable label with before/after values,
source spans, reason code, reviewer qualification, document/quality class, and
affected model/rule version.

The feedback worker:

- excludes projects without explicit training consent;
- de-identifies only under an approved process;
- prevents project and duplicate-document leakage across train/test splits;
- maintains fixed private holdouts;
- recalibrates confidence separately from retraining;
- evaluates challenger OCR/extractors in shadow;
- proposes, but cannot deploy, a version change.

Training examples are never raw audit logs. Reviewer disagreement is retained
and excluded from a single-label training set until adjudicated.

Promotion state is:

```text
DRAFT -> TRAINED -> EVALUATED -> SHADOW_APPROVED -> CANARY_APPROVED
      -> PRODUCTION_APPROVED -> RETIRED
```

Only the model-governance service account can request a transition; only a
qualified human can approve one; only the deployment worker can enact the exact
approved model and deployment-manifest hashes. Consent withdrawal appends a
revocation, excludes examples from future dataset versions, and triggers
lineage review of derived models according to policy. Dataset manifests,
split hashes, code, base weights, environment, output weights, evaluations,
promotion, deployment, and retirement are all immutable and reproducible.

## 16. Failure detection, recovery, rollback, and audit

| Failure | Detection | Recovery / rollback | Audit and release effect |
| --- | --- | --- | --- |
| source changes after lock | provider revision/hash mismatch | cancel descendants; create new snapshot | source-drift event; approval invalid; blocked |
| missing Drive permission | coverage check/change-feed error | retain cursor; reauthorize; bounded rescan | degraded coverage, never “no changes”; blocked |
| corrupt/encrypted file | safe parser/inspection | quarantine copy; request replacement/password | terminal or human wait; blocked if in scope |
| archive bomb/path traversal | size/member/path limits | reject isolated input | security event; no extraction |
| malware or active payload | scanner and type inventory | isolate bytes; security review | blocked |
| render page mismatch | source page count vs manifest | retry pinned alternate renderer, then review | all attempts retained |
| worker crash/stale lease | heartbeat/expiry | reclaim same idempotent task | attempt event; no duplicate canonical writes |
| OCR timeout/OOM | worker limit and watchdog | retry lower shard size/clean process | route/attempt metrics |
| poor OCR | calibrated field metrics and validators | alternate variant/engine/remote/human | alternatives retained; material value blocked |
| remote provider 429/5xx | typed response/circuit breaker | exponential backoff with jitter; local fallback if valid | cost/route event |
| privacy route violation | policy preflight | terminal; no remote fallback | security event; task blocked |
| model schema invalid | strict contract | one bounded repair, challenger, or review | raw response archived privately |
| prompt injection in source | data/tool boundary and output schema | discard instruction-like output | adversarial finding; no capability escalation |
| missing evidence geometry | provenance validator | reject candidate and rerun region extraction | cannot become claim |
| material claim conflict | reconciliation | qualified human resolution | conflict remains open; blocked |
| false party merge | reviewer/correction or invariant | append split event; rebuild affected graph | old decision retained; approval invalid |
| duplicate double-count | instrument identity and ledger idempotency | reverse bad transaction; rebuild projection | compensating event, never deletion |
| graph cycle/impossible chain | graph invariants | isolate revision; examiner review | prior valid graph remains current |
| over-conveyance/math failure | exact deferred constraints | reject projection; correct source/basis | calculation trace; blocked |
| GIS mismatch/nonclosure | PostGIS and closure tests | review description/source; no auto-repair | defect result |
| DB deadlock/serialization | PostgreSQL error | bounded transaction retry | attempt metric; no partial commit |
| DB corruption | checksums/backup verification | stop writers; restore and replay outbox/events | incident; releases paused |
| vault hash mismatch | periodic read verification | quarantine and restore replica | critical incident; affected outputs blocked |
| budget exhausted | task budget | wait for explicit increase or alternate local route | approval event required |
| stale workbook write plan | expected-old-value digest | regenerate and reapprove | old plan retained; blocked |
| unsupported OOXML feature | capability inventory | qualify transform or revise template | template blocked |
| unauthorized OOXML change | package semantic diff | discard candidate; inspect patcher | integrity receipt fails |
| Excel crash/hang | watchdog | destroy task desktop; retry once from clean image | blocked after repeat |
| macro/signature change | binary hash/signature verification | discard candidate | security event; blocked |
| formula error | native recalc scan | correct data/template and create new candidate | prior candidate immutable |
| print/visual regression | PDF and image diff | inspect mapping/template; rerun new version | blocked |
| approval stale | hash/policy/version comparison | request fresh review | no release |
| Drive upload response lost | idempotency property/hash query | recover existing upload or retry create-only | no duplicate release |
| upload hash mismatch | re-download verification | isolate remote copy and incident review | delivery not complete |
| released report later defective | user report/monitoring | mark superseded; issue corrected release | never overwrite; client notification recorded |
| backup failure | backup-age alert and verify job | repair target; perform immediate backup | releases pause when recovery SLO breached |
| audit chain failure | daily hash verification | stop releases; restore/investigate | critical incident |

Rollback means selecting a prior immutable version or appending a compensating
event. It never means deleting evidence or rewriting audit history.

## 17. Testing and benchmarks

### 17.1 Golden corpus

Build a private, examiner-approved corpus stratified by:

- document family and jurisdiction;
- clean typed, fax, low DPI, skew, blur, bleed-through, faded, handwriting,
  cursive, stamps, columns, tables, indexes, exhibits;
- easy and adversarial names, dates, instrument references, fractions, legal
  descriptions, reservations, depth clauses, probate, and assignments;
- simple and branching title chains;
- `.xlsx` and `.xlsm` feature combinations.

Keep public synthetic fixtures, private de-identified regression fixtures, and
real restricted gold in separate stores. Gold labels include page polygons,
not only strings.

### 17.2 Required suites

- Unit: parsers, value states, rational math, rules, mappings, OPC parts.
- Property: arbitrary valid fractions and conveyance trees preserve
  conservation; workbook writes cannot escape approved cells.
- Integration: connector through release with local fake providers.
- Golden OCR: CER/WER and exact field by quality/document class.
- Extraction: precision, recall, exact match, provenance coverage, schema-valid
  rate, unsupported-claim rate.
- Entity: pairwise precision/recall plus catastrophic false-merge rate.
- Title: examiner-approved chain edge precision/recall and defect recall.
- GIS: PLSS AST, known polygons, overlap, acreage, and metes closure.
- Workbook mutation: alter one protected feature and prove the gate fails.
- Visual: PDF page, clipping, header/footer, image/chart regression.
- Adversarial: hostile PDFs/ZIP/XML, prompt injection, formula injection,
  oversized inputs, OCR confusion, tenant isolation.
- Reliability: crash at every vault/DB boundary, stale leases, duplicate events,
  provider timeouts, Drive token expiry.
- Performance: representative concurrent projects and page counts.
- Disaster: database/vault/Drive restore and released-report reproduction.

### 17.3 Release thresholds

Initial thresholds are deliberately strict and field-specific:

- 100% source and artifact hash verification.
- 100% material accepted claims have valid direct evidence.
- 0 unresolved material conflicts at release.
- 0 title/interest invariant failures.
- 0 automatic party false merges in the release corpus; non-unique merges
  require review.
- At least 99.5% exact match for recording references and dates on eligible
  clean typed pages, reported separately for degraded/handwritten pages.
- At least 99% exact match for material fractions after review routing; no
  incorrect fraction may be auto-accepted in the release gold set.
- 100% protected workbook parts preserved; 0 unauthorized semantic diffs.
- 0 new native Excel formula errors.
- 100% release upload/re-download hash equality.
- 100 consecutive crash/restart workflow tests yield equivalent manifests.
- Search citation precision of 100% for returned evidence links; benchmark
  recall is reported by query class.

Targets that are not met route more work to humans; they do not lower the
release gate.

General production qualification requires a locked out-of-project holdout with
at least 10,000 material fields, 2,000 instruments, 200 complete title chains,
and representation from every enabled jurisdiction/document/degradation
stratum. Each enabled stratum has at least 1,000 material fields unless its
entire material output remains human-reviewed. Report Wilson 95% confidence
bounds. A model/rule update may regress no material-field lower bound by more
than 0.2 percentage points and may introduce zero new release-blocking title or
workbook failures. Only the named model-governance and title leads may grant a
temporary waiver, which must narrow automation, expire, and be audit-recorded;
no waiver can bypass evidence, exact-math, workbook-integrity, or human-release
gates.

### 17.4 Performance objectives

On the qualified production hardware:

- inventory metadata: at least 100,000 occurrences/hour excluding downloads;
- rendering/OCR: median at least 2 pages/second per printed worker at 300 DPI,
  with quality reported alongside speed;
- API read p95 under 500 ms for paginated project/review queries;
- evidence tile p95 under 1 second on private LAN;
- task recovery within twice the lease duration;
- no lost or duplicate canonical effect under repeated delivery;
- release reproduction of a 10,000-page project without manual file hunting;
- recovery point objective 15 minutes for database, 24 hours for off-site
  object replication; recovery time objective 4 hours, proven by drill.

## 18. Observability and operating controls

Metrics include queue depth/age, task attempts/latency, source coverage, cursor
lag, page quality, OCR CER/WER/exact-field, calibration error, schema-valid
rate, support rate, conflict/correction/escalation rates, false-merge findings,
chain gaps, invariant failures, workbook gate failures, model/provider cost,
cache hit rate, backup age, and release blockers.

Alerts fire for source drift, vault mismatch, audit-chain failure, unauthorized
workbook difference, stale Drive cursor, backup age, Office-build drift,
privacy-route rejection, repeated dead letters, and release without a current
approval.

Logs use IDs, versions, timings, and error codes. They exclude client names,
party names, source text, legal descriptions, local paths, Drive IDs,
credentials, and workbook cell values.

## 19. Six-month build sequence

### Month 1 — evidence kernel and one vertical slice

- contain known credential exposure and freeze legacy releases;
- select three representative real projects and three templates;
- implement PostgreSQL migrations, object vault, manifests, task leases,
  outbox, local/Drive read-only inventory, and source-lock gate;
- qualify workbook features and build the surgical three-cell proof;
- port exact fraction tests;
- establish private golden corpus and labeling protocol.

Exit: one de-identified candidate moves from locked source to evidence-linked
cells with no protected workbook change.

### Month 2 — documents, OCR, and claims

- implement safe document inspection, page rendering, quality profiles,
  preprocessing, local OCR/layout/handwriting routes, consensus, and
  calibration data capture;
- implement classification, extraction candidates, evidence spans, claims,
  conflicts, and review UI;
- benchmark routes by page and field class.

Exit: representative documents have page-complete OCR and field-level evidence;
material uncertainty reliably enters review.

### Month 3 — title domain

- implement party/alias/successor review, PLSS/metes/depth models, PostGIS
  validation, instrument effects, temporal title graph, probate/corporate
  events, exact ledger, WI/NRI, defects, and calculation traces;
- port useful Horizon regression cases and retire it as a second authority.

Exit: one real project reaches an examiner-approved ownership projection with
all invariants passing.

### Month 4 — report and Drive production

- productionize template registry, write plans, OOXML patch/diff, Windows Excel
  worker, PDF visual QA, control workbook, Drive change feed, verified release
  upload, backup, and restore;
- convert Roger Mills and other mappings into profiles.

Exit: one real report is reproduced, natively verified, hash-approved, and
delivered without template damage.

### Month 5 — consolidation and hardening

- migrate DOTO connector/cost controls and Grocery stages;
- connect the sole React UI to all production APIs;
- retire mock backend, CRA frontend, product-specific databases/queues, and
  duplicate report authorities;
- complete RLS/RBAC, dual control, adversarial tests, incident runbooks,
  dashboards, restore drills, and publication controls.

Exit: one domain model, API, task graph, audit stream, UI, and release path.

### Month 6 — controlled rollout

- run two real canary projects with dual review;
- execute load, failover, restore, security, model-regression, workbook
  mutation, and complete reproduction tests;
- calibrate routing from corrections without weakening gates;
- qualify the next template/document/jurisdiction set only after benchmark
  approval.

Exit: two real releases satisfy Section 2 and can be reproduced by an operator
who did not create them.

## 20. First week

### Day 1 — establish authority

- revoke and rotate every credential identified in `SECURITY.md`;
- freeze legacy automated exports;
- quarantine the root legacy deployment entrypoints and add the production
  image allowlist/mock-OCR CI check;
- name the product owner, title examiner, template administrator, release
  approver, and security owner;
- choose one representative project and its exact approved workbook;
- fetch PR #26, build a feature/test parity matrix, and record port/reject
  decisions before rewriting its evidence or workbook machinery;
- hash and copy source/template bytes into controlled private storage.

Deliverable: signed project charter, role matrix, source root list, template
hash, and incident-closure record.

### Day 2 — inventory reality

- run read-only inventory over the project, Drive folder, prior reports, SQLite
  databases, and relevant code;
- group exact and near duplicates without deleting anything;
- identify missing source classes and conflicting versions;
- inspect every template package feature.

Deliverable: reviewed source manifest and workbook feature inventory. Gate: no
unclassified source or workbook part.

### Day 3 — lock contracts

- define the first document schemas and material fields;
- finalize task, artifact, evidence, claim, review, and release contracts;
- map approved report fields to existing workbook cells;
- define jurisdiction rules and exact interest bases for the selected project;
- create the first private golden labels.

Deliverable: versioned schemas, workbook profile, write-plan example, and gold
manifest.

### Day 4 — build the irreversible foundation

- create PostgreSQL, migrations, RLS, object vault, custody receipts, task
  lease/outbox, and audit chain;
- ingest and re-read-verify a small real source subset;
- prove workers cannot write the database or mutate originals.

Deliverable: source-to-vault trace with crash/retry tests.

### Day 5 — prove evidence

- render representative clean, poor, handwritten, index, and table pages;
- run bounded preprocessing/OCR routes;
- store geometry and compare against gold;
- extract three material fields with clickable evidence;
- route an intentional disagreement to review.

Deliverable: benchmark report and working evidence-review screen.

### Day 6 — prove the workbook

- compile a three-cell evidence-backed write plan;
- patch without saving through `openpyxl`;
- prove all non-target parts remain protected;
- run deliberate mutation tests;
- open/recalculate/render in the pinned Excel VM.

Deliverable: candidate, PDF, package diff, and integrity receipt.

### Day 7 — attack and decide

- test source drift, stale lease, bad OCR, unsupported claim, hostile document,
  stale write plan, Excel crash, unauthorized package edit, and failed upload;
- have the examiner inspect source, claims, calculation trace, and candidate;
- record every failure as backlog with owner, acceptance test, and severity;
- approve the vertical-slice architecture only if evidence supports it.

Week-one exit: one small real subset reaches X0-X9, with no production release
claim. The next week expands the same path; it does not start another pipeline.

## 21. Final identification

AI Name: GPT-5.6 Sol  
Company: OpenAI  
Model: GPT-5.6 Sol  
Web Search Used: No  
Confidence: High on the architecture and controls; medium on corpus-specific OCR and title-rule thresholds until benchmarked against the private real documents.
