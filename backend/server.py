"""Legacy demo backend — fail-closed until retired.

Do not use this service for client evidence. Bind loopback by default.
Data endpoints require an explicit demo token. Mock OCR is synthetic-only.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import security_controls as security

SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./databossx.db")


class Document(BaseModel):
    id: str
    filename: str
    file_hash: str
    upload_time: datetime
    file_size: int
    status: str


def _generic_error(status_code: int, code: str = "request rejected") -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status_code)


def _header_map(request: Request) -> dict[str, str]:
    return {k: v for k, v in request.headers.items()}


def create_app() -> FastAPI:
    app = FastAPI(title="DataBossX API", version="1.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=security.cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Databossx-Demo-Token", "X-Databossx-Synthetic"],
    )

    @app.middleware("http")
    async def enforce_auth(request: Request, call_next):
        path = request.url.path
        if security.is_public_path(path):
            return await call_next(request)
        if security.is_protected_path(path) and not security.authorized(_header_map(request)):
            return _generic_error(401, "unauthorized")
        return await call_next(request)

    @app.get("/api/health")
    @app.get("/healthz")
    async def health_check():
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.1.0",
            "demo_mode": security.demo_mode_enabled(),
            "bind": security.bind_host(),
            "mock_ocr": "synthetic_only" if security.demo_mode_enabled() else "disabled",
        }

    @app.post("/api/documents/upload")
    async def upload_document(request: Request, file: UploadFile = File(...)):
        content = await file.read()
        try:
            security.validate_upload(file.filename, len(content), _header_map(request))
        except security.SecurityError:
            return _generic_error(403, "upload rejected")
        if not security.mock_ocr_allowed(file.filename, _header_map(request)):
            return _generic_error(403, "ocr refused")
        text = security.synthetic_ocr_placeholder(file.filename or "upload.txt")
        return {
            "document_id": str(uuid.uuid4()),
            "filename": file.filename,
            "file_size": len(content),
            "file_hash": hashlib.sha256(content).hexdigest(),
            "status": "synthetic_demo",
            "ocr": {
                "raw_text": text,
                "cleaned_text": text,
                "confidence_score": 0.0,
                "ocr_engine": "synthetic_placeholder",
            },
        }

    @app.get("/api/documents")
    async def get_documents():
        return []

    @app.get("/api/documents/{document_id}")
    async def get_document_details(document_id: str):
        return _generic_error(404, "not found")

    @app.get("/api/logs")
    async def get_system_logs(limit: int = 100):
        return []

    @app.get("/api/analytics")
    async def get_analytics():
        return {"document_stats": {}, "ocr_metrics": {}, "llm_usage": {}, "recent_activity": {}}

    return app


app = create_app()


# Retained names so older callers fail closed instead of inventing facts.
async def process_ocr(file_content: bytes, filename: str, headers: Optional[dict[str, str]] = None) -> dict[str, Any]:
    if not security.mock_ocr_allowed(filename, headers):
        raise security.SecurityError("REAL_UPLOAD_REFUSED")
    text = security.synthetic_ocr_placeholder(filename)
    return {
        "raw_text": text,
        "cleaned_text": text,
        "confidence_score": 0.0,
        "processing_time": 0.0,
        "ocr_engine": "synthetic_placeholder",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=security.bind_host(), port=int(os.getenv("PORT", "8001")))
