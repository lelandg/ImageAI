"""Configuration management for ImageAI."""

import copy
import json
import logging
import platform
from pathlib import Path
from typing import Optional, Dict, Any

from . import config_io
# Re-exported so a caller of save() can catch the write failure without
# importing core.config_io itself.
from .config_io import (  # noqa: F401
    ConfigIOError,
    ConfigLockError,
    ConfigReadError,
    ConfigWriteError,
)
from .constants import APP_NAME, PROVIDER_KEY_URLS
from .paths import get_data_paths
from .security import secure_storage

logger = logging.getLogger(__name__)

_MISSING = object()


class ConfigManager:
    """Manages application configuration and persistence."""
    
    def __init__(self):
        """Initialize configuration manager."""
        self.config_dir = self._get_config_dir()
        self.config_path = get_data_paths().config_file()
        self.details_path = get_data_paths().details()
        # Set by a failed load or a failed save, so a caller can report them.
        self.load_error: Optional[str] = None
        self.last_save_error: Optional[str] = None
        # Where an unreadable config.json was copied to, and the bytes that
        # were copied. The bytes stop one damaged file from making a new
        # sidecar on every save.
        self.preserved_config_path: Optional[Path] = None
        self._preserved_bytes: Optional[bytes] = None
        self.config = self._load_config()

        if self.load_error is None:
            # Normalize auth_mode on load (handle legacy display values)
            self._normalize_auth_mode()

            # Migrate legacy API keys to providers structure
            self._migrate_api_keys()
        else:
            # Both steps call save(). config.json could not be read, so this
            # session holds an empty document, and saving it would replace the
            # file that still holds the API keys and the data_roots entry.
            logger.error(
                "Startup did not normalise auth_mode and did not migrate the "
                "legacy API keys, because config.json at %s could not be read. "
                "The file is left as it is. Repair it or restore the preserved "
                "copy, then restart the application.",
                self.config_path,
            )

    def _get_config_dir(self) -> Path:
        """Get the directory that holds config.json. This directory never moves."""
        return get_data_paths().config_file().parent
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from disk and record the on-disk baseline."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.error("Could not create the config directory %s: %s",
                         self.config_dir, exc)

        try:
            loaded = self._read_config_file()
        except ConfigReadError as exc:
            # The application must still start. The original stays on disk: a
            # copy goes beside it now, and __init__ skips every step that
            # would write this session's empty document over it.
            self.load_error = str(exc)
            self._preserve_unreadable_config(exc)
            logger.error(
                "%s The application starts with default settings for this "
                "session, and it does not overwrite the file.", exc,
            )
            loaded = {}

        # The baseline is what disk held at load time. save() compares against
        # it to tell a local edit apart from a value this process never touched.
        self._baseline = copy.deepcopy(loaded)
        return loaded

    def _read_config_file(self) -> Dict[str, Any]:
        """Return the parsed config.json, or {} when the file is missing.

        Raises ConfigReadError when the file exists but cannot be read or
        parsed. An unreadable file still holds the API keys and the data_roots
        entry, so no caller may treat it as an empty document.
        """
        return config_io.read_config(self.config_path)

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
    
    @classmethod
    def _merge_over_disk(
        cls,
        disk: Dict[str, Any],
        memory: Dict[str, Any],
        baseline: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge the in-memory config over the current on-disk config.

        Another writer — the storage migrator, or a second ImageAI window —
        can change config.json after this process loaded it. A value this
        process never edited must therefore come from disk, or the save
        erases the other writer's work. ``baseline`` is the disk content at
        load time, so ``memory != baseline`` marks a real local edit.

        A key that disk no longer holds follows the same rule. The other writer
        deleted it, so it returns only when this process edited it. An
        unconditional write-back would resurrect every setting another writer
        removed, which is the mirror image of the deletion pass below.

        ``disk`` must be a document a writer really wrote. A file that is gone
        or damaged is no writer's decision, and save() passes the load-time
        baseline for it instead — every rule here reads a deletion into a key
        that is simply not present.
        """
        merged = copy.deepcopy(disk)

        for key, mem_value in memory.items():
            base_value = baseline.get(key, _MISSING)
            if key not in merged:
                if base_value is not _MISSING and mem_value == base_value:
                    continue  # deleted by the other writer; untouched here
                merged[key] = copy.deepcopy(mem_value)
                continue
            disk_value = merged[key]
            if isinstance(mem_value, dict) and isinstance(disk_value, dict):
                # Merge per sub-key: a group the user renamed wins, and a
                # group only the other writer touched survives.
                sub_base = base_value if isinstance(base_value, dict) else {}
                merged[key] = cls._merge_over_disk(disk_value, mem_value, sub_base)
            elif mem_value == base_value:
                merged[key] = disk_value  # untouched here; disk is newer
            else:
                merged[key] = copy.deepcopy(mem_value)

        # A key this process deleted goes away, unless disk changed it since.
        for key, base_value in baseline.items():
            if key in memory:
                continue
            if key in merged and merged[key] == base_value:
                del merged[key]

        return merged

    def _write_config_file(self, data: Dict[str, Any]) -> None:
        """Write config.json atomically so a crash cannot truncate it.

        The lock is re-entrant, so this costs nothing when save() already
        holds it, and it still protects a caller that writes on its own.
        """
        with config_io.config_lock(self.config_path):
            config_io.write_config(self.config_path, data)

    @classmethod
    def _apply_in_place(cls, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Copy ``source`` into ``target`` without replacing nested dicts.

        Callers hold live references to nested sections — get_layout_config()
        returns the real dict and the caller mutates it. Rebinding those
        sections would orphan the caller's reference, so update them in place.
        """
        for key in list(target):
            if key not in source:
                del target[key]
        for key, value in source.items():
            current = target.get(key)
            if isinstance(current, dict) and isinstance(value, dict):
                cls._apply_in_place(current, value)
            else:
                target[key] = value

    def save(self) -> bool:
        """Merge with the current config.json on disk, then save it.

        The lock covers the read and the write together. The storage migrator
        writes ``data_roots`` to the same file, and worker threads build a
        ConfigManager while a long move runs, so an unsynchronised
        read-modify-write drops whichever change finished last.

        Returns True when config.json now holds this session's settings. Every
        failure is logged and reported through the return value and through
        ``last_save_error``. save() runs from about forty Qt slots and from
        ``__init__``, so an exception that escapes aborts a slot halfway or
        stops the application from starting.
        """
        self.last_save_error = None
        try:
            with config_io.config_lock(self.config_path):
                try:
                    disk = config_io.read_config_document(self.config_path)
                except ConfigReadError as exc:
                    if not self._preserve_unreadable_config(exc):
                        self.last_save_error = str(exc)
                        return False
                    disk = None
                if disk is None:
                    # There is no readable document on disk: the file is gone
                    # or damaged. That is not a writer that deleted every key,
                    # and this process still holds the whole document, so the
                    # merge runs over the baseline it loaded. A merge over {}
                    # would drop every key this session did not edit.
                    merged = self._merge_over_disk(
                        copy.deepcopy(self._baseline), self.config, self._baseline,
                    )
                else:
                    merged = self._merge_over_disk(disk, self.config, self._baseline)
                self._write_config_file(merged)
        except ConfigIOError as exc:
            # One handler for the lock timeout and the write failure. Both are
            # "config.json was not written", and both used to behave
            # differently: the lock error was logged, the write error escaped
            # into the caller.
            self.last_save_error = str(exc)
            logger.error("Could not save config.json: %s Your settings for this "
                         "session were not written.", exc)
            return False

        # Disk and memory now agree, so the merged result is the new baseline.
        self._apply_in_place(self.config, merged)
        self._baseline = copy.deepcopy(merged)
        return True

    def _preserve_unreadable_config(self, error: ConfigReadError) -> bool:
        """Copy an unreadable config.json aside before a save replaces it.

        config.json holds the API keys and the data_roots entry that points at
        the relocated data. A read failure must never lead to a silent full
        overwrite, so the save continues only when a copy of the original
        exists. Returns True when a copy of the current bytes exists.
        """
        try:
            current = self.config_path.read_bytes()
        except OSError:
            current = None

        if (self.preserved_config_path is not None
                and current is not None
                and current == self._preserved_bytes):
            # The same damaged file, already copied aside. One sidecar per
            # save would bury the first copy under identical ones.
            logger.error(
                "config.json at %s is still unreadable: %s A copy of it is "
                "already at %s.",
                self.config_path, error, self.preserved_config_path,
            )
            return True

        sidecar = config_io.quarantine_unreadable(self.config_path)
        if sidecar is None:
            logger.error(
                "Could not save config.json at %s: %s The file could not be "
                "copied aside either, so it was left untouched. Repair or "
                "remove it, then restart the application.",
                self.config_path, error,
            )
            return False

        self.preserved_config_path = sidecar
        self._preserved_bytes = current
        logger.error(
            "config.json at %s could not be read: %s A copy of the original is "
            "at %s. It still holds any stored API key and the recorded data "
            "locations. This session's settings replace the unreadable file.",
            self.config_path, error, sidecar,
        )
        return True

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
        images_dir = get_data_paths().images()
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
        templates_dir = get_data_paths().settings_root() / "templates" / "layouts"
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

    def get_layout_llm_model(self) -> str:
        """Get last-selected LLM model for the layout designer ('' if none)."""
        layout_config = self.get_layout_config()
        return layout_config.get("llm_model", "")

    def set_layout_llm_model(self, model: str) -> None:
        """Persist the layout designer's LLM model selection."""
        layout_config = self.get_layout_config()
        layout_config["llm_model"] = model
        self.set_layout_config(layout_config)

    def get_layout_content_kind(self) -> str:
        """Get last-selected designer content kind ('' if none)."""
        layout_config = self.get_layout_config()
        return layout_config.get("content_kind", "")

    def set_layout_content_kind(self, kind: str) -> None:
        """Persist the layout designer's content-kind selection."""
        layout_config = self.get_layout_config()
        layout_config["content_kind"] = kind
        self.set_layout_config(layout_config)

    def get_layout_style_role(self) -> str:
        """Get last-viewed style role in the Style panel ('' if none)."""
        layout_config = self.get_layout_config()
        return layout_config.get("style_role", "")

    def set_layout_style_role(self, role: str) -> None:
        """Persist the Style panel's last-viewed role."""
        layout_config = self.get_layout_config()
        layout_config["style_role"] = role
        self.set_layout_config(layout_config)

    # Discord Rich Presence Configuration

    def get_discord_config(self) -> Dict[str, Any]:
        """Get Discord Rich Presence configuration.

        Returns:
            Dictionary with Discord settings:
            - enabled: bool (default False - opt-in)
            - privacy_level: str ("full", "activity_only", "minimal")
            - show_elapsed_time: bool
            - show_model: bool
            - show_buttons: bool (GitHub link)
        """
        defaults = {
            "enabled": False,
            "privacy_level": "full",
            "show_elapsed_time": True,
            "show_model": True,
            "show_buttons": True,
        }
        config = self.config.get("discord", {})
        # Merge with defaults
        return {**defaults, **config}

    def set_discord_config(self, discord_config: Dict[str, Any]) -> None:
        """Set Discord Rich Presence configuration."""
        self.config["discord"] = discord_config

    def get_discord_enabled(self) -> bool:
        """Check if Discord Rich Presence is enabled."""
        return self.get_discord_config().get("enabled", False)

    def set_discord_enabled(self, enabled: bool) -> None:
        """Enable or disable Discord Rich Presence."""
        config = self.get_discord_config()
        config["enabled"] = enabled
        self.set_discord_config(config)


def get_api_key_url(provider: str) -> str:
    """Get the API key documentation URL for a provider."""
    provider = (provider or "google").strip().lower()
    return PROVIDER_KEY_URLS.get(provider, PROVIDER_KEY_URLS["google"])