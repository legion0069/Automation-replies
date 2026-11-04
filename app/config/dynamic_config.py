import json
import logging
import os
import threading
from typing import Optional
from app.config.settings import get_settings
from app.schemas.config import AutomationConfig, AutomationConfigUpdate

logger = logging.getLogger(__name__)


class DynamicConfigManager:
    """Thread-safe manager for dynamic config.json settings."""

    _instance: Optional["DynamicConfigManager"] = None
    _lock = threading.Lock()

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or get_settings().CONFIG_PATH
        self._rw_lock = threading.RLock()
        self._config: AutomationConfig = self._load()

    def _load(self) -> AutomationConfig:
        """Load configuration from JSON file or fall back to defaults."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return AutomationConfig(**data)
            except Exception as e:
                logger.error(
                    "Failed to parse config from %s: %s. Using default settings.",
                    self.config_path,
                    e,
                )
                return AutomationConfig()
        else:
            default_config = AutomationConfig()
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
                with open(self.config_path, "w", encoding="utf-8") as f:
                    f.write(default_config.model_dump_json(indent=2))
                logger.info("Initialized default config at %s", self.config_path)
            except Exception as e:
                logger.warning("Could not write default config file: %s", e)
            return default_config

    def get_config(self) -> AutomationConfig:
        """Get the current configuration snapshot."""
        with self._rw_lock:
            return self._config.model_copy()

    def reload(self) -> AutomationConfig:
        """Reload configuration from disk."""
        with self._rw_lock:
            self._config = self._load()
            logger.info("Configuration reloaded successfully from %s", self.config_path)
            return self.get_config()

    def update(self, update_data: AutomationConfigUpdate) -> AutomationConfig:
        """Update configuration and persist to config.json."""
        with self._rw_lock:
            current_dict = self._config.model_dump()
            patch_dict = update_data.model_dump(exclude_unset=True)
            current_dict.update(patch_dict)

            new_config = AutomationConfig(**current_dict)
            self._config = new_config

            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    f.write(new_config.model_dump_json(indent=2))
                logger.info("Configuration updated and saved to %s", self.config_path)
            except Exception as e:
                logger.error("Failed to persist updated config to %s: %s", self.config_path, e)

            return self.get_config()


def get_dynamic_config() -> DynamicConfigManager:
    """Singleton getter for DynamicConfigManager."""
    if DynamicConfigManager._instance is None:
        with DynamicConfigManager._lock:
            if DynamicConfigManager._instance is None:
                DynamicConfigManager._instance = DynamicConfigManager()
    return DynamicConfigManager._instance
