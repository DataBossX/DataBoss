# Start, Stop, and Backup

`START_DATABOSS_TITLE_INTELLIGENCE.bat` validates `.venv` and `DATABOSS_AUTH_DB`, rejects a duplicate recorded process, launches authenticated Streamlit on `http://127.0.0.1:8501`, logs stdout/stderr, and records its PID under `.runtime`.

`OPEN_DATABOSS_TITLE_INTELLIGENCE.bat` opens that loopback URL only when the recorded process matches the DataBoss serve command. `STOP_DATABOSS_TITLE_INTELLIGENCE.bat` stops only the numeric PID from that file and refuses a command-line mismatch. It is not a general process killer.

`BACKUP_DATABOSS_TITLE_INTELLIGENCE.bat` archives only generated `.runtime\config`, the local auth database, and `DataBoss_Title_Factory_Output` under the configured project. It deliberately does not archive the source corpus. Backups are written to `.runtime\backups`; copy them to approved protected storage and test restore separately.

Review `.runtime\logs` after every operation. Do not expose port 8501 through firewall, proxy, tunnel, or port forwarding.
