"""
Video feature configuration management.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import json
import logging


class VideoConfig:
    """Configuration for video features"""
    
    DEFAULT_CONFIG = {
        "enabled": True,
        "video_projects_dir": None,  # Will be set to user config dir / video_projects
        "default_video_provider": "slideshow",  # "veo" or "slideshow"
        "veo_model": "veo-3.0-generate-001",  # Default Veo model
        "ffmpeg_path": "ffmpeg",  # Auto-detect or user-specified
        "cache_size_mb": 5000,  # Max cache size in MB
        "concurrent_images": 3,  # Max parallel image generations
        "default_aspect_ratio": "16:9",
        "default_resolution": "1080p",
        "default_fps": 24,
        "default_transition_duration": 0.5,  # seconds
        "enable_ken_burns": True,  # Pan/zoom effect for slideshows
        "default_scene_duration": 4.0,  # seconds
        "timing_presets": {
            "fast": 2.5,  # seconds per scene
            "medium": 4.0,
            "slow": 6.0
        },
        "llm_providers": {
            "openai": {
                "enabled": True,
                "models": ["gpt-5", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"]
            },
            "anthropic": {
                "enabled": True,
                "models": ["claude-opus-4.1", "claude-opus-4", "claude-sonnet-4", "claude-3.7-sonnet", "claude-3.5-sonnet", "claude-3.5-haiku"]
            },
            "gemini": {
                "enabled": True,
                "models": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-pro"]
            },
            "ollama": {
                "enabled": False,  # Disabled by default, requires local setup
                "models": ["llama3.2:latest", "llama3.1:8b", "mistral:7b", "mixtral:8x7b"],
                "endpoint": "http://localhost:11434"
            },
            "lmstudio": {
                "enabled": False,  # Disabled by default, requires local setup
                "endpoint": "http://localhost:1234/v1"
            }
        },
        "veo_settings": {
            "models": {
                "veo-3.0-generate-001": {
                    "duration": 8,
                    "fps": 24,
                    "resolutions": ["720p", "1080p"],
                    "aspect_ratios": ["16:9"],
                    "has_audio": True
                },
                "veo-3.0-fast-generate-001": {
                    "duration": 8,
                    "fps": 24,
                    "resolutions": ["720p", "1080p"],
                    "aspect_ratios": ["16:9"],
                    "has_audio": True
                },
                "veo-2.0-generate-001": {
                    "duration": 5,  # 5-8 seconds
                    "fps": 24,
                    "resolutions": ["720p"],
                    "aspect_ratios": ["16:9", "9:16"],
                    "has_audio": False
                }
            },
            "person_generation_options": ["dont_allow", "allow"],
            "default_person_generation": "dont_allow",
            "retention_days": 2,  # Server retention period
            "polling_interval": 10,  # seconds between status checks
            "timeout": 600  # Maximum wait time in seconds
        },
        "export_settings": {
            "video_codec": "libx264",
            "audio_codec": "aac",
            "preset": "medium",  # FFmpeg preset: ultrafast, fast, medium, slow
            "crf": 23,  # Quality (0-51, lower is better)
            "audio_bitrate": "192k"
        }
    }
    
    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize video configuration.
        
        Args:
            config_file: Path to configuration file. If None, uses default location.
        """
        self.logger = logging.getLogger(__name__)
        
        # Determine config file location
        if config_file is None:
            import platform
            system = platform.system()
            
            if system == "Windows":
                import os
                config_dir = Path(os.environ.get('APPDATA', '')) / 'ImageAI'
            elif system == "Darwin":  # macOS
                config_dir = Path.home() / 'Library' / 'Application Support' / 'ImageAI'
            else:  # Linux and others
                config_dir = Path.home() / '.config' / 'ImageAI'
            
            config_file = config_dir / 'video_config.json'
        
        self.config_file = config_file
        self.config = self.DEFAULT_CONFIG.copy()
        
        # Set dynamic defaults
        if self.config["video_projects_dir"] is None:
            self.config["video_projects_dir"] = str(self.config_file.parent / "video_projects")
        
        # Load existing config if available
        self.load()
    
    def load(self) -> bool:
        """
        Load configuration from file.
        
        Returns:
            True if config was loaded, False if using defaults
        """
        if not self.config_file.exists():
            self.logger.info(f"No config file found at {self.config_file}, using defaults")
            return False
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
            
            # Merge with defaults (file config overrides defaults)
            self._deep_merge(self.config, file_config)
            
            self.logger.info(f"Loaded video config from {self.config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save configuration to file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            
            self.logger.info(f"Saved video config to {self.config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key (supports dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value.
        
        Args:
            key: Configuration key (supports dot notation for nested keys)
            value: Value to set
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def _deep_merge(self, base: Dict, override: Dict) -> None:
        """
        Deep merge override dictionary into base dictionary.
        
        Args:
            base: Base dictionary (modified in place)
            override: Override dictionary
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def validate_ffmpeg(self) -> bool:
        """
        Check if FFmpeg is available.
        
        Returns:
            True if FFmpeg is available, False otherwise
        """
        import subprocess
        
        ffmpeg_path = self.get("ffmpeg_path", "ffmpeg")
        
        try:
            subprocess.run(
                [ffmpeg_path, "-version"],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.warning(f"FFmpeg not found at: {ffmpeg_path}")
            return False
    
    def get_veo_model_config(self, model: str) -> Dict[str, Any]:
        """
        Get configuration for a specific Veo model.
        
        Args:
            model: Veo model name
            
        Returns:
            Model configuration dictionary
        """
        return self.get(f"veo_settings.models.{model}", {})
    
    def is_llm_provider_enabled(self, provider: str) -> bool:
        """
        Check if an LLM provider is enabled.
        
        Args:
            provider: Provider name (openai, anthropic, gemini, etc.)
            
        Returns:
            True if enabled, False otherwise
        """
        return self.get(f"llm_providers.{provider}.enabled", False)
    
    def get_llm_models(self, provider: str) -> list:
        """
        Get available models for an LLM provider.
        
        Args:
            provider: Provider name
            
        Returns:
            List of model names
        """
        return self.get(f"llm_providers.{provider}.models", [])
    
    def get_projects_dir(self) -> Path:
        """
        Get the video projects directory path.
        
        Returns:
            Path to video projects directory
        """
        return Path(self.get("video_projects_dir", str(self.config_file.parent / "video_projects")))