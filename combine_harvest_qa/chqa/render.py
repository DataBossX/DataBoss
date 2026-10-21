"""Render real pages (LibreOffice -> PDF -> PNG via Poppler) and compare candidate vs donor visually."""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile
from typing import Optional

from PIL import Image, ImageChops

from .findings import Report


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def to_pdf(src: str, out_dir: str, timeout: int = 180) -> Optional[str]:
    """Render any Office/ODS file to PDF with headless LibreOffice. Returns None if unavailable."""
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return None
    os.makedirs(out_dir, exist_ok=True)
    profile = tempfile.mkdtemp(prefix="lo_profile_")
    try:
        subprocess.run([exe, f"-env:UserInstallation=file://{profile}", "--headless", "--convert-to", "pdf",
                        "--outdir", out_dir, src], check=True, timeout=timeout, capture_output=True)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    pdf = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + ".pdf")
    return pdf if os.path.exists(pdf) else None


def pdf_to_pngs(pdf: str, out_dir: str, dpi: int = 80, first: int = 1, last: Optional[int] = None) -> list[str]:
    if not have("pdftoppm"):
        return []
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, os.path.splitext(os.path.basename(pdf))[0])
    cmd = ["pdftoppm", "-png", "-r", str(dpi), "-f", str(first)] + (["-l", str(last)] if last else []) + [pdf, stem]
    subprocess.run(cmd, check=True, capture_output=True)
    return sorted(glob.glob(stem + "*.png"))


def image_diff(a: str, b: str, diff_out: Optional[str] = None) -> float:
    """Return fraction of differing pixels (0..1) after padding to a common canvas."""
    ia, ib = Image.open(a).convert("L"), Image.open(b).convert("L")
    w, h = max(ia.width, ib.width), max(ia.height, ib.height)
    ca, cb = Image.new("L", (w, h), 255), Image.new("L", (w, h), 255)
    ca.paste(ia), cb.paste(ib)
    d = ImageChops.difference(ca, cb).point(lambda v: 255 if v > 40 else 0)
    n = sum(1 for v in d.getdata() if v)
    if diff_out:
        d.save(diff_out)
    return n / float(w * h)


def compare_renders(cand_pdf: str, donor_pdf: str, out_dir: str, rep: Report, pages: int = 3, threshold: float = 0.02,
                    dpi: int = 80) -> list[dict]:
    """Page-by-page pixel comparison of the first `pages` pages. Layout drift above threshold is a finding.
    Note: different row counts legitimately change page content; this is an engineered-layout check
    (header block, column grid, borders), so compare page 1 for the pass/fail signal."""
    if not have("pdftoppm"):
        rep.skipped.append("visual comparison: pdftoppm not available")
        return []
    ca = pdf_to_pngs(cand_pdf, os.path.join(out_dir, "cand"), dpi, 1, pages)
    do = pdf_to_pngs(donor_pdf, os.path.join(out_dir, "donor"), dpi, 1, pages)
    results = []
    for i, (a, b) in enumerate(zip(ca, do), 1):
        diff_png = os.path.join(out_dir, f"diff_page{i}.png")
        frac = image_diff(a, b, diff_png)
        results.append({"page": i, "diff_fraction": round(frac, 5), "candidate": a, "donor": b, "diff": diff_png})
        if i == 1 and frac > threshold:
            rep.add("visual_diff", "warn", cand_pdf, "page 1 differs visibly from donor render", cell="page 1",
                    expected=f"<= {threshold}", actual=str(round(frac, 5)))
    return results
