"""
Data models for the Layout/Books module.

Defines the core data structures for pages, blocks, styles, and documents.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Literal, Dict, Union

# Type aliases for clarity
Size = Tuple[int, int]  # (width, height) in pixels
Rect = Tuple[int, int, int, int]  # (x, y, width, height) in pixels


@dataclass
class TextStyle:
    """Style configuration for text blocks."""

    family: List[str]  # Priority-ordered font families
    weight: Literal["regular", "medium", "semibold", "bold", "black"] = "regular"
    italic: bool = False
    size_px: int = 32
    line_height: float = 1.3  # Multiplier of font size
    color: str = "#111111"  # Hex color
    align: Literal["left", "center", "right", "justify"] = "left"
    wrap: Literal["word", "char"] = "word"
    letter_spacing: float = 0.0  # Additional spacing in pixels


@dataclass
class ImageStyle:
    """Style configuration for image blocks."""

    fit: Literal["cover", "contain", "fill", "fit_width", "fit_height"] = "cover"
    border_radius_px: int = 0
    stroke_px: int = 0
    stroke_color: str = "#000000"


@dataclass
class BlockBase:
    """Base class for all block types."""

    id: str  # Unique identifier within the page
    rect: Rect  # Position and size within page


@dataclass
class TextBlock(BlockBase):
    """A text content block."""

    type: Literal["text"] = "text"
    text: str = ""
    style: TextStyle = field(default_factory=lambda: TextStyle(
        family=["Arial", "Helvetica", "DejaVu Sans"]
    ))


@dataclass
class ImageBlock(BlockBase):
    """An image content block."""

    type: Literal["image"] = "image"
    image_path: Optional[str] = None
    style: ImageStyle = field(default_factory=ImageStyle)
    alt_text: Optional[str] = None


@dataclass
class PageSpec:
    """Specification for a single page layout."""

    page_size_px: Size
    margin_px: int = 64
    bleed_px: int = 0
    background: Optional[str] = None  # Hex color or image path
    blocks: List[Union[TextBlock, ImageBlock]] = field(default_factory=list)
    variables: Dict[str, str] = field(default_factory=dict)  # Template variables


@dataclass
class DocumentSpec:
    """Specification for a complete multi-page document."""

    title: str
    author: Optional[str] = None
    pages: List[PageSpec] = field(default_factory=list)
    theme: Dict[str, str] = field(default_factory=dict)  # Color palette, etc.
    metadata: Dict[str, str] = field(default_factory=dict)  # Custom metadata
