"""
drive_sync.py
=============
Google Drive input/output with two modes:

  Mode A - Google Drive Desktop sync:
      If GOOGLE_DRIVE_LOCAL_SYNC_PATH is set, read the source workbook from the
      locally synced folder and write the output into a timestamped subfolder
      there. Google Drive Desktop handles the upload automatically.

  Mode B - Google Drive API:
      Authenticate (service account or OAuth), list the Drive folder, pick the
      latest non-AI-review workbook, download it, create a timestamped AI output
      folder, and upload the review workbook + logs + summary.

If neither write path is configured, the tool still produces local output and
prints exact manual-upload instructions.

This module also implements the SECURITY CHECK that warns when the Drive folder
is writable by "anyone with the link".
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

log = logging.getLogger("horizon.drive")

EXCLUDE_TOKENS = ["ai_review", "_ai_updated", "backup", "temp", "logs", "debug"]
PREFER_TOKENS = ["cursory title report", "roger mills", "31-12n-24w"]


def extract_folder_id(url: str) -> Optional[str]:
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", url or "")
    return m.group(1) if m else None


@dataclass
class WorkbookCandidate:
    name: str
    path: Optional[str] = None  # local path (Mode A) or download target
    file_id: Optional[str] = None  # Drive file id (Mode B)
    modified: float = 0.0  # epoch seconds


def _is_excluded(name: str) -> bool:
    low = name.lower()
    return any(tok in low for tok in EXCLUDE_TOKENS)


def _score(name: str) -> int:
    low = name.lower()
    return sum(1 for tok in PREFER_TOKENS if tok in low)


def select_workbook(
    candidates: List[WorkbookCandidate], name_override: Optional[str]
) -> Optional[WorkbookCandidate]:
    """Pick the source workbook per the configured strategy."""
    xlsx = [c for c in candidates if c.name.lower().endswith((".xlsx", ".xlsm"))]
    if name_override:
        for c in xlsx:
            if c.name == name_override:
                return c
        log.warning("source_workbook_name_override '%s' not found.", name_override)

    usable = [c for c in xlsx if not _is_excluded(c.name)]
    if not usable:
        return None
    # Prefer matching tokens, then newest modified date.
    usable.sort(key=lambda c: (_score(c.name), c.modified), reverse=True)
    return usable[0]


def timestamped_folder_name(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y-%m-%d_%H%M')}"


# ===========================================================================
# Base interface
# ===========================================================================


class DriveBackend:
    mode = "none"

    def list_candidates(self) -> List[WorkbookCandidate]:
        raise NotImplementedError

    def download(self, candidate: WorkbookCandidate, dest_dir: str) -> str:
        raise NotImplementedError

    def upload_outputs(self, files: List[str], folder_prefix: str) -> Optional[str]:
        """Upload files into a timestamped folder. Returns destination desc."""
        raise NotImplementedError

    def security_check(self) -> Optional[str]:
        """Return a warning string if the folder is anyone-with-link writer."""
        return None


# ===========================================================================
# Mode A - Google Drive Desktop (local synced folder)
# ===========================================================================


class LocalSyncBackend(DriveBackend):
    mode = "drive_desktop"

    def __init__(self, sync_path: str):
        self.sync_path = sync_path

    def list_candidates(self) -> List[WorkbookCandidate]:
        out: List[WorkbookCandidate] = []
        if not os.path.isdir(self.sync_path):
            log.error("GOOGLE_DRIVE_LOCAL_SYNC_PATH does not exist: %s", self.sync_path)
            return out
        for name in os.listdir(self.sync_path):
            full = os.path.join(self.sync_path, name)
            if os.path.isfile(full) and name.lower().endswith((".xlsx", ".xlsm")):
                out.append(
                    WorkbookCandidate(
                        name=name, path=full, modified=os.path.getmtime(full)
                    )
                )
        return out

    def download(self, candidate: WorkbookCandidate, dest_dir: str) -> str:
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, candidate.name)
        shutil.copy2(candidate.path, dest)
        log.info("Copied source workbook from Drive Desktop folder -> %s", dest)
        return dest

    def upload_outputs(self, files: List[str], folder_prefix: str) -> Optional[str]:
        folder = os.path.join(self.sync_path, timestamped_folder_name(folder_prefix))
        os.makedirs(folder, exist_ok=True)
        for f in files:
            if f and os.path.exists(f):
                shutil.copy2(f, os.path.join(folder, os.path.basename(f)))
        log.info("Wrote outputs to Drive Desktop folder: %s", folder)
        return folder

    def security_check(self) -> Optional[str]:
        # Local sync cannot inspect sharing settings via the filesystem.
        return None


# ===========================================================================
# Mode B - Google Drive API
# ===========================================================================


class DriveApiBackend(DriveBackend):
    mode = "drive_api"

    SCOPES = ["https://www.googleapis.com/auth/drive"]

    def __init__(self, folder_id: str):
        self.folder_id = folder_id
        self.service = self._build_service()

    def _build_service(self):
        from googleapiclient.discovery import build

        creds = self._load_credentials()
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    def _load_credentials(self):
        # Prefer a service account; fall back to OAuth client secret + token cache.
        sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if sa_path and os.path.exists(sa_path):
            from google.oauth2 import service_account

            return service_account.Credentials.from_service_account_file(
                sa_path, scopes=self.SCOPES
            )

        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_JSON")
        if client_secret and os.path.exists(client_secret):
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials

            token_path = ".auth/google_token.json"
            creds = None
            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        client_secret, self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                os.makedirs(".auth", exist_ok=True)
                with open(token_path, "w", encoding="utf-8") as fh:
                    fh.write(creds.to_json())
            return creds

        raise RuntimeError(
            "No Google credentials. Set GOOGLE_APPLICATION_CREDENTIALS or "
            "GOOGLE_OAUTH_CLIENT_SECRET_JSON in .env, or use Drive Desktop mode."
        )

    def list_candidates(self) -> List[WorkbookCandidate]:
        out: List[WorkbookCandidate] = []
        q = f"'{self.folder_id}' in parents and trashed=false"
        page_token = None
        while True:
            resp = (
                self.service.files()
                .list(
                    q=q,
                    fields="nextPageToken, files(id, name, modifiedTime, mimeType)",
                    pageToken=page_token,
                    pageSize=200,
                )
                .execute()
            )
            for f in resp.get("files", []):
                name = f["name"]
                if not name.lower().endswith((".xlsx", ".xlsm")):
                    continue
                mod = self._parse_time(f.get("modifiedTime"))
                out.append(
                    WorkbookCandidate(name=name, file_id=f["id"], modified=mod)
                )
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return out

    @staticmethod
    def _parse_time(s: Optional[str]) -> float:
        if not s:
            return 0.0
        try:
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()
        except ValueError:
            try:
                return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").timestamp()
            except ValueError:
                return 0.0

    def download(self, candidate: WorkbookCandidate, dest_dir: str) -> str:
        from googleapiclient.http import MediaIoBaseDownload

        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, candidate.name)
        request = self.service.files().get_media(fileId=candidate.file_id)
        with open(dest, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        log.info("Downloaded source workbook from Drive -> %s", dest)
        return dest

    def upload_outputs(self, files: List[str], folder_prefix: str) -> Optional[str]:
        from googleapiclient.http import MediaFileUpload

        meta = {
            "name": timestamped_folder_name(folder_prefix),
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [self.folder_id],
        }
        folder = self.service.files().create(body=meta, fields="id, name").execute()
        folder_id = folder["id"]
        for f in files:
            if not f or not os.path.exists(f):
                continue
            media = MediaFileUpload(f, resumable=True)
            self.service.files().create(
                body={"name": os.path.basename(f), "parents": [folder_id]},
                media_body=media,
                fields="id",
            ).execute()
            log.info("Uploaded %s to Drive folder %s", os.path.basename(f), folder["name"])
        return f"Drive folder: {folder['name']} (id={folder_id})"

    def security_check(self) -> Optional[str]:
        """Warn if the folder allows anyone-with-link write access."""
        try:
            perms = (
                self.service.permissions()
                .list(fileId=self.folder_id, fields="permissions(id,type,role)")
                .execute()
            )
        except Exception as exc:
            log.debug("Could not read folder permissions: %s", exc)
            return None
        for p in perms.get("permissions", []):
            if p.get("type") == "anyone" and p.get("role") in (
                "writer",
                "owner",
                "fileOrganizer",
                "organizer",
            ):
                return (
                    "SECURITY WARNING: the Google Drive folder is shared as "
                    "'Anyone with the link' with WRITE access. Anyone with the "
                    "link can modify or delete your files. Change it to "
                    "'Restricted' or 'Viewer', and grant write access only to "
                    "you or your automation account."
                )
        return None


# ===========================================================================
# Factory
# ===========================================================================


def build_backend(config: dict) -> DriveBackend:
    """Choose Mode A or Mode B based on environment, or a no-op local backend."""
    sync_path = os.getenv("GOOGLE_DRIVE_LOCAL_SYNC_PATH", "").strip()
    if sync_path:
        log.info("Using Google Drive Desktop mode: %s", sync_path)
        return LocalSyncBackend(sync_path)

    folder_id = extract_folder_id(config.get("drive_folder_url", ""))
    has_api = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv(
        "GOOGLE_OAUTH_CLIENT_SECRET_JSON"
    )
    if folder_id and has_api:
        try:
            log.info("Using Google Drive API mode (folder %s)", folder_id)
            return DriveApiBackend(folder_id)
        except Exception as exc:
            log.error("Drive API init failed (%s); falling back to local-only.", exc)

    log.warning("Google Drive write/upload is NOT configured - local output only.")
    return DriveBackend()  # no-op base; caller handles local-only output
