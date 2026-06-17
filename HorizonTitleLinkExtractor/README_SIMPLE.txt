============================================================================
  HorizonTitleLinkExtractor  -  SIMPLE GUIDE (for non-coders)
============================================================================

WHAT THIS TOOL DOES
-------------------
It reads your Excel title / runsheet workbook from the "Horizon Work"
Google Drive folder, opens each document link, looks at the real county
document with AI, and writes SUGGESTED corrections into NEW columns in a
COPY of the workbook. It NEVER changes your original file.

It is REVIEW ONLY by default. Nothing is auto-applied. You stay in control.


****  STEP 0 - SECURITY: LOCK DOWN YOUR GOOGLE DRIVE FOLDER  ****
----------------------------------------------------------------------------
Before doing anything else, check who can edit the "Horizon Work" folder.

If the folder is set to "Anyone with the link - Editor", ANYONE who gets
the link can change or delete your files. That is dangerous.

DO THIS:
  1. Open the folder in Google Drive.
  2. Click Share.
  3. Change "Anyone with the link" to:
        - "Restricted"  (best), OR
        - "Viewer" only (if you must share read access).
  4. Give EDIT access only to YOU and your authorized automation account.

The tool will also warn you on screen if it detects the folder is
world-writable.


WHAT YOU NEED ONCE
----------------------------------------------------------------------------
  - A Windows PC.
  - Python 3.11 or newer installed (https://www.python.org/downloads/ ,
    check "Add Python to PATH" during install).
  - An OpenAI API key (required).
  - Optional: a Gemini key and/or an Anthropic (Claude) key for double-checking.


STEP-BY-STEP
----------------------------------------------------------------------------
1. Lock down the Google Drive folder permissions (see STEP 0 above).

2. Put your API keys in the .env file.
      - After you run INSTALL.bat the first time, a file called ".env"
        is created for you.
      - Open ".env" in Notepad.
      - Paste your key after  OPENAI_API_KEY=
      - Save and close.

3. Double-click  INSTALL.bat
      - This sets everything up. Wait for it to say "INSTALL COMPLETE".

4. Double-click  RUN_LOGIN_SETUP.bat
      - A browser opens.

5. Log into the county records website manually in that browser.
      - Type your username and password, solve any captcha.
      - Make sure you can actually see records/search results.

6. Close the browser ONLY AFTER you are fully logged in.
      - Your session is saved so the tool can reuse your login.

7. Double-click  RUN_TEST_5_ROWS.bat
      - This processes just 5 rows as a test.
      - When done, it prints WHERE the output workbook was saved.

8. Open that output workbook and check the new "AI ..." columns on the
   right side.
      - GREEN  = AI agrees / high confidence.
      - YELLOW = AI found a possible correction - look at it.
      - RED    = something failed (bad link, blocked page, unreadable,
                 or login expired) - needs a human.

9. If the test looks good, double-click  RUN_AI_REVIEW.bat
      - This processes the whole workbook.

10. Find the finished workbook in the  output\  folder, and (if Drive
    upload is set up) inside a new timestamped folder in your Google
    Drive "Horizon Work" folder named like:
        _AI_Updated_Reports_2026-06-17_1430


OPTIONAL: UPLOAD LATER
----------------------------------------------------------------------------
If Drive upload was not configured when you ran the review, you can run
RUN_UPLOAD_OUTPUT.bat later, or just drag the file from output\ into the
Drive folder yourself. The tool always prints exact manual instructions.


****  SECURITY WARNINGS - PLEASE READ  ****
----------------------------------------------------------------------------
The file  .auth\county_state.json  may contain your LOGIN COOKIES.
  - Do NOT upload it anywhere.
  - Do NOT email it to anyone.
  - Do NOT commit it to GitHub or any code repository.
  - Do NOT share it.
  - Keep it on your local machine only.

The file  .env  contains your API keys. Treat it the same way:
  - Keep it private. Never share or commit it.

This tool will NEVER:
  - Overwrite your original workbook.
  - Permanently save county document images (unless you turn on debug mode).
  - Change a cell unless you deliberately turn on apply_corrections in
    config.yaml (it is OFF by default).


IF SOMETHING GOES WRONG
----------------------------------------------------------------------------
  - "login expired" in red rows  -> run RUN_LOGIN_SETUP.bat again.
  - Many RED rows                -> check your internet and county login.
  - Check  logs\run_log.csv      -> one line per row, with the reason.
  - Check  logs\errors.log       -> technical error details.

The tool keeps going after failures, so one bad row will not stop the job.
============================================================================
