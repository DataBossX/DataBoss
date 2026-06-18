import os
import uuid
import json
import time
import hashlib
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Deque, Tuple

import aiosqlite

# FastAPI imports
from fastapi import (
    FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from config import Settings
from logging_utils import configure_logging

# --- Optional heavy dependencies -------------------------------------------
# The API must start even when individual LLM SDKs are not installed; each
# provider degrades gracefully and is simply reported as "unavailable".
try:
    import openai  # type: ignore
except Exception:  # pragma: no cover - import guard
    openai = None  # type: ignore
try:
    import anthropic  # type: ignore
except Exception:  # pragma: no cover - import guard
    anthropic = None  # type: ignore
try:
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover - import guard
    genai = None  # type: ignore

# Load environment variables, then resolve typed settings.
load_dotenv()
settings = Settings.from_env()

# Logger with secret redaction (prefers loguru, falls back to stdlib).
logger = configure_logging(
    settings.log_path,
    settings.log_level,
    extra_secrets=[
        settings.openai_api_key,
        settings.anthropic_api_key,
        settings.gemini_api_key,
    ],
)

# Back-compat module-level aliases (referenced by tests and helpers).
SQLITE_DB_PATH = settings.db_path
MAX_UPLOAD_BYTES = settings.max_upload_bytes
GEMINI_API_KEY = settings.gemini_api_key
_cors_origins = settings.cors_origins
_allow_credentials = settings.allow_credentials

# Initialize LLM clients lazily/defensively.
openai_client = (
    openai.OpenAI(api_key=settings.openai_api_key)
    if (openai and settings.openai_api_key) else None
)
anthropic_client = (
    anthropic.Anthropic(api_key=settings.anthropic_api_key)
    if (anthropic and settings.anthropic_api_key) else None
)
if genai and settings.gemini_api_key:
    try:
        genai.configure(api_key=settings.gemini_api_key)
    except Exception as exc:  # pragma: no cover
        logger.warning(f"Gemini configuration failed: {exc}")
        genai = None  # type: ignore

# Initialize OCR engine (simplified for demo)
PRIMARY_OCR = "demo_ocr"


# --- Simple in-memory sliding-window rate limiter --------------------------
_rate_buckets: Dict[str, Deque[float]] = {}


def _rate_limit_ok(client_id: str) -> bool:
    """Return True if a request from ``client_id`` is within the limit."""
    if settings.rate_limit_max <= 0:
        return True
    now = time.monotonic()
    window = settings.rate_limit_window_sec
    bucket = _rate_buckets.setdefault(client_id, deque())
    while bucket and (now - bucket[0]) > window:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_max:
        return False
    bucket.append(now)
    return True


# Application lifespan (replaces deprecated @app.on_event hooks)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database and log startup/shutdown."""
    for warning in settings.validate():
        logger.warning(f"config: {warning}")
    await init_database()
    await log_system_event("INFO", "DataBossX API started", "system")
    logger.info(
        "DataBossX API started "
        f"(providers={settings.configured_providers() or 'none'})"
    )
    yield
    logger.info("DataBossX API shutting down")


# Initialize FastAPI app
app = FastAPI(title="DataBossX API", version="1.1.0", lifespan=lifespan)

# CORS — configured via CORS_ALLOW_ORIGINS (comma-separated). Credentials are
# disabled automatically when a wildcard origin is used (per the CORS spec).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.allow_credentials,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Attach a request id, enforce rate limits, and add timing headers."""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    client_ip = request.client.host if request.client else "unknown"

    # Rate-limit mutating requests only (keeps reads cheap).
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if not _rate_limit_ok(client_ip):
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests", "request_id": request_id},
                headers={"Retry-After": str(int(settings.rate_limit_window_sec))},
            )

    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception as exc:  # defensive: never leak stack traces to clients
        logger.error(f"Unhandled error [{request_id}]: {exc}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "request_id": request_id},
        )
    elapsed_ms = (time.monotonic() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-ms"] = f"{elapsed_ms:.1f}"
    return response

# Data models
class Document(BaseModel):
    id: str
    filename: str
    file_hash: str
    upload_time: datetime
    file_size: int
    status: str
    
class OCRResult(BaseModel):
    id: str
    document_id: str
    raw_text: str
    cleaned_text: str
    confidence_score: float
    processing_time: float
    created_at: datetime
    
class LLMAnalysis(BaseModel):
    id: str
    document_id: str
    model_name: str
    prompt_type: str
    analysis_result: Dict[str, Any]
    processing_time: float
    created_at: datetime
    
class SystemLog(BaseModel):
    id: str
    level: str
    message: str
    component: str
    details: Optional[Dict[str, Any]]
    created_at: datetime

# Database initialization
async def init_database():
    """Initialize SQLite database with required tables"""
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        # Documents table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_hash TEXT UNIQUE NOT NULL,
                upload_time TIMESTAMP NOT NULL,
                file_size INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'uploaded'
            )
        """)
        
        # OCR results table
        await db.execute("""
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
        """)
        
        # LLM analysis table
        await db.execute("""
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
        """)
        
        # System logs table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id TEXT PRIMARY KEY,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                component TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP NOT NULL
            )
        """)
        
        await db.commit()

# Utility functions
def calculate_file_hash(file_content: bytes) -> str:
    """Calculate SHA-256 hash of file content"""
    return hashlib.sha256(file_content).hexdigest()

def sanitize_filename(filename: Optional[str]) -> str:
    """Return a safe base filename, stripping any path components.

    Prevents path-traversal (e.g. '../../etc/passwd') from user-supplied
    upload filenames being persisted or echoed back.
    """
    # Normalise Windows-style separators so traversal is stripped regardless of
    # the server OS (uploads may originate from Windows clients).
    raw = (filename or "").replace("\\", "/")
    name = Path(raw).name  # drop directory components
    name = name.replace("\x00", "").strip()
    return name or "unnamed"


def is_allowed_extension(filename: str) -> bool:
    """Return True if the file extension is permitted by configuration.

    An empty allow-list means "allow any type".
    """
    allowed = settings.allowed_upload_extensions
    if not allowed:
        return True
    return Path(filename).suffix.lower() in allowed

async def log_system_event(level: str, message: str, component: str, details: Optional[Dict] = None):
    """Log system events to database"""
    log_id = str(uuid.uuid4())
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        await db.execute(
            "INSERT INTO system_logs (id, level, message, component, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (log_id, level, message, component, json.dumps(details) if details else None, datetime.now())
        )
        await db.commit()

async def process_ocr(file_content: bytes, filename: str) -> Dict[str, Any]:
    """Process document with mock OCR engine for demo purposes"""
    try:
        # Mock OCR processing
        start_time = datetime.now()
        
        # Return mock OCR results
        raw_text = f"Mock OCR result for {filename}.\nThis is a demo document with extracted text.\nKey Information:\n- Document Type: Sample Legal Document\n- Parties: DataBossX Corp, Client ABC\n- Date: {datetime.now().strftime('%Y-%m-%d')}\n- Summary: This document contains important legal information.\n\nNote: This is a mock OCR result for demonstration purposes."
        cleaned_text = raw_text.strip()
        mock_confidence = 0.95
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return {
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "confidence_score": mock_confidence,
            "processing_time": processing_time,
            "ocr_engine": PRIMARY_OCR
        }
        
    except Exception as e:
        logger.error(f"OCR processing failed for {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

async def analyze_with_llm(text: str, model_name: str, prompt_type: str) -> Dict[str, Any]:
    """Analyze text with specified LLM"""
    start_time = datetime.now()
    
    prompts = {
        "legal_summary": f"Analyze this legal document and extract key information:\n\nDocument: {text}\n\nPlease provide:\n1. Document type\n2. Key parties involved\n3. Important dates\n4. Main legal points\n5. Summary",
        "general_summary": f"Provide a concise summary of this document:\n\n{text}",
        "field_extraction": f"Extract structured data from this document:\n\n{text}\n\nReturn as JSON with relevant fields."
    }
    
    prompt = prompts.get(prompt_type, prompts["general_summary"])
    
    try:
        if model_name == "gpt-4" and openai_client:
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000
            )
            result = response.choices[0].message.content
            
        elif model_name == "claude" and anthropic_client:
            response = anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            result = response.content[0].text
            
        elif model_name == "gemini" and GEMINI_API_KEY:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            result = response.text
            
        else:
            raise HTTPException(status_code=400, detail=f"Model {model_name} not available")
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return {
            "analysis": result,
            "processing_time": processing_time,
            "model_used": model_name,
            "prompt_type": prompt_type
        }
        
    except Exception as e:
        logger.error(f"LLM analysis failed with {model_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {str(e)}")

# API Endpoints
@app.get("/")
async def root():
    """Service metadata / liveness root."""
    return {
        "service": "DataBossX API",
        "version": app.version,
        "status": "ok",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "version": app.version,
        "services": {
            "ocr": "available",
            "openai": "available" if openai_client else "unavailable",
            "anthropic": "available" if anthropic_client else "unavailable",
            "gemini": "available" if (GEMINI_API_KEY and genai) else "unavailable",
        },
        "limits": {
            "max_upload_mb": settings.max_upload_mb,
            "rate_limit_per_window": settings.rate_limit_max,
            "rate_limit_window_sec": settings.rate_limit_window_sec,
        },
    }

@app.post("/api/documents/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload and process document with OCR"""
    try:
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # Reject empty or oversized uploads early
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        if file_size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
            )

        safe_filename = sanitize_filename(file.filename)
        if not is_allowed_extension(safe_filename):
            allowed = ", ".join(sorted(settings.allowed_upload_extensions))
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type. Allowed: {allowed}",
            )
        file_hash = calculate_file_hash(file_content)

        # Check for duplicates
        async with aiosqlite.connect(SQLITE_DB_PATH) as db:
            async with db.execute("SELECT id FROM documents WHERE file_hash = ?", (file_hash,)) as cursor:
                existing = await cursor.fetchone()
                if existing:
                    return JSONResponse(
                        status_code=409,
                        content={"error": "Document already exists", "document_id": existing[0]}
                    )
        
        # Create document record
        doc_id = str(uuid.uuid4())
        async with aiosqlite.connect(SQLITE_DB_PATH) as db:
            await db.execute(
                "INSERT INTO documents (id, filename, file_hash, upload_time, file_size, status) VALUES (?, ?, ?, ?, ?, ?)",
                (doc_id, safe_filename, file_hash, datetime.now(), file_size, "processing")
            )
            await db.commit()

        # Process OCR in background
        background_tasks.add_task(process_document_background, doc_id, file_content, safe_filename)

        await log_system_event("INFO", f"Document uploaded: {safe_filename}", "upload", {"document_id": doc_id})

        return {
            "document_id": doc_id,
            "filename": safe_filename,
            "file_size": file_size,
            "status": "processing"
        }

    except HTTPException:
        # Preserve intended client-error status codes (400/409/413/...)
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

async def process_document_background(doc_id: str, file_content: bytes, filename: str):
    """Background task to process document with OCR and LLM"""
    try:
        # Update status to processing
        async with aiosqlite.connect(SQLITE_DB_PATH) as db:
            await db.execute("UPDATE documents SET status = ? WHERE id = ?", ("processing", doc_id))
            await db.commit()
        
        # Process OCR
        ocr_result = await process_ocr(file_content, filename)
        
        # Save OCR result
        ocr_id = str(uuid.uuid4())
        async with aiosqlite.connect(SQLITE_DB_PATH) as db:
            await db.execute(
                "INSERT INTO ocr_results (id, document_id, raw_text, cleaned_text, confidence_score, processing_time, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ocr_id, doc_id, ocr_result["raw_text"], ocr_result["cleaned_text"], 
                 ocr_result["confidence_score"], ocr_result["processing_time"], datetime.now())
            )
            await db.commit()
        
        # Process with available LLMs
        available_models = []
        if openai_client:
            available_models.append("gpt-4")
        if anthropic_client:
            available_models.append("claude")
        if GEMINI_API_KEY:
            available_models.append("gemini")
        
        for model in available_models:
            try:
                llm_result = await analyze_with_llm(ocr_result["cleaned_text"], model, "legal_summary")
                
                # Save LLM analysis
                analysis_id = str(uuid.uuid4())
                async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                    await db.execute(
                        "INSERT INTO llm_analysis (id, document_id, model_name, prompt_type, analysis_result, processing_time, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (analysis_id, doc_id, model, "legal_summary", json.dumps(llm_result), 
                         llm_result["processing_time"], datetime.now())
                    )
                    await db.commit()
            except Exception as e:
                logger.error(f"LLM analysis failed for {model}: {str(e)}")
        
        # Update document status to completed
        async with aiosqlite.connect(SQLITE_DB_PATH) as db:
            await db.execute("UPDATE documents SET status = ? WHERE id = ?", ("completed", doc_id))
            await db.commit()
        
        await log_system_event("INFO", f"Document processing completed: {filename}", "processing", {"document_id": doc_id})
        
    except Exception as e:
        # Update status to failed
        async with aiosqlite.connect(SQLITE_DB_PATH) as db:
            await db.execute("UPDATE documents SET status = ? WHERE id = ?", ("failed", doc_id))
            await db.commit()
        
        await log_system_event("ERROR", f"Document processing failed: {filename}", "processing", 
                              {"document_id": doc_id, "error": str(e)})
        logger.error(f"Background processing failed for {doc_id}: {str(e)}")

@app.get("/api/documents")
async def get_documents():
    """Get all documents"""
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
            "status": doc[5]
        }
        for doc in documents
    ]

@app.get("/api/documents/{document_id}")
async def get_document_details(document_id: str):
    """Get detailed document information including OCR and LLM results"""
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        # Get document info
        async with db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)) as cursor:
            doc = await cursor.fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
        
        # Get OCR results
        async with db.execute("SELECT * FROM ocr_results WHERE document_id = ?", (document_id,)) as cursor:
            ocr_results = await cursor.fetchall()
        
        # Get LLM analysis
        async with db.execute("SELECT * FROM llm_analysis WHERE document_id = ?", (document_id,)) as cursor:
            llm_results = await cursor.fetchall()
    
    return {
        "document": {
            "id": doc[0],
            "filename": doc[1],
            "file_hash": doc[2],
            "upload_time": doc[3],
            "file_size": doc[4],
            "status": doc[5]
        },
        "ocr_results": [
            {
                "id": result[0],
                "raw_text": result[2],
                "cleaned_text": result[3],
                "confidence_score": result[4],
                "processing_time": result[5],
                "created_at": result[6]
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
                "created_at": result[6]
            }
            for result in llm_results
        ]
    }

@app.get("/api/logs")
async def get_system_logs(limit: int = 100):
    """Get system logs"""
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        async with db.execute("SELECT * FROM system_logs ORDER BY created_at DESC LIMIT ?", (limit,)) as cursor:
            logs = await cursor.fetchall()
    
    return [
        {
            "id": log[0],
            "level": log[1],
            "message": log[2],
            "component": log[3],
            "details": json.loads(log[4]) if log[4] else None,
            "created_at": log[5]
        }
        for log in logs
    ]

@app.get("/api/analytics")
async def get_analytics():
    """Get system analytics and metrics"""
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        # Document counts by status
        async with db.execute("SELECT status, COUNT(*) FROM documents GROUP BY status") as cursor:
            doc_stats = await cursor.fetchall()
        
        # OCR performance metrics
        async with db.execute("SELECT AVG(confidence_score), AVG(processing_time) FROM ocr_results") as cursor:
            ocr_metrics = await cursor.fetchone()
        
        # LLM usage stats
        async with db.execute("SELECT model_name, COUNT(*) FROM llm_analysis GROUP BY model_name") as cursor:
            llm_stats = await cursor.fetchall()
        
        # Recent activity
        async with db.execute("SELECT COUNT(*) FROM documents WHERE upload_time >= datetime('now', '-24 hours')") as cursor:
            recent_uploads = (await cursor.fetchone())[0]
    
    return {
        "document_stats": {status: count for status, count in doc_stats},
        "ocr_metrics": {
            "avg_confidence": ocr_metrics[0] if ocr_metrics[0] else 0,
            "avg_processing_time": ocr_metrics[1] if ocr_metrics[1] else 0
        },
        "llm_usage": {model: count for model, count in llm_stats},
        "recent_activity": {
            "uploads_24h": recent_uploads
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
