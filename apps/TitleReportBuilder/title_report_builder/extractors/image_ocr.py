"""Image preprocessing + OCR. Preprocessing (grayscale, autocontrast, sharpen,
optional 180deg rotate) materially improves vision/OCR on faded scans."""
from __future__ import annotations


def preprocess(in_path: str, out_path: str, contrast: float = 1.6,
               rotate180: bool = False, max_width: int = 2600) -> str:
    from PIL import Image, ImageOps, ImageFilter, ImageEnhance
    img = Image.open(in_path).convert("L")
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = img.filter(ImageFilter.SHARPEN)
    if rotate180:
        img = img.rotate(180)
    w, h = img.size
    if w > max_width:
        img = img.resize((max_width, int(h * max_width / w)), Image.LANCZOS)
    img.save(out_path, optimize=True)
    return out_path


def ocr_image(path: str, psm: int = 6) -> str:
    import pytesseract
    from PIL import Image
    return pytesseract.image_to_string(Image.open(path), config=f"--psm {psm}")
