"""Configuration management for ImageAI."""

import json
import logging
import os
import platform
from pathlib import Path
from typing import Optional, Dict, Any

from .constants import APP_NAME, PROVIDER_KEY_URLS
from .security import secure_storage

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration and persistence."""
    
    def __init__(self):
        """Initialize configuration manager."""
        self.config_dir = self._get_config_dir()
        self.config_path = self.config_dir / "config.json"
        self.details_path = self.config_dir / "details.jsonl"
        self.config = self._load_config()

        # Normalize auth_mode on load (handle legacy display values)
        self._normalize_auth_mode()

        # Migrate legacy API keys to providers structure
        self._migrate_api_keys()
    
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

    def _normalize_auth_mode(self) -> None:
        """Normalize auth_mode values to internal format."""
        auth_mode = self.config.get("auth_mode", "api-key")

        # Map legacy/display values to internal values
        if auth_mode in ["api_key", "API Key"]:
            self.config["auth_mode"] = "api-key"
        elif auth_mode == "Google Cloud Account":
            self.config["auth_mode"] = "gcloud"

        # Save if we made changes
        if self.config.get("auth_mode") != auth_mode:
            self.save()

    def _migrate_api_keys(self) -> None:
        """Migrate legacy top-level API keys to providers structure."""
        migrated = False

        # List of providers to migrate
        providers_to_migrate = ["anthropic", "google", "openai", "stability"]

        for provider in providers_to_migrate:
            # Check if key exists at top level but not in providers structure
            top_level_key = f"{provider}_api_key"
            if top_level_key in self.config:
                key_value = self.config[top_level_key]
                if key_value:  # Only migrate non-empty keys
                    # Check if already in providers
                    provider_config = self.get_provider_config(provider)
                    if "api_key" not in provider_config:
                        # Migrate to providers structure
                        provider_config["api_key"] = key_value
                        self.set_provider_config(provider, provider_config)
                        migrated = True

        if migrated:
            self.save()
    
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
        """Get API key for a provider.

        For Google provider with gcloud auth mode, returns a fresh access token.
        Otherwise returns the stored API key.
        """
        # Special handling for Google provider with gcloud auth
        if provider == "google" and self.get_auth_mode("google") == "gcloud":
            try:
                from .gcloud_utils import find_gcloud_command
                import subprocess
                import platform

                gcloud_cmd = find_gcloud_command()
                if gcloud_cmd:
                    result = subprocess.run(
                        [gcloud_cmd, "auth", "application-default", "print-access-token"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        shell=(platform.system() == "Windows")
                    )
                    if result.returncode == 0:
                        token = result.stdout.strip()
                        if token:
                            return token
            except Exception:
                # Fall through to normal API key lookup if gcloud fails
                pass

        # Try keyring first (most secure)
        key = secure_storage.retrieve_key(provider)
        if key:
            logger.debug(f"API key for {provider} retrieved from keyring (len={len(key)})")
            return key

        # Check provider-specific config
        provider_config = self.get_provider_config(provider)
        if "api_key" in provider_config:
            key = provider_config["api_key"]
            logger.debug(f"API key for {provider} retrieved from config file (len={len(key) if key else 0})")
            return key

        logger.debug(f"No API key found for {provider} in keyring or config")
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
            # DON'T fetch project ID here - it would block the main thread
            # Project ID should be fetched in background thread and set separately via set_gcloud_project_id()
    
    def get_gcloud_project_id(self) -> Optional[str]:
        """Get the stored Google Cloud project ID."""
        return self.config.get("gcloud_project_id")
    
    def set_gcloud_project_id(self, project_id: str) -> None:
        """Set the Google Cloud project ID."""
        self.config["gcloud_project_id"] = project_id
    
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

    # Layout/Books Module Configuration

    def get_layout_config(self) -> Dict[str, Any]:
        """Get layout module configuration."""
        return self.config.get("layout", {})

    def set_layout_config(self, layout_config: Dict[str, Any]) -> None:
        """Set layout module configuration."""
        self.config["layout"] = layout_config

    def get_templates_dir(self) -> Path:
        """Get directory for layout templates."""
        # Check if custom path is set in config
        layout_config = self.get_layout_config()
        custom_path = layout_config.get("templates_dir")

        if custom_path:
            path = Path(custom_path)
            if path.exists() and path.is_dir():
                return path

        # Default to templates/layouts in project directory
        # Find project root (look for main.py)
        from pathlib import Path
        current = Path(__file__).resolve()
        for parent in [current.parent.parent, current.parent.parent.parent]:
            if (parent / "main.py").exists():
                return parent / "templates" / "layouts"

        # Fallback to config directory
        templates_dir = self.config_dir / "templates" / "layouts"
        templates_dir.mkdir(parents=True, exist_ok=True)
        return templates_dir

    def get_fonts_dir(self) -> Optional[Path]:
        """Get directory for custom fonts (optional)."""
        layout_config = self.get_layout_config()
        fonts_path = layout_config.get("fonts_dir")

        if fonts_path:
            path = Path(fonts_path)
            if path.exists() and path.is_dir():
                return path

        return None

    def get_layout_export_dpi(self) -> int:
        """Get default DPI for layout exports."""
        layout_config = self.get_layout_config()
        return layout_config.get("export_dpi", 300)

    def set_layout_export_dpi(self, dpi: int) -> None:
        """Set default DPI for layout exports."""
        layout_config = self.get_layout_config()
        layout_config["export_dpi"] = dpi
        self.set_layout_config(layout_config)

    def get_layout_llm_provider(self) -> str:
        """Get LLM provider for layout text generation."""
        layout_config = self.get_layout_config()
        return layout_config.get("llm_provider", "google")

    def set_layout_llm_provider(self, provider: str) -> None:
        """Set LLM provider for layout text generation."""
        layout_config = self.get_layout_config()
        layout_config["llm_provider"] = provider
        self.set_layout_config(layout_config)


def get_api_key_url(provider: str) -> str:
    """Get the API key documentation URL for a provider."""
    provider = (provider or "google").strip().lower()
    return PROVIDER_KEY_URLS.get(provider, PROVIDER_KEY_URLS["google"])