"""
Font Generator package for ImageAI.

This package provides functionality to generate typeface files (OTF/TTF/SVG)
from alphabet images. It supports automatic character segmentation, vector
tracing, and font assembly.

Workflow:
1. Load an alphabet image (characters arranged in a grid or rows)
2. Segment individual characters using AlphabetSegmenter
3. Vectorize character outlines (Phase 2)
4. Build font metrics and assemble (Phase 3)
5. Export to font format (Phase 3)
"""

from .segmentation import (
    AlphabetSegmenter,
    CharacterCell,
    SegmentationResult,
    SegmentationMethod,
    UPPERCASE,
    LOWERCASE,
    DIGITS,
    PUNCTUATION,
    FULL_ALPHABET,
)
from .vectorizer import (
    GlyphVectorizer,
    VectorGlyph,
    VectorPath,
    PathSegment,
    PathCommand,
    SmoothingLevel,
    glyphs_to_svg_font,
)
from .metrics import (
    FontMetrics,
    FontMetricsCalculator,
)
from .font_builder import (
    FontBuilder,
    FontInfo,
    create_font_from_glyphs,
    FONTTOOLS_AVAILABLE,
)
from .glyph_identifier import (
    AIGlyphIdentifier,
    GlyphIdentificationResult,
    BatchIdentificationResult,
    get_position_hint,
)
from .glyph_generator import (
    GlyphGenerator,
    GlyphGenerationResult,
)
from .row_detector import (
    RowDetector,
    TextRow,
    CharacterColumn,
)
from .row_column_segmenter import (
    RowColumnSegmenter,
)

__all__ = [
    # Segmentation
    "AlphabetSegmenter",
    "CharacterCell",
    "SegmentationResult",
    "SegmentationMethod",
    # Character sets
    "UPPERCASE",
    "LOWERCASE",
    "DIGITS",
    "PUNCTUATION",
    "FULL_ALPHABET",
    # Vectorization
    "GlyphVectorizer",
    "VectorGlyph",
    "VectorPath",
    "PathSegment",
    "PathCommand",
    "SmoothingLevel",
    "glyphs_to_svg_font",
    # Metrics
    "FontMetrics",
    "FontMetricsCalculator",
    # Font Building
    "FontBuilder",
    "FontInfo",
    "create_font_from_glyphs",
    "FONTTOOLS_AVAILABLE",
    # AI Glyph Identification
    "AIGlyphIdentifier",
    "GlyphIdentificationResult",
    "BatchIdentificationResult",
    "get_position_hint",
    # AI Glyph Generation
    "GlyphGenerator",
    "GlyphGenerationResult",
    # Row-Column Segmentation
    "RowDetector",
    "TextRow",
    "CharacterColumn",
    "RowColumnSegmenter",
]
