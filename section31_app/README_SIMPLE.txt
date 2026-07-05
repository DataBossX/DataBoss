========================================================================
 SECTION 31-12N-24W ROGER MILLS -- OWNERSHIP & TITLE REPORT MACHINE
========================================================================

WHAT THIS IS
------------
A small desktop app that finds, compares, updates, validates, exports, and
organizes the best Section 31 title/ownership workbook. The workbook is the
product. The app is the machine that keeps making it better.

The one file you care about ends up here, alone, in your main folder:
  D:\Desktop\Horizon\Roger Mills\
    SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx


THE 30-SECOND START (WINDOWS)
-----------------------------
1. Double-click:  Launch_Section31_Report_App.bat
   (a copy is placed on your Desktop the first time you run it)
2. The launcher will, automatically:
      - find your Python (or tell you to install it)
      - create a private virtual environment (.venv)
      - install the needed packages the first time
      - create the D:\Desktop\Horizon\Roger Mills folder + subfolders
      - open the dashboard in your web browser
3. In the browser:
      - Tab 1: click "Scan now" to find Section 31 files
      - Tab 2: click "Build / update the final workbook"
      - Tab 3: review QA, spend, totals, and download the workbook


WHERE TO PUT YOUR FILES
-----------------------
Drop source files into these subfolders (created for you):
  _candidate_workbooks   your XLSX workbooks and runsheets
  _source_images         recorded document PDFs / TIFFs
The app scans them every run and merges the best data forward.


FOLDER LAYOUT (created automatically)
-------------------------------------
D:\Desktop\Horizon\Roger Mills\
  SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx   <- the product
  _section31_app\          app code
  _candidate_workbooks\    input workbooks / runsheets
  _source_images\          document images
  _archive\                non-final files moved here after each run
  _qa\                     QA log + completion note
  _logs\                   run log (secrets scrubbed) + spend log
  _exports\                a timestamped copy of every export


WHAT IT DOES, IN ORDER
----------------------
 1. Scan local folders (and Google Drive if you turn it on).
 2. Rank candidate workbooks and pick the best base.
 3. Merge the best data from every workbook's tabs.
 4. Treat the runsheet legal descriptions/notes as the controlling fallback.
 5. Crosswalk runsheet legals to OGL legals (fuzzy match).
 6. Push the matched OGL number onto tract / title / working-interest records.
 7. Track title ownership: net acres, royalty, owner addresses, lease status.
 8. Track leasehold / working interest by OGL and assignment chain.
 9. Pull well data (OKCountyRecords / OCC when configured) into a Wells sheet.
10. Enforce a hard $100 image-spend cap; log every purchase.
11. Run QA checks and write a QA log.
12. Export the final XLSX and keep a timestamped copy.
13. Archive all non-final files, leaving only the final workbook in the folder.


SECRETS
-------
Optional keys go in a ".env" file next to the app (copy .env.example).
The app loads it automatically and NEVER prints secret values -- the
dashboard shows only whether each key is "set" or "not set".
Nothing is required: with no .env at all the app runs local-first.


RUN IT WITHOUT THE DASHBOARD (optional)
---------------------------------------
  python -m section31_app --root "D:\Desktop\Horizon\Roger Mills"

Add --drive to enable the Google Drive fallback, or --no-archive to keep
non-final files in place.


TROUBLESHOOTING
---------------
- "Python was not found": install Python 3.10+ from python.org and check
  "Add Python to PATH" during setup, then re-run the .bat.
- First launch is slow: it's building the virtual environment and installing
  packages once. Later launches are fast.
- Nothing found on scan: make sure your workbooks are in the folder you point
  at (or in _candidate_workbooks), or enable the Google Drive fallback.
========================================================================
