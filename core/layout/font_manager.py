"""
Font management system for the Layout/Books module.

Handles font discovery from system directories and custom font paths,
builds font manifests, and provides font loading for rendering.
"""

import json
import platform
from pathlib import Path
from typing import Dict, List, Optional, Set
from PIL import ImageFont

from core.logging_config import LogManager

logger = LogManager().get_logger("layout.fonts")


class FontManager:
    """
    Manages font discovery and loading.

    Discovers fonts from:
    - System font directories (platform-specific)
    - MyFonts repository (if configured)
    - Custom font directories from config
    """

    def __init__(self, manifest_path: Optional[Path] = None, custom_dirs: Optional[List[Path]] = None):
        """
        Initialize the font manager.

        Args:
            manifest_path: Path to fonts_manifest.json (if exists)
            custom_dirs: Additional directories to scan for fonts
        """
        self.manifest_path = manifest_path
        self.custom_dirs = custom_dirs or []
        self._manifest: Dict[str, Dict] = {}
        self._font_cache: Dict[str, Path] = {}  # Cache for quick lookups

        # Load existing manifest if provided
        if manifest_path and manifest_path.exists():
            try:
                self._manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                logger.info(f"Loaded font manifest from {manifest_path}")
            except Exception as e:
                logger.error(f"Failed to load font manifest: {e}")
        else:
            logger.info("No existing font manifest found, will build from system fonts")
            self.discover_fonts()

    def discover_fonts(self) -> None:
        """Discover fonts from system directories and custom paths."""
        logger.info("Starting font discovery...")

        font_dirs = self._get_system_font_dirs()
        font_dirs.extend(self.custom_dirs)

        discovered = 0
        for font_dir in font_dirs:
            if not font_dir.exists():
                continue

            logger.debug(f"Scanning font directory: {font_dir}")

            # Scan for font files
            for ext in ["*.ttf", "*.otf", "*.TTF", "*.OTF"]:
                for font_file in font_dir.rglob(ext):
                    try:
                        self._add_font_to_manifest(font_file)
                        discovered += 1
                    except Exception as e:
                        logger.warning(f"Failed to process font {font_file}: {e}")

        logger.info(f"Font discovery complete. Found {discovered} fonts across {len(self._manifest)} families.")

    def _get_system_font_dirs(self) -> List[Path]:
        """Get platform-specific system font directories."""
        system = platform.system()

        if system == "Windows":
            return [
                Path("C:/Windows/Fonts"),
                Path.home() / "AppData/Local/Microsoft/Windows/Fonts"
            ]
        elif system == "Darwin":  # macOS
            return [
                Path("/System/Library/Fonts"),
                Path("/Library/Fonts"),
                Path.home() / "Library/Fonts"
            ]
        else:  # Linux and others
            return [
                Path("/usr/share/fonts"),
                Path("/usr/local/share/fonts"),
                Path.home() / ".fonts",
                Path.home() / ".local/share/fonts"
            ]

    def _add_font_to_manifest(self, font_path: Path) -> None:
        """
        Add a font file to the manifest.

        Attempts to extract font family name and properties.
        """
        try:
            # Try to load the font to get its family name
            # Note: This is a simplified approach; a full implementation
            # would use fonttools to extract proper font metadata
            font = ImageFont.truetype(str(font_path), size=12)

            # Extract family name from font path as fallback
            # Format is typically: FamilyName-Weight.ttf
            stem = font_path.stem
            parts = stem.split("-")
            family_name = parts[0] if parts else stem

            # Store in manifest
            if family_name not in self._manifest:
                self._manifest[family_name] = {
                    "family": family_name,
                    "files": []
                }

            if str(font_path) not in self._manifest[family_name]["files"]:
                self._manifest[family_name]["files"].append(str(font_path))

            # Add to cache for quick lookup
            cache_key = f"{family_name.lower()}"
            self._font_cache[cache_key] = font_path

        except Exception as e:
            # If we can't load the font, skip it
            logger.debug(f"Skipping font {font_path}: {e}")

    def save_manifest(self, path: Path) -> None:
        """Save the current font manifest to a JSON file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._manifest, indent=2), encoding="utf-8")
            logger.info(f"Saved font manifest to {path}")
        except Exception as e:
            logger.error(f"Failed to save font manifest: {e}")

    def select_font_file(self, families: List[str], weight: str = "regular", italic: bool = False) -> Optional[Path]:
        """
        Select a font file from the manifest based on family priority.

        Args:
            families: Priority-ordered list of font family names
            weight: Font weight (not fully implemented yet)
            italic: Whether to prefer italic variant (not fully implemented yet)

        Returns:
            Path to the font file, or None if no match found
        """
        for family in families:
            # Try exact match
            if family in self._manifest:
                files = self._manifest[family].get("files", [])
                if files:
                    return Path(files[0])

            # Try case-insensitive match
            family_lower = family.lower()
            if family_lower in self._font_cache:
                return self._font_cache[family_lower]

            # Try fuzzy match
            for manifest_family in self._manifest.keys():
                if family_lower in manifest_family.lower() or manifest_family.lower() in family_lower:
                    files = self._manifest[manifest_family].get("files", [])
                    if files:
                        return Path(files[0])

        return None

    def pil_font(
        self,
        families: List[str],
        size_px: int,
        weight: str = "regular",
        italic: bool = False
    ) -> ImageFont.FreeTypeFont:
        """
        Load a PIL ImageFont based on family and size.

        Args:
            families: Priority-ordered list of font family names
            size_px: Font size in pixels
            weight: Font weight (not fully implemented yet)
            italic: Whether to prefer italic variant (not fully implemented yet)

        Returns:
            ImageFont.FreeTypeFont instance (falls back to default if no match)
        """
        font_path = self.select_font_file(families, weight, italic)

        if font_path and font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size_px, layout_engine=ImageFont.LAYOUT_BASIC)
            except Exception as e:
                logger.warning(f"Failed to load font {font_path}: {e}")

        # Fallback to default font
        logger.debug(f"Using default font for families {families}")
        return ImageFont.load_default()

    def get_available_families(self) -> List[str]:
        """Get a list of all available font families."""
        return sorted(self._manifest.keys())
