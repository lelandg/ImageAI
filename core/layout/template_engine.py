"""
Template variable substitution and processing for the Layout/Books module.

Provides runtime variable replacement, color palette support, and
computed values for dynamic template customization.
"""

import re
from typing import Dict, Any, Optional
from pathlib import Path
import json

from core.logging_config import LogManager
from .models import PageSpec, TextBlock, ImageBlock, TextStyle, ImageStyle

logger = LogManager().get_logger("layout.template")


class TemplateEngine:
    """
    Template processing engine with variable substitution.

    Supports:
    - Variable syntax: {{variable_name}}
    - Color palette variables
    - Computed values (lighter/darker colors)
    - Nested variable references
    - Per-page variable overrides
    """

    VARIABLE_PATTERN = re.compile(r'\{\{([^}]+)\}\}')

    def __init__(self, global_variables: Optional[Dict[str, str]] = None):
        """
        Initialize the template engine.

        Args:
            global_variables: Global variables available to all templates
        """
        self.global_variables = global_variables or {}

    def process_page(
        self,
        page: PageSpec,
        page_variables: Optional[Dict[str, str]] = None
    ) -> PageSpec:
        """
        Process a page specification, substituting all variables.

        Args:
            page: Source page specification
            page_variables: Page-specific variables (override global)

        Returns:
            Processed page with all variables substituted
        """
        # Merge variables (page > template > global)
        variables = {**self.global_variables}
        variables.update(page.variables)
        if page_variables:
            variables.update(page_variables)

        logger.debug(f"Processing page with {len(variables)} variables")

        # Process background
        background = self._substitute(page.background or "", variables)

        # Process blocks
        processed_blocks = []
        for block in page.blocks:
            if isinstance(block, TextBlock):
                processed_blocks.append(self._process_text_block(block, variables))
            elif isinstance(block, ImageBlock):
                processed_blocks.append(self._process_image_block(block, variables))

        return PageSpec(
            page_size_px=page.page_size_px,
            margin_px=page.margin_px,
            bleed_px=page.bleed_px,
            background=background,
            blocks=processed_blocks,
            variables=variables
        )

    def _process_text_block(
        self,
        block: TextBlock,
        variables: Dict[str, str]
    ) -> TextBlock:
        """Process a text block, substituting variables in text and style."""
        # Process text content
        text = self._substitute(block.text, variables)

        # Process style colors
        style = TextStyle(
            family=block.style.family,
            weight=block.style.weight,
            italic=block.style.italic,
            size_px=block.style.size_px,
            line_height=block.style.line_height,
            color=self._substitute(block.style.color, variables),
            align=block.style.align,
            wrap=block.style.wrap,
            letter_spacing=block.style.letter_spacing
        )

        return TextBlock(
            id=block.id,
            rect=block.rect,
            text=text,
            style=style
        )

    def _process_image_block(
        self,
        block: ImageBlock,
        variables: Dict[str, str]
    ) -> ImageBlock:
        """Process an image block, substituting variables in path and style."""
        # Process image path
        image_path = self._substitute(block.image_path or "", variables)

        # Process style colors
        style = ImageStyle(
            fit=block.style.fit,
            border_radius_px=block.style.border_radius_px,
            stroke_px=block.style.stroke_px,
            stroke_color=self._substitute(block.style.stroke_color, variables)
        )

        return ImageBlock(
            id=block.id,
            rect=block.rect,
            image_path=image_path,
            style=style,
            alt_text=block.alt_text
        )

    def _substitute(self, text: str, variables: Dict[str, str]) -> str:
        """
        Substitute variables in text.

        Supports:
        - Simple variables: {{name}}
        - Computed color functions: {{accent_light}}, {{accent_dark}}
        """
        if not text:
            return text

        def replace_var(match):
            var_name = match.group(1).strip()

            # Check for color functions
            if var_name.endswith('_light'):
                base_name = var_name[:-6]
                if base_name in variables:
                    return self._lighten_color(variables[base_name])

            if var_name.endswith('_dark'):
                base_name = var_name[:-5]
                if base_name in variables:
                    return self._darken_color(variables[base_name])

            # Simple variable lookup
            if var_name in variables:
                return variables[var_name]

            # Variable not found, leave as-is
            logger.warning(f"Variable '{var_name}' not found in template")
            return match.group(0)

        return self.VARIABLE_PATTERN.sub(replace_var, text)

    def _lighten_color(self, hex_color: str, amount: float = 0.2) -> str:
        """
        Lighten a hex color by the specified amount.

        Args:
            hex_color: Hex color string (#RRGGBB)
            amount: Amount to lighten (0.0 to 1.0)

        Returns:
            Lightened hex color string
        """
        try:
            # Parse hex color
            h = hex_color.strip('#')
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

            # Lighten by moving towards white
            r = int(r + (255 - r) * amount)
            g = int(g + (255 - g) * amount)
            b = int(b + (255 - b) * amount)

            # Clamp to 0-255
            r, g, b = min(255, r), min(255, g), min(255, b)

            return f"#{r:02x}{g:02x}{b:02x}"

        except Exception as e:
            logger.warning(f"Failed to lighten color {hex_color}: {e}")
            return hex_color

    def _darken_color(self, hex_color: str, amount: float = 0.2) -> str:
        """
        Darken a hex color by the specified amount.

        Args:
            hex_color: Hex color string (#RRGGBB)
            amount: Amount to darken (0.0 to 1.0)

        Returns:
            Darkened hex color string
        """
        try:
            # Parse hex color
            h = hex_color.strip('#')
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

            # Darken by moving towards black
            r = int(r * (1 - amount))
            g = int(g * (1 - amount))
            b = int(b * (1 - amount))

            # Clamp to 0-255
            r, g, b = max(0, r), max(0, g), max(0, b)

            return f"#{r:02x}{g:02x}{b:02x}"

        except Exception as e:
            logger.warning(f"Failed to darken color {hex_color}: {e}")
            return hex_color

    @staticmethod
    def create_color_palette(
        primary: str,
        name: str = "palette"
    ) -> Dict[str, str]:
        """
        Create a color palette from a primary color.

        Args:
            primary: Primary hex color
            name: Palette name prefix

        Returns:
            Dictionary of palette colors
        """
        engine = TemplateEngine()

        return {
            f"{name}_primary": primary,
            f"{name}_light": engine._lighten_color(primary, 0.3),
            f"{name}_lighter": engine._lighten_color(primary, 0.5),
            f"{name}_dark": engine._darken_color(primary, 0.3),
            f"{name}_darker": engine._darken_color(primary, 0.5),
        }

    @staticmethod
    def load_theme(theme_path: Path) -> Dict[str, str]:
        """
        Load a theme file with color palettes and variables.

        Theme file format (JSON):
        {
            "colors": {
                "primary": "#2C7BE5",
                "secondary": "#6C757D",
                "accent": "#FF6B6B"
            },
            "fonts": {
                "heading": "Georgia",
                "body": "Arial"
            },
            "custom": {
                "author": "John Doe"
            }
        }

        Args:
            theme_path: Path to theme JSON file

        Returns:
            Flattened dictionary of theme variables
        """
        try:
            data = json.loads(theme_path.read_text(encoding="utf-8"))
            variables = {}

            # Flatten nested structure
            for category, values in data.items():
                if isinstance(values, dict):
                    for key, value in values.items():
                        variables[f"{category}_{key}"] = str(value)

            logger.info(f"Loaded theme from {theme_path} with {len(variables)} variables")
            return variables

        except Exception as e:
            logger.error(f"Failed to load theme {theme_path}: {e}")
            return {}
