"""Local, non-destructive processing pipeline for DataBoss Title Factory.

Every source is read-only. Generated files are written to a timestamped run
folder under ``DataBoss_Title_Factory_Output`` and weak results are copied into
that run's quarantine area for examiner review.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

OUTPUT_DIR_NAME = "DataBoss_Title_Factory_Output"
SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", OUTPUT_DIR_NAME,
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
PDF_EXTENSIONS = {".pdf"}
TEXT_EXTENSIONS = {".txt", ".md", ".log", ".text"}
TABLE_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xlsm"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS | TEXT_EXTENSIONS | TABLE_EXTENSIONS

INSTRUMENT_FIELDS = (
    "instrument_number", "instrument_type", "instrument_date", "recorded_date",
    "book", "page", "grantor", "grantee", "legal_description",
    "interest_conveyed", "lease_royalty_terms",
)
EXPORT_FIELDS = (
    "entry_no", "instrument_date", "recorded_date", "instrument_type",
    "grantor", "grantee", "instrument_number", "book", "page",
    "legal_description", "interest_conveyed", "lease_royalty_terms",
    "confidence", "status", "citation", "source_path", "source_locator",
    "reconciliation_notes",
)


@dataclass(frozen=True)
class RunContext:
    root: Path
    output_dir: Path
    run_dir: Path
    run_id: str

    @property
    def quarantine_dir(self) -> Path:
        return self.run_dir / "quarantine"

    @property
    def preprocessed_dir(self) -> Path:
        return self.run_dir / "preprocessed"


def _now_id() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def start_run(root: str | Path) -> RunContext:
    """Create a new immutable run folder and mark it as the latest run."""
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise ValueError(f"Project folder does not exist: {root_path}")
    output = root_path / OUTPUT_DIR_NAME
    run_id = _now_id()
    run_dir = output / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "quarantine").mkdir()
    output.mkdir(parents=True, exist_ok=True)
    _atomic_text(output / "latest_run.txt", run_id)
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_id,
            "project_root": str(root_path),
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source_policy": "read-only; generated results are versioned; nothing is deleted",
        },
    )
    return RunContext(root_path, output, run_dir, run_id)


def latest_run(root: str | Path) -> RunContext:
    root_path = Path(root).expanduser().resolve()
    output = root_path / OUTPUT_DIR_NAME
    pointer = output / "latest_run.txt"
    if not pointer.exists():
        raise FileNotFoundError("No run exists. Run Inventory first.")
    run_id = pointer.read_text(encoding="utf-8").strip()
    run_dir = output / "runs" / run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Latest run folder is missing: {run_dir}")
    return RunContext(root_path, output, run_dir, run_id)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{_now_id()}.tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_text(path, json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{_now_id()}.tmp")
    with temp.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    temp.replace(path)


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def build_inventory(ctx: RunContext) -> list[dict[str, Any]]:
    """Inventory every source file without modifying the source tree."""
    records: list[dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(ctx.root):
        dirnames[:] = sorted(
            name for name in dirnames
            if name not in SKIP_DIRS and not (Path(dirpath) / name).is_symlink()
        )
        parent = Path(dirpath)
        for filename in sorted(filenames):
            path = parent / filename
            if path.is_symlink() or not path.is_file():
                continue
            try:
                stat = path.stat()
                rel = path.relative_to(ctx.root).as_posix()
                records.append(
                    {
                        "source_path": rel,
                        "folder": path.parent.relative_to(ctx.root).as_posix(),
                        "filename": filename,
                        "extension": path.suffix.lower(),
                        "size_bytes": stat.st_size,
                        "modified_at": dt.datetime.fromtimestamp(
                            stat.st_mtime, tz=dt.timezone.utc
                        ).isoformat(),
                        "sha256": _sha256(path),
                        "supported": path.suffix.lower() in SUPPORTED_EXTENSIONS,
                        "status": "inventoried",
                    }
                )
            except OSError as exc:
                records.append(
                    {
                        "source_path": str(path),
                        "folder": "",
                        "filename": filename,
                        "extension": path.suffix.lower(),
                        "size_bytes": "",
                        "modified_at": "",
                        "sha256": "",
                        "supported": False,
                        "status": f"scan_error: {exc}",
                    }
                )
    fields = (
        "source_path", "folder", "filename", "extension", "size_bytes",
        "modified_at", "sha256", "supported", "status",
    )
    _write_json(ctx.run_dir / "file_inventory.json", records)
    _write_csv(ctx.run_dir / "file_inventory.csv", records, fields)
    return records


def load_inventory(ctx: RunContext) -> list[dict[str, Any]]:
    records = _read_json(ctx.run_dir / "file_inventory.json")
    if records is None:
        return build_inventory(ctx)
    return records


def _safe_rel_name(rel: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", rel).strip("._")
    suffix = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:10]
    return f"{clean[:100]}_{suffix}" if clean else suffix


def _prepare_image(source: Path, destination: Path) -> None:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps

    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("L")
        if image.width < 1800:
            scale = min(3.0, 1800 / max(image.width, 1))
            image = image.resize(
                (int(image.width * scale), int(image.height * scale)),
                Image.Resampling.LANCZOS,
            )
        image = ImageOps.autocontrast(image, cutoff=1)
        image = ImageEnhance.Contrast(image).enhance(1.35)
        image = image.filter(ImageFilter.SHARPEN)
        image.save(destination, format="PNG", optimize=True)


def preprocess_images(ctx: RunContext, dpi: int = 240) -> list[dict[str, Any]]:
    """Create OCR-ready image copies; originals remain untouched."""
    inventory = load_inventory(ctx)
    ctx.preprocessed_dir.mkdir(parents=True, exist_ok=True)
    pages: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for record in inventory:
        rel = str(record.get("source_path", ""))
        ext = str(record.get("extension", "")).lower()
        source = ctx.root / rel
        stem = _safe_rel_name(rel)
        if ext in IMAGE_EXTENSIONS:
            destination = ctx.preprocessed_dir / f"{stem}_page_0001.png"
            try:
                _prepare_image(source, destination)
                pages.append(_page_map(rel, 1, destination, ctx))
            except Exception as exc:
                errors.append({"source_path": rel, "error": str(exc)})
        elif ext in PDF_EXTENSIONS:
            try:
                import fitz

                with fitz.open(source) as document:
                    matrix = fitz.Matrix(dpi / 72, dpi / 72)
                    for index, page in enumerate(document, start=1):
                        raw = ctx.preprocessed_dir / f".{stem}_{index:04d}_raw.png"
                        destination = ctx.preprocessed_dir / f"{stem}_page_{index:04d}.png"
                        page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY, alpha=False).save(raw)
                        try:
                            _prepare_image(raw, destination)
                        finally:
                            raw.unlink(missing_ok=True)
                        pages.append(_page_map(rel, index, destination, ctx))
            except Exception as exc:
                errors.append({"source_path": rel, "error": str(exc)})
    _write_json(ctx.run_dir / "preprocessed_pages.json", pages)
    _write_json(ctx.run_dir / "preprocess_errors.json", errors)
    if errors:
        _write_csv(
            ctx.quarantine_dir / "preprocess_failures.csv",
            errors,
            ("source_path", "error"),
        )
    return pages


def _page_map(rel: str, page: int, destination: Path, ctx: RunContext) -> dict[str, Any]:
    return {
        "source_path": rel,
        "page": page,
        "preprocessed_path": destination.relative_to(ctx.run_dir).as_posix(),
        "citation": f"{rel}#page={page}",
    }


def _ocr_image(path: Path) -> tuple[str, float]:
    import pytesseract
    from PIL import Image

    with Image.open(path) as image:
        data = pytesseract.image_to_data(
            image, config="--oem 3 --psm 6", output_type=pytesseract.Output.DICT
        )
    words: list[str] = []
    confidences: list[float] = []
    current_line = None
    chunks: list[str] = []
    for index, word in enumerate(data.get("text", [])):
        word = str(word).strip()
        if not word:
            continue
        line_key = (
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )
        if current_line is not None and line_key != current_line:
            chunks.append(" ".join(words))
            words = []
        current_line = line_key
        words.append(word)
        try:
            confidence = float(data["conf"][index])
            if confidence >= 0:
                confidences.append(confidence / 100.0)
        except (TypeError, ValueError):
            pass
    if words:
        chunks.append(" ".join(words))
    return "\n".join(chunks).strip(), (
        sum(confidences) / len(confidences) if confidences else 0.0
    )


def _text_records(ctx: RunContext, record: dict[str, Any]) -> list[dict[str, Any]]:
    rel = record["source_path"]
    source = ctx.root / rel
    ext = source.suffix.lower()
    results: list[dict[str, Any]] = []
    if ext in TEXT_EXTENSIONS:
        text = source.read_text(encoding="utf-8", errors="replace")
        results.append(_citation(rel, "file", text, 1.0, "native_text"))
    elif ext in {".csv", ".tsv"}:
        delimiter = "\t" if ext == ".tsv" else ","
        with source.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            for row_number, row in enumerate(csv.reader(handle, delimiter=delimiter), start=1):
                text = " | ".join(str(value) for value in row if value)
                if text:
                    results.append(
                        _citation(rel, f"row={row_number}", text, 1.0, "table_text")
                    )
    elif ext in {".xlsx", ".xlsm"}:
        import openpyxl

        workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
        try:
            for sheet in workbook.worksheets:
                for row_number, values in enumerate(sheet.iter_rows(values_only=True), start=1):
                    text = " | ".join(str(value) for value in values if value not in (None, ""))
                    if text:
                        locator = f"sheet={sheet.title};row={row_number}"
                        results.append(_citation(rel, locator, text, 1.0, "workbook_text"))
        finally:
            workbook.close()
    return results


def _citation(
    source_path: str,
    locator: str,
    text: str,
    confidence: float,
    method: str,
) -> dict[str, Any]:
    return {
        "citation": f"{source_path}#{locator}",
        "source_path": source_path,
        "source_locator": locator,
        "text": text,
        "confidence": round(float(confidence), 4),
        "method": method,
        "status": "ok" if text.strip() else "weak",
    }


def run_ocr(ctx: RunContext, weak_threshold: float = 0.55) -> list[dict[str, Any]]:
    """Extract text from native documents and OCR page images with citations."""
    inventory = load_inventory(ctx)
    pages = preprocess_images(ctx)
    page_index = {(p["source_path"], p["page"]): p for p in pages}
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for item in inventory:
        rel = str(item.get("source_path", ""))
        ext = str(item.get("extension", "")).lower()
        try:
            if ext in TEXT_EXTENSIONS | TABLE_EXTENSIONS:
                records.extend(_text_records(ctx, item))
            elif ext in PDF_EXTENSIONS:
                records.extend(_ocr_pdf(ctx, rel, page_index))
            elif ext in IMAGE_EXTENSIONS:
                mapped = page_index.get((rel, 1))
                if mapped:
                    text, confidence = _ocr_image(ctx.run_dir / mapped["preprocessed_path"])
                    records.append(_citation(rel, "page=1", text, confidence, "tesseract"))
        except Exception as exc:
            failures.append({"source_path": rel, "error": str(exc)})
    for record in records:
        if not record["text"].strip() or float(record["confidence"]) < weak_threshold:
            record["status"] = "weak"
    fields = (
        "citation", "source_path", "source_locator", "confidence", "method",
        "status", "text",
    )
    _write_jsonl(ctx.run_dir / "ocr_citations.jsonl", records)
    _write_csv(ctx.run_dir / "ocr_citations.csv", records, fields)
    weak = [record for record in records if record["status"] == "weak"]
    if weak:
        _write_json(ctx.quarantine_dir / "weak_ocr_results.json", weak)
        _write_csv(ctx.quarantine_dir / "weak_ocr_results.csv", weak, fields)
    if failures:
        _write_json(ctx.quarantine_dir / "ocr_failures.json", failures)
        _write_csv(ctx.quarantine_dir / "ocr_failures.csv", failures, ("source_path", "error"))
    return records


def _ocr_pdf(
    ctx: RunContext,
    rel: str,
    page_index: dict[tuple[str, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    import fitz

    output: list[dict[str, Any]] = []
    with fitz.open(ctx.root / rel) as document:
        for page_number, page in enumerate(document, start=1):
            embedded = page.get_text("text").strip()
            if len(re.sub(r"\s+", "", embedded)) >= 40:
                output.append(_citation(rel, f"page={page_number}", embedded, 0.99, "pdf_text"))
                continue
            mapped = page_index.get((rel, page_number))
            if mapped:
                text, confidence = _ocr_image(ctx.run_dir / mapped["preprocessed_path"])
                output.append(
                    _citation(rel, f"page={page_number}", text, confidence, "tesseract")
                )
    return output


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    text = "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in rows)
    _atomic_text(path, text)


def load_ocr(ctx: RunContext) -> list[dict[str, Any]]:
    path = ctx.run_dir / "ocr_citations.jsonl"
    if not path.exists():
        raise FileNotFoundError("OCR output is missing. Run OCR first.")
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


_LABEL_PATTERNS: dict[str, tuple[str, ...]] = {
    "instrument_number": (
        r"(?:instrument|document|doc|reception)\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/.]+)",
        r"\b(?:INST|DOC)\s*#\s*([A-Z0-9][A-Z0-9\-/.]+)",
    ),
    "book": (r"\b(?:book|bk\.?)\s*[:#]?\s*([A-Z0-9-]+)",),
    "page": (r"\b(?:page|pg\.?)\s*[:#]?\s*([A-Z0-9-]+)",),
    "grantor": (
        r"\b(?:grantor|lessor|assignor)\s*[:\-]\s*([^\n|;]{2,100})",
        r"\bfrom\s*[:\-]\s*([^\n|;]{2,100})",
    ),
    "grantee": (
        r"\b(?:grantee|lessee|assignee)\s*[:\-]\s*([^\n|;]{2,100})",
        r"\bto\s*[:\-]\s*([^\n|;]{2,100})",
    ),
    "legal_description": (
        r"\b(?:legal description|lands?|tract)\s*[:\-]\s*([^\n]{4,250})",
        r"\b((?:NE|NW|SE|SW|N/2|S/2|E/2|W/2)[^\n]{0,180}\b(?:section|sec\.?)\s*\d+[^\n]{0,100})",
    ),
    "interest_conveyed": (
        r"\b(?:interest conveyed|conveyed interest|interest)\s*[:\-]\s*([^\n|;]{1,80})",
    ),
    "lease_royalty_terms": (
        r"\b(?:royalty|lease royalty|royalty terms?)\s*[:\-]\s*([^\n|;]{1,100})",
    ),
}
_DATE_RX = re.compile(
    r"\b(?:0?[1-9]|1[0-2])[/.-](?:0?[1-9]|[12]\d|3[01])[/.-](?:19|20)\d{2}\b"
)
_TYPE_RX = re.compile(
    r"\b(warranty deed|quitclaim deed|mineral deed|oil and gas lease|"
    r"assignment(?: of [^\n,;]+)?|affidavit|memorandum|probate|court order|deed)\b",
    re.IGNORECASE,
)


def _first_match(text: str, patterns: Sequence[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip(" ,.;:-")
    return ""


def _extract_cursor_candidate(citation: dict[str, Any]) -> Optional[dict[str, Any]]:
    text = str(citation.get("text", ""))
    fields = {name: _first_match(text, patterns) for name, patterns in _LABEL_PATTERNS.items()}
    dates = _DATE_RX.findall(text)
    fields["instrument_date"] = dates[0] if dates else ""
    fields["recorded_date"] = dates[1] if len(dates) > 1 else ""
    type_match = _TYPE_RX.search(text)
    fields["instrument_type"] = type_match.group(1).title() if type_match else ""
    if not any(fields.values()):
        return None
    return _candidate(citation, fields, "cursor")


def _extract_codex_candidate(citation: dict[str, Any]) -> Optional[dict[str, Any]]:
    text = str(citation.get("text", ""))
    fields = {name: _first_match(text, patterns) for name, patterns in _LABEL_PATTERNS.items()}
    if not fields["instrument_number"]:
        fallback = re.search(
            r"\b(?:recorded|filed)\s+(?:as\s+)?(?:instrument\s+)?([A-Z]?\d[\d-]{4,})\b",
            text,
            flags=re.IGNORECASE,
        )
        fields["instrument_number"] = fallback.group(1) if fallback else ""
    dates = _DATE_RX.findall(text)
    recorded = re.search(
        r"\b(?:recorded|filed)\s*(?:on)?\s*[:\-]?\s*(" + _DATE_RX.pattern[2:-2] + r")",
        text,
        flags=re.IGNORECASE,
    )
    fields["recorded_date"] = recorded.group(1) if recorded else (dates[-1] if dates else "")
    fields["instrument_date"] = dates[0] if dates else ""
    type_match = _TYPE_RX.search(text)
    fields["instrument_type"] = type_match.group(1).title() if type_match else ""
    if not any(fields.values()):
        return None
    return _candidate(citation, fields, "codex")


def _candidate(
    citation: dict[str, Any], fields: dict[str, Any], engine: str
) -> dict[str, Any]:
    completeness = sum(bool(fields.get(field)) for field in INSTRUMENT_FIELDS) / len(
        INSTRUMENT_FIELDS
    )
    source_confidence = float(citation.get("confidence", 0.0) or 0.0)
    confidence = min(0.98, 0.35 * source_confidence + 0.65 * completeness)
    return {
        **{field: str(fields.get(field, "") or "").strip() for field in INSTRUMENT_FIELDS},
        "engine": engine,
        "confidence": round(confidence, 4),
        "citation": citation.get("citation", ""),
        "source_path": citation.get("source_path", ""),
        "source_locator": citation.get("source_locator", ""),
    }


def _load_external_candidates(path: Optional[str | Path], engine: str) -> Optional[list[dict[str, Any]]]:
    if not path:
        return None
    candidate_path = Path(path).expanduser()
    if not candidate_path.exists():
        raise FileNotFoundError(f"{engine.title()} output does not exist: {candidate_path}")
    data = json.loads(candidate_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("instruments") or data.get("results") or data.get("rows") or [data]
    if not isinstance(data, list):
        raise ValueError(f"{engine.title()} output must be a JSON object or array.")
    normalized: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                **{field: str(row.get(field, "") or "").strip() for field in INSTRUMENT_FIELDS},
                "engine": engine,
                "confidence": float(row.get("confidence", row.get("confidence_score", 0.5)) or 0.0),
                "citation": str(row.get("citation", "") or ""),
                "source_path": str(row.get("source_path", "") or ""),
                "source_locator": str(row.get("source_locator", row.get("page", "")) or ""),
            }
        )
    return normalized


def extract_and_reconcile(
    ctx: RunContext,
    weak_threshold: float = 0.65,
    cursor_json: Optional[str | Path] = None,
    codex_json: Optional[str | Path] = None,
) -> list[dict[str, Any]]:
    """Create/load Cursor and Codex candidates, then run a field-level tournament."""
    ocr = load_ocr(ctx)
    cursor = _load_external_candidates(cursor_json, "cursor")
    codex = _load_external_candidates(codex_json, "codex")
    if cursor is None:
        cursor = [
            candidate for item in ocr
            if (candidate := _extract_cursor_candidate(item)) is not None
        ]
    if codex is None:
        codex = [
            candidate for item in ocr
            if (candidate := _extract_codex_candidate(item)) is not None
        ]
    candidates_dir = ctx.run_dir / "candidates"
    fields = (*INSTRUMENT_FIELDS, "engine", "confidence", "citation", "source_path", "source_locator")
    for engine, rows in (("cursor", cursor), ("codex", codex)):
        _write_json(candidates_dir / f"{engine}_output.json", rows)
        _write_csv(candidates_dir / f"{engine}_output.csv", rows, fields)
    reconciled = tournament_reconcile(cursor, codex, weak_threshold)
    for number, row in enumerate(reconciled, start=1):
        row["entry_no"] = number
    _write_json(ctx.run_dir / "instruments.json", reconciled)
    _write_csv(ctx.run_dir / "instruments.csv", reconciled, EXPORT_FIELDS)
    weak = [row for row in reconciled if row["status"] == "QUARANTINED - REVIEW REQUIRED"]
    if weak:
        _write_json(ctx.quarantine_dir / "weak_instruments.json", weak)
        _write_csv(ctx.quarantine_dir / "weak_instruments.csv", weak, EXPORT_FIELDS)
    _write_json(
        ctx.quarantine_dir / "README.json",
        {
            "policy": "Review copies only. No source file was moved, overwritten, or deleted.",
            "weak_threshold": weak_threshold,
            "weak_instrument_count": len(weak),
        },
    )
    return reconciled


def _key(row: dict[str, Any]) -> str:
    instrument = re.sub(r"[^A-Z0-9]", "", str(row.get("instrument_number", "")).upper())
    if instrument:
        return f"instrument:{instrument}"
    citation = str(row.get("citation", ""))
    parties = "|".join(
        re.sub(r"\W", "", str(row.get(field, "")).upper())
        for field in ("grantor", "grantee", "instrument_date")
    )
    return f"citation:{citation}|{parties}"


def _norm(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def tournament_reconcile(
    cursor_rows: Sequence[dict[str, Any]],
    codex_rows: Sequence[dict[str, Any]],
    weak_threshold: float = 0.65,
) -> list[dict[str, Any]]:
    """Reconcile candidate rows without inventing values.

    Exact normalized agreement wins. Conflicts use the higher-confidence
    candidate and are explicitly flagged. Unsupported fields stay blank.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in [*cursor_rows, *codex_rows]:
        grouped.setdefault(_key(row), []).append(dict(row))
    output: list[dict[str, Any]] = []
    for group_key in sorted(grouped):
        candidates = grouped[group_key]
        candidates.sort(key=lambda row: float(row.get("confidence", 0.0)), reverse=True)
        winner: dict[str, Any] = {}
        agreements = 0
        conflicts: list[str] = []
        for field in INSTRUMENT_FIELDS:
            populated = [row for row in candidates if str(row.get(field, "")).strip()]
            if not populated:
                winner[field] = ""
                continue
            by_value: dict[str, list[dict[str, Any]]] = {}
            for row in populated:
                by_value.setdefault(_norm(row[field]), []).append(row)
            agreed = max(by_value.values(), key=len)
            if len(agreed) >= 2:
                winner[field] = agreed[0][field]
                agreements += 1
            else:
                winner[field] = populated[0][field]
                if len(by_value) > 1:
                    conflicts.append(field)
        best = candidates[0]
        completeness = sum(bool(winner[field]) for field in INSTRUMENT_FIELDS) / len(
            INSTRUMENT_FIELDS
        )
        agreement_ratio = agreements / max(
            1, sum(bool(winner[field]) for field in INSTRUMENT_FIELDS)
        )
        score = (
            0.45 * float(best.get("confidence", 0.0))
            + 0.35 * completeness
            + 0.20 * agreement_ratio
            - min(0.25, len(conflicts) * 0.04)
        )
        citations = sorted({str(row.get("citation", "")) for row in candidates if row.get("citation")})
        source_paths = sorted(
            {str(row.get("source_path", "")) for row in candidates if row.get("source_path")}
        )
        locators = sorted(
            {str(row.get("source_locator", "")) for row in candidates if row.get("source_locator")}
        )
        reasons = []
        if conflicts:
            reasons.append("candidate disagreement: " + ", ".join(conflicts))
        if not winner["instrument_number"]:
            reasons.append("missing instrument number")
        if not citations:
            reasons.append("missing source citation")
        status = "ACCEPTED"
        if score < weak_threshold or not winner["instrument_number"] or not citations:
            status = "QUARANTINED - REVIEW REQUIRED"
        output.append(
            {
                **winner,
                "entry_no": "",
                "confidence": round(max(0.0, min(1.0, score)), 4),
                "status": status,
                "citation": " | ".join(citations),
                "source_path": " | ".join(source_paths),
                "source_locator": " | ".join(locators),
                "reconciliation_notes": "; ".join(reasons) or "candidate evidence reconciled",
            }
        )
    return output


def build_runsheet(ctx: RunContext) -> dict[str, list[dict[str, Any]]]:
    instruments = _read_json(ctx.run_dir / "instruments.json")
    if instruments is None:
        raise FileNotFoundError("Instrument output is missing. Run Extract first.")
    runsheet = sorted(
        instruments,
        key=lambda row: (
            str(row.get("recorded_date", "")),
            str(row.get("instrument_date", "")),
            str(row.get("instrument_number", "")),
        ),
    )
    missing: list[dict[str, Any]] = []
    for row in runsheet:
        missing_fields = [
            field for field in ("instrument_number", "instrument_type", "grantor", "grantee", "legal_description")
            if not str(row.get(field, "")).strip()
        ]
        if missing_fields or row.get("status") != "ACCEPTED":
            missing.append(
                {
                    "instrument_number": row.get("instrument_number", ""),
                    "missing_or_issue": ", ".join(missing_fields) or row.get("status", ""),
                    "citation": row.get("citation", ""),
                    "recommended_action": "Locate source document and obtain examiner verification.",
                }
            )
    failures = _read_json(ctx.quarantine_dir / "ocr_failures.json", []) or []
    for failure in failures:
        missing.append(
            {
                "instrument_number": "",
                "missing_or_issue": f"OCR failed: {failure.get('error', '')}",
                "citation": failure.get("source_path", ""),
                "recommended_action": "Inspect the source manually and rerun OCR.",
            }
        )
    ogl = [
        row for row in runsheet
        if any(term in str(row.get("instrument_type", "")).lower() for term in ("lease", "memorandum"))
        or str(row.get("lease_royalty_terms", "")).strip()
    ]
    tracts: list[dict[str, Any]] = []
    for row in runsheet:
        if str(row.get("legal_description", "")).strip():
            tracts.append(
                {
                    "tract_id": hashlib.sha1(
                        str(row["legal_description"]).encode("utf-8")
                    ).hexdigest()[:10].upper(),
                    **row,
                }
            )
    result = {
        "runsheet": runsheet,
        "missing_documents": missing,
        "ogl_draft": ogl,
        "tract_drafts": tracts,
    }
    _write_json(ctx.run_dir / "runsheet_bundle.json", result)
    _write_csv(ctx.run_dir / "runsheet.csv", runsheet, EXPORT_FIELDS)
    _write_csv(
        ctx.run_dir / "missing_documents.csv",
        missing,
        ("instrument_number", "missing_or_issue", "citation", "recommended_action"),
    )
    _write_csv(ctx.run_dir / "ogl_draft.csv", ogl, EXPORT_FIELDS)
    _write_csv(ctx.run_dir / "tract_drafts.csv", tracts, ("tract_id", *EXPORT_FIELDS))
    return result


def _safe_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _unique_export_path(output_dir: Path, stem: str, suffix: str = ".xlsx") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate = output_dir / f"{stem}_{_now_id()}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = output_dir / f"{stem}_{_now_id()}_{counter}{suffix}"
        counter += 1
    return candidate


def export_safe_xlsx(
    ctx: RunContext,
    template: str | Path,
    section: str = "",
) -> Path:
    """Copy a template and add generated sheets; never overwrite the template."""
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    template_path = Path(template).expanduser().resolve()
    if not template_path.is_file() or template_path.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise ValueError("Choose an existing .xlsx or .xlsm template.")
    bundle = _read_json(ctx.run_dir / "runsheet_bundle.json")
    if bundle is None:
        bundle = build_runsheet(ctx)
    suffix = template_path.suffix.lower()
    destination = _unique_export_path(
        ctx.output_dir / "exports",
        f"DataBoss_Title_Factory_{re.sub(r'[^A-Za-z0-9_-]+', '_', section).strip('_') or 'Report'}",
        suffix,
    )
    shutil.copy2(template_path, destination)
    workbook = openpyxl.load_workbook(destination, keep_vba=suffix == ".xlsm")
    generated_names = ("DBTF Runsheet", "DBTF Missing Docs", "DBTF OGL Draft", "DBTF Tract Drafts")
    for name in generated_names:
        if name in workbook.sheetnames:
            del workbook[name]
    sheet_specs = (
        ("DBTF Runsheet", EXPORT_FIELDS, bundle["runsheet"]),
        (
            "DBTF Missing Docs",
            ("instrument_number", "missing_or_issue", "citation", "recommended_action"),
            bundle["missing_documents"],
        ),
        ("DBTF OGL Draft", EXPORT_FIELDS, bundle["ogl_draft"]),
        ("DBTF Tract Drafts", ("tract_id", *EXPORT_FIELDS), bundle["tract_drafts"]),
    )
    for name, fields, rows in sheet_specs:
        sheet = workbook.create_sheet(name)
        sheet.append([field.replace("_", " ").title() for field in fields])
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="163A3D")
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        for row in rows:
            sheet.append([_safe_cell(row.get(field, "")) for field in fields])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column, field in enumerate(fields, start=1):
            width = 42 if field in {"citation", "legal_description", "reconciliation_notes"} else 20
            sheet.column_dimensions[get_column_letter(column)].width = width
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    manifest = workbook.create_sheet("DBTF Run Manifest")
    manifest_rows = (
        ("Run ID", ctx.run_id),
        ("Project Root", str(ctx.root)),
        ("Template Source", str(template_path)),
        ("Section", section),
        ("Generated At UTC", dt.datetime.now(dt.timezone.utc).isoformat()),
        ("Safety", "Template copied; source files untouched; weak results retained in quarantine."),
    )
    for key, value in manifest_rows:
        manifest.append([key, _safe_cell(value)])
        manifest.cell(manifest.max_row, 1).font = Font(bold=True)
    workbook.save(destination)
    workbook.close()
    _write_json(
        ctx.run_dir / "export_manifest.json",
        {
            "export_path": str(destination),
            "template_path": str(template_path),
            "template_sha256": _sha256(template_path),
            "export_sha256": _sha256(destination),
            "section": section,
        },
    )
    return destination


def run_summary(ctx: RunContext) -> dict[str, Any]:
    inventory = _read_json(ctx.run_dir / "file_inventory.json", []) or []
    ocr = load_ocr(ctx) if (ctx.run_dir / "ocr_citations.jsonl").exists() else []
    instruments = _read_json(ctx.run_dir / "instruments.json", []) or []
    bundle = _read_json(ctx.run_dir / "runsheet_bundle.json", {}) or {}
    return {
        "run_id": ctx.run_id,
        "files": len(inventory),
        "ocr_citations": len(ocr),
        "instruments": len(instruments),
        "quarantined": sum(
            row.get("status") == "QUARANTINED - REVIEW REQUIRED" for row in instruments
        ),
        "runsheet_rows": len(bundle.get("runsheet", [])),
        "run_dir": str(ctx.run_dir),
    }
