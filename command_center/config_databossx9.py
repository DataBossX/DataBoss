"""
DataBossX Configuration Manager
Handles all configuration settings for the Command Center.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Setup logging
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
    Handles loading, saving, and accessing configuration settings.
    """

    def __init__(self, config_file: str = "config_databossx9.json"):
        """
        Initialize the configuration manager.

        Args:
            config_file: Path to the configuration JSON file
        """
        self.config_file = config_file
        self.config: Dict[str, Any] = {}
        self._load_or_create_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Generate default configuration settings.

        Returns:
            Dictionary with default configuration values
        """
        # Detect current directory and adapt paths
        current_dir = Path.cwd()

        return {
            "version": "9.0",
            "last_updated": datetime.now().isoformat(),
            "paths": {
                "root_dir": str(current_dir),
                "input_dir": str(current_dir / "input"),
                "output_dir": str(current_dir / "output"),
                "assets_dir": str(current_dir / "assets"),
                "logs_dir": str(current_dir / "logs"),
                "database_path": str(current_dir / "databossx_tasks.db"),
                "penterra_dir": str(current_dir / "penterra_files"),
                "genealogy_dir": str(current_dir / "genealogy"),
            },
            "ai": {
                "use_llm_router": True,
                "llm_router_path": "backend.llm_router",
                "default_model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            "ui": {
                "theme": "dark",
                "page_title": "DataBossX Command Center",
                "page_icon": "🚀",
                "layout": "wide",
                "sidebar_state": "expanded",
            },
            "features": {
                "enable_ocr": True,
                "enable_deals_engine": True,
                "enable_agents": True,
                "enable_todo": True,
                "auto_scan_pdfs": True,
                "auto_suggestions": True,
            },
            "ocr": {
                "supported_formats": [".pdf", ".png", ".jpg", ".jpeg", ".tiff"],
                "output_format": "json",
                "batch_size": 10,
            },
            "deals": {
                "min_score_threshold": 60,
                "auto_generate_packages": False,
                "categories": ["Missing Owner", "Mineral Rights", "Real Estate"],
            },
            "notifications": {
                "show_tips": True,
                "show_warnings": True,
                "tip_frequency": "session",  # session, daily, always
            },
            "performance": {
                "cache_enabled": True,
                "cache_ttl": 3600,  # seconds
                "max_parallel_tasks": 5,
            }
        }

    def _load_or_create_config(self) -> None:
        """
        Load configuration from file or create default if it doesn't exist.
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"Configuration loaded from {self.config_file}")

                # Update last_updated timestamp
                self.config['last_updated'] = datetime.now().isoformat()
                self.save_config()
            else:
                logger.info(f"Configuration file not found. Creating default: {self.config_file}")
                self.config = self._get_default_config()
                self.save_config()
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            logger.info("Using default configuration")
            self.config = self._get_default_config()

    def save_config(self) -> bool:
        """
        Save current configuration to file.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.config['last_updated'] = datetime.now().isoformat()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info(f"Configuration saved to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key_path: Path to the key (e.g., 'paths.input_dir')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            logger.warning(f"Configuration key not found: {key_path}, using default: {default}")
            return default

    def set(self, key_path: str, value: Any, save: bool = True) -> bool:
        """
        Set a configuration value using dot notation.

        Args:
            key_path: Path to the key (e.g., 'paths.input_dir')
            value: Value to set
            save: Whether to save configuration after setting

        Returns:
            True if successful, False otherwise
        """
        keys = key_path.split('.')
        config_ref = self.config

        try:
            # Navigate to the parent dictionary
            for key in keys[:-1]:
                if key not in config_ref:
                    config_ref[key] = {}
                config_ref = config_ref[key]

            # Set the value
            config_ref[keys[-1]] = value
            logger.info(f"Configuration updated: {key_path} = {value}")

            if save:
                return self.save_config()
            return True
        except Exception as e:
            logger.error(f"Error setting configuration: {e}")
            return False

    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration settings.

        Returns:
            Complete configuration dictionary
        """
        return self.config.copy()

    def reset_to_defaults(self) -> bool:
        """
        Reset configuration to default values.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.config = self._get_default_config()
            logger.warning("Configuration reset to defaults")
            return self.save_config()
        except Exception as e:
            logger.error(f"Error resetting configuration: {e}")
            return False

    def ensure_directories(self) -> None:
        """
        Ensure all configured directories exist.
        """
        path_keys = ['input_dir', 'output_dir', 'assets_dir', 'logs_dir',
                     'penterra_dir', 'genealogy_dir']

        for key in path_keys:
            path = self.get(f'paths.{key}')
            if path:
                Path(path).mkdir(parents=True, exist_ok=True)
                logger.info(f"Ensured directory exists: {path}")

    def validate_config(self) -> tuple[bool, list[str]]:
        """
        Validate configuration for completeness and correctness.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required sections
        required_sections = ['paths', 'ai', 'ui', 'features']
        for section in required_sections:
            if section not in self.config:
                errors.append(f"Missing required section: {section}")

        # Check critical paths
        root_dir = self.get('paths.root_dir')
        if root_dir and not os.path.exists(root_dir):
            errors.append(f"Root directory does not exist: {root_dir}")

        # Validate feature flags
        features = self.get('features', {})
        if not isinstance(features, dict):
            errors.append("Features section must be a dictionary")

        is_valid = len(errors) == 0
        return is_valid, errors


# Global configuration instance
_config_instance: Optional[DataBossXConfig] = None


def get_config() -> DataBossXConfig:
    """
    Get the global configuration instance (singleton pattern).

    Returns:
        DataBossXConfig instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = DataBossXConfig()
        _config_instance.ensure_directories()
    return _config_instance


def reload_config() -> DataBossXConfig:
    """
    Force reload of configuration from file.

    Returns:
        Reloaded DataBossXConfig instance
    """
    global _config_instance
    _config_instance = DataBossXConfig()
    _config_instance.ensure_directories()
    return _config_instance


if __name__ == "__main__":
    # Test configuration manager
    print("Testing DataBossX Configuration Manager...")

    config = get_config()
    print(f"\nConfiguration version: {config.get('version')}")
    print(f"Root directory: {config.get('paths.root_dir')}")
    print(f"Dark theme enabled: {config.get('ui.theme') == 'dark'}")

    # Validate configuration
    is_valid, errors = config.validate_config()
    if is_valid:
        print("\n✓ Configuration is valid")
    else:
        print("\n✗ Configuration has errors:")
        for error in errors:
            print(f"  - {error}")

    print(f"\nConfiguration saved to: {config.config_file}")
