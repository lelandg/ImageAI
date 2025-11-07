"""Loader for prompt builder data (artists, styles, mediums, etc.)."""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class PromptDataLoader:
    """Loads and manages prompt builder data from JSON files."""

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize the prompt data loader.

        Args:
            data_dir: Directory containing JSON data files. If None, uses default location.
        """
        if data_dir is None:
            # Default to data/prompts in the project root
            project_root = Path(__file__).parent.parent
            data_dir = project_root / "data" / "prompts"

        self.data_dir = data_dir
        self._cache: Dict[str, List[str]] = {}

    def load_data(self, category: str) -> List[str]:
        """
        Load data for a specific category.

        Args:
            category: Category name (e.g., 'artists', 'styles', 'mediums')

        Returns:
            List of strings for that category, or empty list if not found
        """
        # Check cache first
        if category in self._cache:
            return self._cache[category]

        # Load from file
        file_path = self.data_dir / f"{category}.json"

        if not file_path.exists():
            logger.warning(f"Prompt data file not found: {file_path}")
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                logger.error(f"Expected list in {file_path}, got {type(data)}")
                return []

            # Cache the data
            self._cache[category] = data
            logger.info(f"Loaded {len(data)} items from {category}.json")

            return data

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return []

    def get_artists(self) -> List[str]:
        """Get list of artists."""
        return self.load_data('artists')

    def get_styles(self) -> List[str]:
        """Get list of art styles."""
        return self.load_data('styles')

    def get_mediums(self) -> List[str]:
        """Get list of art mediums/techniques."""
        return self.load_data('mediums')

    def get_colors(self) -> List[str]:
        """Get list of color schemes."""
        return self.load_data('colors')

    def get_lighting(self) -> List[str]:
        """Get list of lighting options."""
        return self.load_data('lighting')

    def get_moods(self) -> List[str]:
        """Get list of moods."""
        return self.load_data('moods')

    def get_banners(self) -> List[str]:
        """Get list of banner/composition options."""
        return self.load_data('banners')

    def get_all_categories(self) -> Dict[str, List[str]]:
        """
        Get all available categories and their data.

        Returns:
            Dictionary mapping category names to their data lists
        """
        categories = ['artists', 'styles', 'mediums', 'colors', 'lighting', 'moods', 'banners']
        result = {}

        for category in categories:
            data = self.load_data(category)
            if data:
                result[category] = data

        return result

    def reload(self):
        """Clear cache and reload all data."""
        self._cache.clear()
        logger.info("Prompt data cache cleared")

    def save_data(self, category: str, data: List[str]) -> bool:
        """
        Save data for a specific category.

        Args:
            category: Category name
            data: List of strings to save

        Returns:
            True if successful, False otherwise
        """
        file_path = self.data_dir / f"{category}.json"

        try:
            # Ensure directory exists
            self.data_dir.mkdir(parents=True, exist_ok=True)

            # Write JSON with nice formatting
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Update cache
            self._cache[category] = data

            logger.info(f"Saved {len(data)} items to {category}.json")
            return True

        except Exception as e:
            logger.error(f"Error saving {file_path}: {e}")
            return False
