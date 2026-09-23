import os
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import Depends, FastAPI, File, Header, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from security_controls import (
    AUTH_HEADER,
    authenticate,
    bind_host,
    cors_origins,
    demo_mode_enabled,
    demo_ocr_payload,
    mock_ocr_allowed,
    validate_upload,
)

try:
    import aiosqlite
except ImportError:  # pragma: no cover
    aiosqlite = None

try:
    from loguru import logger
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("databossx.backend")

load_dotenv()

os.makedirs("logs", exist_ok=True)
if hasattr(logger, "add"):
    logger.add("logs/databossx.log", rotation="10 MB", retention="10 days")

app = FastAPI(title="DataBossX API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", AUTH_HEADER, "Content-Type"],
)

SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./databossx.db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

openai_client = None
anthropic_client = None
if OPENAI_API_KEY:
    try:
        import openai
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        openai_client = None
if ANTHROPIC_API_KEY:
    try:
        import anthropic
        anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception:
        anthropic_client = None
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception:
        GEMINI_API_KEY = None


def _require_db():
    if aiosqlite is None:
        raise HTTPException(status_code=503, detail="storage unavailable")


async def require_auth(x_databossx_token: Optional[str] = Header(default=None, alias=AUTH_HEADER)):
    ok, reason = authenticate(x_databossx_token)
    if not ok:
        raise HTTPException(status_code=401, detail="unauthorized")
    return True


def calculate_file_hash(file_content: bytes) -> str:
    import hashlib
    return hashlib.sha256(file_content).hexdigest()


async def init_database():
    _require_db()
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_hash TEXT UNIQUE NOT NULL,
                upload_time TIMESTAMP NOT NULL,
                file_size INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'uploaded'
            )
            """
        )
        await db.execute(
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
            """
        )
        await db.execute(
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
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS system_logs (
                id TEXT PRIMARY KEY,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                component TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        await db.commit()


async def log_system_event(level: str, message: str, component: str, details: Optional[Dict] = None):
    if aiosqlite is None:
        return
    log_id = str(uuid.uuid4())
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        await db.execute(
            "INSERT INTO system_logs (id, level, message, component, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (log_id, level, message, component, json.dumps(details) if details else None, datetime.now()),
        )
        await db.commit()


async def process_ocr(file_content: bytes, filename: str) -> Dict[str, Any]:
    allowed, reason = mock_ocr_allowed()
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)
    payload = demo_ocr_payload(filename)
    payload["byte_size"] = len(file_content)
    return payload


@app.on_event("startup")
async def startup_event():
    if aiosqlite is not None:
        await init_database()
        await log_system_event("INFO", "DataBossX API started", "system")
    logger.info("DataBossX API started in fail-closed mode")


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "version": "1.1.0",
        "demo_mode": demo_mode_enabled(),
        "bind_host": bind_host(),
        "services": {
            "ocr": "demo-only" if demo_mode_enabled() else "disabled",
            "openai": "available" if openai_client else "unavailable",
            "anthropic": "available" if anthropic_client else "unavailable",
            "gemini": "available" if GEMINI_API_KEY else "unavailable",
        },
    }


@app.post("/api/documents/upload", dependencies=[Depends(require_auth)])
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    file_content = await file.read()
    ok, reason = validate_upload(file.filename, len(file_content))
    if not ok:
        raise HTTPException(status_code=400, detail="upload refused")
    if not demo_mode_enabled():
        raise HTTPException(status_code=403, detail="real-upload mode refuses mock OCR")

    _require_db()
    file_hash = calculate_file_hash(file_content)
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        async with db.execute("SELECT id FROM documents WHERE file_hash = ?", (file_hash,)) as cursor:
            existing = await cursor.fetchone()
            if existing:
                return JSONResponse(status_code=409, content={"error": "Document already exists", "document_id": existing[0]})
        doc_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO documents (id, filename, file_hash, upload_time, file_size, status) VALUES (?, ?, ?, ?, ?, ?)",
            (doc_id, file.filename, file_hash, datetime.now(), len(file_content), "processing"),
        )
        await db.commit()
    background_tasks.add_task(process_document_background, doc_id, file_content, file.filename)
    return {"document_id": doc_id, "filename": file.filename, "file_size": len(file_content), "status": "processing"}


async def process_document_background(doc_id: str, file_content: bytes, filename: str):
    try:
        ocr_result = await process_ocr(file_content, filename)
        if ocr_result.get("raw_text") or ocr_result.get("cleaned_text"):
            raise RuntimeError("demo OCR must not emit invented text")
        async with aiosqlite.connect(SQLITE_DB_PATH) as db:
            await db.execute(
                "INSERT INTO ocr_results (id, document_id, raw_text, cleaned_text, confidence_score, processing_time, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    doc_id,
                    ocr_result["raw_text"],
                    ocr_result["cleaned_text"],
                    ocr_result["confidence_score"],
                    ocr_result["processing_time"],
                    datetime.now(),
                ),
            )
            await db.execute("UPDATE documents SET status = ? WHERE id = ?", ("completed", doc_id))
            await db.commit()
    except Exception as exc:
        if aiosqlite is not None:
            async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                await db.execute("UPDATE documents SET status = ? WHERE id = ?", ("failed", doc_id))
                await db.commit()
        logger.error("Background processing failed for %s: %s", doc_id, exc)


@app.get("/api/documents", dependencies=[Depends(require_auth)])
async def get_documents():
    _require_db()
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        async with db.execute("SELECT * FROM documents ORDER BY upload_time DESC") as cursor:
            documents = await cursor.fetchall()
    return [
        {
            "id": doc[0],
            "filename": doc[1],
            "file_hash": doc[2],
            "upload_time": doc[3],
            "file_size": doc[4],
            "status": doc[5],
        }
        for doc in documents
    ]


@app.get("/api/documents/{document_id}", dependencies=[Depends(require_auth)])
async def get_document_details(document_id: str):
    _require_db()
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        async with db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)) as cursor:
            doc = await cursor.fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail="not found")
        async with db.execute("SELECT * FROM ocr_results WHERE document_id = ?", (document_id,)) as cursor:
            ocr_results = await cursor.fetchall()
        async with db.execute("SELECT * FROM llm_analysis WHERE document_id = ?", (document_id,)) as cursor:
            llm_results = await cursor.fetchall()
    return {
        "document": {
            "id": doc[0],
            "filename": doc[1],
            "file_hash": doc[2],
            "upload_time": doc[3],
            "file_size": doc[4],
            "status": doc[5],
        },
        "ocr_results": [
            {
                "id": result[0],
                "raw_text": result[2],
                "cleaned_text": result[3],
                "confidence_score": result[4],
                "processing_time": result[5],
                "created_at": result[6],
            }
            for result in ocr_results
        ],
        "llm_analysis": [
            {
                "id": result[0],
                "model_name": result[2],
                "prompt_type": result[3],
                "analysis_result": json.loads(result[4]),
                "processing_time": result[5],
                "created_at": result[6],
            }
            for result in llm_results
        ],
    }


@app.get("/api/logs", dependencies=[Depends(require_auth)])
async def get_system_logs(limit: int = 100):
    _require_db()
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        async with db.execute("SELECT * FROM system_logs ORDER BY created_at DESC LIMIT ?", (limit,)) as cursor:
            logs = await cursor.fetchall()
    return [
        {
            "id": row[0],
            "level": row[1],
            "message": row[2],
            "component": row[3],
            "details": json.loads(row[4]) if row[4] else None,
            "created_at": row[5],
        }
        for row in logs
    ]


@app.get("/api/analytics", dependencies=[Depends(require_auth)])
async def get_analytics():
    _require_db()
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        async with db.execute("SELECT status, COUNT(*) FROM documents GROUP BY status") as cursor:
            doc_stats = await cursor.fetchall()
        async with db.execute("SELECT AVG(confidence_score), AVG(processing_time) FROM ocr_results") as cursor:
            ocr_metrics = await cursor.fetchone()
        async with db.execute("SELECT model_name, COUNT(*) FROM llm_analysis GROUP BY model_name") as cursor:
            llm_stats = await cursor.fetchall()
        async with db.execute("SELECT COUNT(*) FROM documents WHERE upload_time >= datetime('now', '-24 hours')") as cursor:
            recent_uploads = (await cursor.fetchone())[0]
    return {
        "document_stats": {status: count for status, count in doc_stats},
        "ocr_metrics": {
            "avg_confidence": ocr_metrics[0] if ocr_metrics and ocr_metrics[0] else 0,
            "avg_processing_time": ocr_metrics[1] if ocr_metrics and ocr_metrics[1] else 0,
        },
        "llm_usage": {model: count for model, count in llm_stats},
        "recent_activity": {"uploads_24h": recent_uploads},
    }


@app.middleware("http")
async def reject_untrusted_credentialed_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in cors_origins() and request.url.path != "/api/health":
        if request.headers.get("cookie") or request.headers.get(AUTH_HEADER.lower()):
            return JSONResponse(status_code=403, content={"detail": "untrusted origin"})
    return await call_next(request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=bind_host(), port=8001)
