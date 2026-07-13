# DataBossX Section 32 File Watcher

## Purpose

This watcher monitors **local synced copies** of the Dropbox and Google Drive Section 32 source folders. It does not edit either source. New or changed files are:

1. checked for file stability;
2. SHA-256 hashed;
3. copied into content-addressed isolated staging;
4. re-hashed after copying;
5. recorded in SQLite state;
6. given an immutable JSON receipt; and
7. converted into an `INGEST_AND_EXTRACT` queue job.

The canonical title workbook is never written by this watcher. Spreadsheet promotion must be performed by a separate validated writer after provenance, schema, duplicate, and title-QC gates pass.

## Source facts currently controlling the setup

- Dropbox source folder: `11N 25W 32`
- Expected Dropbox children: `Images`, `Index`, `Section Notes`, `Plat Map`, and `Tax Roll`
- Expected title-image count: 4,893
- Current selected accessible workbook base: the 79/100 candidate
- Current release policy: `HOLD_NO_RELEASE`

Counts are validation targets, not permission to fabricate missing files or instrument rows.

## Install on Rodney's Windows machine

1. Clone or update `DataBossX/DataBoss` on the isolated watcher branch.
2. Copy `config.example.json` to `config.local.json`.
3. Set the two environment variables to the actual local sync folders:

```bat
setx DBX_DROPBOX_SECTION32 "D:\path\to\Dropbox\11N 25W 32"
setx DBX_GDRIVE_SECTION32 "G:\My Drive\32-11N-25W Diversified Cursory - Beckham County - 2026-07"
```

4. Open a new Command Prompt and run:

```bat
start_section32_watcher.bat
```

For one validation scan only:

```bat
py -3 watcher.py --config config.local.json --once
```

## Output tree

```text
D:\DataBoss\Section32_Watcher\
  state\watcher.sqlite3
  staging\<source>\<hash-prefix>\<sha256>\<filename>
  receipts\<event-id>.json
  queue\INBOX\DBX-S32-<event-id>.json
  status\latest_scan.json
  logs\watcher_<date>.log
```

## Required downstream worker contract

A worker claiming an inbox job must atomically move it through:

```text
INBOX -> CLAIMED -> RUNNING -> COMPLETED
                         \-> REJECTED
                         \-> QUARANTINE
```

Every claimed job must produce:

- `ACK.json`
- heartbeat updated during work
- `document_metadata.json`
- `page_manifest.json`
- `extractions.jsonl`
- `instrument_rows.csv`
- `validation_receipt.json`
- final completion or quarantine receipt

No worker may write directly to the source folders or canonical workbook.

## Parsing and workbook rules

- One instrument may span multiple images. Continue the same instrument until the document boundary is proven.
- Every row must retain source file, image/page number, document identifier when available, and extraction text span.
- Preserve grantor/grantee spelling as recorded and add normalized names separately.
- Record book/page, instrument number, recording date, execution date, legal description, interest type, depth/wellbore limitations, reservations, exceptions, and exhibits when actually present.
- Do not convert index ticks into ownership.
- Do not force totals or create negative owners.
- Keep unknown, unreadable, partial, duplicate, and conflicting items open and visible.
- Never calculate Diversified NMA, WI, NRI, RI, MRI, or ORRI without a complete evidence trail supporting the specific calculation.

## Recommended Windows Task Scheduler settings

- Trigger: At startup, delayed 2 minutes
- Run whether user is logged on or not
- Restart every 5 minutes after failure, up to 3 times
- Stop if running longer than 7 days
- Start in: the watcher folder
- Program: `start_section32_watcher.bat`

## Security

Do not place Dropbox, Google, GitHub, county-site, or email credentials in this repository or JSON config. The watcher uses already-synced local folders. Keep the output root on `D:` and deny public/anonymous write access.
