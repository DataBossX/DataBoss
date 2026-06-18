"""Async SQLite access layer.

Uses a single shared aiosqlite connection for the lifetime of the application.
aiosqlite serializes operations through a dedicated worker thread, so a shared
connection is safe to use concurrently and avoids the per-operation
connect/close overhead the original code paid on every query.
"""
import aiosqlite

_conn: aiosqlite.Connection | None = None


SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        file_hash TEXT UNIQUE NOT NULL,
        upload_time TIMESTAMP NOT NULL,
        file_size INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'uploaded'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ocr_results (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        raw_text TEXT NOT NULL,
        cleaned_text TEXT NOT NULL,
        confidence_score REAL NOT NULL,
        processing_time REAL NOT NULL,
        created_at TIMESTAMP NOT NULL,
        FOREIGN KEY (document_id) REFERENCES documents (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS llm_analysis (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        model_name TEXT NOT NULL,
        prompt_type TEXT NOT NULL,
        analysis_result TEXT NOT NULL,
        processing_time REAL NOT NULL,
        created_at TIMESTAMP NOT NULL,
        FOREIGN KEY (document_id) REFERENCES documents (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS system_logs (
        id TEXT PRIMARY KEY,
        level TEXT NOT NULL,
        message TEXT NOT NULL,
        component TEXT NOT NULL,
        details TEXT,
        created_at TIMESTAMP NOT NULL
    )
    """,
    # Indexes for the lookups the API actually performs.
    "CREATE INDEX IF NOT EXISTS idx_ocr_results_document_id ON ocr_results (document_id)",
    "CREATE INDEX IF NOT EXISTS idx_llm_analysis_document_id ON llm_analysis (document_id)",
    "CREATE INDEX IF NOT EXISTS idx_documents_upload_time ON documents (upload_time)",
    "CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs (created_at)",
]


async def init(path: str) -> aiosqlite.Connection:
    """Open the shared connection and create the schema if needed."""
    global _conn
    _conn = await aiosqlite.connect(path)
    _conn.row_factory = aiosqlite.Row
    await _conn.execute("PRAGMA journal_mode=WAL")
    await _conn.execute("PRAGMA foreign_keys=ON")
    for stmt in SCHEMA:
        await _conn.execute(stmt)
    await _conn.commit()
    return _conn


async def close() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


def conn() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("Database is not initialized; call db.init() first.")
    return _conn


async def execute(sql: str, params: tuple = ()) -> None:
    c = conn()
    await c.execute(sql, params)
    await c.commit()


async def fetchone(sql: str, params: tuple = ()) -> aiosqlite.Row | None:
    async with conn().execute(sql, params) as cur:
        return await cur.fetchone()


async def fetchall(sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
    async with conn().execute(sql, params) as cur:
        return list(await cur.fetchall())
