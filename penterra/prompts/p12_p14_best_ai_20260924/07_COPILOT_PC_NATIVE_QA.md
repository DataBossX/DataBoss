# COPILOT — Windows PC native QA — paste on the PC

You are on the machine that has Excel, Word, Adobe, and the Penterra tree. You do not decide title. You prove the writer’s file survives real Office.

P12 tree: `C:\DataBoss\Penterra\Overtime\45N-76W Sec 12`

P14 tree: `C:\DataBoss\Penterra\Overtime\45N-76W Sec 14`

Do this for the one ZIP the orchestrator names:

1. Copy it to a new local folder `_AI_NATIVE_QA_20260924`. Do not open the copy that lives in the source PDF folders.
2. Record size and SHA-256 before Excel touches it.
3. Unzip. Open every ODS and XLSX in Excel. Open every DOCX in Word. If Excel offers to repair, stop and fail. Do not accept the repair.
4. Save, close, and reopen each file once. Hash the file after reopen. If the hash changed, save that new file as `AFTER_NATIVE_SAVE` and report both hashes. The writer must adopt or reject that save; you do not keep editing.
5. Export each index to PDF. Count pages. Confirm the header row repeats and no column prints as `###`.
6. Open the matching source PDF for every row the writer marked as changed. You only check that the cited file opens and the cited page exists. Gemini reads the words.
7. Search the PC tree, and only these extra roots if they exist, for a Contango-to-Brothers instrument that is not an SRP screenshot: the Section 14 folder, the Section 12 folder, and any `WYW-042622` folder. If you find a candidate, copy it out, hash it, and stop. Do not index it.
8. Do not delete source PDFs. Do not upload a file whose name contains FINAL.

Return a short receipt: paths, before-hash, after-hash, page counts, repair prompts, and any file you could not open.
