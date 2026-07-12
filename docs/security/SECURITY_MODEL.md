# Security Model

The application is local-first and fail-closed. Streamlit binds only to `127.0.0.1`; launch requires an existing local authentication database. Sessions and project-scoped roles gate viewing and processing. Paths must resolve inside an explicit allowed root, including after symlink resolution.

Source files are opened read-only by workflow code, hashed at inventory, and checked again before processing. Outputs use separate versioned directories. Spreadsheet exports escape formula-like CSV values, verify workbook structure, and never overwrite a source template. ZIP validation rejects traversal, encryption, and configured bomb limits.

The Windows stop launcher reads one PID file and refuses to stop a process whose command line is not the DataBoss `serve` command. These controls reduce risk but do not provide host isolation, disk encryption, enterprise identity, malware scanning, or a formal compliance certification.
