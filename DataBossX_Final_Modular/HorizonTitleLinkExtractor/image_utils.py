"""
image_utils.py
==============
In-memory document image preprocessing + quality scoring.

Better pixels => better vision extraction. Before an image is sent to the AI we:
  * respect EXIF orientation (phones/scanners rotate),
  * convert to grayscale + auto-contrast (county scans are low-contrast),
  * sharpen slightly,
  * upscale tiny crops so small print is legible,
  * compute a blur/quality score so unreadable captures get flagged RED and
    routed to validators instead of silently producing garbage.

Pillow-only (no numpy / OpenCV) so it installs cleanly on plain Windows.
Everything stays in memory; bytes in, bytes out.
"""

from __future__ import annotations

import io
import logging
import statistics
from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageOps

log = logging.getLogger("horizon.image")

# A 3x3 discrete Laplacian; variance of its response approximates focus/sharpness.
_LAPLACIAN = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1)

MIN_GOOD_DIM = 1000        # below this we upscale
BLUR_VAR_FLOOR = 60.0      # Laplacian variance below this == likely too blurry


@dataclass
class ImageQuality:
    width: int
    height: int
    sharpness: float       # Laplacian variance (higher = sharper)
    blurry: bool
    too_small: bool
    score: float           # 0..1 overall readability estimate

    @property
    def is_poor(self) -> bool:
        return self.blurry or self.score < 0.45


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def _sharpness(img: Image.Image) -> float:
    gray = img.convert("L")
    # Downscale very large images so the metric is fast and resolution-stable.
    if max(gray.size) > 1400:
        ratio = 1400 / max(gray.size)
        gray = gray.resize((max(1, int(gray.width * ratio)),
                            max(1, int(gray.height * ratio))))
    edges = gray.filter(_LAPLACIAN)
    try:  # Pillow >= 11.3 renamed getdata -> get_flattened_data
        pixels = list(edges.get_flattened_data())
    except AttributeError:
        pixels = list(edges.getdata())
    if len(pixels) < 2:
        return 0.0
    try:
        return statistics.pvariance(pixels)
    except statistics.StatisticsError:
        return 0.0


def assess_quality(data: bytes) -> ImageQuality:
    """Score an image without modifying it."""
    img = _open(data)
    w, h = img.size
    sharp = _sharpness(img)
    too_small = max(w, h) < MIN_GOOD_DIM
    blurry = sharp < BLUR_VAR_FLOOR
    # Map sharpness to ~0..1 with a soft knee around the floor.
    sharp_score = min(1.0, sharp / (BLUR_VAR_FLOOR * 4))
    size_score = min(1.0, max(w, h) / MIN_GOOD_DIM)
    score = round(0.7 * sharp_score + 0.3 * size_score, 3)
    return ImageQuality(w, h, round(sharp, 2), blurry, too_small, score)


def enhance(data: bytes, upscale: bool = True) -> bytes:
    """Return preprocessed PNG bytes optimized for OCR/vision legibility."""
    try:
        img = _open(data)
        img = ImageOps.exif_transpose(img)          # honor orientation
        img = img.convert("L")                       # grayscale
        img = ImageOps.autocontrast(img, cutoff=1)   # stretch contrast
        img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120,
                                                 threshold=3))
        if upscale and max(img.size) < MIN_GOOD_DIM:
            factor = MIN_GOOD_DIM / max(img.size)
            img = img.resize((int(img.width * factor), int(img.height * factor)),
                             Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception as exc:  # never let preprocessing break the pipeline
        log.warning("Image enhance failed, using original bytes: %s", exc)
        return data


def prepare_for_ai(images: list[bytes]) -> tuple[list[bytes], ImageQuality | None]:
    """Enhance every page and return (enhanced_pages, worst_quality).

    worst_quality lets the caller flag poor captures and force validation.
    """
    enhanced: list[bytes] = []
    worst: ImageQuality | None = None
    for raw in images:
        try:
            q = assess_quality(raw)
            if worst is None or q.score < worst.score:
                worst = q
        except Exception:
            q = None
        enhanced.append(enhance(raw))
    return enhanced, worst
