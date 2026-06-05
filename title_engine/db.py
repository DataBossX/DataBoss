"""
SQLite persistence layer for the Title Engine.
Single file, WAL mode, fully self-contained schema.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DB_PATH: Path = Path("title_engine.db")
Tuple_str_bool = Tuple[str, bool]


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Every unique instrument discovered (search results + manual adds)
CREATE TABLE IF NOT EXISTS instruments (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key         TEXT    UNIQUE NOT NULL,
    hit_id            TEXT,
    county            TEXT,
    book              TEXT,
    page              TEXT,
    instrument_number TEXT,
    instrument_type   TEXT,
    doc_date          TEXT,
    recording_date    TEXT,
    effective_date    TEXT,
    grantor           TEXT,   -- JSON array
    grantee           TEXT,   -- JSON array
    legal             TEXT,
    section_27        INTEGER DEFAULT 0,   -- 1 = expressly includes S27
    aol_flag          INTEGER DEFAULT 0,   -- 1 = "and other lands"
    image_url         TEXT,
    source_url        TEXT,
    search_query      TEXT,
    -- Pipeline state
    download_status   TEXT    DEFAULT 'pending',  -- pending/downloaded/skipped/failed
    local_pdf         TEXT,
    local_pdf_size    INTEGER DEFAULT 0,
    ocr_status        TEXT    DEFAULT 'pending',  -- pending/done/failed
    ocr_text_path     TEXT,
    extraction_status TEXT    DEFAULT 'pending',  -- pending/done/failed
    extracted_json    TEXT,
    confidence        REAL    DEFAULT 0.0,
    needs_review      INTEGER DEFAULT 0,
    created_at        TEXT    DEFAULT (datetime('now')),
    updated_at        TEXT    DEFAULT (datetime('now'))
);

-- All searches executed (prevents re-running the same query)
CREATE TABLE IF NOT EXISTS search_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    search_type  TEXT,   -- legal / quarter / entity / dynamic
    query        TEXT,
    county       TEXT,
    result_count INTEGER DEFAULT 0,
    status       TEXT    DEFAULT 'pending',  -- pending/done/empty/error
    ran_at       TEXT    DEFAULT (datetime('now'))
);

-- Dynamic entity queue: every new grantor/grantee queues a follow-up search
CREATE TABLE IF NOT EXISTS entity_queue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_name   TEXT    UNIQUE NOT NULL,
    entity_type   TEXT,   -- grantor/grantee/assignor/assignee/operator
    search_status TEXT    DEFAULT 'pending',
    source_dedup  TEXT,   -- which instrument triggered this
    added_at      TEXT    DEFAULT (datetime('now'))
);

-- Cost ledger
CREATE TABLE IF NOT EXISTS cost_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    api_type    TEXT,
    amount      REAL,
    description TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Human-readable research log
CREATE TABLE IF NOT EXISTS research_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    action     TEXT,
    detail     TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_inst_dedup   ON instruments(dedup_key);
CREATE INDEX IF NOT EXISTS idx_inst_type    ON instruments(instrument_type);
CREATE INDEX IF NOT EXISTS idx_inst_dl      ON instruments(download_status);
CREATE INDEX IF NOT EXISTS idx_search_query ON search_log(query);
CREATE INDEX IF NOT EXISTS idx_entity       ON entity_queue(entity_name);
"""


def init_db(path: Path = None) -> None:
    global DB_PATH
    if path:
        DB_PATH = path
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def execute(sql: str, params: tuple = ()) -> int:
    with conn() as c:
        cur = c.execute(sql, params)
        return cur.lastrowid or cur.rowcount or 0


def fetch_all(sql: str, params: tuple = ()) -> List[Dict]:
    with conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def fetch_one(sql: str, params: tuple = ()) -> Optional[Dict]:
    with conn() as c:
        r = c.execute(sql, params).fetchone()
        return dict(r) if r else None


# ── Instrument upserts ────────────────────────────────────────────────────────

def upsert_instrument(hit_dict: Dict[str, Any]) -> Tuple_str_bool:
    """Insert or skip. Returns (dedup_key, is_new)."""
    existing = fetch_one("SELECT dedup_key FROM instruments WHERE dedup_key=?",
                         (hit_dict["dedup_key"],))
    if existing:
        return hit_dict["dedup_key"], False

    def _j(v):
        return json.dumps(v) if isinstance(v, list) else (str(v) if v else None)

    execute("""
        INSERT INTO instruments
          (dedup_key, hit_id, county, book, page, instrument_number,
           instrument_type, doc_date, recording_date,
           grantor, grantee, legal, image_url, source_url, search_query)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        hit_dict["dedup_key"],
        hit_dict.get("hit_id"),
        hit_dict.get("county"),
        hit_dict.get("book"),
        hit_dict.get("page"),
        hit_dict.get("instrument_number"),
        hit_dict.get("instrument_type"),
        hit_dict.get("doc_date"),
        hit_dict.get("recording_date"),
        _j(hit_dict.get("grantor")),
        _j(hit_dict.get("grantee")),
        hit_dict.get("legal"),
        hit_dict.get("image_url"),
        hit_dict.get("source_url"),
        hit_dict.get("search_query"),
    ))
    return hit_dict["dedup_key"], True


def get_stats() -> Dict[str, Any]:
    with conn() as c:
        def _q(sql, default=0):
            r = c.execute(sql).fetchone()
            return r[0] if r and r[0] is not None else default

        total = _q("SELECT COUNT(*) FROM instruments")
        s27   = _q("SELECT COUNT(*) FROM instruments WHERE section_27=1")
        dl_done = _q("SELECT COUNT(*) FROM instruments WHERE download_status='downloaded'")
        dl_pend = _q("SELECT COUNT(*) FROM instruments WHERE download_status='pending'")
        ocr_done = _q("SELECT COUNT(*) FROM instruments WHERE ocr_status='done'")
        ext_done = _q("SELECT COUNT(*) FROM instruments WHERE extraction_status='done'")
        needs_review = _q("SELECT COUNT(*) FROM instruments WHERE needs_review=1")
        okcr_cost = _q("SELECT COALESCE(SUM(amount),0) FROM cost_log WHERE api_type='okcr'")
        ai_cost   = _q("SELECT COALESCE(SUM(amount),0) FROM cost_log WHERE api_type='ai'")
        entity_pending = _q("SELECT COUNT(*) FROM entity_queue WHERE search_status='pending'")
        searches_done  = _q("SELECT COUNT(*) FROM search_log WHERE status='done'")

    return {
        "total": total, "section_27": s27,
        "dl_pending": dl_pend, "dl_done": dl_done,
        "ocr_done": ocr_done, "ext_done": ext_done,
        "needs_review": needs_review,
        "entity_pending": entity_pending,
        "searches_done": searches_done,
        "okcr_cost": round(okcr_cost, 4),
        "ai_cost": round(ai_cost, 4),
        "total_cost": round(okcr_cost + ai_cost, 4),
    }


def log_cost(api_type: str, amount: float, description: str) -> None:
    execute("INSERT INTO cost_log(api_type,amount,description) VALUES(?,?,?)",
            (api_type, amount, description))


def log_research(action: str, detail: str) -> None:
    execute("INSERT INTO research_log(action,detail) VALUES(?,?)", (action, detail))


def add_to_entity_queue(name: str, etype: str, source_dedup: str = None) -> bool:
    """Returns True if newly added."""
    existing = fetch_one("SELECT id FROM entity_queue WHERE entity_name=?", (name,))
    if existing:
        return False
    execute("INSERT INTO entity_queue(entity_name,entity_type,source_dedup) VALUES(?,?,?)",
            (name.strip(), etype, source_dedup))
    return True


def mark_search_done(query: str, county: str, stype: str, count: int) -> None:
    existing = fetch_one("SELECT id FROM search_log WHERE query=? AND county=?",
                         (query, county))
    if existing:
        execute("UPDATE search_log SET status='done', result_count=?, ran_at=datetime('now') WHERE id=?",
                (count, existing["id"]))
    else:
        execute("INSERT INTO search_log(search_type,query,county,result_count,status) VALUES(?,?,?,?,?)",
                (stype, query, county, count, "done"))


def search_already_done(query: str, county: str) -> bool:
    r = fetch_one("SELECT status FROM search_log WHERE query=? AND county=? AND status='done'",
                  (query, county))
    return r is not None


