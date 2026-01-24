"""
Font metrics calculation for vectorized glyphs.

This module analyzes vectorized characters to calculate font metrics
including baseline, x-height, cap-height, ascenders, descenders,
and basic kerning pairs.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set

from .vectorizer import VectorGlyph

logger = logging.getLogger(__name__)


# Character categories for metric analysis
UPPERCASE_FLAT = set("EFHILTZ")  # Uppercase with flat tops (for cap-height)
UPPERCASE_ROUND = set("CDGOQS")  # Uppercase with round tops
LOWERCASE_XHEIGHT = set("acemnorsuvwxz")  # Lowercase for x-height
LOWERCASE_ASCENDER = set("bdfhklt")  # Lowercase with ascenders
LOWERCASE_DESCENDER = set("gjpqy")  # Lowercase with descenders
DIGITS = set("0123456789")

# Common kerning pairs (characters that often need spacing adjustment)
KERNING_PAIRS = [
    # Capital + lowercase
    ("A", "v"), ("A", "w"), ("A", "y"),
    ("F", "a"), ("F", "e"), ("F", "o"),
    ("L", "T"), ("L", "V"), ("L", "W"), ("L", "Y"),
    ("P", "a"), ("P", "e"), ("P", "o"),
    ("T", "a"), ("T", "e"), ("T", "o"), ("T", "r"), ("T", "y"),
    ("V", "a"), ("V", "e"), ("V", "o"),
    ("W", "a"), ("W", "e"), ("W", "o"),
    ("Y", "a"), ("Y", "e"), ("Y", "o"),
    # Capital + Capital
    ("A", "T"), ("A", "V"), ("A", "W"), ("A", "Y"),
    ("L", "A"),
    # Lowercase pairs
    ("f", "f"), ("f", "i"), ("f", "l"),
    ("r", "a"), ("r", "e"), ("r", "o"),
    ("v", "a"), ("v", "e"), ("v", "o"),
    ("w", "a"), ("w", "e"), ("w", "o"),
    ("y", "a"), ("y", "e"), ("y", "o"),
    # Punctuation
    (".", "'"), (",", "'"),
    ("A", "'"), ("T", "'"),
]


@dataclass
class FontMetrics:
    """
    Calculated font metrics for a set of glyphs.

    All values are in font units (typically 1000 or 2048 units per em).
    """

    # Vertical metrics
    units_per_em: int = 1000
    ascender: float = 800      # Top of tallest lowercase ascender (b, d, h, etc.)
    descender: float = -200    # Bottom of deepest descender (g, j, p, etc.)
    cap_height: float = 700    # Top of uppercase letters
    x_height: float = 500      # Top of lowercase x (and similar)
    baseline: float = 0        # Baseline position

    # Line metrics
    line_gap: float = 0        # Extra space between lines

    # Character widths (label -> advance width)
    advance_widths: Dict[str, float] = field(default_factory=dict)

    # Kerning adjustments (pair -> adjustment)
    kerning: Dict[Tuple[str, str], float] = field(default_factory=dict)

    # Bounding boxes per character (label -> (xMin, yMin, xMax, yMax))
    bboxes: Dict[str, Tuple[float, float, float, float]] = field(default_factory=dict)

    @property
    def typo_ascender(self) -> float:
        """OS/2 sTypoAscender value."""
        return self.ascender

    @property
    def typo_descender(self) -> float:
        """OS/2 sTypoDescender value (negative)."""
        return self.descender

    @property
    def win_ascent(self) -> float:
        """OS/2 usWinAscent (positive)."""
        return max(self.ascender, self.cap_height)

    @property
    def win_descent(self) -> float:
        """OS/2 usWinDescent (positive, despite measuring below baseline)."""
        return abs(self.descender)


class FontMetricsCalculator:
    """
    Calculates font metrics from a set of vectorized glyphs.

    Analyzes glyph bounds to determine baseline, x-height, cap-height,
    ascenders, and descenders. Also generates basic kerning pairs.
    """

    def __init__(
        self,
        units_per_em: int = 1000,
        default_side_bearing: float = 3,
        kerning_threshold: float = 0.15,
    ):
        """
        Initialize the calculator.

        Args:
            units_per_em: Font units per em (standard: 1000 or 2048)
            default_side_bearing: Default side bearing as % of em (typically 2-5%)
            kerning_threshold: Threshold for kerning (% of em)
        """
        self.units_per_em = units_per_em
        self.default_side_bearing = default_side_bearing * units_per_em / 100
        self.kerning_threshold = kerning_threshold * units_per_em
        self._normalized_glyphs: List[VectorGlyph] = []

    def get_normalized_glyphs(self) -> List[VectorGlyph]:
        """
        Get the normalized glyphs after calculate() has been called.

        Returns:
            List of VectorGlyph objects with proper baseline positioning,
            including descenders below baseline (negative Y).
        """
        return self._normalized_glyphs

    def calculate(self, glyphs: List[VectorGlyph]) -> FontMetrics:
        """
        Calculate font metrics from a list of vectorized glyphs.

        Args:
            glyphs: List of VectorGlyph objects

        Returns:
            FontMetrics with calculated values

        Note:
            After calling this method, use get_normalized_glyphs() to retrieve
            the glyphs with proper baseline/descender positioning.
        """
        if not glyphs:
            logger.warning("No glyphs provided for metrics calculation")
            self._normalized_glyphs = []
            return FontMetrics(units_per_em=self.units_per_em)

        # Normalize glyphs to standard coordinate space
        normalized = self._normalize_glyphs(glyphs)
        self._normalized_glyphs = normalized  # Store for later retrieval
        norm_map = {g.label: g for g in normalized}

        metrics = FontMetrics(units_per_em=self.units_per_em)

        # Calculate vertical metrics
        metrics.baseline = 0  # By convention
        metrics.cap_height = self._calculate_cap_height(norm_map)
        metrics.x_height = self._calculate_x_height(norm_map)
        metrics.ascender = self._calculate_ascender(norm_map, metrics.cap_height)
        metrics.descender = self._calculate_descender(norm_map)

        # Calculate advance widths and bboxes
        for glyph in normalized:
            bbox = glyph.bounds
            metrics.bboxes[glyph.label] = bbox

            # Advance width = glyph width + side bearings
            glyph_width = bbox[2] - bbox[0]
            metrics.advance_widths[glyph.label] = glyph_width + self.default_side_bearing * 2

        # Calculate kerning
        metrics.kerning = self._calculate_kerning(norm_map, metrics.advance_widths)

        logger.info(
            f"Calculated metrics: cap={metrics.cap_height:.0f}, "
            f"x={metrics.x_height:.0f}, asc={metrics.ascender:.0f}, "
            f"desc={metrics.descender:.0f}"
        )

        return metrics

    def _normalize_glyphs(self, glyphs: List[VectorGlyph]) -> List[VectorGlyph]:
        """
        Normalize glyphs to standard font coordinate space.

        Scales glyphs so the tallest uppercase letter fits within units_per_em,
        and positions baseline at y=0. Handles descenders by aligning their
        x-height with other lowercase letters.

        Note: Glyphs from vectorizer already have Y-up coordinates (font space),
        so we only need to scale and translate, NOT flip Y again.
        """
        if not glyphs:
            return glyphs

        glyph_map = {g.label: g for g in glyphs}

        # Find the tallest uppercase letter for scaling reference
        max_cap_height = 0
        for glyph in glyphs:
            if glyph.label in UPPERCASE_FLAT or glyph.label in UPPERCASE_ROUND:
                bbox = glyph.bounds
                height = bbox[3] - bbox[1]
                max_cap_height = max(max_cap_height, height)

        if max_cap_height == 0:
            # Fallback: use any uppercase glyph
            for glyph in glyphs:
                if glyph.label.isupper():
                    bbox = glyph.bounds
                    height = bbox[3] - bbox[1]
                    max_cap_height = max(max_cap_height, height)

        if max_cap_height == 0:
            # Last resort: use tallest glyph
            for glyph in glyphs:
                bbox = glyph.bounds
                height = bbox[3] - bbox[1]
                max_cap_height = max(max_cap_height, height)

        if max_cap_height == 0:
            return glyphs

        # Scale factor to make cap height ~70% of em
        target_cap_height = self.units_per_em * 0.7
        scale = target_cap_height / max_cap_height

        # Calculate x-height from non-descender lowercase letters
        # These letters have their bottom at the baseline
        x_height_samples = []
        for char in LOWERCASE_XHEIGHT:
            if char in glyph_map:
                bbox = glyph_map[char].bounds
                x_height_samples.append(bbox[3] - bbox[1])  # Height of x-height chars

        avg_xheight = sum(x_height_samples) / len(x_height_samples) if x_height_samples else max_cap_height * 0.7

        # Create normalized glyphs
        normalized = []
        for glyph in glyphs:
            from .vectorizer import VectorGlyph, VectorPath, PathSegment

            bbox = glyph.bounds
            glyph_height = bbox[3] - bbox[1]

            # Determine vertical offset based on character type
            # Goal: after (y - y_offset) * scale, baseline chars have yMin at 0,
            # and descender chars have their x-height top at avg_xheight
            if glyph.label == 'j':
                # Special case: 'j' has both a descender AND a dot above x-height
                # Compare to other descender chars (g, p, q, y) to estimate dot height
                other_descender_heights = []
                for dc in ['g', 'p', 'q', 'y']:
                    if dc in glyph_map:
                        dc_bbox = glyph_map[dc].bounds
                        other_descender_heights.append(dc_bbox[3] - dc_bbox[1])

                if other_descender_heights:
                    avg_descender_height = sum(other_descender_heights) / len(other_descender_heights)
                    # The dot portion is the extra height of 'j' compared to other descenders
                    dot_height = max(0, glyph_height - avg_descender_height)
                    # Align 'j' like other descenders, but accounting for the dot
                    y_offset = bbox[3] - avg_xheight - dot_height
                else:
                    # Fallback: treat like other descenders
                    y_offset = bbox[3] - avg_xheight

                descender_depth = (bbox[1] - y_offset) * scale
                logger.debug(f"Descender 'j' (special): height={glyph_height:.0f}, "
                           f"x-height={avg_xheight:.0f}, descender={descender_depth:.0f}")
            elif glyph.label in LOWERCASE_DESCENDER:
                # Descender characters (g, p, q, y): align their TOP (yMax) with x-height
                # After transform: (bbox[3] - y_offset) * scale = avg_xheight * scale
                # So: y_offset = bbox[3] - avg_xheight
                y_offset = bbox[3] - avg_xheight
                descender_depth = (bbox[1] - y_offset) * scale  # Will be negative
                logger.debug(f"Descender '{glyph.label}': height={glyph_height:.0f}, "
                           f"x-height={avg_xheight:.0f}, descender={descender_depth:.0f}")
            elif glyph.label in LOWERCASE_XHEIGHT:
                # x-height lowercase: bottom at baseline (y=0)
                y_offset = bbox[1]
            elif glyph.label in LOWERCASE_ASCENDER:
                # Ascender lowercase (b, d, h, etc.): bottom at baseline
                y_offset = bbox[1]
            elif glyph.label.isupper() or glyph.label in DIGITS:
                # Uppercase and digits: bottom at baseline
                y_offset = bbox[1]
            else:
                # Default: bottom at baseline
                y_offset = bbox[1]

            new_paths = []
            for path in glyph.paths:
                new_segments = []
                for seg in path.segments:
                    new_points = []
                    for x, y in seg.points:
                        new_x = x * scale
                        # Translate so baseline is at y=0
                        new_y = (y - y_offset) * scale
                        new_points.append((new_x, new_y))
                    new_segments.append(PathSegment(seg.command, new_points))
                new_paths.append(VectorPath(segments=new_segments, is_hole=path.is_hole))

            new_glyph = VectorGlyph(
                label=glyph.label,
                paths=new_paths,
                width=glyph.width * scale,
                height=glyph.height * scale,
                advance_width=glyph.advance_width * scale,
            )
            normalized.append(new_glyph)

        return normalized

    def _calculate_cap_height(self, glyph_map: Dict[str, VectorGlyph]) -> float:
        """Calculate cap height from uppercase letters."""
        heights = []

        # Prefer flat-top letters for accuracy
        for char in UPPERCASE_FLAT:
            if char in glyph_map:
                bbox = glyph_map[char].bounds
                heights.append(bbox[3])  # yMax

        if not heights:
            # Fallback to any uppercase
            for char in UPPERCASE_ROUND:
                if char in glyph_map:
                    bbox = glyph_map[char].bounds
                    heights.append(bbox[3])

        if heights:
            return sum(heights) / len(heights)

        return self.units_per_em * 0.7  # Default fallback

    def _calculate_x_height(self, glyph_map: Dict[str, VectorGlyph]) -> float:
        """Calculate x-height from lowercase letters."""
        heights = []

        for char in LOWERCASE_XHEIGHT:
            if char in glyph_map:
                bbox = glyph_map[char].bounds
                heights.append(bbox[3])  # yMax

        if heights:
            return sum(heights) / len(heights)

        # Fallback: ~50% of cap height
        return self.units_per_em * 0.5

    def _calculate_ascender(
        self,
        glyph_map: Dict[str, VectorGlyph],
        cap_height: float,
    ) -> float:
        """Calculate ascender height from lowercase letters with ascenders."""
        heights = []

        for char in LOWERCASE_ASCENDER:
            if char in glyph_map:
                bbox = glyph_map[char].bounds
                heights.append(bbox[3])  # yMax

        if heights:
            return max(max(heights), cap_height)

        # Fallback: slightly above cap height
        return cap_height * 1.1

    def _calculate_descender(self, glyph_map: Dict[str, VectorGlyph]) -> float:
        """Calculate descender depth from lowercase letters with descenders."""
        depths = []

        for char in LOWERCASE_DESCENDER:
            if char in glyph_map:
                bbox = glyph_map[char].bounds
                depths.append(bbox[1])  # yMin (negative)

        if depths:
            return min(depths)

        # Fallback: ~20% below baseline
        return -self.units_per_em * 0.2

    def _calculate_kerning(
        self,
        glyph_map: Dict[str, VectorGlyph],
        advance_widths: Dict[str, float],
    ) -> Dict[Tuple[str, str], float]:
        """
        Calculate basic kerning pairs.

        Uses simple heuristics based on glyph shapes to determine
        which character pairs need spacing adjustment.
        """
        kerning = {}

        for left, right in KERNING_PAIRS:
            if left not in glyph_map or right not in glyph_map:
                continue

            # Get glyph shapes
            left_glyph = glyph_map[left]
            right_glyph = glyph_map[right]

            # Calculate kern value based on shape analysis
            kern = self._calculate_kern_value(left_glyph, right_glyph)

            if abs(kern) >= self.kerning_threshold:
                kerning[(left, right)] = kern
                logger.debug(f"Kerning '{left}'+'{right}': {kern:.0f}")

        return kerning

    def _calculate_kern_value(
        self,
        left: VectorGlyph,
        right: VectorGlyph,
    ) -> float:
        """
        Calculate kerning value for a pair of glyphs.

        Uses shape analysis to determine optimal spacing.
        Negative values bring characters closer together.
        """
        left_bbox = left.bounds
        right_bbox = right.bounds

        # Analyze right edge of left glyph
        left_edge_type = self._analyze_edge(left, "right")

        # Analyze left edge of right glyph
        right_edge_type = self._analyze_edge(right, "left")

        # Determine kern based on edge types
        # Diagonal + diagonal = tighten
        # Diagonal + straight = slight tighten
        # Round + round = no change

        kern = 0.0
        base_kern = -self.units_per_em * 0.05  # -5% of em

        if left_edge_type == "diagonal" and right_edge_type == "diagonal":
            kern = base_kern * 2
        elif left_edge_type == "diagonal" or right_edge_type == "diagonal":
            kern = base_kern
        elif left_edge_type == "open" or right_edge_type == "open":
            kern = base_kern * 0.5

        # Special cases
        if left.label in "FPTY" and right.label in "aeo":
            kern = base_kern * 2.5
        if left.label == "L" and right.label in "TVWY":
            kern = base_kern * 3
        if left.label == "A" and right.label in "VWY":
            kern = base_kern * 2.5

        return kern

    def _analyze_edge(self, glyph: VectorGlyph, side: str) -> str:
        """
        Analyze the edge shape of a glyph.

        Returns:
            "straight": Vertical edge (H, I, etc.)
            "diagonal": Angled edge (A, V, W, etc.)
            "round": Curved edge (O, C, etc.)
            "open": Open/concave edge (L, T crossbar, etc.)
        """
        bbox = glyph.bounds

        if not glyph.paths:
            return "straight"

        # Sample points along the edge
        edge_points = []
        for path in glyph.paths:
            if path.is_hole:
                continue
            for seg in path.segments:
                for x, y in seg.points:
                    if side == "right" and x > bbox[2] - (bbox[2] - bbox[0]) * 0.2:
                        edge_points.append((x, y))
                    elif side == "left" and x < bbox[0] + (bbox[2] - bbox[0]) * 0.2:
                        edge_points.append((x, y))

        if not edge_points:
            return "straight"

        # Analyze distribution
        xs = [p[0] for p in edge_points]
        x_range = max(xs) - min(xs) if xs else 0

        width = bbox[2] - bbox[0]
        if width == 0:
            return "straight"

        variation = x_range / width

        if variation < 0.1:
            return "straight"
        elif variation < 0.3:
            return "round"
        else:
            return "diagonal"
