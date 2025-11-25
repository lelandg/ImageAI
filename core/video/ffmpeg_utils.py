"""
Centralized FFmpeg detection, installation, and management utilities.

This module provides a single point of access for FFmpeg functionality,
handling auto-detection, automatic installation via imageio-ffmpeg,
and caching of FFmpeg status in the main config.
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class FFmpegManager:
    """
    Centralized manager for FFmpeg detection and installation.

    This class handles:
    - Detection of system FFmpeg
    - Fallback to imageio-ffmpeg package
    - Auto-installation of imageio-ffmpeg if needed
    - Caching of FFmpeg status in main config
    """

    _instance: Optional['FFmpegManager'] = None
    _ffmpeg_path: Optional[str] = None
    _ffprobe_path: Optional[str] = None
    _is_available: Optional[bool] = None
    _source: Optional[str] = None  # 'system', 'imageio', or None

    def __new__(cls):
        """Singleton pattern to ensure consistent state."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the manager (only runs once due to singleton)."""
        # Check if already initialized
        if FFmpegManager._is_available is not None:
            return

        # Try to load cached status from config first
        self._load_from_config()

        # If not cached or cache is stale, detect FFmpeg
        if FFmpegManager._is_available is None:
            self._detect_ffmpeg()

    def _load_from_config(self) -> None:
        """Load cached FFmpeg status from main config."""
        try:
            from core.config import ConfigManager
            config = ConfigManager()

            ffmpeg_config = config.get("ffmpeg", {})
            if ffmpeg_config and ffmpeg_config.get("path"):
                cached_path = ffmpeg_config.get("path")
                cached_source = ffmpeg_config.get("source")

                # Verify the cached path still works
                if self._verify_ffmpeg(cached_path):
                    FFmpegManager._ffmpeg_path = cached_path
                    FFmpegManager._source = cached_source
                    FFmpegManager._is_available = True
                    FFmpegManager._ffprobe_path = ffmpeg_config.get("ffprobe_path")
                    logger.info(f"Loaded cached FFmpeg path: {cached_path} (source: {cached_source})")
                else:
                    logger.info("Cached FFmpeg path no longer valid, re-detecting")
        except Exception as e:
            logger.debug(f"Could not load FFmpeg config: {e}")

    def _save_to_config(self) -> None:
        """Save FFmpeg status to main config."""
        try:
            from core.config import ConfigManager
            config = ConfigManager()

            config.set("ffmpeg", {
                "path": FFmpegManager._ffmpeg_path,
                "ffprobe_path": FFmpegManager._ffprobe_path,
                "source": FFmpegManager._source,
                "available": FFmpegManager._is_available
            })
            config.save()
            logger.info(f"Saved FFmpeg config: path={FFmpegManager._ffmpeg_path}, source={FFmpegManager._source}")
        except Exception as e:
            logger.warning(f"Could not save FFmpeg config: {e}")

    def _verify_ffmpeg(self, path: str) -> bool:
        """Verify that FFmpeg at the given path works."""
        try:
            result = subprocess.run(
                [path, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _detect_ffmpeg(self) -> None:
        """Detect FFmpeg from system or imageio-ffmpeg."""
        # Try system FFmpeg first
        if self._try_system_ffmpeg():
            self._save_to_config()
            return

        # Try imageio-ffmpeg
        if self._try_imageio_ffmpeg():
            self._save_to_config()
            return

        # FFmpeg not available
        FFmpegManager._is_available = False
        FFmpegManager._ffmpeg_path = None
        FFmpegManager._ffprobe_path = None
        FFmpegManager._source = None
        logger.warning("FFmpeg not found on system or via imageio-ffmpeg")

    def _try_system_ffmpeg(self) -> bool:
        """Try to use system FFmpeg."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                FFmpegManager._ffmpeg_path = "ffmpeg"
                FFmpegManager._is_available = True
                FFmpegManager._source = "system"

                # Also check for ffprobe
                try:
                    probe_result = subprocess.run(
                        ["ffprobe", "-version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if probe_result.returncode == 0:
                        FFmpegManager._ffprobe_path = "ffprobe"
                except Exception:
                    pass

                logger.info("Found system FFmpeg")
                return True
        except Exception as e:
            logger.debug(f"System FFmpeg not found: {e}")

        return False

    def _try_imageio_ffmpeg(self) -> bool:
        """Try to use imageio-ffmpeg package."""
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()

            # Verify it works
            result = subprocess.run(
                [exe, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                FFmpegManager._ffmpeg_path = exe
                FFmpegManager._is_available = True
                FFmpegManager._source = "imageio"

                # imageio-ffmpeg doesn't include ffprobe, but check just in case
                ffprobe_path = str(Path(exe).parent / "ffprobe")
                if Path(ffprobe_path).exists():
                    FFmpegManager._ffprobe_path = ffprobe_path

                logger.info(f"Using imageio-ffmpeg: {exe}")
                return True
        except ImportError:
            logger.debug("imageio-ffmpeg not installed")
        except Exception as e:
            logger.debug(f"imageio-ffmpeg failed: {e}")

        return False

    def install_ffmpeg(self) -> Tuple[bool, str]:
        """
        Install FFmpeg via imageio-ffmpeg package.

        Returns:
            Tuple of (success: bool, message: str)
        """
        logger.info("Attempting to install imageio-ffmpeg...")

        try:
            # Install imageio-ffmpeg via pip
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "imageio-ffmpeg"],
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout for pip install
            )

            if result.returncode != 0:
                error_msg = f"pip install failed: {result.stderr}"
                logger.error(error_msg)
                return False, error_msg

            logger.info("imageio-ffmpeg installed successfully")

            # Clear cached state to force re-detection
            FFmpegManager._is_available = None
            FFmpegManager._ffmpeg_path = None
            FFmpegManager._ffprobe_path = None
            FFmpegManager._source = None

            # Re-detect FFmpeg
            self._detect_ffmpeg()

            if FFmpegManager._is_available:
                return True, f"FFmpeg installed successfully via imageio-ffmpeg: {FFmpegManager._ffmpeg_path}"
            else:
                return False, "imageio-ffmpeg installed but FFmpeg still not working"

        except subprocess.TimeoutExpired:
            error_msg = "Installation timed out after 2 minutes"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Installation failed: {e}"
            logger.error(error_msg)
            return False, error_msg

    @property
    def is_available(self) -> bool:
        """Check if FFmpeg is available."""
        return FFmpegManager._is_available or False

    @property
    def ffmpeg_path(self) -> Optional[str]:
        """Get the path to FFmpeg executable."""
        return FFmpegManager._ffmpeg_path

    @property
    def ffprobe_path(self) -> Optional[str]:
        """Get the path to ffprobe executable (may be None)."""
        return FFmpegManager._ffprobe_path

    @property
    def source(self) -> Optional[str]:
        """Get the source of FFmpeg ('system', 'imageio', or None)."""
        return FFmpegManager._source

    def get_status(self) -> dict:
        """Get complete FFmpeg status as a dictionary."""
        return {
            "available": self.is_available,
            "path": self.ffmpeg_path,
            "ffprobe_path": self.ffprobe_path,
            "source": self.source
        }

    def ensure_available(self, auto_install: bool = True) -> Tuple[bool, str]:
        """
        Ensure FFmpeg is available, optionally auto-installing if not.

        Args:
            auto_install: If True, attempt to install imageio-ffmpeg if FFmpeg not found

        Returns:
            Tuple of (available: bool, message: str)
        """
        if self.is_available:
            return True, f"FFmpeg available at: {self.ffmpeg_path} (source: {self.source})"

        if auto_install:
            logger.info("FFmpeg not found, attempting auto-install...")
            return self.install_ffmpeg()

        return False, "FFmpeg not available and auto-install disabled"

    def refresh(self) -> None:
        """Force re-detection of FFmpeg (clears cache)."""
        FFmpegManager._is_available = None
        FFmpegManager._ffmpeg_path = None
        FFmpegManager._ffprobe_path = None
        FFmpegManager._source = None
        self._detect_ffmpeg()


# Module-level convenience functions
_manager: Optional[FFmpegManager] = None


def get_ffmpeg_manager() -> FFmpegManager:
    """Get the FFmpeg manager singleton instance."""
    global _manager
    if _manager is None:
        _manager = FFmpegManager()
    return _manager


def get_ffmpeg_path() -> Optional[str]:
    """Get the FFmpeg executable path, or None if not available."""
    return get_ffmpeg_manager().ffmpeg_path


def is_ffmpeg_available() -> bool:
    """Check if FFmpeg is available."""
    return get_ffmpeg_manager().is_available


def ensure_ffmpeg(auto_install: bool = True) -> Tuple[bool, str]:
    """
    Ensure FFmpeg is available, optionally auto-installing.

    Args:
        auto_install: If True, attempt to install imageio-ffmpeg if FFmpeg not found

    Returns:
        Tuple of (available: bool, message: str)
    """
    return get_ffmpeg_manager().ensure_available(auto_install)


def install_ffmpeg() -> Tuple[bool, str]:
    """
    Install FFmpeg via imageio-ffmpeg.

    Returns:
        Tuple of (success: bool, message: str)
    """
    return get_ffmpeg_manager().install_ffmpeg()


def get_ffmpeg_status() -> dict:
    """Get complete FFmpeg status."""
    return get_ffmpeg_manager().get_status()
