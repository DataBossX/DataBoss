"""Offline API tests using FastAPI's TestClient (no live server required)."""
import uuid


def _upload(client, text=None, filename=None, content_type="text/plain"):
    body = (text if text is not None else f"Doc {uuid.uuid4()}").encode()
    name = filename or f"{uuid.uuid4()}.txt"
    return client.post(
        "/api/documents/upload",
        files={"file": (name, body, content_type)},
    )


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert "ocr" in data["services"]
    # No provider keys in the test env → providers unavailable.
    assert data["services"]["anthropic"] == "unavailable"


def test_upload_text_and_process(client):
    content = f"Contract between Acme and Globex. id={uuid.uuid4()}"
    r = _upload(client, text=content)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "processing"
    doc_id = data["document_id"]

    # Background processing runs to completion within the TestClient call.
    details = client.get(f"/api/documents/{doc_id}").json()
    assert details["document"]["status"] == "completed"
    assert len(details["ocr_results"]) == 1
    ocr = details["ocr_results"][0]
    assert "Acme" in ocr["raw_text"]
    assert ocr["confidence_score"] == 1.0
    # No LLMs configured → no analyses, but the document still completes.
    assert details["llm_analysis"] == []


def test_duplicate_upload_returns_409(client):
    content = f"dedupe-{uuid.uuid4()}"
    first = _upload(client, text=content)
    assert first.status_code == 200
    second = _upload(client, text=content)
    assert second.status_code == 409
    assert second.json()["document_id"] == first.json()["document_id"]


def test_empty_file_rejected(client):
    r = _upload(client, text="")
    assert r.status_code == 400


def test_too_large_rejected(client):
    big = "x" * 200_000  # exceeds the 100 KB test limit
    r = _upload(client, text=big)
    assert r.status_code == 413


def test_unsupported_type_rejected(client):
    r = client.post(
        "/api/documents/upload",
        files={"file": ("malware.exe", b"MZ\x90\x00", "application/x-msdownload")},
    )
    assert r.status_code == 415


def test_documents_list(client):
    _upload(client)
    r = client.get("/api/documents")
    assert r.status_code == 200
    docs = r.json()
    assert isinstance(docs, list) and docs
    assert {"id", "filename", "status"} <= docs[0].keys()


def test_document_not_found(client):
    r = client.get(f"/api/documents/{uuid.uuid4()}")
    assert r.status_code == 404
    assert "error" in r.json()


def test_analytics_shape(client):
    r = client.get("/api/analytics")
    assert r.status_code == 200
    data = r.json()
    for key in ("document_stats", "ocr_metrics", "llm_usage", "recent_activity"):
        assert key in data
    assert "uploads_24h" in data["recent_activity"]


def test_logs_shape(client):
    r = client.get("/api/logs?limit=10")
    assert r.status_code == 200
    logs = r.json()
    assert isinstance(logs, list) and logs
    assert {"id", "level", "message", "component"} <= logs[0].keys()


def test_metrics_endpoints(client):
    _upload(client)  # generate some activity
    j = client.get("/api/metrics")
    assert j.status_code == 200
    assert "counters" in j.json()

    p = client.get("/metrics")
    assert p.status_code == 200
    assert "http_requests_total" in p.text
