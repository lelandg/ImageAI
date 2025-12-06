"""Base class for lip-sync providers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseLipSyncProvider(ABC):
    """
    Abstract base class for lip-sync providers.

    Lip-sync providers take a video/image and audio file and generate
    a lip-synced video where the mouth movements match the audio.
    """

    @abstractmethod
    def generate(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Optional[Path] = None,
        **kwargs
    ) -> Path:
        """
        Generate a lip-synced video.

        Args:
            video_path: Path to the source video or image
            audio_path: Path to the audio file
            output_path: Optional output path (auto-generated if not provided)
            **kwargs: Provider-specific parameters

        Returns:
            Path to the generated lip-synced video
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this provider is available and ready to use.

        Returns:
            True if the provider can be used, False otherwise
        """
        pass

    @abstractmethod
    def get_install_prompt(self) -> str:
        """
        Get a user-friendly message about how to install this provider.

        Returns:
            Installation instructions string
        """
        pass

    def get_name(self) -> str:
        """Get the display name of this provider."""
        return self.__class__.__name__.replace("Provider", "")

    def get_supported_video_formats(self) -> list:
        """Get list of supported input video formats."""
        return [".mp4", ".avi", ".mov", ".mkv", ".webm"]

    def get_supported_image_formats(self) -> list:
        """Get list of supported input image formats."""
        return [".jpg", ".jpeg", ".png", ".bmp", ".webp"]

    def get_supported_audio_formats(self) -> list:
        """Get list of supported audio formats."""
        return [".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"]

    def validate_inputs(self, video_path: Path, audio_path: Path) -> tuple[bool, str]:
        """
        Validate input files.

        Args:
            video_path: Path to video/image file
            audio_path: Path to audio file

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check video/image exists
        if not video_path.exists():
            return False, f"Video/image file not found: {video_path}"

        # Check audio exists
        if not audio_path.exists():
            return False, f"Audio file not found: {audio_path}"

        # Check video/image format
        video_suffix = video_path.suffix.lower()
        valid_video = video_suffix in self.get_supported_video_formats()
        valid_image = video_suffix in self.get_supported_image_formats()

        if not (valid_video or valid_image):
            return False, f"Unsupported video/image format: {video_suffix}"

        # Check audio format
        audio_suffix = audio_path.suffix.lower()
        if audio_suffix not in self.get_supported_audio_formats():
            return False, f"Unsupported audio format: {audio_suffix}"

        return True, ""

    def get_parameters_schema(self) -> Dict[str, Any]:
        """
        Get the schema for provider-specific parameters.

        Returns:
            Dictionary describing available parameters
        """
        return {}
