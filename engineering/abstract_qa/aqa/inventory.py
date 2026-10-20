"""Recursive, read-only inventory of folders and (nested) ZIPs with a stat-keyed resume cache."""
from __future__ import annotations

import io
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Iterator

from . import safety
from .util import sha256_stream

PDF_EXT = {".pdf"}
IMAGE_EXT = {".tif", ".tiff", ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".jp2"}
TABLE_EXT = {".ods", ".xlsx", ".xlsm", ".docx"}
ZIP_EXT = {".zip"}
SEP = "!/"


def display_path(root_label: str, rel: str, chain: list[str]) -> str:
    return SEP.join([f"{root_label}/{rel}".replace("\\", "/")] + chain)


def pdf_info(source) -> dict[str, Any]:
    """Actual page count and embedded image count from file bytes (never from names/metadata claims)."""
    info: dict[str, Any] = {"pages": None, "images": None, "method": None, "error": None, "meta": {}}
    try:
        from pypdf import PdfReader

        rd = PdfReader(source)
        if rd.is_encrypted:
            try:
                rd.decrypt("")
            except Exception:
                info["error"] = "encrypted"
                return info
        info["pages"] = len(rd.pages)
        info["method"] = "pypdf"
        imgs = 0
        for pg in rd.pages:
            try:
                imgs += len(pg.images)
            except Exception:
                try:
                    xo = pg["/Resources"].get("/XObject", {})
                    imgs += sum(1 for k in xo if xo[k].get_object().get("/Subtype") == "/Image")
                except Exception:
                    pass
        info["images"] = imgs
        md = rd.metadata or {}
        info["meta"] = {k.lstrip("/"): str(v) for k, v in md.items()}
        sizes = {(round(float(p.mediabox.width)), round(float(p.mediabox.height))) for p in rd.pages}
        info["meta"]["_page_sizes"] = sorted(f"{w}x{h}" for w, h in sizes)[:10]
    except Exception as exc:  # fall back to a byte scan so a damaged xref still yields evidence
        info["error"] = f"{type(exc).__name__}: {exc}"[:200]
        try:
            if hasattr(source, "seek"):
                source.seek(0)
                data = source.read()
            else:
                data = Path(source).read_bytes()
            info["pages"] = len(re.findall(rb"/Type\s*/Page(?![A-Za-z])", data))
            info["images"] = len(re.findall(rb"/Subtype\s*/Image", data))
            info["method"] = "regex_fallback"
        except Exception:
            pass
    return info


def image_count(data: bytes) -> int:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as im:
            return int(getattr(im, "n_frames", 1))
    except Exception:
        return 1


def _entry(path: str, ext: str, size: int, sha: str | None, **kw: Any) -> dict[str, Any]:
    e = {
        "path": path, "ext": ext, "size": size, "sha256": sha, "crc32": None,
        "mtime_ns": None, "pdf_pages": None, "pdf_images": None, "pdf_method": None,
        "image_frames": None, "container": None, "errors": [], "meta": {}, "skipped": None,
    }
    e.update(kw)
    return e


def _walk_zip(zf: zipfile.ZipFile, label: list[str], base: str, depth: int, max_depth: int,
              max_parse: int, out: list[dict[str, Any]], zip_path: str) -> None:
    for zi in sorted(zf.infolist(), key=lambda z: z.filename):
        if zi.is_dir():
            continue
        name = zi.filename
        if name.startswith("/") or ".." in Path(name).parts:
            out.append(_entry(f"{base}{SEP}{name}", "", zi.file_size, None, container=zip_path,
                              skipped="unsafe_member_path", errors=["unsafe member path"]))
            continue
        ext = Path(name).suffix.lower()
        path = f"{base}{SEP}{name}"
        e = _entry(path, ext, zi.file_size, None, container=zip_path, crc32=f"{zi.CRC:08x}",
                   mtime_ns=None, meta={"zip_datetime": list(zi.date_time)})
        if zi.flag_bits & 0x1:
            e["skipped"] = "encrypted_member"
            e["errors"].append("encrypted member")
            out.append(e)
            continue
        try:
            with zf.open(zi) as fh:
                e["sha256"] = sha256_stream(fh)
            # zipfile verifies CRC at EOF while streaming; reaching here means it matched.
            need = ext in PDF_EXT or ext in IMAGE_EXT or ext in ZIP_EXT
            if need and zi.file_size <= max_parse:
                data = zf.read(zi)
                if ext in PDF_EXT:
                    _apply_pdf(e, io.BytesIO(data))
                elif ext in IMAGE_EXT:
                    e["image_frames"] = image_count(data)
                elif ext in ZIP_EXT and depth < max_depth:
                    out.append(e)
                    with zipfile.ZipFile(io.BytesIO(data)) as inner:
                        _walk_zip(inner, label, path, depth + 1, max_depth, max_parse, out, path)
                    continue
                elif ext in ZIP_EXT:
                    e["skipped"] = "zip_depth_limit"
            elif need:
                e["skipped"] = "too_large_to_parse"
        except zipfile.BadZipFile as exc:
            e["errors"].append(f"BadZipFile: {exc}")
        except Exception as exc:
            e["errors"].append(f"{type(exc).__name__}: {exc}"[:200])
        out.append(e)


def _apply_pdf(e: dict[str, Any], source) -> None:
    info = pdf_info(source)
    e["pdf_pages"], e["pdf_images"], e["pdf_method"] = info["pages"], info["images"], info["method"]
    e["meta"].update(info["meta"])
    if info["error"]:
        e["errors"].append(f"pdf: {info['error']}")


def _scan_file(full: Path, display: str, st: os.stat_result, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    ext = full.suffix.lower()
    if safety.is_placeholder(st):
        e = _entry(display, ext, st.st_size, None, mtime_ns=st.st_mtime_ns,
                   skipped="cloud_placeholder_not_read", errors=["cloud placeholder; not read to avoid hydration"])
        return [e]
    e = _entry(display, ext, st.st_size, None, mtime_ns=st.st_mtime_ns)
    try:
        with open(full, "rb") as fh:
            e["sha256"] = sha256_stream(fh)
        if ext in PDF_EXT:
            _apply_pdf(e, str(full))
        elif ext in IMAGE_EXT:
            e["image_frames"] = image_count(full.read_bytes()) if st.st_size <= cfg["max_parse_bytes"] else 1
        elif ext in ZIP_EXT:
            out.append(e)
            with zipfile.ZipFile(full) as zf:
                bad = zf.testzip()  # verifies every member CRC
                if bad:
                    e["errors"].append(f"zip CRC failure at member {bad}")
                _walk_zip(zf, [], display, 1, cfg["max_zip_depth"], cfg["max_parse_bytes"], out, display)
            return out
    except zipfile.BadZipFile as exc:
        e["errors"].append(f"BadZipFile: {exc}")
    except OSError as exc:
        e["errors"].append(f"OSError: {exc}")
        e["skipped"] = "unreadable"
    out.append(e)
    return out


def iter_files(root: Path) -> Iterator[tuple[Path, str]]:
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for fn in sorted(filenames):
            full = Path(dirpath) / fn
            yield full, full.relative_to(root).as_posix()


def run_inventory(cfg: dict[str, Any], cache_path: Path | None = None) -> dict[str, Any]:
    cache: dict[str, list[dict[str, Any]]] = {}
    if cache_path and cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                cache[rec["key"]] = rec["entries"]
    new_cache: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    stats_before: dict[str, tuple[int, int] | None] = {}
    hits = misses = 0
    for ri, root in enumerate(cfg["source_roots"]):
        rootp = Path(os.path.abspath(os.path.expanduser(root)))
        if not rootp.is_dir():
            continue
        label = f"root{ri}"
        for full, rel in iter_files(rootp):
            display = display_path(label, rel, [])
            if full.is_symlink():
                entries.append(_entry(display, full.suffix.lower(), 0, None, skipped="symlink_not_followed"))
                findings.append(safety.finding("WARN", "SYMLINK_SKIPPED", f"symlink not followed: {display}", path=display))
                continue
            try:
                st = full.stat()
            except OSError as exc:
                entries.append(_entry(display, full.suffix.lower(), 0, None, skipped="unstatable", errors=[str(exc)]))
                continue
            stats_before[str(full)] = (st.st_size, st.st_mtime_ns)
            key = f"{display}|{st.st_size}|{st.st_mtime_ns}"
            if key in cache:
                got = cache[key]
                hits += 1
            else:
                got = _scan_file(full, display, st, cfg)
                misses += 1
            new_cache.append({"key": key, "entries": got})
            entries.extend(got)
            findings.extend(safety.classify_name(display))
            for g in got:
                if g.get("skipped") == "cloud_placeholder_not_read":
                    findings.append(safety.finding("BLOCK", "CLOUD_PLACEHOLDER_UNHYDRATED",
                                                   f"online-only cloud placeholder was not read: {g['path']}", path=g["path"]))
                if g["size"] == 0 and not g.get("skipped"):
                    findings.append(safety.finding("WARN", "ZERO_BYTE_SOURCE", f"zero-byte file: {g['path']}", path=g["path"]))
                for err in g["errors"]:
                    findings.append(safety.finding("WARN", "SOURCE_READ_ERROR", f"{g['path']}: {err}", path=g["path"]))
    entries.sort(key=lambda e: e["path"])
    return {
        "entries": entries, "findings": findings, "stats_before": stats_before,
        "cache_records": new_cache, "cache_hits": hits, "cache_misses": misses,
    }


def save_cache(cache_path: Path, records: list[dict[str, Any]]) -> None:
    """Cache lives outside run dirs and is rewritten via temp + replace (it is derived data only)."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    os.replace(tmp, cache_path)


def open_entry_bytes(cfg: dict[str, Any], path: str) -> bytes:
    """Resolve a display path (``rootN/rel!/member!/member``) back to bytes, read-only."""
    parts = path.split(SEP)
    head = parts[0]
    label, rel = head.split("/", 1)
    root = cfg["source_roots"][int(label[4:])]
    full = Path(os.path.abspath(os.path.expanduser(root))) / rel
    if len(parts) == 1:
        return full.read_bytes()
    data = full.read_bytes()
    for member in parts[1:]:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            data = zf.read(member)
    return data
