"""Midjourney provider with embedded web interface."""

import logging
import subprocess
import platform
import webbrowser
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field

from .base import ImageProvider

logger = logging.getLogger(__name__)
console = logging.getLogger("console")


@dataclass
class MidjourneyParams:
    """Parameters for Midjourney image generation."""
    prompt: str
    negative_prompt: Optional[str] = None
    image_urls: List[str] = field(default_factory=list)
    aspect_ratio: Optional[str] = None
    stylize: Optional[int] = None
    quality: Optional[float] = None
    seed: Optional[int] = None
    chaos: Optional[int] = None
    weird: Optional[int] = None
    tile: bool = False
    raw: bool = False
    model_version: Optional[str] = None


class MidjourneyProvider(ImageProvider):
    """Midjourney provider using embedded web interface."""

    PROVIDER_ID = "midjourney"
    PROVIDER_NAME = "Midjourney"

    # Available models
    MODELS = {
        "v7": "Midjourney v7",
        "v6.1": "Midjourney v6.1",
        "v6": "Midjourney v6",
        "niji-6": "Niji Journey v6 (Anime)",
        "v5.2": "Midjourney v5.2",
    }

    # Midjourney web app URL
    # The old "/app" route intermittently returns a 404 in some
    # embedded browsers. Direct users to the stable home route which
    # properly handles login + human verification and then redirects
    # to the app experience.
    WEB_URL = "https://www.midjourney.com/home"

    def __init__(self, config: Dict[str, Any]):
        """Initialize Midjourney provider."""
        super().__init__(config)
        self.web_url = config.get("web_url", self.WEB_URL)
        self.auto_open_browser = config.get("auto_open_browser", True)

        # Discord mode settings
        self.use_discord = config.get("use_discord", False)
        self.discord_server_id = config.get("discord_server_id", "")
        self.discord_channel_id = config.get("discord_channel_id", "")
        self.open_in_external_browser = config.get("open_in_external_browser", False)

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """
        Generate Midjourney command and open web interface.

        Args:
            prompt: Text prompt for generation
            model: Model version to use
            **kwargs: Additional parameters

        Returns:
            Special tuple indicating manual generation mode
        """
        try:
            # Build parameters
            params = MidjourneyParams(
                prompt=prompt,
                model_version=model or self.get_default_model(),
                negative_prompt=kwargs.get("negative_prompt"),
                aspect_ratio=kwargs.get("aspect_ratio"),
                stylize=kwargs.get("stylize"),
                quality=kwargs.get("quality"),
                seed=kwargs.get("seed"),
                chaos=kwargs.get("chaos"),
                weird=kwargs.get("weird"),
                tile=kwargs.get("tile", False),
                raw=kwargs.get("raw", False),
                image_urls=kwargs.get("image_urls", [])
            )

            # Build slash command
            slash_command = self._build_slash_command(params)

            # Copy to clipboard
            self._copy_to_clipboard(slash_command)

            logger.info(f"Midjourney command: {slash_command}")
            console.info(f"Midjourney command copied to clipboard: {slash_command}")

            # Return special response for GUI to handle based on mode
            if self.use_discord and self.discord_server_id and self.discord_channel_id:
                # Discord mode with direct URL
                discord_url = f"https://discord.com/channels/{self.discord_server_id}/{self.discord_channel_id}"

                if self.open_in_external_browser:
                    # Open in external browser
                    return (
                        [f"MIDJOURNEY_EXTERNAL_BROWSER:{discord_url}|{slash_command}"],
                        []  # No image bytes for manual mode
                    )
                else:
                    # Open in embedded browser
                    return (
                        [f"MIDJOURNEY_WEB_MODE:{discord_url}|{slash_command}"],
                        []  # No image bytes for manual mode
                    )
            else:
                # Standard Midjourney web app mode
                if self.open_in_external_browser:
                    # Open in external browser
                    return (
                        [f"MIDJOURNEY_EXTERNAL_BROWSER:{self.web_url}|{slash_command}"],
                        []  # No image bytes for manual mode
                    )
                else:
                    # Open in embedded browser
                    return (
                        [f"MIDJOURNEY_WEB_MODE:{self.web_url}|{slash_command}"],
                        []  # No image bytes for manual mode
                    )

        except Exception as e:
            logger.error(f"Midjourney generation error: {e}")
            raise Exception(f"Midjourney generation failed: {str(e)}")

    def _build_slash_command(self, params: MidjourneyParams) -> str:
        """Build Midjourney slash command from parameters."""
        parts = ["/imagine prompt:"]

        # Build prompt body
        body_parts = []

        # Add image URLs if present
        if params.image_urls:
            body_parts.extend(params.image_urls)

        # Add main prompt
        body_parts.append(params.prompt.strip())

        # Join body parts
        body = " ".join(body_parts)

        # Add negative prompt
        if params.negative_prompt:
            body += f" --no {params.negative_prompt.strip()}"

        parts.append(body)

        # Add parameters
        if params.aspect_ratio:
            parts.append(f"--ar {params.aspect_ratio}")
        if params.stylize is not None:
            parts.append(f"--s {params.stylize}")
        if params.quality is not None:
            parts.append(f"--q {params.quality}")
        if params.seed is not None:
            parts.append(f"--seed {params.seed}")
        if params.chaos is not None:
            parts.append(f"--chaos {params.chaos}")
        if params.weird is not None:
            parts.append(f"--weird {params.weird}")

        # Add model version
        if params.model_version:
            # Extract version number (e.g., "v7" -> "7", "niji-6" -> "niji 6")
            if params.model_version.startswith("niji"):
                parts.append("--niji 6")
            else:
                version = params.model_version.replace("v", "")
                parts.append(f"--v {version}")

        # Add boolean flags
        if params.tile:
            parts.append("--tile")
        if params.raw:
            parts.append("--raw")

        return " ".join(parts)

    def _copy_to_clipboard(self, text: str):
        """Copy text to system clipboard."""
        system = platform.system()
        try:
            if system == "Windows":
                # Windows clipboard
                process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=text)
            elif system == "Darwin":
                # macOS clipboard
                process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=text)
            else:
                # Linux clipboard (requires xclip)
                try:
                    process = subprocess.Popen(['xclip', '-selection', 'clipboard'],
                                             stdin=subprocess.PIPE, text=True)
                    process.communicate(input=text)
                except FileNotFoundError:
                    # Try xsel as fallback
                    process = subprocess.Popen(['xsel', '--clipboard', '--input'],
                                             stdin=subprocess.PIPE, text=True)
                    process.communicate(input=text)

            logger.info("Command copied to clipboard successfully")
            console.info("✓ Command copied to clipboard")

        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            console.error(f"Failed to copy to clipboard: {e}")
            console.info(f"Manual copy: {text}")

    def validate_auth(self) -> Tuple[bool, str]:
        """
        Validate authentication - Midjourney doesn't need API keys.

        Returns:
            Always returns success as no auth needed
        """
        return True, "Midjourney (manual mode) - no authentication required"

    def get_models(self) -> Dict[str, str]:
        """Get available Midjourney models."""
        return self.MODELS.copy()

    def get_default_model(self) -> str:
        """Get default model."""
        return "v7"

    def get_supported_features(self) -> List[str]:
        """Get supported features."""
        return [
            "generate",
            "reference_image",  # Image URLs for reference
            "negative_prompt",
            "aspect_ratio",
            "style_control",  # stylize parameter
            "quality_control",
            "seed_control",
            "chaos_control",
            "weird_control",
            "tile_mode",
            "raw_mode"
        ]

    def get_api_key_url(self) -> str:
        """Get URL for Midjourney subscription."""
        return "https://www.midjourney.com/account"

    def supports_web_interface(self) -> bool:
        """Indicate this provider uses web interface."""
        return True

    def get_web_url(self) -> str:
        """Get web interface URL."""
        return self.web_url
