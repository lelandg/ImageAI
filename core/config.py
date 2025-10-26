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

    # LTX-Video Configuration

    def get_ltx_deployment(self) -> str:
        """Get LTX-Video deployment mode."""
        return self.config.get("ltx_deployment", "local")

    def set_ltx_deployment(self, mode: str) -> None:
        """Set LTX-Video deployment mode (local, fal, replicate, comfyui)."""
        self.config["ltx_deployment"] = mode

    def get_ltx_model(self) -> str:
        """Get LTX-Video model."""
        return self.config.get("ltx_model", "ltx-video-2b")

    def set_ltx_model(self, model: str) -> None:
        """Set LTX-Video model."""
        self.config["ltx_model"] = model

    def get_ltx_resolution(self) -> str:
        """Get LTX-Video resolution."""
        return self.config.get("ltx_resolution", "1080p")

    def set_ltx_resolution(self, resolution: str) -> None:
        """Set LTX-Video resolution."""
        self.config["ltx_resolution"] = resolution

    def get_ltx_fps(self) -> int:
        """Get LTX-Video FPS."""
        return self.config.get("ltx_fps", 30)

    def set_ltx_fps(self, fps: int) -> None:
        """Set LTX-Video FPS."""
        self.config["ltx_fps"] = fps

    def get_ltx_duration(self) -> int:
        """Get LTX-Video duration (seconds)."""
        return self.config.get("ltx_duration", 5)

    def set_ltx_duration(self, duration: int) -> None:
        """Set LTX-Video duration (seconds)."""
        self.config["ltx_duration"] = duration

    def get_ltx_local_path(self) -> str:
        """Get LTX-Video local installation path."""
        default_path = str(Path.home() / ".cache" / "ltx-video")
        return self.config.get("ltx_local_path", default_path)

    def set_ltx_local_path(self, path: str) -> None:
        """Set LTX-Video local installation path."""
        self.config["ltx_local_path"] = path

    def get_ltx_camera_motion(self) -> Optional[str]:
        """Get LTX-Video camera motion setting."""
        return self.config.get("ltx_camera_motion")

    def set_ltx_camera_motion(self, motion: Optional[str]) -> None:
        """Set LTX-Video camera motion."""
        if motion:
            self.config["ltx_camera_motion"] = motion
        elif "ltx_camera_motion" in self.config:
            del self.config["ltx_camera_motion"]

    def get_ltx_guidance_scale(self) -> float:
        """Get LTX-Video guidance scale."""
        return self.config.get("ltx_guidance_scale", 7.5)

    def set_ltx_guidance_scale(self, scale: float) -> None:
        """Set LTX-Video guidance scale."""
        self.config["ltx_guidance_scale"] = scale

    def get_ltx_num_inference_steps(self) -> int:
        """Get LTX-Video number of inference steps."""
        return self.config.get("ltx_num_inference_steps", 50)

    def set_ltx_num_inference_steps(self, steps: int) -> None:
        """Set LTX-Video number of inference steps."""
        self.config["ltx_num_inference_steps"] = steps

    def get_fal_api_key(self) -> Optional[str]:
        """Get Fal.ai API key for LTX-Video."""
        return self.get_api_key("fal")

    def set_fal_api_key(self, api_key: str) -> None:
        """Set Fal.ai API key for LTX-Video."""
        self.set_api_key("fal", api_key)

    def get_replicate_api_key(self) -> Optional[str]:
        """Get Replicate API key for LTX-Video."""
        return self.get_api_key("replicate")

    def set_replicate_api_key(self, api_key: str) -> None:
        """Set Replicate API key for LTX-Video."""
        self.set_api_key("replicate", api_key)


def get_api_key_url(provider: str) -> str:
    """Get the API key documentation URL for a provider."""
    provider = (provider or "google").strip().lower()
    return PROVIDER_KEY_URLS.get(provider, PROVIDER_KEY_URLS["google"])