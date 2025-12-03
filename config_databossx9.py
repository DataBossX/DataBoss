"""
DataBossX Configuration Manager v9
Handles all configuration settings for the Command Center
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('databossx_log9.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DataBossXConfig:
    """
    Configuration manager for DataBossX Command Center.
    Handles settings persistence and runtime configuration.
    """

    def __init__(self, config_file: str = "config/databossx_settings9.json"):
        """
        Initialize configuration manager.

        Args:
            config_file: Path to configuration JSON file
        """
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = {}
        self._ensure_config_directory()
        self.load_config()

    def _ensure_config_directory(self):
        """Ensure configuration directory exists"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration settings.

        Returns:
            Default configuration dictionary
        """
        return {
            "system": {
                "version": "9.0",
                "environment": "production",
                "log_file": "databossx_log9.log",
                "log_level": "INFO",
                "auto_backup": True,
                "backup_interval_hours": 24
            },
            "paths": {
                "root_directory": str(Path.cwd()),
                "input_folder": "input",
                "output_folder": "output",
                "penterra_folder": "penterra_docs",
                "genealogy_folder": "genealogy",
                "deals_folder": "output/deals",
                "database_path": "databossx.db",
                "tasks_database": "databossx_tasks.db"
            },
            "database": {
                "sqlite_db_path": "databossx.db",
                "tasks_db_path": "databossx_tasks.db",
                "enable_wal_mode": True,
                "connection_timeout": 30
            },
            "api_keys": {
                "openai_enabled": False,
                "anthropic_enabled": False,
                "gemini_enabled": False,
                "deepseek_enabled": False,
                "use_env_vars": True
            },
            "llm_router": {
                "default_model": "auto",
                "fallback_enabled": True,
                "timeout_seconds": 60,
                "max_retries": 3,
                "temperature": 0.7,
                "max_tokens": 2000
            },
            "ocr": {
                "primary_engine": "demo",
                "fallback_engines": ["tesseract"],
                "confidence_threshold": 0.85,
                "auto_process": True,
                "supported_formats": [".pdf", ".png", ".jpg", ".jpeg", ".tiff"]
            },
            "ui": {
                "theme": "dark",
                "logo_path": "assets/databossx_logo.png",
                "page_title": "DataBossX Command Center",
                "page_icon": "assets/databossx_logo.ico",
                "sidebar_expanded": True,
                "show_tips": True
            },
            "tasks": {
                "default_project": "General",
                "projects": ["Penterra", "Genealogy", "System", "General"],
                "priority_levels": ["Low", "Medium", "High", "Critical"],
                "status_options": ["To Do", "In Progress", "Blocked", "Done"],
                "enable_ai_suggestions": True
            },
            "agents": {
                "enabled": True,
                "auto_assign": False,
                "queue_processing": True,
                "max_concurrent": 3
            },
            "deals": {
                "min_score_threshold": 60,
                "auto_contact_generation": True,
                "track_follow_ups": True,
                "deal_types": ["Missing Owner", "Mineral Rights", "Real Estate", "Estate"]
            },
            "links": {
                "track_usage": True,
                "suggest_workflows": True,
                "max_recent_links": 10
            },
            "notifications": {
                "enabled": True,
                "desktop_notifications": False,
                "email_notifications": False,
                "notification_email": ""
            },
            "performance": {
                "cache_enabled": True,
                "cache_ttl_minutes": 30,
                "parallel_processing": True,
                "max_workers": 4
            },
            "security": {
                "require_auth": False,
                "session_timeout_minutes": 480,
                "encrypt_sensitive_data": False
            },
            "last_updated": datetime.now().isoformat()
        }

    def load_config(self):
        """Load configuration from file or create default"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                logger.info(f"Configuration loaded from {self.config_file}")
            else:
                self.config = self._get_default_config()
                self.save_config()
                logger.info(f"Default configuration created at {self.config_file}")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.config = self._get_default_config()

    def save_config(self):
        """Save current configuration to file"""
        try:
            self.config["last_updated"] = datetime.now().isoformat()
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        """
        Get configuration value.

        Args:
            section: Configuration section name
            key: Optional key within section
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        try:
            if key is None:
                return self.config.get(section, default)
            return self.config.get(section, {}).get(key, default)
        except Exception as e:
            logger.error(f"Error getting config {section}.{key}: {e}")
            return default

    def set(self, section: str, key: str, value: Any):
        """
        Set configuration value.

        Args:
            section: Configuration section name
            key: Key within section
            value: Value to set
        """
        try:
            if section not in self.config:
                self.config[section] = {}
            self.config[section][key] = value
            self.save_config()
            logger.info(f"Configuration updated: {section}.{key} = {value}")
        except Exception as e:
            logger.error(f"Error setting config {section}.{key}: {e}")

    def update_section(self, section: str, updates: Dict[str, Any]):
        """
        Update entire configuration section.

        Args:
            section: Configuration section name
            updates: Dictionary of updates
        """
        try:
            if section not in self.config:
                self.config[section] = {}
            self.config[section].update(updates)
            self.save_config()
            logger.info(f"Configuration section updated: {section}")
        except Exception as e:
            logger.error(f"Error updating config section {section}: {e}")

    def get_all(self) -> Dict[str, Any]:
        """Get entire configuration dictionary"""
        return self.config.copy()

    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self.config = self._get_default_config()
        self.save_config()
        logger.warning("Configuration reset to defaults")

    def export_config(self, export_path: str):
        """
        Export configuration to specified path.

        Args:
            export_path: Path to export configuration
        """
        try:
            with open(export_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configuration exported to {export_path}")
        except Exception as e:
            logger.error(f"Error exporting configuration: {e}")

    def import_config(self, import_path: str):
        """
        Import configuration from specified path.

        Args:
            import_path: Path to import configuration from
        """
        try:
            with open(import_path, 'r') as f:
                imported_config = json.load(f)
            self.config = imported_config
            self.save_config()
            logger.info(f"Configuration imported from {import_path}")
        except Exception as e:
            logger.error(f"Error importing configuration: {e}")


# Singleton instance
_config_instance: Optional[DataBossXConfig] = None


def get_config() -> DataBossXConfig:
    """
    Get singleton configuration instance.

    Returns:
        DataBossXConfig instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = DataBossXConfig()
    return _config_instance


def reload_config():
    """Reload configuration from file"""
    global _config_instance
    if _config_instance is not None:
        _config_instance.load_config()


if __name__ == "__main__":
    # Test configuration manager
    config = get_config()
    print("Configuration loaded successfully!")
    print(f"Version: {config.get('system', 'version')}")
    print(f"Root directory: {config.get('paths', 'root_directory')}")
