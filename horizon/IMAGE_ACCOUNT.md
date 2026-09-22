# Image account, vision/OCR, and 13/15 format

Work date for this lane is **2026-09-22**. These runners count every
image, account for each one, queue vision before OCR, and format
isolated copies like Section 13 and Section 15. They never invent
legal, party, or recorded-date cells and never mark a package complete.

## Count every image

A raster file (`.png`, `.jpg`, `.tif`, …) is one image. Each PDF page
is one image. The PDF file is a container, not a second image. Other
files stay on the ledger so they cannot hide in the folder.

```bash
python3 -m horizon.image_account \
  --bind-dir /path/to/section-images \
  --packet-id SEC15-IMAGES-20260922 \
  --inventory \
  --output /path/to/image-account-packet.json \
  --vision-queue /path/to/section15-image-account-queue.json
```

`every_image_accounted` is true only when every raster and PDF page is
hashed, classified, and listed once. Empty-text faces stay held.

## Vision before OCR

```bash
python3 -m horizon.vision_ocr \
  --bind-dir /path/to/section-images \
  --packet-id SEC15-IMAGES-20260922 \
  --output /path/to/vision-ocr-receipt.json
```

`--allow-ocr` may run Tesseract on a raster region only. OCR text is
review-only. It is never copied into required abstract cells. This
cloud VM has no authenticated vision worker, so vision status stays
`unavailable` until a PC worker can see the faces.

## Format like Section 13 and 15

Match Section 15 by role, not facts. Isolated Letters are US Letter,
landscape, print titles on rows 1–8. Exact-N ZIP names use
`SUPERSEDING_TURNIN_DATED_20260922`.

```bash
python3 -m horizon.package_format \
  --workbook /path/to/isolated-index.xlsx \
  --letter-output /path/to/section15-letter.xlsx \
  --receipt /path/to/format-receipt.json

python3 -m horizon.package_format \
  --package-id P13 \
  --member county-index.xlsx \
  --member federal-index.xlsx \
  --member checklist.xlsx \
  --member cert.docx \
  --member sources.xlsx \
  --zip-output P13_45N-76W-13__SUPERSEDING_TURNIN_DATED_20260922_EXACT5.zip \
  --receipt /path/to/membership-receipt.json

python3 -m horizon.package_format --portfolio --receipt /path/to/portfolio.json
```

Frozen P15 and closed P10 must not be rebuilt. UNKNOWN counts stay
UNKNOWN until a bind-dir is measured.

## Improvement-loop tournament

```bash
python3 -m horizon.tournament_loop \
  --bind-dir /path/to/section-images \
  --packet-id SEC15-TOURNAMENT-20260922 \
  --workbook /path/to/isolated-index.xlsx \
  --letter-dir /path/to/isolated-letters \
  --max-loops 10 \
  --output /path/to/tournament-receipt.json
```

Each pass re-counts images, queues vision, applies the Letter contract,
and scores challengers. The loop stops when images are unaccounted, no
new defects are found, or 10 passes complete. `packages_complete` stays
false.

Finish accepts the same bind-dir:

```bash
python3 -m horizon.package_finish \
  --section 15 --section 13 --section 11 \
  --image-bind-dir /path/to/section-images \
  --output /path/to/package-finish-receipt.json
```
