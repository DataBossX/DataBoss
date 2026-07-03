#!/usr/bin/env python3
"""
Upload the generated Roger Mills report artifacts to a Google Drive folder.

Why this exists: the session's Drive MCP caps downloads at 10 MB and gates uploads
behind an interactive approval, so a byte-perfect push of large artifacts (HTML/PDF)
is unreliable from the agent. Run this locally with your own Google credentials to
upload the report files directly — no size cap, no per-call approval.

Setup (one time):
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
    # Option A (service account): set GOOGLE_APPLICATION_CREDENTIALS=/path/sa.json
    #   and share the target Drive folder with the service-account email.
    # Option B (OAuth): download an OAuth client_secret.json and set OAUTH_CLIENT=/path/client_secret.json

Usage:
    python scripts/upload_report_to_drive.py \
        --folder 1cmfCYsFkUoBXgo5fanDTOZsprtFZrGhc \
        reports/31-12N-24W_Roger_Mills_Mineral_and_Leasehold_Ownership_Report.pdf \
        reports/31-12N-24W_Roger_Mills_Mineral_and_Leasehold_Ownership_Report.html \
        reports/31-12N-24W_Roger_Mills_Mineral_and_Leasehold_Ownership_Report.md \
        reports/31-12N-24W_Index_OCR_Lead_Memo.md
"""
from __future__ import annotations
import argparse
import mimetypes
import os
import sys

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_service():
    from googleapiclient.discovery import build
    sa = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if sa and os.path.exists(sa):
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(sa, scopes=SCOPES)
        return build("drive", "v3", credentials=creds)
    client = os.getenv("OAUTH_CLIENT")
    if client and os.path.exists(client):
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import pickle
        token_path = os.path.expanduser("~/.drive_upload_token.pickle")
        creds = None
        if os.path.exists(token_path):
            creds = pickle.load(open(token_path, "rb"))
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds = InstalledAppFlow.from_client_secrets_file(client, SCOPES).run_local_server(port=0)
            pickle.dump(creds, open(token_path, "wb"))
        return build("drive", "v3", credentials=creds)
    sys.exit("No credentials. Set GOOGLE_APPLICATION_CREDENTIALS or OAUTH_CLIENT (see module docstring).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True, help="Destination Drive folder ID")
    ap.add_argument("files", nargs="+", help="Local files to upload")
    args = ap.parse_args()

    from googleapiclient.http import MediaFileUpload
    svc = get_service()
    for path in args.files:
        if not os.path.exists(path):
            print(f"skip (missing): {path}"); continue
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        meta = {"name": os.path.basename(path), "parents": [args.folder]}
        media = MediaFileUpload(path, mimetype=mime, resumable=True)
        f = svc.files().create(body=meta, media_body=media, fields="id,name,webViewLink").execute()
        print(f"uploaded {f['name']} -> {f.get('webViewLink', f['id'])}")


if __name__ == "__main__":
    main()
