# Research Evidence Audit — DBX-OK-BECKHAM-32-11N-25W

Audit run: 2026-07-13T22:14:33Z (UTC)
Executor model ID: `claude-fable-5` (Claude Code remote session; not a HuggingChat session)
Repository state at audit start: commit `4587803` on branch `claude/research-evidence-audit-57ow2n`
Scope: strict self-audit of previously claimed public-record research (wells, API numbers,
operators, production totals, OCC matters, Diversified succession) for Section 32,
Township 11N, Range 25W, Beckham County, Oklahoma.

## Audit method

1. Searched the entire repository for any persisted record of the prior claims:
   aggregator names (ShaleXP, DrillingEdge, MineralAnswers), API numbers (`35-011…`),
   well names containing `32-11-25`, retrieval URLs, saved pages, screenshots,
   or an evidence ledger. **Result: none exist.**
2. Reviewed the controlled project records that do exist:
   `project_manifest.json`, `authoritative_source_set.md`, `verified_gap_list.md`.
3. No new web research was performed in this audit run (per instruction).

## Controlling finding

The prior response's public-record findings are supported by **no retrievable evidence
trail** — no source URLs, no retrieval timestamps, no quoted passages, no saved files,
no screenshots, in either the session execution record or this repository. Under the
audit rule "retract any finding for which you cannot provide the exact supporting
source," **every previously claimed public-record finding is RETRACTED.** None may be
carried into the title report, the workbook, or any client deliverable.

## Claim-by-claim evidence ledger

Legend for fields 3–8: where no source record exists, the field is marked
`NONE ON RECORD`. A claim with `NONE ON RECORD` in field 3 cannot hold any status
other than RETRACTED or UNRESOLVED.

### Class 1 — Prior public-record claims (all retracted)

| # | Field | C-01 Well identities | C-02 API numbers | C-03 Operators | C-04 Production totals | C-05 Diversified succession | C-06 OCC matters | C-07 Spacing/pooling/640 ac | C-08 HBP effect |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Claim ID | C-01 | C-02 | C-03 | C-04 | C-05 | C-06 | C-07 | C-08 |
| 2 | Exact claim | Named wells with "32-11-25" in the well name asserted to sit in/serve Sec 32-11N-25W | Specific 10-digit API numbers assigned to those wells | Current/historic operator identities for those wells | Cumulative or property-level oil/gas production figures attributed to Section 32 wells | That Diversified succeeded to specific Section 32 leasehold/WI via corporate acquisition | Existence/content of OCC orders (pooling, spacing, increased density) covering Sec 32 | 640-acre unit and spacing/pooling terms inferred for Sec 32 | Leases held by production based on well existence |
| 3 | Exact source URL | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD |
| 4 | Source publisher | Recalled as aggregators (ShaleXP / DrillingEdge / MineralAnswers class); no citation preserved | Same | Same | Same | Recalled as press/announcement coverage; no citation preserved | NONE ON RECORD | Inference only — no source | Inference only — no source |
| 5 | Retrieval date/time | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD | N/A | N/A |
| 6 | Supporting passage/table/row | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD | NONE ON RECORD | N/A | N/A |
| 7 | Source class | Aggregator (non-controlling) | Aggregator | Aggregator | Aggregator | Secondary (announcement) | Unknown | None | None |
| 8 | Opened vs. search-result | Cannot be attested — no access log preserved | Same | Same | Same | Same | Same | N/A | N/A |
| 9 | Confidence | None assignable | None | None | None | None | None | None | None |
| 10 | Conflicting evidence | Unknown — cannot assess without sources | Unknown | Unknown | Unknown | Unknown | Unknown | Unknown | Unknown |
| 11 | Required official verification | OCC well records + OTC production (Section D) | OCC well browse/completion reports | OCC Form 1073 / completion reports | OTC gross-production by PUN, isolated to specific API numbers | Recorded assignments in Beckham County + SEC/Companies House filings (Section E) | OCC case processing / OAP docket search | OCC spacing & pooling orders for 32-11N-25W | Operative leases + production records tied to the leased premises |
| 12 | **Status** | **RETRACTED** | **RETRACTED** | **RETRACTED** | **RETRACTED** | **RETRACTED** | **RETRACTED** | **RETRACTED** | **RETRACTED** |

### Class 2 — Facts standing on this repository's controlled project records

These are internal project-control facts, not public-record verification. They are
DERIVED from client-provided project files and remain subject to the project's own
gap list.

| # | Field | R-01 Project legal locus | R-02 Assignment scope | R-03 Source corpus counts | R-04 Workbook candidate |
|---|---|---|---|---|---|
| 1 | Claim ID | R-01 | R-02 | R-03 | R-04 |
| 2 | Exact claim | Project covers Section 32, T11N, R25W, Beckham County, Oklahoma | Assignment is a cursory title review of Diversified's apparent record interest | Dropbox root `/11N 25W 32` holds 4,898 files (4,893 title images; 62 PDF/index sheets; 60 unique; 21 open items reported) | Release candidate workbook `32-11N-25W_Beckham_Co_Diversified_Cursory_Title_Report_FINAL_VERIFIED_2026-07-11.xlsx`, reported SHA-256 `1d8b4a67…3265b02` |
| 3 | Exact source URL | repo file `projects/OK-BECKHAM-32-11N-25W/project_manifest.json` (fields `county`,`section`,`township`,`range`) | same file, field `assignment` | same file, `known_source_counts` | same file, `candidate_deliverables[0]` |
| 4 | Source publisher | DataBossX governance repo (client project record) | Same | Same | Same |
| 5 | Retrieval date/time | 2026-07-13T22:14Z (read in this audit run) | Same | Same | Same |
| 6 | Supporting passage | JSON lines 7–10 | JSON line 11 | JSON line 19 | JSON line 20 |
| 7 | Source class | Primary for project scope; NOT public-record proof of title | Same | Project-control figure only (gap list item 3: hash manifest unconfirmed) | Reported hash; not independently re-hashed in this run |
| 8 | Opened? | Yes — file read in this run | Yes | Yes | Yes |
| 9 | Confidence | High as to what the client instructed; none as to underlying title facts | High | Medium (unreconciled) | Medium (hash not re-verified here) |
| 10 | Conflicting evidence | None found | None found | Open-item count conflicts (21 vs. 8 per gap list item 7) | Competing BEST/PERFECT/MERGED candidates (gap list item 4) |
| 11 | Required official verification | County/OCC records per Sections D–E | N/A (scope statement) | Full recursive hash manifest | Independent re-hash + G7 human release |
| 12 | **Status** | **DERIVED** | **DERIVED** | **UNRESOLVED** | **UNRESOLVED** |

## Retracted or downgraded claims — consolidated

RETRACTED in full (no supporting source can be produced): C-01 through C-08 above,
including every specific well name, every API number, every operator attribution,
every production figure, every OCC-matter assertion, the Diversified
acquisition-to-Section-32 succession conclusion, the 640-acre assumption, all
spacing/pooling inferences, and all HBP conclusions.

Standing corrections adopted as permanent project rules:
- Aggregators (ShaleXP, DrillingEdge, MineralAnswers, blogs) are never controlling
  title or regulatory evidence; at most they are lead-generation pointers.
- A "32-11-25"-style well name proves nothing about legal location, unit, acreage,
  ownership, lateral path, or HBP effect.
- Property-level production totals may not be attributed to Section 32 wells unless
  the official source isolates those exact API numbers/PUNs.
- Corporate acquisition announcements do not prove transfer of any specific lease,
  WI, depth, formation, override, or wellbore interest.
- No acreage, spacing, or pooling term is assumed; each must come from the operative
  OCC order or recorded instrument.
- VERIFIED status requires that the source was actually opened and the supporting
  content identified by page/table/row/passage.

## Official OCC records still required (Section D)

For Sec. 32-T11N-R25W, Beckham County (Meridian: Indian):

1. OCC Oil & Gas Well Records (Well Browse / RBDMS): all wellbores with surface or
   bottomhole location in Sec 32-11N-25W — API numbers, well names, status, operator
   of record. Capture the record page itself, not a search-results list.
2. OCC Form 1000 (Intent to Drill) and Form 1002A (Completion Report) for each such
   API — legal location, lateral path, completion formation, first production.
3. OCC Form 1073 (Change of Operator) chain for each API — operator succession,
   including any transfer into a Diversified entity.
4. OCC Case Processing / OAP docket search for 32-11N-25W: spacing orders, pooling
   orders, increased-density, location-exception, and multiunit/allocation orders —
   order numbers, cause numbers, and the order text (unit size and formations come
   only from the order itself).
5. OCC Imaging (ECF) copies of each order and form identified above.
6. Oklahoma Tax Commission gross production records by PUN for each API — the only
   official production figures; must be tied to specific wells, never property-level
   aggregates.

## Official county or corporate records still required (Section E)

1. Beckham County Clerk tract index for Sec 32-11N-25W: all recorded oil & gas
   leases, assignments, mineral/royalty deeds, probates, AOGLs, and releases
   (book/page or instrument number for each; the 22-copy / $8.80 Tier 1 acquisition
   queue in the gap list remains open and must run from an authorized local machine).
2. The operative recorded assignment(s) into the specific Diversified entity
   (e.g., Diversified Production LLC or affiliate) covering Section 32 leasehold —
   the only proof of succession; exhibits/schedules must list the lease or wellbore.
3. Oklahoma Secretary of State registrations for the exact Diversified entity names
   appearing in county records and OCC Form 1073s (entity continuity, mergers,
   name changes).
4. SEC EDGAR / UK Companies House filings for Diversified Energy Company PLC only as
   corroboration of which subsidiary acquired which seller's assets — never as proof
   that a specific Section 32 interest transferred.
5. Beckham County Assessor/Treasurer tax roll cross-check against the Dropbox
   `Tax Roll` branch.

## Clean handoff for the file-access agent (Section F)

Authoritative inputs (read-only; freeze rule applies):
- Dropbox root `/11N 25W 32` (branches: Index, Section Notes, Plat Map, Tax Roll,
  Images) — 4,898 objects reported, unreconciled.
- Google Drive project folder `1WiB-VquRfVjbDdyxfvL66hDxYfuC2AJO`; registry snapshot
  `_DATABOSSX_REGISTRY` (`1R1riL4SVj2UJOELl842inGrPljeByAyU`).

Tasks, in order:
1. Build the complete recursive asset manifest of the Dropbox root: path, size,
   SHA-256, content type. Reconcile against the 4,898/4,893/62/60 control counts and
   report deltas (closes gap list item 3).
2. Extract the 60 unique index sheets and the Section Notes; emit one evidence-ledger
   row per index line using the 12-field schema in this audit (claim, source file
   path + page/row, opened=yes, class=county-record copy).
3. Reconcile the 21 vs. 8 open-item conflict (gap list item 7) into one normalized
   open-item register.
4. Run the Tier 1 county-copy acquisition queue (22 copies, est. $8.80) from the
   authorized local machine; hash and ingest each copy into the manifest.
5. Independently re-hash the release-candidate workbook and compare to
   `1d8b4a67c540ba41a6340530d9b17bae4e4c4c840de0e552daa2268ef3265b02`; mark all
   competing BEST/PERFECT/MERGED candidates superseded (gap list item 4).
6. Populate the evidence-to-report crosswalk (gap list item 5). No cell in the
   workbook may cite C-01…C-08; only ledger rows with status VERIFIED or DERIVED
   may feed the report.

Hard rules carried over: no renames/moves/deletes in source roots; extraction writes
to staging only; every derivative carries source IDs and hashes; technical
verification is not release — G7 human landman gate required.

## Corrected run receipt (Section G)

- Run start (UTC): 2026-07-13T22:14:33Z
- Executor: model ID `claude-fable-5`, Claude Code remote session, repository
  `DataBossX/DataBoss`, branch `claude/research-evidence-audit-57ow2n`, base commit
  `4587803`.
- Actions performed: repository-wide search for any persisted source citations of the
  prior claims (none found); read of the three controlled project files; production
  of this ledger. No web searches, no OCC/county retrievals, no file downloads, no
  external publications.
- Net evidentiary position: zero public-record claims survive at VERIFIED. Two claims
  stand at DERIVED (project locus and assignment scope, from the client's own
  manifest), two at UNRESOLVED (source counts; workbook hash), eight claim classes
  RETRACTED.
- This document is the sole output of the audit run and is committed to the project
  directory as the controlling evidence baseline for all future research runs.
