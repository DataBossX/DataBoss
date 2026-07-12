# Install on Windows

Prerequisites: 64-bit Windows, Python 3.11 available through `py -3.11`, PowerShell, sufficient local disk, and Tesseract OCR on `PATH` for image OCR.

1. Clone the repository to a local path without client evidence.
2. Run `SETUP_DATABOSS_TITLE_INTELLIGENCE.bat`. It creates `.venv`, installs the local package and pinned dependencies, and writes `.runtime\logs\setup.log`.
3. Initialize `.runtime\databoss_auth.sqlite3` with:
   `".venv\Scripts\python.exe" -m databoss_title_factory auth init-db --database ".runtime\databoss_auth.sqlite3" --allow-root ".runtime"`
4. Set `DATABOSS_OWNER_USERNAME` and `DATABOSS_OWNER_PASSWORD`, then bootstrap the exact evidence-folder path as the project role binding using `auth bootstrap-owner`.
5. Set `DATABOSS_PROJECT_ROOT` to the mounted evidence folder. Run the health launcher before processing.

Installation does not mount evidence, configure Tesseract, create legal approvals, or process Section 32.
