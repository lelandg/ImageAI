"""Preset Loader for Prompt Builder.

Manages loading, saving, and filtering of style presets for the Prompt Builder.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PresetLoader:
    """Loads and manages style presets for the Prompt Builder."""

    def __init__(self):
        """Initialize the PresetLoader."""
        # Get presets directory
        self.presets_dir = Path(__file__).parent.parent / "data" / "prompts"
        self.presets_file = self.presets_dir / "presets.json"
        self.custom_presets_file = self.presets_dir / "custom_presets.json"

        # Cache for loaded presets
        self._presets_cache: Optional[List[Dict]] = None
        self._last_load_time: Optional[float] = None

    def get_presets(
        self,
        category: Optional[str] = None,
        sort_by_popularity: bool = True,
        include_custom: bool = True
    ) -> List[Dict]:
        """Get all presets, optionally filtered by category.

        Args:
            category: Optional category to filter by (e.g., "Comics", "Digital")
            sort_by_popularity: If True, sort by popularity (highest first)
            include_custom: If True, include user's custom presets

        Returns:
            List of preset dictionaries
        """
        try:
            # Load built-in presets
            presets = self._load_built_in_presets()

            # Load custom presets if requested
            if include_custom:
                custom_presets = self._load_custom_presets()
                presets.extend(custom_presets)

            # Filter by category if specified
            if category:
                presets = [p for p in presets if p.get("category") == category]

            # Sort by popularity if requested
            if sort_by_popularity:
                presets.sort(key=lambda p: p.get("popularity", 0), reverse=True)

            logger.info(f"Loaded {len(presets)} presets" +
                       (f" (category: {category})" if category else ""))
            return presets

        except Exception as e:
            logger.error(f"Error loading presets: {e}")
            return []

    def _load_built_in_presets(self) -> List[Dict]:
        """Load built-in presets from presets.json.

        Returns:
            List of built-in preset dictionaries
        """
        if not self.presets_file.exists():
            logger.warning(f"Presets file not found: {self.presets_file}")
            return []

        try:
            with open(self.presets_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            presets = data.get("presets", [])

            # Mark as built-in
            for preset in presets:
                preset["is_custom"] = False
                preset["is_built_in"] = True

            return presets

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in presets file: {e}")
            return []
        except Exception as e:
            logger.error(f"Error reading presets file: {e}")
            return []

    def _load_custom_presets(self) -> List[Dict]:
        """Load custom user presets from custom_presets.json.

        Returns:
            List of custom preset dictionaries
        """
        if not self.custom_presets_file.exists():
            return []

        try:
            with open(self.custom_presets_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            presets = data.get("presets", [])

            # Mark as custom
            for preset in presets:
                preset["is_custom"] = True
                preset["is_built_in"] = False

            logger.info(f"Loaded {len(presets)} custom presets")
            return presets

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in custom presets file: {e}")
            return []
        except Exception as e:
            logger.error(f"Error reading custom presets file: {e}")
            return []

    def save_custom_preset(
        self,
        name: str,
        settings: Dict,
        description: str = "",
        category: str = "Custom",
        icon: str = "⭐",
        tags: Optional[List[str]] = None,
        popularity: int = 5
    ) -> bool:
        """Save a new custom preset.

        Args:
            name: Display name for the preset
            settings: Dictionary of prompt builder settings
            description: Optional description of the preset
            category: Category for organization (default: "Custom")
            icon: Emoji icon for display (default: "⭐")
            tags: Optional list of searchable tags
            popularity: Initial popularity score (default: 5)

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Load existing custom presets
            existing_presets = self._load_custom_presets()

            # Generate unique ID
            preset_id = self._generate_preset_id(name)

            # Check for duplicate ID
            if any(p.get("id") == preset_id for p in existing_presets):
                # Append timestamp to make unique
                preset_id = f"{preset_id}_{int(datetime.now().timestamp())}"

            # Create new preset
            new_preset = {
                "id": preset_id,
                "name": name,
                "description": description,
                "category": category,
                "icon": icon,
                "settings": settings,
                "tags": tags or [],
                "popularity": popularity,
                "created_at": datetime.now().isoformat(),
                "is_custom": True,
                "is_built_in": False
            }

            # Add to existing presets
            existing_presets.append(new_preset)

            # Save to file
            self._save_custom_presets_file(existing_presets)

            logger.info(f"Saved custom preset: {name} (id: {preset_id})")
            return True

        except Exception as e:
            logger.error(f"Error saving custom preset: {e}")
            return False

    def delete_preset(self, preset_id: str) -> bool:
        """Delete a custom preset by ID.

        Args:
            preset_id: Unique ID of the preset to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Load custom presets
            presets = self._load_custom_presets()

            # Find preset to delete
            initial_count = len(presets)
            presets = [p for p in presets if p.get("id") != preset_id]

            if len(presets) == initial_count:
                logger.warning(f"Preset not found for deletion: {preset_id}")
                return False

            # Save updated list
            self._save_custom_presets_file(presets)

            logger.info(f"Deleted preset: {preset_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting preset: {e}")
            return False

    def update_preset_popularity(self, preset_id: str, delta: int = 1) -> bool:
        """Increment or decrement a preset's popularity score.

        Args:
            preset_id: Unique ID of the preset
            delta: Amount to change popularity (default: +1)

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Check if it's a custom preset
            presets = self._load_custom_presets()

            for preset in presets:
                if preset.get("id") == preset_id:
                    preset["popularity"] = preset.get("popularity", 5) + delta
                    self._save_custom_presets_file(presets)
                    logger.info(f"Updated popularity for {preset_id}: +{delta}")
                    return True

            logger.warning(f"Cannot update popularity for built-in preset: {preset_id}")
            return False

        except Exception as e:
            logger.error(f"Error updating preset popularity: {e}")
            return False

    def get_categories(self, include_custom: bool = True) -> List[str]:
        """Get list of all unique preset categories.

        Args:
            include_custom: If True, include custom preset categories

        Returns:
            Sorted list of unique category names
        """
        try:
            presets = self.get_presets(include_custom=include_custom, sort_by_popularity=False)
            categories = set(p.get("category", "Uncategorized") for p in presets)
            return sorted(categories)

        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []

    def get_preset_by_id(self, preset_id: str) -> Optional[Dict]:
        """Get a specific preset by its ID.

        Args:
            preset_id: Unique ID of the preset

        Returns:
            Preset dictionary or None if not found
        """
        try:
            all_presets = self.get_presets(sort_by_popularity=False, include_custom=True)

            for preset in all_presets:
                if preset.get("id") == preset_id:
                    return preset

            logger.warning(f"Preset not found: {preset_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting preset by ID: {e}")
            return None

    def _save_custom_presets_file(self, presets: List[Dict]) -> None:
        """Save custom presets to file.

        Args:
            presets: List of preset dictionaries to save
        """
        # Ensure directory exists
        self.presets_dir.mkdir(parents=True, exist_ok=True)

        # Remove metadata fields that shouldn't be saved
        clean_presets = []
        for preset in presets:
            clean_preset = preset.copy()
            # Remove runtime fields
            clean_preset.pop("is_custom", None)
            clean_preset.pop("is_built_in", None)
            clean_presets.append(clean_preset)

        # Write to file
        data = {"presets": clean_presets}

        with open(self.custom_presets_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(presets)} custom presets to {self.custom_presets_file}")

    def _generate_preset_id(self, name: str) -> str:
        """Generate a preset ID from a name.

        Args:
            name: Preset name

        Returns:
            Generated ID (lowercase, underscores)
        """
        # Convert to lowercase and replace spaces with underscores
        preset_id = name.lower().replace(" ", "_")

        # Remove non-alphanumeric characters except underscores
        preset_id = "".join(c for c in preset_id if c.isalnum() or c == "_")

        return preset_id

    def export_preset(self, preset_id: str, export_path: Path) -> bool:
        """Export a preset to a standalone JSON file.

        Args:
            preset_id: ID of the preset to export
            export_path: Path where to save the exported preset

        Returns:
            True if exported successfully, False otherwise
        """
        try:
            preset = self.get_preset_by_id(preset_id)

            if not preset:
                logger.error(f"Cannot export - preset not found: {preset_id}")
                return False

            # Clean up runtime fields
            export_data = preset.copy()
            export_data.pop("is_custom", None)
            export_data.pop("is_built_in", None)

            # Write to file
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported preset {preset_id} to {export_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting preset: {e}")
            return False

    def import_preset(self, import_path: Path) -> bool:
        """Import a preset from a JSON file.

        Args:
            import_path: Path to the preset JSON file

        Returns:
            True if imported successfully, False otherwise
        """
        try:
            # Load preset from file
            with open(import_path, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)

            # Validate required fields
            if not all(k in preset_data for k in ["name", "settings"]):
                logger.error("Invalid preset file - missing required fields")
                return False

            # Save as custom preset
            return self.save_custom_preset(
                name=preset_data.get("name"),
                settings=preset_data.get("settings"),
                description=preset_data.get("description", ""),
                category=preset_data.get("category", "Imported"),
                icon=preset_data.get("icon", "📥"),
                tags=preset_data.get("tags", []),
                popularity=preset_data.get("popularity", 5)
            )

        except Exception as e:
            logger.error(f"Error importing preset: {e}")
            return False
