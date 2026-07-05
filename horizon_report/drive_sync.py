"""Google Drive synchronization for report outputs."""

import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any


class GoogleDriveSync:
    """Google Drive synchronization handler."""
    
    def __init__(self, logger, config):
        """Initialize Drive sync.
        
        Args:
            logger: Logger instance
            config: Configuration instance
        """
        self.logger = logger
        self.config = config
        self.mode = config.get_google_drive_mode()
    
    def sync_files(self, file_paths: List[Path]) -> Dict[str, Any]:
        """Sync files to Google Drive.
        
        Args:
            file_paths: List of file paths to sync
            
        Returns:
            Dictionary with sync results
        """
        if self.mode == "none":
            self.logger.info("Google Drive sync skipped - no configured sync path or API credentials")
            self.logger.info("To configure:")
            self.logger.info("  - Local sync: Set GOOGLE_DRIVE_SYNC_PATH in .env")
            self.logger.info("  - API sync: Set GOOGLE_DRIVE_FOLDER_ID and GOOGLE_SERVICE_ACCOUNT_JSON in .env")
            return {
                "status": "skipped",
                "mode": "none",
                "files_synced": 0,
                "message": "Google Drive not configured"
            }
        
        if self.mode == "local":
            return self._sync_local(file_paths)
        elif self.mode == "api":
            return self._sync_api(file_paths)
        
        return {"status": "error", "message": "Unknown sync mode"}
    
    def _sync_local(self, file_paths: List[Path]) -> Dict[str, Any]:
        """Sync files to local Google Drive folder.
        
        Args:
            file_paths: Files to sync
            
        Returns:
            Sync results
        """
        try:
            sync_path = self.config.google_drive_sync_path
            
            self.logger.info(f"Syncing {len(file_paths)} files to local Google Drive path: {sync_path}")
            
            synced_files = []
            for file_path in file_paths:
                if not file_path.exists():
                    self.logger.warning(f"File not found, skipping: {file_path}")
                    continue
                
                dest_path = sync_path / file_path.name
                
                # Copy file
                shutil.copy2(file_path, dest_path)
                
                # Verify copy
                if dest_path.exists() and dest_path.stat().st_size == file_path.stat().st_size:
                    synced_files.append(str(dest_path))
                    self.logger.info(f"  ✓ Copied: {file_path.name}")
                else:
                    self.logger.error(f"  ✗ Copy verification failed: {file_path.name}")
            
            result = {
                "status": "success",
                "mode": "local",
                "files_synced": len(synced_files),
                "synced_files": synced_files,
                "message": f"Successfully copied {len(synced_files)} files to Google Drive folder"
            }
            
            self.logger.info(f"Local sync complete: {len(synced_files)}/{len(file_paths)} files")
            return result
            
        except Exception as e:
            self.logger.error(f"Local sync failed: {e}")
            return {
                "status": "failed",
                "mode": "local",
                "files_synced": 0,
                "message": f"Local sync error: {e}"
            }
    
    def _sync_api(self, file_paths: List[Path]) -> Dict[str, Any]:
        """Sync files using Google Drive API.
        
        Args:
            file_paths: Files to sync
            
        Returns:
            Sync results
        """
        try:
            # Import Google API libraries
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            
            self.logger.info("Initializing Google Drive API...")
            
            # Load service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                str(self.config.google_service_account_json),
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            
            # Build Drive service
            service = build('drive', 'v3', credentials=credentials)
            
            folder_id = self.config.google_drive_folder_id
            self.logger.info(f"Uploading {len(file_paths)} files to Drive folder ID: {folder_id[:8]}...")
            
            uploaded_files = []
            for file_path in file_paths:
                if not file_path.exists():
                    self.logger.warning(f"File not found, skipping: {file_path}")
                    continue
                
                try:
                    # Prepare file metadata
                    file_metadata = {
                        'name': file_path.name,
                        'parents': [folder_id]
                    }
                    
                    # Determine MIME type
                    mime_type = self._get_mime_type(file_path)
                    
                    # Upload file
                    media = MediaFileUpload(
                        str(file_path),
                        mimetype=mime_type,
                        resumable=True
                    )
                    
                    file = service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id, name, webViewLink'
                    ).execute()
                    
                    uploaded_files.append({
                        "name": file.get('name'),
                        "id": file.get('id'),
                        "link": file.get('webViewLink', '')
                    })
                    
                    self.logger.info(f"  ✓ Uploaded: {file_path.name} (ID: {file.get('id')})")
                    
                except Exception as e:
                    self.logger.error(f"  ✗ Upload failed for {file_path.name}: {e}")
            
            result = {
                "status": "success",
                "mode": "api",
                "files_synced": len(uploaded_files),
                "uploaded_files": uploaded_files,
                "message": f"Successfully uploaded {len(uploaded_files)} files to Google Drive"
            }
            
            self.logger.info(f"API sync complete: {len(uploaded_files)}/{len(file_paths)} files")
            return result
            
        except ImportError:
            self.logger.error("Google API libraries not installed")
            self.logger.info("Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
            return {
                "status": "failed",
                "mode": "api",
                "files_synced": 0,
                "message": "Google API libraries not installed"
            }
        except Exception as e:
            self.logger.error(f"API sync failed: {e}")
            return {
                "status": "failed",
                "mode": "api",
                "files_synced": 0,
                "message": f"API sync error: {str(e)}"
            }
    
    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type for file.
        
        Args:
            file_path: File path
            
        Returns:
            MIME type string
        """
        mime_types = {
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.json': 'application/json',
        }
        
        return mime_types.get(file_path.suffix.lower(), 'application/octet-stream')
    
    def test_connection(self) -> bool:
        """Test Google Drive connection.
        
        Returns:
            True if connection works
        """
        if self.mode == "none":
            self.logger.info("No Google Drive configuration to test")
            return False
        
        if self.mode == "local":
            if self.config.google_drive_sync_path.exists():
                # Try to write a test file
                try:
                    test_file = self.config.google_drive_sync_path / ".horizon_test"
                    test_file.write_text("test")
                    test_file.unlink()
                    self.logger.info("✓ Local Google Drive path is writable")
                    return True
                except Exception as e:
                    self.logger.error(f"✗ Cannot write to Google Drive path: {e}")
                    return False
            else:
                self.logger.error(f"✗ Google Drive path does not exist: {self.config.google_drive_sync_path}")
                return False
        
        if self.mode == "api":
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                
                credentials = service_account.Credentials.from_service_account_file(
                    str(self.config.google_service_account_json),
                    scopes=['https://www.googleapis.com/auth/drive.file']
                )
                
                service = build('drive', 'v3', credentials=credentials)
                
                # Try to get folder metadata
                folder = service.files().get(
                    fileId=self.config.google_drive_folder_id,
                    fields='id, name'
                ).execute()
                
                self.logger.info(f"✓ Connected to Google Drive folder: {folder.get('name')}")
                return True
                
            except Exception as e:
                self.logger.error(f"✗ Google Drive API connection failed: {e}")
                return False
        
        return False
