==============================================================================
 HorizonTitleLinkExtractor - SIMPLE GUIDE (for non-coders)
==============================================================================

WHAT THIS DOES
--------------
It opens your Horizon title/runsheet Excel file from Google Drive, opens each
document link, clicks "View" to see the real county document, takes a picture
of the document, asks AI to read it, compares it to your spreadsheet, and
writes its suggestions into a NEW review workbook.

It NEVER changes your original file. It only adds "AI Suggested..." columns to
a copy and color-codes the rows:
   GREEN  = looks correct, high confidence.
   YELLOW = possible correction, please check.
   RED    = could not read it (failed link, blocked, expired login, blurry).

You stay in control. Nothing is "auto-fixed" by default.


==============================================================================
 STEP 0 (DO THIS FIRST): LOCK DOWN THE GOOGLE DRIVE FOLDER
==============================================================================
Open the "Horizon Work" folder in Google Drive in your web browser.
Click Share. If it says "Anyone with the link - Editor", CHANGE IT.

   * Set it to "Restricted", OR
   * Set link access to "Viewer" only.
   * Give EDIT/WRITE access only to YOU (or your automation account).

Why: "Anyone with the link can edit" means strangers could change or delete
your title files. This tool will also warn you if it detects this.


==============================================================================
 STEP 1: PUT YOUR API KEYS IN .env
==============================================================================
1. Find the file called  .env.example  in this folder.
2. Make a copy and rename the copy to just   .env
3. Open .env in Notepad.
4. Paste your OpenAI key after  OPENAI_API_KEY=
   (Gemini and Anthropic keys are optional second-opinion validators.)
5. (Optional) For Google Drive:
      - Easiest: set GOOGLE_DRIVE_LOCAL_SYNC_PATH to your synced Horizon Work
        folder path, e.g.  G:\My Drive\Horizon Work
      - Advanced: set GOOGLE_OAUTH_CLIENT_SECRET_JSON to your OAuth file.
6. Save and close.

NEVER share your .env file. It contains your private keys.


==============================================================================
 STEP 2: INSTALL
==============================================================================
Double-click   INSTALL.bat
Wait for it to finish (it sets up Python, libraries, and the browser).


==============================================================================
 STEP 3: LOG INTO COUNTY RECORDS
==============================================================================
Double-click   RUN_LOGIN_SETUP.bat
A browser window opens.
   1. Go to your county-records website.
   2. Log in completely (until you can see records).
   3. Close the browser window ONLY AFTER you are fully logged in.

This saves your login locally so the tool can open documents.

*** SECURITY WARNING about .auth\county_state.json ***
   - This file may contain your login cookies.
   - Do NOT upload it.
   - Do NOT email it.
   - Do NOT commit it to git.
   - Do NOT share it with anyone.
   - Keep it on this computer only.


==============================================================================
 STEP 3b (RECOMMENDED): CHECK EVERYTHING IS READY
==============================================================================
Double-click   RUN_DOCTOR.bat
It prints a checklist (Python, libraries, your API key, county login, Google
Drive, config). Fix anything marked [FAIL] before running a real job. Items
marked [WARN] are optional.


==============================================================================
 STEP 4: TEST ON 5 ROWS
==============================================================================
Double-click   RUN_TEST_5_ROWS.bat
When it finishes it prints where the output workbook was saved (the output\
folder). Open that workbook and look at the AI review columns on the right.


==============================================================================
 STEP 5: RUN THE FULL JOB
==============================================================================
If the test looked good, double-click   RUN_AI_REVIEW.bat
This processes the whole workbook. It keeps going even if some rows fail.


==============================================================================
 STEP 6: GET YOUR FINISHED FILE
==============================================================================
Find the finished workbook in the   output\   folder
(name ends in _AI_REVIEW_<date>.xlsx).

There is ALSO a friendly web-page report next to it:
   output\..._AI_REVIEW_..._REPORT.html
Double-click it to open a color-coded summary in your browser (green/yellow/red
rows, what changed, and the estimated AI cost for the run). The cost detail per
row is in   logs\cost.csv .

TIP: Re-running is cheap. The tool remembers documents it already read (cache),
so a second pass does not pay for the same images twice.

If Google Drive upload is configured, it is also uploaded into a timestamped
folder named _AI_Updated_Reports_YYYY-MM-DD_HHMM inside your Drive folder.
If not, double-click RUN_UPLOAD_OUTPUT.bat or follow the printed instructions
to upload it yourself.


==============================================================================
 WHAT IF SOMETHING GOES WRONG?
==============================================================================
 * "Login expired" message: just run RUN_LOGIN_SETUP.bat again.
 * A row is RED: open the link yourself and check it manually.
 * Check  logs\run_log.csv  to see what happened on every row.
 * Check  logs\errors.log   for technical errors.

Nothing is ever deleted or overwritten in your original file. You are safe to
re-run as many times as you like.
==============================================================================

 FOR DEVELOPERS (optional)
------------------------------------------------------------------------------
 * Run the test suite:   .venv\Scripts\python.exe -m pytest tests\ -q
 * Smarter matching: names ("ACME L.L.C." = "ACME LLC") and legal descriptions
   are compared with field-aware fuzzy logic, so trivial punctuation isn't
   flagged as a correction, while NW/4 vs NE/4 IS flagged (direction matters).
 * Images are auto-oriented, contrast-enhanced and upscaled before AI reads
   them; blurry/tiny captures are scored, flagged RED, and sent to validators.
 * AI reads are cached by image hash (.cache\) and every call's cost is logged.
==============================================================================
