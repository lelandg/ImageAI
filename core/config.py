"""Configuration management for ImageAI."""

import json
import os
import platform
from pathlib import Path
from typing import Optional, Dict, Any

from .constants import APP_NAME, PROVIDER_KEY_URLS
from .security import secure_storage


class ConfigManager:
    """Manages application configuration and persistence."""
    
    def __init__(self):
        """Initialize configuration manager."""
        self.config_dir = self._get_config_dir()
        self.config_path = self.config_dir / "config.json"
        self.details_path = self.config_dir / "details.jsonl"
        self.config = self._load_config()
    
    def _get_config_dir(self) -> Path:
        """Get platform-specific configuration directory."""
        system = platform.system()
        home = Path.home()
        
        if system == "Windows":
            base = Path(os.getenv("APPDATA", home / "AppData" / "Roaming"))
            return base / APP_NAME
        elif system == "Darwin":  # macOS
            return home / "Library" / "Application Support" / APP_NAME
        else:  # Linux/Unix
            base = Path(os.getenv("XDG_CONFIG_HOME", home / ".config"))
            return base / APP_NAME
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from disk."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text(encoding="utf-8"))
            except (OSError, IOError, json.JSONDecodeError):
                return {}
        return {}
    
    def save(self) -> None:
        """Save current configuration to disk."""
        self.config_path.write_text(
            json.dumps(self.config, indent=2),
            encoding="utf-8"
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self.config[key] = value
    
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """Get provider-specific configuration."""
        providers = self.config.get("providers", {})
        return providers.get(provider, {})
    
    def set_provider_config(self, provider: str, config: Dict[str, Any]) -> None:
        """Set provider-specific configuration."""
        if "providers" not in self.config:
            self.config["providers"] = {}
        self.config["providers"][provider] = config
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider."""
        # Try keyring first (most secure)
        key = secure_storage.retrieve_key(provider)
        if key:
            return key
        
        # Check provider-specific config
        provider_config = self.get_provider_config(provider)
        if "api_key" in provider_config:
            return provider_config["api_key"]
        
        return None
    
    def set_api_key(self, provider: str, api_key: str) -> None:
        """Set API key for a provider."""
        # Try to store in keyring first (most secure)
        stored_in_keyring = secure_storage.store_key(provider, api_key)
        
        # If keyring storage failed or not available, fall back to file storage
        if not stored_in_keyring:
            provider_config = self.get_provider_config(provider)
            provider_config["api_key"] = api_key
            self.set_provider_config(provider, provider_config)
    
    def get_auth_mode(self, provider: str = "google") -> str:
        """Get authentication mode for a provider."""
        if provider == "google":
            return self.config.get("auth_mode", "api_key")
        return "api_key"
    
    def set_auth_mode(self, provider: str, mode: str) -> None:
        """Set authentication mode for a provider."""
        if provider == "google":
            self.config["auth_mode"] = mode
    
    def get_auth_validated(self, provider: str = "google") -> bool:
        """Check if authentication has been validated for a provider."""
        if provider == "google":
            return self.config.get("gcloud_auth_validated", False)
        return False
    
    def set_auth_validated(self, provider: str, validated: bool) -> None:
        """Set authentication validation status for a provider."""
        if provider == "google":
            self.config["gcloud_auth_validated"] = validated
            # Also store the project ID if available
            if validated:
                from pathlib import Path
                import subprocess
                import platform
                try:
                    gcloud_cmd = "gcloud.cmd" if platform.system() == "Windows" else "gcloud"
                    result = subprocess.run(
                        [gcloud_cmd, "config", "get-value", "project"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0 and result.stdout:
                        self.config["gcloud_project_id"] = result.stdout.strip()
                except Exception:
                    pass
    
    def get_gcloud_project_id(self) -> Optional[str]:
        """Get the stored Google Cloud project ID."""
        return self.config.get("gcloud_project_id")
    
    def save_details_record(self, details: Dict[str, Any]) -> None:
        """Save a template/details record to history."""
        try:
            with self.details_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(details, ensure_ascii=False) + "\n")
        except (OSError, IOError, json.JSONEncodeError):
            pass
    
    def load_details_records(self) -> list:
        """Load all template/details records."""
        records = []
        if self.details_path.exists():
            try:
                with self.details_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            records.append(json.loads(line))
            except (OSError, IOError, json.JSONDecodeError):
                pass
        return records
    
    def get_images_dir(self) -> Path:
        """Get directory for saved images."""
        images_dir = self.config_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        return images_dir


def get_api_key_url(provider: str) -> str:
    """Get the API key documentation URL for a provider."""
    provider = (provider or "google").strip().lower()
    return PROVIDER_KEY_URLS.get(provider, PROVIDER_KEY_URLS["google"])