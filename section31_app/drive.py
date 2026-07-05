"""Google Drive fallback client.

Local-first means Drive is only used when local sources are thin or the operator
opts in. This wrapper prefers the MCP/pydrive/google-api client that happens to
be available and degrades to a no-op (returning empty lists) when none is, so
the pipeline never crashes just because Drive isn't wired up.

Credentials are read from the environment only and never logged.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from .logbook import LogBook


class DriveClient:
    """Minimal, defensive Google Drive reader."""

    def __init__(self, log: Optional[LogBook] = None) -> None:
        self.log = log or LogBook()
        self.folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
        self._service = None

    def is_configured(self) -> bool:
        # Either a service-account file or an OAuth token env var.
        return bool(
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            or os.environ.get("GOOGLE_DRIVE_TOKEN")
            or self.folder_id
        )

    def _connect(self):
        if self._service is not None:
            return self._service
        try:
            from googleapiclient.discovery import build  # type: ignore
            from google.oauth2 import service_account  # type: ignore
        except Exception:
            self.log.warn("google-api-python-client not installed; "
                          "Drive fallback disabled")
            return None
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not cred_path or not Path(cred_path).exists():
            self.log.warn("no Google service-account credentials found")
            return None
        try:
            creds = service_account.Credentials.from_service_account_file(
                cred_path,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            self._service = build("drive", "v3", credentials=creds,
                                  cache_discovery=False)
            return self._service
        except Exception as exc:
            self.log.warn(f"Drive connect failed: {type(exc).__name__}")
            return None

    def list_files(self, name_contains: str = "31") -> List[Dict]:
        service = self._connect()
        if service is None:
            return []
        q = [f"name contains '{name_contains}'", "trashed = false"]
        if self.folder_id:
            q.append(f"'{self.folder_id}' in parents")
        try:
            resp = service.files().list(
                q=" and ".join(q),
                fields="files(id,name,mimeType,size,modifiedTime)",
                pageSize=200,
            ).execute()
            files = resp.get("files", [])
            self.log.info(f"Google Drive fallback listed {len(files)} files")
            return files
        except Exception as exc:
            self.log.warn(f"Drive list failed: {type(exc).__name__}")
            return []

    def download(self, file_id: str, dest: Path) -> Optional[Path]:
        service = self._connect()
        if service is None:
            return None
        try:
            from googleapiclient.http import MediaIoBaseDownload  # type: ignore
            import io

            dest = Path(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            request = service.files().get_media(fileId=file_id)
            buf = io.FileIO(str(dest), "wb")
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            buf.close()
            return dest
        except Exception as exc:
            self.log.warn(f"Drive download failed: {type(exc).__name__}")
            return None
