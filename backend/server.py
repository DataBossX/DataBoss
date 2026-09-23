import os
import uuid
import sqlite3
import json
import asyncio
import secrets
from datetime import datetime
from typing import Optional, List, Dict, Any
import aiosqlite
from pathlib import Path

# FastAPI imports
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# OCR and LLM imports - Simplified for demo
import openai
import anthropic
import google.generativeai as genai
from PIL import Image
import io
import hashlib
import base64

# Logging
from loguru import logger

# Load environment variables
load_dotenv()

# Configure logger
logger.add("logs/databossx.log", rotation="10 MB", retention="10 days")

# --------------------------------------------------------------------------
# Security configuration (issue #94, items 4-6)
#
# All env-driven security settings are centralized here in a single
# pydantic-style Settings object instead of scattering os.environ.get() calls
# across the request handlers. Relevant environment variables:
#
#   DATABOSSX_API_KEY               Shared secret required in the X-API-Key
#                                    header on every non-health endpoint. If
#                                    unset, ALL authenticated endpoints fail
#                                    closed (401) rather than allowing access.
#   DATABOSSX_ALLOWED_ORIGINS       Comma-separated list of trusted origins
#                                    for CORS (e.g. "http://localhost:3000").
#                                    Defaults to a localhost-only origin.
#                                    "*" is always stripped out: wildcard
#                                    origins are never combined with
#                                    allow_credentials=True.
#   DATABOSSX_DEMO_MODE             "true"/"1" to explicitly opt into the
#                                    synthetic demo-OCR mode. Defaults to
#                                    False. Outside this mode, the mock OCR
#                                    engine refuses to run (fails closed)
#                                    instead of fabricating document content.
#   DATABOSSX_MAX_UPLOAD_SIZE_BYTES Maximum accepted upload size in bytes.
#                                    Defaults to 10 MB.
#   DATABOSSX_ALLOWED_CONTENT_TYPES Comma-separated list of accepted upload
#                                    MIME types. Defaults to a small set of
#                                    document/image types.
#   DATABOSSX_HOST / DATABOSSX_PORT Bind address for `python server.py`.
#                                    Defaults to 127.0.0.1 (localhost only).
# --------------------------------------------------------------------------


def _parse_bool_env(value: Optional[str], default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_list_env(value: Optional[str], default: List[str]) -> List[str]:
    if value is None or value.strip() == "":
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


def _strip_wildcards(origins: List[str]) -> List[str]:
    """Never allow '*' to reach CORSMiddleware alongside allow_credentials=True."""
    return [origin for origin in origins if origin and origin != "*"]


class SecuritySettings(BaseModel):
    """Centralized, env-driven security configuration for the demo backend."""

    host: str = Field(default_factory=lambda: os.getenv("DATABOSSX_HOST", "127.0.0.1"))
    port: int = Field(default_factory=lambda: int(os.getenv("DATABOSSX_PORT", "8001")))

    # Style B auth: shared secret compared against the X-API-Key header.
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("DATABOSSX_API_KEY") or None)

    # Explicit trusted-origin allowlist for CORS. No wildcard, ever.
    allowed_origins: List[str] = Field(
        default_factory=lambda: _strip_wildcards(
            _parse_list_env(os.getenv("DATABOSSX_ALLOWED_ORIGINS"), ["http://localhost:3000"])
        )
    )

    # Explicit synthetic/demo-mode gate. Mock OCR only runs when this is True.
    demo_mode: bool = Field(default_factory=lambda: _parse_bool_env(os.getenv("DATABOSSX_DEMO_MODE"), False))

    # Upload limits.
    max_upload_size_bytes: int = Field(
        default_factory=lambda: int(os.getenv("DATABOSSX_MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024)))
    )
    allowed_content_types: List[str] = Field(
        default_factory=lambda: _parse_list_env(
            os.getenv("DATABOSSX_ALLOWED_CONTENT_TYPES"),
            ["application/pdf", "image/png", "image/jpeg", "image/tiff", "text/plain"],
        )
    )


settings = SecuritySettings()

# Initialize FastAPI app
app = FastAPI(title="DataBossX API", version="1.0.0")

# CORS middleware - explicit trusted-origin allowlist only, never "*" with
# allow_credentials=True (defect #94 item 5).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# --------------------------------------------------------------------------
# Authentication (issue #94 item 4): API-key header validated against
# DATABOSSX_API_KEY, using FastAPI's Security/APIKeyHeader pattern.
# --------------------------------------------------------------------------
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Dependency enforcing X-API-Key auth on every protected endpoint.

    Fails closed: if no server-side key is configured (DATABOSSX_API_KEY
    unset), every request is rejected rather than silently allowing
    unauthenticated access.
    """
    if not settings.api_key:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not api_key or not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return api_key


# Database configuration
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./databossx.db")

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize clients
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Initialize OCR engine (simplified for demo). This is a mock engine, not a
# real OCR backend - see process_ocr() for the fail-closed gating.
PRIMARY_OCR = "demo_ocr"

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
    """Run OCR on an uploaded document.

    PRIMARY_OCR ("demo_ocr") is a mock engine only - it never reads
    file_content and never extracts real text. To avoid fabricating
    legal-looking content that could be mistaken for a real OCR result
    (issue #94 item 6):

      * Outside DATABOSSX_DEMO_MODE this fails closed with a 503 rather
        than returning any invented text.
      * Inside DATABOSSX_DEMO_MODE the output is a placeholder that is
        unambiguously labeled synthetic on every line, carries no invented
        parties/dates/legal facts, and is flagged with is_synthetic=True.
    """
    if not settings.demo_mode:
        logger.error(
            f"Refused to run mock OCR engine '{PRIMARY_OCR}' for {filename}: "
            "DATABOSSX_DEMO_MODE is not enabled, failing closed instead of "
            "fabricating OCR output."
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "OCR is unavailable: no real OCR engine is configured. "
                "Set DATABOSSX_DEMO_MODE=true to use the synthetic demo OCR engine."
            ),
        )

    try:
        start_time = datetime.now()

        # Synthetic placeholder only - unambiguously labeled, no invented
        # parties, dates, or legal content that could pass as real output.
        raw_text = (
            "[SYNTHETIC DEMO OCR OUTPUT - NOT A REAL OCR RESULT]\n"
            f"This is placeholder text generated by the demo OCR engine for filename: {filename}.\n"
            "No file content was read and no legal or factual information was extracted.\n"
            "This output exists only to exercise the demo pipeline and must never be treated "
            "as a real document extraction.\n"
            "[END SYNTHETIC DEMO OCR OUTPUT]"
        )
        cleaned_text = raw_text.strip()
        processing_time = (datetime.now() - start_time).total_seconds()

        return {
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            # 0.0 signals "not a real confidence measurement", not a quality score.
            "confidence_score": 0.0,
            "processing_time": processing_time,
            "ocr_engine": f"{PRIMARY_OCR}-synthetic",
            "is_synthetic": True,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception(f"OCR processing failed for {filename}")
        raise HTTPException(status_code=500, detail="OCR processing failed")

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
        
    except HTTPException:
        raise
    except Exception:
        logger.exception(f"LLM analysis failed with {model_name}")
        raise HTTPException(status_code=500, detail="LLM analysis failed")

# API Endpoints
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await init_database()
    await log_system_event("INFO", "DataBossX API started", "system")
    logger.info("DataBossX API started successfully")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "version": "1.0.0",
        "services": {
            # Mock OCR fails closed unless DATABOSSX_DEMO_MODE is on (issue
            # #94 item 6) -- reporting "available" regardless would let a
            # client upload a document that is guaranteed to fail OCR later.
            "ocr": "available (synthetic demo mode)" if settings.demo_mode else "unavailable",
            "openai": "available" if openai_client else "unavailable",
            "anthropic": "available" if anthropic_client else "unavailable", 
            "gemini": "available" if GEMINI_API_KEY else "unavailable"
        }
    }

@app.post("/api/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    api_key: str = Depends(require_api_key),
):
    """Upload and process document with OCR"""
    try:
        # Reject synchronously when OCR is unavailable (issue #94 item 6):
        # background processing already fails closed via process_ocr(), but
        # by then the caller has already received a 200 "processing"
        # response and the record has been created, so the advertised 503
        # never reaches them and every accepted upload is guaranteed to fail
        # later. Check before creating any record.
        if not settings.demo_mode:
            raise HTTPException(
                status_code=503,
                detail=(
                    "OCR is unavailable: no real OCR engine is configured. "
                    "Set DATABOSSX_DEMO_MODE=true to use the synthetic demo OCR engine."
                ),
            )

        # Enforce the file-type allowlist up front (defect #94 item 4/6 hardening).
        if file.content_type not in settings.allowed_content_types:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        # Read file content
        file_content = await file.read()
        file_hash = calculate_file_hash(file_content)
        file_size = len(file_content)

        # Enforce the upload size limit.
        if file_size > settings.max_upload_size_bytes:
            raise HTTPException(status_code=413, detail="File too large")

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
                (doc_id, file.filename, file_hash, datetime.now(), file_size, "processing")
            )
            await db.commit()
        
        # Process OCR in background
        background_tasks.add_task(process_document_background, doc_id, file_content, file.filename)
        
        await log_system_event("INFO", f"Document uploaded: {file.filename}", "upload", {"document_id": doc_id})
        
        return {
            "document_id": doc_id,
            "filename": file.filename,
            "file_size": file_size,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception:
        logger.exception("Document upload failed")
        raise HTTPException(status_code=500, detail="Upload failed")

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
async def get_documents(api_key: str = Depends(require_api_key)):
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
async def get_document_details(document_id: str, api_key: str = Depends(require_api_key)):
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
async def get_system_logs(limit: int = 100, api_key: str = Depends(require_api_key)):
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
async def get_analytics(api_key: str = Depends(require_api_key)):
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
    # Bind to localhost only by default (issue #94: no unauthenticated
    # network-wide exposure). Override via DATABOSSX_HOST if deliberately
    # deploying behind a reverse proxy that terminates auth elsewhere.
    uvicorn.run(app, host=settings.host, port=settings.port)
