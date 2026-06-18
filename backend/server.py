"""DataBossX API.

Document ingestion -> OCR/text extraction -> multi-provider LLM analysis,
with structured logging, metrics, input validation, and reliability hardening.
"""
import asyncio
import hashlib
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from loguru import logger

import config
import db
import llm
import observability
from ocr import extract_text, OCRError, supported as ocr_supported, tesseract_available


# --------------------------------------------------------------------------- #
# Lifespan
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    observability.configure_logging()
    await db.init(config.SQLITE_DB_PATH)
    await log_system_event("INFO", "DataBossX API started", "system")
    logger.info("DataBossX API started successfully")
    try:
        yield
    finally:
        await db.close()


app = FastAPI(title="DataBossX API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=config.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(observability.metrics_middleware)


# --------------------------------------------------------------------------- #
# Error handling — consistent JSON error envelope
# --------------------------------------------------------------------------- #
class ApiError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


@app.exception_handler(ApiError)
async def _api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


@app.exception_handler(Exception)
async def _unhandled_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class Document(BaseModel):
    id: str
    filename: str
    file_hash: str
    upload_time: datetime
    file_size: int
    status: str


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def calculate_file_hash(file_content: bytes) -> str:
    return hashlib.sha256(file_content).hexdigest()


async def log_system_event(level: str, message: str, component: str, details: Optional[Dict] = None):
    await db.execute(
        "INSERT INTO system_logs (id, level, message, component, details, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), level, message, component,
         json.dumps(details) if details else None, datetime.now().isoformat()),
    )
    observability.inc("system_logs_total", level=level, component=component)


async def process_ocr(file_content: bytes, filename: str, content_type: Optional[str]) -> Dict[str, Any]:
    """Run extraction off the event loop (CPU-bound)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, extract_text, file_content, filename, content_type)


# --------------------------------------------------------------------------- #
# Background processing
# --------------------------------------------------------------------------- #
async def process_document_background(doc_id: str, file_content: bytes, filename: str, content_type: Optional[str]):
    try:
        await db.execute("UPDATE documents SET status = ? WHERE id = ?", ("processing", doc_id))

        ocr_result = await process_ocr(file_content, filename, content_type)

        await db.execute(
            "INSERT INTO ocr_results (id, document_id, raw_text, cleaned_text, confidence_score, "
            "processing_time, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), doc_id, ocr_result["raw_text"], ocr_result["cleaned_text"],
             ocr_result["confidence_score"], ocr_result["processing_time"], datetime.now().isoformat()),
        )
        observability.inc("ocr_processed_total", engine=ocr_result.get("ocr_engine", "unknown"))

        # Analyze with every available provider; one failing provider must not
        # abort the others or the whole document.
        for model in llm.available_models():
            try:
                llm_result = await llm.analyze(ocr_result["cleaned_text"], model, "legal_summary")
                await db.execute(
                    "INSERT INTO llm_analysis (id, document_id, model_name, prompt_type, "
                    "analysis_result, processing_time, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), doc_id, model, "legal_summary", json.dumps(llm_result),
                     llm_result["processing_time"], datetime.now().isoformat()),
                )
                observability.inc("llm_analysis_total", model=model, outcome="success")
            except Exception as exc:
                observability.inc("llm_analysis_total", model=model, outcome="error")
                logger.error(f"LLM analysis failed for {model}: {exc}")
                await log_system_event("ERROR", f"LLM analysis failed for {model}", "processing",
                                       {"document_id": doc_id, "error": str(exc)})

        await db.execute("UPDATE documents SET status = ? WHERE id = ?", ("completed", doc_id))
        observability.inc("documents_completed_total")
        await log_system_event("INFO", f"Document processing completed: {filename}", "processing",
                               {"document_id": doc_id})

    except OCRError as exc:
        await db.execute("UPDATE documents SET status = ? WHERE id = ?", ("failed", doc_id))
        observability.inc("documents_failed_total", reason="ocr")
        await log_system_event("ERROR", f"OCR failed: {filename}", "processing",
                               {"document_id": doc_id, "error": str(exc)})
        logger.error(f"OCR failed for {doc_id}: {exc}")
    except Exception as exc:
        await db.execute("UPDATE documents SET status = ? WHERE id = ?", ("failed", doc_id))
        observability.inc("documents_failed_total", reason="error")
        await log_system_event("ERROR", f"Document processing failed: {filename}", "processing",
                               {"document_id": doc_id, "error": str(exc)})
        logger.error(f"Background processing failed for {doc_id}: {exc}")


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@app.get("/api/health")
async def health_check():
    providers = llm.provider_status()
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "version": app.version,
        "services": {
            "ocr": "available",
            "ocr_image": "available" if tesseract_available() else "unavailable",
            **providers,
        },
    }


@app.post("/api/documents/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    file_content = await file.read()
    file_size = len(file_content)

    # --- Validation ---
    if file_size == 0:
        raise ApiError(400, "Uploaded file is empty")
    if file_size > config.MAX_UPLOAD_BYTES:
        raise ApiError(413, f"File exceeds maximum size of {config.MAX_UPLOAD_BYTES} bytes")
    if not ocr_supported(file.filename or "", file.content_type):
        raise ApiError(415, f"Unsupported file type: {file.content_type or file.filename}")

    file_hash = calculate_file_hash(file_content)

    existing = await db.fetchone("SELECT id FROM documents WHERE file_hash = ?", (file_hash,))
    if existing:
        return JSONResponse(
            status_code=409,
            content={"error": "Document already exists", "document_id": existing["id"]},
        )

    doc_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO documents (id, filename, file_hash, upload_time, file_size, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (doc_id, file.filename, file_hash, datetime.now().isoformat(), file_size, "processing"),
    )
    observability.inc("documents_uploaded_total")

    background_tasks.add_task(
        process_document_background, doc_id, file_content, file.filename, file.content_type
    )
    await log_system_event("INFO", f"Document uploaded: {file.filename}", "upload",
                           {"document_id": doc_id})

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "file_size": file_size,
        "status": "processing",
    }


@app.get("/api/documents")
async def get_documents():
    rows = await db.fetchall("SELECT * FROM documents ORDER BY upload_time DESC")
    return [
        {
            "id": r["id"],
            "filename": r["filename"],
            "file_hash": r["file_hash"],
            "upload_time": r["upload_time"],
            "file_size": r["file_size"],
            "status": r["status"],
        }
        for r in rows
    ]


@app.get("/api/documents/{document_id}")
async def get_document_details(document_id: str):
    doc = await db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not doc:
        raise ApiError(404, "Document not found")

    ocr_rows = await db.fetchall("SELECT * FROM ocr_results WHERE document_id = ?", (document_id,))
    llm_rows = await db.fetchall("SELECT * FROM llm_analysis WHERE document_id = ?", (document_id,))

    return {
        "document": {
            "id": doc["id"],
            "filename": doc["filename"],
            "file_hash": doc["file_hash"],
            "upload_time": doc["upload_time"],
            "file_size": doc["file_size"],
            "status": doc["status"],
        },
        "ocr_results": [
            {
                "id": r["id"],
                "raw_text": r["raw_text"],
                "cleaned_text": r["cleaned_text"],
                "confidence_score": r["confidence_score"],
                "processing_time": r["processing_time"],
                "created_at": r["created_at"],
            }
            for r in ocr_rows
        ],
        "llm_analysis": [
            {
                "id": r["id"],
                "model_name": r["model_name"],
                "prompt_type": r["prompt_type"],
                "analysis_result": json.loads(r["analysis_result"]),
                "processing_time": r["processing_time"],
                "created_at": r["created_at"],
            }
            for r in llm_rows
        ],
    }


@app.get("/api/logs")
async def get_system_logs(limit: int = 100):
    limit = max(1, min(limit, 1000))
    rows = await db.fetchall(
        "SELECT * FROM system_logs ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    return [
        {
            "id": r["id"],
            "level": r["level"],
            "message": r["message"],
            "component": r["component"],
            "details": json.loads(r["details"]) if r["details"] else None,
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.get("/api/analytics")
async def get_analytics():
    doc_stats = await db.fetchall("SELECT status, COUNT(*) AS n FROM documents GROUP BY status")
    ocr_metrics = await db.fetchone(
        "SELECT AVG(confidence_score) AS conf, AVG(processing_time) AS pt FROM ocr_results"
    )
    llm_stats = await db.fetchall(
        "SELECT model_name, COUNT(*) AS n FROM llm_analysis GROUP BY model_name"
    )
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    recent = await db.fetchone(
        "SELECT COUNT(*) AS n FROM documents WHERE upload_time >= ?", (cutoff,)
    )

    return {
        "document_stats": {r["status"]: r["n"] for r in doc_stats},
        "ocr_metrics": {
            "avg_confidence": ocr_metrics["conf"] if ocr_metrics and ocr_metrics["conf"] else 0,
            "avg_processing_time": ocr_metrics["pt"] if ocr_metrics and ocr_metrics["pt"] else 0,
        },
        "llm_usage": {r["model_name"]: r["n"] for r in llm_stats},
        "recent_activity": {"uploads_24h": recent["n"] if recent else 0},
    }


@app.get("/api/metrics")
async def metrics_json():
    return observability.snapshot()


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics_prometheus():
    return observability.prometheus_text()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
