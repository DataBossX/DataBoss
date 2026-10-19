"""Offline, single-writer SQLite accounting for immutable sources and index cells.

Imports measure/hash source files and record field states. It does not infer
document boundaries, recover unknowns, certify title, or contact an AI service.
All reports are scoped to the current import; history remains in the database.
"""
from __future__ import annotations
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from . import index_qa, inventory, vision_queue, wb

SCHEMA_VERSION = "2"
SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources (
 sha256 TEXT PRIMARY KEY, size_bytes INTEGER NOT NULL, ext TEXT NOT NULL,
 page_count INTEGER, measurement_error TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS source_instances (
 sha256 TEXT NOT NULL REFERENCES sources(sha256), relative_path TEXT NOT NULL,
 PRIMARY KEY(sha256, relative_path));
CREATE TABLE IF NOT EXISTS pages (
 source_sha256 TEXT NOT NULL REFERENCES sources(sha256),
 page INTEGER NOT NULL CHECK(page > 0), page_id TEXT UNIQUE NOT NULL,
 status TEXT NOT NULL DEFAULT 'UNREVIEWED', review_method TEXT NOT NULL DEFAULT '',
 reviewer TEXT NOT NULL DEFAULT '', reviewed_at TEXT NOT NULL DEFAULT '',
 evidence_ref TEXT NOT NULL DEFAULT '', disposition TEXT NOT NULL DEFAULT '',
 review_origin TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(source_sha256, page));
CREATE TABLE IF NOT EXISTS workbooks (
 sha256 TEXT PRIMARY KEY, sheet TEXT NOT NULL, kind TEXT NOT NULL,
 data_row_count INTEGER NOT NULL, schema_match INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS cells (
 workbook_sha256 TEXT NOT NULL REFERENCES workbooks(sha256),
 sheet TEXT NOT NULL, row_number INTEGER NOT NULL, column_number INTEGER NOT NULL,
 header TEXT NOT NULL, raw_value TEXT NOT NULL, classification TEXT NOT NULL,
 PRIMARY KEY(workbook_sha256, sheet, row_number, column_number));
CREATE TABLE IF NOT EXISTS runs (
 run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, inputs_json TEXT NOT NULL,
 issues_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS run_sources (
 run_id TEXT NOT NULL REFERENCES runs(run_id),
 sha256 TEXT NOT NULL REFERENCES sources(sha256), relative_path TEXT NOT NULL,
 PRIMARY KEY(run_id, sha256, relative_path));
CREATE TABLE IF NOT EXISTS run_workbooks (
 run_id TEXT NOT NULL REFERENCES runs(run_id),
 sha256 TEXT NOT NULL REFERENCES workbooks(sha256), path TEXT NOT NULL,
 PRIMARY KEY(run_id, sha256, path));
"""


def classify_cell(kind, header, value):
    """Classify literal cell state; populated data remains source-unverified."""
    text = str(value or "").strip()
    if not text:
        expected = header == "Comments" or (kind == "federal" and header == "File No")
        return "EXPECTED_BLANK" if expected else "UNRESOLVED_BLANK"
    if text.upper() == "UNKNOWN":
        return "UNKNOWN_EXACT"
    if "UNKNOWN" in text.upper():
        return "UNKNOWN_QUALIFIED"
    return "POPULATED_UNVERIFIED"


@contextmanager
def writer_lease(db_path):
    """Do not steal an existing lock, even if it appears stale."""
    lock = Path(str(db_path) + ".writer.lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, json.dumps({"pid": os.getpid(),
                 "created_at": datetime.now(timezone.utc).isoformat()}).encode())
        os.close(descriptor)
        descriptor = None
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        lock.unlink()


def _checked_sources(inventory_csv, source_root):
    """Validate relative paths, bytes, hashes, and measured physical page counts."""
    root = Path(source_root).resolve(strict=True)
    result = []
    measured = {}
    with open(inventory_csv, newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            path = (root / row["path"]).resolve(strict=True)
            if not path.is_relative_to(root):
                raise ValueError("source path escapes source root")
            sha = inventory.sha256_file(path)
            if sha != row.get("sha256", "").lower():
                raise ValueError("source content differs from inventory: " + row["path"])
            size = path.stat().st_size
            if size != int(row["bytes"]):
                raise ValueError("source size differs from inventory: " + row["path"])
            ext = row.get("ext", "").lower()
            pages = None
            error = row.get("error", "")
            if ext == ".pdf":
                if sha not in measured:
                    try:
                        with inventory._pdf.open(path) as doc:
                            measured[sha] = (doc.page_count, "")
                    except Exception as exc:
                        measured[sha] = (None, type(exc).__name__ + ": " + str(exc))
                pages, actual_error = measured[sha]
                if pages is not None and (str(pages) != row.get("pages") or error):
                    raise ValueError("PDF measurement differs from inventory: " + row["path"])
                if pages is None and row.get("pages"):
                    raise ValueError("unreadable PDF has a claimed page count: " + row["path"])
                error = actual_error or error
            result.append(dict(sha256=sha, size_bytes=size, ext=ext,
                               page_count=pages, measurement_error=error,
                               relative_path=row["path"]))
    return result


def _workbook_records(paths):
    records = []
    for path in paths:
        path = Path(path).resolve(strict=True)
        sha = inventory.sha256_file(path)
        sheet, grid = wb.read_index_sheet(path)
        headers = [index_qa._cell(grid, 8, col) for col in range(10)]
        kind, schema_match = index_qa.detect_kind(headers)
        # Classifying by a guessed schema can conceal fields, so fail closed.
        if not schema_match:
            raise ValueError("unrecognized index schema: " + str(path))
        schema = wb.COUNTY_HEADERS if kind == "county" else wb.FEDERAL_HEADERS
        cells = []
        rows = 0
        for row in range(9, len(grid)):
            if not any(index_qa._cell(grid, row, col) for col in range(12)):
                continue
            rows += 1
            for col, header in enumerate(schema):
                value = index_qa._cell(grid, row, col)
                cells.append((sha, sheet, row + 1, col + 1, header, value,
                              classify_cell(kind, header, value)))
        if inventory.sha256_file(path) != sha:
            raise ValueError("workbook changed while reading: " + str(path))
        records.append({"path": str(path), "sha": sha, "sheet": sheet,
                        "kind": kind, "rows": rows, "cells": cells})
    return records


def _report(conn, run_id, issues):
    def count(sql):
        return conn.execute(sql, (run_id,)).fetchone()[0]
    source_filter = "SELECT DISTINCT sha256 FROM run_sources WHERE run_id=?"
    book_filter = "SELECT DISTINCT sha256 FROM run_workbooks WHERE run_id=?"
    counts = dict(conn.execute(
        "SELECT classification,COUNT(*) FROM cells WHERE workbook_sha256 IN (" +
        book_filter + ") GROUP BY classification", (run_id,)))
    visual = count("SELECT COUNT(*) FROM pages WHERE source_sha256 IN (" +
                   source_filter + ") AND status='VISUALLY_REVIEWED' "
                   "AND review_method IN ('HUMAN_VISION','MODEL_VISION','INHERITED_VISION') "
                   "AND reviewer<>'' AND reviewed_at<>'' AND evidence_ref<>''")
    physical = count("SELECT COUNT(*) FROM pages WHERE source_sha256 IN (" + source_filter + ")")
    return {
        "schema_version": SCHEMA_VERSION, "run_id": run_id,
        "source_instances": count("SELECT COUNT(*) FROM run_sources WHERE run_id=?"),
        "source_bodies": count("SELECT COUNT(DISTINCT sha256) FROM run_sources WHERE run_id=?"),
        "physical_pages": physical, "visually_reviewed_pages": visual,
        "page_count_complete_for_inventory": not any(r["code"] == "UNMEASURED_PDF" for r in issues),
        "pending_visual_pages": physical - visual,
        "visual_count_basis": "imported or retained reviewer receipts; no pixels reviewed by this tool",
        "workbook_file_instances": count("SELECT COUNT(*) FROM run_workbooks WHERE run_id=?"),
        "workbook_bodies": count("SELECT COUNT(DISTINCT sha256) FROM run_workbooks WHERE run_id=?"),
        "workbook_data_rows": count("SELECT COALESCE(SUM(data_row_count),0) FROM workbooks "
                                   "WHERE sha256 IN (" + book_filter + ")"),
        "source_document_count": None,
        "document_count_status": "UNDETERMINED_REQUIRES_ACCEPTED_BOUNDARY_LEDGER",
        "cell_counts": counts,
        "unresolved_cells": sum(counts.get(key, 0) for key in
                               ("UNRESOLVED_BLANK","UNKNOWN_EXACT","UNKNOWN_QUALIFIED")),
        "issues": issues,
    }


def import_accounting(db_path, inventory_csv, boundaries_csv, source_root,
                      workbook_paths=(), expected_db_sha=None, review_csv=None):
    """Atomically import into an owned database under a content-hash lease.

    Creating a new database requires expected_db_sha=None. Updating an existing
    database requires its observed SHA-256. Readers can keep the old snapshot
    open; cooperating writers must use this same lock protocol.
    """
    db_path = Path(db_path).absolute()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.is_symlink():
        raise ValueError("database path must not be a symlink")
    with writer_lease(db_path):
        existed = db_path.exists()
        for suffix in ("-wal", "-journal"):
            if Path(str(db_path) + suffix).exists():
                raise ValueError("active SQLite sidecar; close the writer before importing")
        actual_sha = inventory.sha256_file(db_path) if existed else None
        if actual_sha != expected_db_sha:
            raise ValueError("database hash lease mismatch; inspect the current database")
        input_paths = [Path(inventory_csv), Path(boundaries_csv)]
        if review_csv:
            input_paths.append(Path(review_csv))
        input_hashes = {str(p.resolve()): inventory.sha256_file(p) for p in input_paths}
        sources = _checked_sources(inventory_csv, source_root)
        for source in sources:
            input_hashes[str((Path(source_root) / source["relative_path"]).resolve())] = source["sha256"]
        issues = []
        queue = vision_queue.build_queue(inventory_csv, boundaries_csv, review_csv, issues)
        books = _workbook_records(workbook_paths)
        for book in books:
            input_hashes[book["path"]] = book["sha"]
        if any(inventory.sha256_file(p) != sha for p, sha in input_hashes.items()):
            raise ValueError("an input changed during import preparation")
        descriptor, temporary = tempfile.mkstemp(prefix=db_path.name+".stage.", dir=db_path.parent)
        os.close(descriptor)
        stage = Path(temporary)
        conn = None
        try:
            if existed:
                shutil.copyfile(db_path, stage)
            conn = sqlite3.connect(stage, timeout=0, isolation_level=None)
            conn.execute("PRAGMA foreign_keys=ON")
            if existed:
                version = conn.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
                if not version or version[0] != SCHEMA_VERSION:
                    raise ValueError("unsupported or unowned database schema")
            conn.executescript(SCHEMA)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT OR IGNORE INTO metadata VALUES ('schema_version',?)", (SCHEMA_VERSION,))
            run_id = uuid4().hex
            conn.execute("INSERT INTO runs VALUES (?,?,?,?)",
                         (run_id, datetime.now(timezone.utc).isoformat(),
                          json.dumps(input_hashes, sort_keys=True), json.dumps(issues)))
            for source in sources:
                prior = conn.execute("SELECT size_bytes,ext,page_count FROM sources WHERE sha256=?",
                                     (source["sha256"],)).fetchone()
                signature = (source["size_bytes"], source["ext"], source["page_count"])
                if prior and prior != signature:
                    raise ValueError("conflicting source measurement for an existing hash")
                conn.execute("INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?)",
                             (source["sha256"], *signature, source["measurement_error"]))
                conn.execute("INSERT OR IGNORE INTO source_instances VALUES (?,?)",
                             (source["sha256"], source["relative_path"]))
                conn.execute("INSERT OR IGNORE INTO run_sources VALUES (?,?,?)",
                             (run_id, source["sha256"], source["relative_path"]))
            for row in queue:
                conn.execute("INSERT OR IGNORE INTO pages(source_sha256,page,page_id) VALUES (?,?,?)",
                             (row["source_sha256"], row["page"], row["page_id"]))
                if vision_queue.visual_receipt_valid(row):
                    old = conn.execute(
                        "SELECT status,review_method,reviewer,reviewed_at,evidence_ref,disposition "
                        "FROM pages WHERE source_sha256=? AND page=?",
                        (row["source_sha256"], row["page"])).fetchone()
                    keys = ["status", "review_method", "reviewer", "reviewed_at",
                            "evidence_ref", "disposition"]
                    previous = dict(zip(keys, old))
                    if vision_queue.visual_receipt_valid(previous) and any(
                            previous[key] != row.get(key, "") for key in keys):
                        raise ValueError("conflicting receipt requires adjudication: " + row["page_id"])
                    conn.execute("UPDATE pages SET status=?, review_method=?, reviewer=?, reviewed_at=?, "
                                 "evidence_ref=?, disposition=?, review_origin=? WHERE source_sha256=? AND page=?",
                                 (row["status"], row["review_method"], row["reviewer"], row["reviewed_at"],
                                  row["evidence_ref"], row["disposition"], row["review_origin"],
                                  row["source_sha256"], row["page"]))
            for book in books:
                conn.execute("INSERT OR IGNORE INTO workbooks VALUES (?,?,?,?,?)",
                             (book["sha"], book["sheet"], book["kind"], book["rows"], 1))
                conn.executemany("INSERT OR IGNORE INTO cells VALUES (?,?,?,?,?,?,?)", book["cells"])
                conn.execute("INSERT OR IGNORE INTO run_workbooks VALUES (?,?,?)",
                             (run_id, book["sha"], book["path"]))
            report = _report(conn, run_id, issues)
            conn.execute("COMMIT")
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("SQLite integrity check failed")
            conn.close()
            conn = None
            if (inventory.sha256_file(db_path) if db_path.exists() else None) != expected_db_sha:
                raise ValueError("database changed before replacement; refusing stale write")
            if any(inventory.sha256_file(p) != sha for p, sha in input_hashes.items()):
                raise ValueError("an input changed before database replacement")
            os.replace(stage, db_path)
            report["database_sha256"] = inventory.sha256_file(db_path)
            return report
        finally:
            if conn is not None:
                conn.close()
            if stage.exists():
                stage.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="peaches.accounting")
    parser.add_argument("--database", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--boundaries", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--workbook", action="append", default=[])
    parser.add_argument("--reviews")
    parser.add_argument("--expected-db-sha")
    args = parser.parse_args(argv)
    result = import_accounting(args.database, args.inventory, args.boundaries,
                               args.source_root, args.workbook,
                               args.expected_db_sha, args.reviews)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
