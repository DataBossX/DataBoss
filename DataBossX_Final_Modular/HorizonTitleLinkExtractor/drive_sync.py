"""
drive_sync.py
=============
Google Drive input/output for HorizonTitleLinkExtractor.

Mode A - Google Drive Desktop:
  If GOOGLE_DRIVE_LOCAL_SYNC_PATH is set, use that locally synced folder.
  Source workbook is copied from there; output is written to a timestamped
  subfolder there and Drive Desktop syncs it automatically.

Mode B - Google Drive API (OAuth or service account):
  List the Drive folder, pick the latest non-AI-review workbook, download it,
  create a timestamped AI output folder, and upload outputs back to Drive.

If neither write path is configured, output is still produced locally and exact
manual-upload instructions are printed.

SECURITY: also exposes a permission check that warns if the Drive folder is
"anyone with the link can edit" (writer) and recommends locking it down.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import re
import shutil
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("horizon.drive")

# Names to EXCLUDE when picking a source workbook.
_EXCLUDE_TOKENS = ("ai_review", "_ai_updated", "backup", "temp", "logs", "debug")
# Names to PREFER (ranked higher when present).
_PREFER_TOKENS = ("cursory title report", "roger mills", "31-12n-24w")
_XLSX_RE = re.compile(r"\.xlsx?$", re.I)
_FOLDER_ID_RE = re.compile(r"/folders/([A-Za-z0-9_\-]+)")
_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


@dataclass
class Candidate:
    name: str
    path_or_id: str
    modified: float  # epoch seconds, larger = newer


def _timestamp_folder(prefix: str) -> str:
    now = _dt.datetime.now()
    return f"{prefix}_{now.strftime('%Y-%m-%d_%H%M')}"


def _score(name: str) -> tuple[int, int]:
    low = name.lower()
    excluded = any(tok in low for tok in _EXCLUDE_TOKENS)
    preferred = sum(1 for tok in _PREFER_TOKENS if tok in low)
    return (0 if excluded else 1, preferred)


def folder_id_from_url(url: str) -> str | None:
    m = _FOLDER_ID_RE.search(url or "")
    return m.group(1) if m else None


# =============================================================================
# Base interface
# =============================================================================
class DriveSync:
    """Factory + shared selection logic for both modes."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.folder_url = config.get("drive_folder_url", "")
        self.override = config.get("source_workbook_name_override")
        self.output_prefix = config.get("output_folder_prefix", "_AI_Updated_Reports")

    @staticmethod
    def create(config: dict[str, Any]) -> "DriveSync":
        local = os.getenv("GOOGLE_DRIVE_LOCAL_SYNC_PATH", "").strip()
        if local:
            log.info("Drive mode A (Desktop sync) -> %s", local)
            return LocalDriveSync(config, local)
        if (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_JSON")
                or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")):
            log.info("Drive mode B (API)")
            return ApiDriveSync(config)
        log.warning("No Drive configured -> local-only output mode.")
        return NullDriveSync(config)

    # subclasses implement these
    def list_candidates(self) -> list[Candidate]:
        raise NotImplementedError

    def download_source(self, dest_dir: str) -> str:
        raise NotImplementedError

    def upload_outputs(self, files: list[str]) -> str | None:
        raise NotImplementedError

    def check_permissions(self) -> dict[str, Any]:
        """Return {'configured': bool, 'public_writer': bool|None, 'message': str}."""
        return {"configured": False, "public_writer": None,
                "message": "Drive permission check not available in this mode."}

    # shared
    def select_source(self) -> Candidate | None:
        cands = self.list_candidates()
        cands = [c for c in cands if _XLSX_RE.search(c.name)]
        if not cands:
            return None
        if self.override:
            for c in cands:
                if c.name == self.override:
                    return c
            log.warning("Override '%s' not found; falling back to auto-select.",
                        self.override)
        eligible = [c for c in cands if _score(c.name)[0] == 1] or cands
        eligible.sort(key=lambda c: (_score(c.name)[1], c.modified), reverse=True)
        return eligible[0]


# =============================================================================
# Mode A - Google Drive Desktop (local synced folder)
# =============================================================================
class LocalDriveSync(DriveSync):
    def __init__(self, config: dict[str, Any], local_path: str):
        super().__init__(config)
        self.local_path = local_path

    def check_permissions(self) -> dict[str, Any]:
        return {
            "configured": True, "public_writer": None,
            "message": ("Using local synced folder. Verify the Drive folder "
                        "sharing in the Google Drive web UI is Restricted or "
                        "Viewer-only public, with write access only for you."),
        }

    def list_candidates(self) -> list[Candidate]:
        out: list[Candidate] = []
        if not os.path.isdir(self.local_path):
            log.error("Local sync path does not exist: %s", self.local_path)
            return out
        for name in os.listdir(self.local_path):
            full = os.path.join(self.local_path, name)
            if os.path.isfile(full) and _XLSX_RE.search(name):
                out.append(Candidate(name, full, os.path.getmtime(full)))
        return out

    def download_source(self, dest_dir: str) -> str:
        src = self.select_source()
        if not src:
            raise FileNotFoundError(
                f"No candidate .xlsx workbook found in {self.local_path}")
        print(f"[Drive] Selected source workbook: {src.name}")
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, src.name)
        shutil.copy2(src.path_or_id, dest)  # copy; never modify original
        return dest

    def upload_outputs(self, files: list[str]) -> str | None:
        out_folder = os.path.join(self.local_path, _timestamp_folder(self.output_prefix))
        os.makedirs(out_folder, exist_ok=True)
        for f in files:
            if f and os.path.exists(f):
                shutil.copy2(f, os.path.join(out_folder, os.path.basename(f)))
        print(f"[Drive] Output copied to synced folder: {out_folder}")
        print("[Drive] Google Drive Desktop will sync it automatically.")
        return out_folder


# =============================================================================
# Mode B - Google Drive API
# =============================================================================
class ApiDriveSync(DriveSync):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.folder_id = folder_id_from_url(self.folder_url)
        self._service = None
        self._out_folder_id: str | None = None

    def _svc(self):
        if self._service is not None:
            return self._service
        from googleapiclient.discovery import build

        sa = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if sa and os.path.exists(sa):
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(
                sa, scopes=_DRIVE_SCOPES)
        else:
            creds = self._oauth_creds()
        self._service = build("drive", "v3", credentials=creds,
                              cache_discovery=False)
        return self._service

    def _oauth_creds(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        token_path = ".auth/google_token.json"
        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_JSON")
        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, _DRIVE_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not client_secret or not os.path.exists(client_secret):
                    raise RuntimeError(
                        "GOOGLE_OAUTH_CLIENT_SECRET_JSON not set or file missing.")
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secret, _DRIVE_SCOPES)
                creds = flow.run_local_server(port=0)
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            with open(token_path, "w", encoding="utf-8") as fh:
                fh.write(creds.to_json())
        return creds

    def check_permissions(self) -> dict[str, Any]:
        if not self.folder_id:
            return {"configured": False, "public_writer": None,
                    "message": "Could not parse folder id from drive_folder_url."}
        try:
            perms = self._svc().permissions().list(
                fileId=self.folder_id,
                fields="permissions(id,type,role)",
                supportsAllDrives=True).execute().get("permissions", [])
        except Exception as exc:
            return {"configured": True, "public_writer": None,
                    "message": f"Could not read folder permissions: {exc}"}
        public_writer = any(
            p.get("type") == "anyone" and p.get("role") in ("writer", "owner")
            for p in perms)
        if public_writer:
            msg = ("SECURITY WARNING: This Drive folder allows 'Anyone with the "
                   "link' to EDIT. Change it to Restricted or Viewer-only public, "
                   "and grant write access only to you or the automation account.")
        else:
            msg = "Drive folder sharing looks acceptable (no public writer access)."
        return {"configured": True, "public_writer": public_writer, "message": msg}

    def list_candidates(self) -> list[Candidate]:
        if not self.folder_id:
            return []
        q = (f"'{self.folder_id}' in parents and trashed=false")
        fields = "files(id,name,modifiedTime,mimeType)"
        out: list[Candidate] = []
        page_token = None
        while True:
            resp = self._svc().files().list(
                q=q, fields=f"nextPageToken,{fields}", pageToken=page_token,
                includeItemsFromAllDrives=True, supportsAllDrives=True).execute()
            for f in resp.get("files", []):
                name = f["name"]
                if not _XLSX_RE.search(name):
                    continue
                ts = _dt.datetime.fromisoformat(
                    f["modifiedTime"].replace("Z", "+00:00")).timestamp()
                out.append(Candidate(name, f["id"], ts))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return out

    def download_source(self, dest_dir: str) -> str:
        from googleapiclient.http import MediaIoBaseDownload

        src = self.select_source()
        if not src:
            raise FileNotFoundError("No candidate workbook found in Drive folder.")
        print(f"[Drive] Selected source workbook: {src.name}")
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, src.name)
        request = self._svc().files().get_media(fileId=src.path_or_id)
        with open(dest, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return dest

    def _ensure_output_folder(self) -> str:
        if self._out_folder_id:
            return self._out_folder_id
        meta = {
            "name": _timestamp_folder(self.output_prefix),
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [self.folder_id],
        }
        folder = self._svc().files().create(
            body=meta, fields="id", supportsAllDrives=True).execute()
        self._out_folder_id = folder["id"]
        return self._out_folder_id

    def upload_outputs(self, files: list[str]) -> str | None:
        from googleapiclient.http import MediaFileUpload

        folder_id = self._ensure_output_folder()
        for f in files:
            if not (f and os.path.exists(f)):
                continue
            media = MediaFileUpload(f, resumable=True)
            self._svc().files().create(
                body={"name": os.path.basename(f), "parents": [folder_id]},
                media_body=media, fields="id", supportsAllDrives=True).execute()
        url = f"https://drive.google.com/drive/folders/{folder_id}"
        print(f"[Drive] Uploaded {len(files)} file(s) to: {url}")
        return url


# =============================================================================
# Null mode - no Drive configured (local output + manual instructions)
# =============================================================================
class NullDriveSync(DriveSync):
    def check_permissions(self) -> dict[str, Any]:
        return {"configured": False, "public_writer": None,
                "message": ("No Drive access configured. Set "
                            "GOOGLE_DRIVE_LOCAL_SYNC_PATH (Mode A) or "
                            "GOOGLE_OAUTH_CLIENT_SECRET_JSON (Mode B). "
                            "Still: lock the Drive folder to Restricted/Viewer.")}

    def list_candidates(self) -> list[Candidate]:
        # Fall back to any workbook already placed in input/.
        out: list[Candidate] = []
        for d in ("input", self.config.get("input_dir", "input")):
            if os.path.isdir(d):
                for name in os.listdir(d):
                    full = os.path.join(d, name)
                    if os.path.isfile(full) and _XLSX_RE.search(name):
                        out.append(Candidate(name, full, os.path.getmtime(full)))
        return out

    def download_source(self, dest_dir: str) -> str:
        src = self.select_source()
        if not src:
            raise FileNotFoundError(
                "Drive not configured and no .xlsx found in input/. "
                "Place the workbook in input/ or configure Drive in .env.")
        print(f"[Drive] Using local input workbook: {src.name}")
        if os.path.dirname(src.path_or_id) == os.path.abspath(dest_dir):
            return src.path_or_id
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, src.name)
        if os.path.abspath(src.path_or_id) != os.path.abspath(dest):
            shutil.copy2(src.path_or_id, dest)
        return dest

    def upload_outputs(self, files: list[str]) -> str | None:
        print("=" * 70)
        print(" Drive upload is NOT configured. Output saved locally only.")
        print(" To finish manually:")
        print("   1. Open the 'Horizon Work' Google Drive folder in your browser.")
        print(f"   2. Create a subfolder: {_timestamp_folder(self.output_prefix)}")
        print("   3. Upload these files into it:")
        for f in files:
            if f and os.path.exists(f):
                print(f"        {os.path.abspath(f)}")
        print("=" * 70)
        return None
