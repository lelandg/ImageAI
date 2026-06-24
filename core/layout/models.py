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
class PageSize:
    """Physical page size with unit + DPI; pixels derived on demand."""

    width: float
    height: float
    unit: Literal["in", "mm", "pt", "px"] = "in"
    orientation: Literal["portrait", "landscape"] = "portrait"
    dpi: int = 300

    def to_pixels(self) -> Tuple[int, int]:
        from core.layout.page_sizes import to_inches
        if self.unit == "px":
            return (round(self.width), round(self.height))
        return (
            round(to_inches(self.width, self.unit) * self.dpi),
            round(to_inches(self.height, self.unit) * self.dpi),
        )

    def swapped(self) -> "PageSize":
        new_orient = "landscape" if self.orientation == "portrait" else "portrait"
        return PageSize(self.height, self.width, self.unit, new_orient, self.dpi)


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
class Region:
    """A selectable layout region (rect or polygon), image or text."""

    id: str
    kind: Literal["image", "text"]
    shape: Literal["rect", "polygon"] = "rect"
    bbox: Rect = (0, 0, 100, 100)
    points: List[Tuple[int, int]] = field(default_factory=list)  # polygon vertices, page px
    z: int = 0
    name: str = ""
    # content (text)
    text: str = ""
    role: str = ""  # font-role name resolved via ProjectStyle (Phase 3)
    # content (image)
    image_ref: Optional[str] = None
    prompt: str = ""  # scaffolding for AI content phases
    gen_settings: Dict[str, Union[str, int, float]] = field(default_factory=dict)
    # style
    text_style: Optional[TextStyle] = None
    image_style: Optional[ImageStyle] = None


@dataclass
class PageSpec:
    """Specification for a single page layout."""

    page_size_px: Size
    margin_px: int = 64
    bleed_px: int = 0
    background: Optional[str] = None  # Hex color or image path
    blocks: List[Union[TextBlock, ImageBlock]] = field(default_factory=list)
    variables: Dict[str, str] = field(default_factory=dict)  # Template variables
    page_size: Optional[PageSize] = None
    regions: List[Region] = field(default_factory=list)


@dataclass
class DocumentSpec:
    """Specification for a complete multi-page document."""

    title: str
    author: Optional[str] = None
    pages: List[PageSpec] = field(default_factory=list)
    theme: Dict[str, str] = field(default_factory=dict)  # Color palette, etc.
    metadata: Dict[str, str] = field(default_factory=dict)  # Custom metadata
    content_kind: str = "custom"
    schema_version: str = "2.0"


def migrate_legacy_blocks(blocks: List[Union[TextBlock, ImageBlock]]) -> List[Region]:
    """Convert legacy TextBlock/ImageBlock objects into Region objects."""
    regions: List[Region] = []
    for b in blocks:
        x, y, w, h = b.rect
        if getattr(b, "type", None) == "image" or isinstance(b, ImageBlock):
            regions.append(Region(
                id=b.id, kind="image", bbox=(x, y, w, h),
                image_ref=getattr(b, "image_path", None),
                image_style=getattr(b, "style", None),
                name=getattr(b, "alt_text", None) or "",
            ))
        else:
            regions.append(Region(
                id=b.id, kind="text", bbox=(x, y, w, h),
                text=getattr(b, "text", "") or "",
                text_style=getattr(b, "style", None),
            ))
    return regions
