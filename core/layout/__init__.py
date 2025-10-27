"""
Layout/Books Module for ImageAI.

Provides template-driven page layout for children's books, comics, and magazines.

Phase 2 enhancements:
- Advanced text rendering with hyphenation
- Image processing with filters and effects
- Template variable substitution
- Smart layout algorithms

Phase 3 enhancements:
- Template discovery and management
- Schema validation
- Preview generation
- Template categories and search
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

# Phase 2 modules
from .text_renderer import TextLayoutEngine, LayoutLine, LayoutParagraph
from .image_processor import ImageProcessor
from .template_engine import TemplateEngine
from .layout_algorithms import LayoutAlgorithms, FitResult, PanelGrid

# Phase 3 modules
from .template_manager import (
    TemplateManager,
    TemplateMetadata,
    TemplateValidator,
    TemplatePreviewGenerator,
    ValidationError,
)

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
    # Phase 1 - Core
    "FontManager",
    "LayoutEngine",
    "load_template_json",
    # Phase 2 - Advanced features
    "TextLayoutEngine",
    "LayoutLine",
    "LayoutParagraph",
    "ImageProcessor",
    "TemplateEngine",
    "LayoutAlgorithms",
    "FitResult",
    "PanelGrid",
    # Phase 3 - Template management
    "TemplateManager",
    "TemplateMetadata",
    "TemplateValidator",
    "TemplatePreviewGenerator",
    "ValidationError",
]
