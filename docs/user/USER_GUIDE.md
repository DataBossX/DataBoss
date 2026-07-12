# User Guide

Install and initialize local authentication first. Set `DATABOSS_PROJECT_ROOT`, start the app, and sign in with a role bound to that exact project path.

Use Inventory before OCR. Inventory creates a new run and source hashes. OCR works on generated image copies and creates cited records. Extract reconciles candidates against those records; Assemble creates draft schedules. Review all weak OCR, quarantine, conflicts, and missing-document rows. “Ready for review” is not approval.

The full pipeline creates a new run; Resume uses the latest run and validates checkpoints. Pause takes effect between stages. Template QA checks an existing workbook. Export creates an exact client-template copy plus a separate control workbook and remains “not ready to submit.”

Never place source evidence inside the repository, change evidence during a run, treat confidence as correctness, or deliver output without examiner and required legal/client approvals.
