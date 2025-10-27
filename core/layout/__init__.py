"""
Layout/Books Module for ImageAI.

Provides template-driven page layout for children's books, comics, and magazines.
"""

from .models import (
    TextStyle,
    ImageStyle,
    TextBlock,
    ImageBlock,
    PageSpec,
    DocumentSpec,
    Size,
    Rect,
)

from .font_manager import FontManager
from .engine import LayoutEngine, load_template_json

__all__ = [
    # Data models
    "TextStyle",
    "ImageStyle",
    "TextBlock",
    "ImageBlock",
    "PageSpec",
    "DocumentSpec",
    "Size",
    "Rect",
    # Managers and engines
    "FontManager",
    "LayoutEngine",
    # Utilities
    "load_template_json",
]
