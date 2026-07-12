# System Architecture

DataBoss Title Intelligence is a local Python workflow. Root launchers call the `.venv` interpreter and `databoss_title_factory.cli`. The CLI resolves allow-listed paths before calling `core.py`; `app.py` exposes the same operations through authenticated Streamlit on `127.0.0.1`.

Sources are read in place. Each run is written beneath the selected project's `DataBoss_Title_Factory_Output/runs/<run-id>` directory. `project_db.py` stores run, stage, and artifact-checkpoint state in SQLite. Hash checks stop processing if a source changes after inventory. OCR, candidate archives, reconciliation decisions, quarantine records, runsheets, and review packages are derived artifacts.

`auth.py` provides local users, sessions, project-scoped roles, and audit events. `security.py` supplies path, signature, filename, and archive controls. `release.py` is a deterministic lifecycle gate; it does not replace examiner approval.

Implemented integrations are local filesystem, SQLite, Tesseract, PyMuPDF, Pillow/OpenCV, openpyxl, and Streamlit. External model providers are policy structures only unless explicitly configured; the supplied Section 32 configuration disables them.
