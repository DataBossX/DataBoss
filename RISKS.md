# Risks

## Release blockers

- The Section 32 production corpus and client template are absent from this environment.
- No approved workbook fingerprint or writable-range mapping exists.
- No human title, tract, OGL, WI, or map review has occurred.
- Excel COM and real-Excel repair-warning checks require the operator's Windows workstation.

## Technical risks

- OpenPyXL can alter unsupported workbook features if used to save a client
  workbook. Current export avoids that by byte-copying the template.
- Tesseract bounding boxes are OCR evidence, not proof that the recognized text
  is correct. Source-image review remains mandatory.
- Handwriting requires independent vision extraction and human confirmation.
- Native text sources cannot provide image coordinates; they remain page/row
  supported and cannot receive the same status as direct image-region support.
- Report-candidate scoring is triage only and requires human confirmation.
