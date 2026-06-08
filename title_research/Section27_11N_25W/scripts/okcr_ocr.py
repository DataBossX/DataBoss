#!/usr/bin/env python3
"""
okcr_ocr.py - OCR every PDF pulled into records_raw/ by okcr_pull.py.

Cross-platform (Windows/macOS/Linux). Requires on PATH:
  - poppler  (pdftoppm / pdfinfo)   -> Windows: install poppler, add bin to PATH
  - tesseract                        -> Windows: UB-Mannheim tesseract installer
Falls back to PyMuPDF (pip: pymupdf) for rendering if poppler is missing.

Output:
  records_ocr/<stem>/page-NN.png   rendered page images
  records_ocr/<stem>.txt           concatenated OCR text per instrument
Never reads/writes any credential.
"""
import os, sys, subprocess, shutil, pathlib, glob
ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW, OCRD = ROOT/"records_raw", ROOT/"records_ocr"
OCRD.mkdir(parents=True, exist_ok=True)
DPI = 300

def have(x): return shutil.which(x) is not None

def render_poppler(pdf, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pdftoppm","-r",str(DPI),"-png",str(pdf),str(outdir/"page")],
                   check=True)
    return sorted(outdir.glob("page*.png"))

def render_pymupdf(pdf, outdir):
    import fitz  # pymupdf
    outdir.mkdir(parents=True, exist_ok=True)
    doc=fitz.open(str(pdf)); imgs=[]
    for i,pg in enumerate(doc, 1):
        p=outdir/f"page-{i:02d}.png"
        pg.get_pixmap(dpi=DPI).save(str(p)); imgs.append(p)
    return imgs

def ocr_image(png):
    if not have("tesseract"):
        return ""  # no OCR engine; images still saved for visual review
    out=str(png)+".txt"
    subprocess.run(["tesseract",str(png),str(png),"-l","eng","--psm","4"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return pathlib.Path(out).read_text(encoding="utf-8", errors="ignore") if os.path.exists(out) else ""

def main():
    pdfs=sorted(glob.glob(str(RAW/"*.pdf")))
    pdfs=[p for p in pdfs if pathlib.Path(p).name.lower()!="index.pdf"]
    if not pdfs:
        print("No instrument PDFs in records_raw/ (run okcr_pull.py first)."); return 1
    use_poppler = have("pdftoppm")
    if not use_poppler:
        try: import fitz  # noqa
        except Exception:
            print("ERROR: need poppler (pdftoppm) or `pip install pymupdf` to render PDFs."); return 2
    for pdf in pdfs:
        stem=pathlib.Path(pdf).stem
        imgs_dir=OCRD/stem
        imgs = render_poppler(pdf,imgs_dir) if use_poppler else render_pymupdf(pdf,imgs_dir)
        text="\n".join(ocr_image(i) for i in imgs)
        (OCRD/f"{stem}.txt").write_text(text, encoding="utf-8")
        tag = "OCR" if have("tesseract") else "images-only (install tesseract for text)"
        print(f"  {stem}: {len(imgs)} pages -> {tag}")
    print(f"Done. Text in records_ocr/*.txt . Next: verify_chain.py")
    return 0

if __name__=="__main__":
    sys.exit(main())
