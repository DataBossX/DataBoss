"""Configuration management with .env support."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


class Config:
    """Configuration settings for the Horizon report system."""
    
    def __init__(self):
        """Initialize configuration by loading .env file."""
        # Load .env from workspace root
        env_path = Path.cwd() / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        
        # Core paths
        self.horizon_root = self._get_path("HORIZON_ROOT", Path.cwd())
        self.input_path = self._get_path("HORIZON_INPUT_PATH", self.horizon_root / "inputs")
        self.template_path = self._get_path("HORIZON_TEMPLATE_PATH", self.horizon_root / "templates")
        self.reports_path = self._get_path("HORIZON_REPORTS_PATH", self.horizon_root / "reports")
        self.logs_path = self._get_path("HORIZON_LOGS_PATH", self.horizon_root / "logs")
        
        # Google Drive settings
        self.google_drive_sync_path = self._get_optional_path("GOOGLE_DRIVE_SYNC_PATH")
        self.google_drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        self.google_service_account_json = self._get_optional_path("GOOGLE_SERVICE_ACCOUNT_JSON")
        
        # Report settings
        self.section_target = os.getenv("SECTION_TARGET", "")
        self.report_county = os.getenv("REPORT_COUNTY", "")
        self.report_state = os.getenv("REPORT_STATE", "")
        self.report_template_name = os.getenv("REPORT_TEMPLATE_NAME", "")
        
        # Validation
        self._validate()
    
    def _get_path(self, env_var: str, default: Path) -> Path:
        """Get path from environment or use default."""
        value = os.getenv(env_var)
        if value:
            return Path(value).expanduser().resolve()
        return default
    
    def _get_optional_path(self, env_var: str) -> Optional[Path]:
        """Get optional path from environment."""
        value = os.getenv(env_var)
        if value:
            return Path(value).expanduser().resolve()
        return None
    
    def _validate(self):
        """Validate critical configuration."""
        # Ensure essential directories exist
        self.input_path.mkdir(parents=True, exist_ok=True)
        self.template_path.mkdir(parents=True, exist_ok=True)
        self.reports_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)
        
        # Create reports subdirectories
        (self.reports_path / "generated").mkdir(parents=True, exist_ok=True)
        (self.reports_path / "qa").mkdir(parents=True, exist_ok=True)
        (self.reports_path / "inventory").mkdir(parents=True, exist_ok=True)
    
    def get_google_drive_mode(self) -> str:
        """Determine Google Drive sync mode.
        
        Returns:
            'local' if sync path configured
            'api' if API credentials configured
            'none' if neither configured
        """
        if self.google_drive_sync_path and self.google_drive_sync_path.exists():
            return "local"
        if self.google_drive_folder_id and self.google_service_account_json:
            if self.google_service_account_json.exists():
                return "api"
        return "none"
    
    def redact_secrets(self, text: str) -> str:
        """Redact any secrets from text for safe logging.
        
        Args:
            text: Text that may contain secrets
            
        Returns:
            Text with secrets redacted
        """
        redacted = text
        
        # Redact Google credentials if present
        if self.google_drive_folder_id:
            redacted = redacted.replace(self.google_drive_folder_id, "[REDACTED_FOLDER_ID]")
        
        # Redact anything that looks like a token/key
        import re
        # Pattern for API keys, tokens, etc.
        patterns = [
            r'[A-Za-z0-9_-]{32,}',  # Long alphanumeric strings
            r'sk-[A-Za-z0-9]{20,}',  # OpenAI-style keys
            r'ya29\.[A-Za-z0-9_-]+',  # Google OAuth tokens
        ]
        
        for pattern in patterns:
            redacted = re.sub(pattern, '[REDACTED_TOKEN]', redacted)
        
        return redacted
    
    def to_dict(self) -> dict:
        """Convert config to dictionary (with secrets redacted)."""
        return {
            "horizon_root": str(self.horizon_root),
            "input_path": str(self.input_path),
            "template_path": str(self.template_path),
            "reports_path": str(self.reports_path),
            "logs_path": str(self.logs_path),
            "google_drive_mode": self.get_google_drive_mode(),
            "section_target": self.section_target,
            "report_county": self.report_county,
            "report_state": self.report_state,
            "report_template_name": self.report_template_name,
        }
    
    def log_configuration(self, logger) -> None:
        """Log configuration safely (redacting secrets)."""
        logger.info("=" * 60)
        logger.info("Configuration:")
        for key, value in self.to_dict().items():
            logger.info(f"  {key}: {value}")
        logger.info("=" * 60)


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
