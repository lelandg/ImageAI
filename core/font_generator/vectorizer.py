"""
Glyph vectorization for converting bitmap characters to vector paths.

This module converts segmented character images into smooth vector outlines
suitable for font generation. It handles both outer contours and inner holes
(like the inside of 'O', 'A', 'B', etc.).
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional, Union

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class PathCommand(Enum):
    """SVG-style path commands."""
    MOVE = "M"      # Move to point
    LINE = "L"      # Line to point
    CURVE = "C"     # Cubic Bezier curve
    QUAD = "Q"      # Quadratic Bezier curve
    CLOSE = "Z"     # Close path


@dataclass
class PathSegment:
    """A single segment in a vector path."""
    command: PathCommand
    points: List[Tuple[float, float]] = field(default_factory=list)

    def to_svg(self) -> str:
        """Convert to SVG path data string."""
        if self.command == PathCommand.CLOSE:
            return "Z"
        coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in self.points)
        return f"{self.command.value} {coords}"


@dataclass
class VectorPath:
    """A complete vector path (contour) for a glyph."""
    segments: List[PathSegment] = field(default_factory=list)
    is_hole: bool = False  # True if this is an inner contour (hole)

    def to_svg_d(self) -> str:
        """Convert to SVG 'd' attribute value."""
        return " ".join(seg.to_svg() for seg in self.segments)

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """Get bounding box (min_x, min_y, max_x, max_y)."""
        all_points = []
        for seg in self.segments:
            all_points.extend(seg.points)
        if not all_points:
            return (0, 0, 0, 0)
        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]
        return (min(xs), min(ys), max(xs), max(ys))


@dataclass
class VectorGlyph:
    """A vectorized glyph containing all paths for a character."""
    label: str
    paths: List[VectorPath] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    advance_width: float = 0.0  # Horizontal advance for font metrics

    def to_svg(self, scale: float = 1.0) -> str:
        """Generate complete SVG element for this glyph."""
        paths_svg = []
        for path in self.paths:
            fill_rule = "evenodd"  # Handles holes correctly
            d = path.to_svg_d()
            paths_svg.append(f'<path d="{d}" fill="black" fill-rule="{fill_rule}"/>')

        return f'''<svg xmlns="http://www.w3.org/2000/svg"
            width="{self.width * scale}" height="{self.height * scale}"
            viewBox="0 0 {self.width} {self.height}">
            {"".join(paths_svg)}
        </svg>'''

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """Get combined bounding box of all paths."""
        if not self.paths:
            return (0, 0, self.width, self.height)
        all_bounds = [p.bounds for p in self.paths]
        return (
            min(b[0] for b in all_bounds),
            min(b[1] for b in all_bounds),
            max(b[2] for b in all_bounds),
            max(b[3] for b in all_bounds),
        )


class SmoothingLevel(Enum):
    """Predefined smoothing levels for vectorization."""
    NONE = 0        # No smoothing, preserve all points
    LOW = 1         # Minimal smoothing
    MEDIUM = 2      # Balanced (default)
    HIGH = 3        # Aggressive smoothing
    MAXIMUM = 4     # Maximum smoothing (may lose detail)


class GlyphVectorizer:
    """
    Converts bitmap character images to vector paths.

    Uses OpenCV contour detection and custom Bezier curve fitting
    to produce smooth, scalable vector outlines.
    """

    # Smoothing parameters for each level
    # Lower epsilon = more detail preserved
    # Higher blur = smoother edges (reduces aliasing artifacts)
    SMOOTHING_PARAMS = {
        SmoothingLevel.NONE: {
            "epsilon_factor": 0.0,
            "corner_threshold": 180,
            "blur_kernel": 0,      # No blur
            "morph_kernel": 0,     # No morphological ops
        },
        SmoothingLevel.LOW: {
            "epsilon_factor": 0.0005,  # Reduced from 0.001 for more detail
            "corner_threshold": 160,   # Increased to detect more corners
            "blur_kernel": 3,          # Light blur to reduce aliasing
            "morph_kernel": 0,
        },
        SmoothingLevel.MEDIUM: {
            "epsilon_factor": 0.001,   # Reduced from 0.002
            "corner_threshold": 145,   # Adjusted from 135
            "blur_kernel": 5,          # Moderate blur
            "morph_kernel": 3,         # Light morphological smoothing
        },
        SmoothingLevel.HIGH: {
            "epsilon_factor": 0.002,   # Reduced from 0.004
            "corner_threshold": 130,
            "blur_kernel": 7,
            "morph_kernel": 5,
        },
        SmoothingLevel.MAXIMUM: {
            "epsilon_factor": 0.004,   # Reduced from 0.008
            "corner_threshold": 110,
            "blur_kernel": 9,
            "morph_kernel": 7,
        },
    }

    def __init__(
        self,
        smoothing: SmoothingLevel = SmoothingLevel.MEDIUM,
        min_contour_area: int = 50,
        use_bezier: bool = True,
        normalize_size: Optional[int] = None,
        preserve_detail: bool = True,
    ):
        """
        Initialize the vectorizer.

        Args:
            smoothing: Smoothing level for path simplification
            min_contour_area: Minimum contour area to include (filters noise)
            use_bezier: If True, fit Bezier curves; if False, use polylines
            normalize_size: If set, normalize glyphs to this height in units
            preserve_detail: If True, use CHAIN_APPROX_NONE for maximum detail
        """
        self.smoothing = smoothing
        self.min_contour_area = min_contour_area
        self.use_bezier = use_bezier
        self.normalize_size = normalize_size
        self.preserve_detail = preserve_detail

        params = self.SMOOTHING_PARAMS[smoothing]
        self.epsilon_factor = params["epsilon_factor"]
        self.corner_threshold = params["corner_threshold"]
        self.blur_kernel = params.get("blur_kernel", 0)
        self.morph_kernel = params.get("morph_kernel", 0)

    def vectorize(
        self,
        image: np.ndarray | Image.Image,
        label: str = "",
    ) -> VectorGlyph:
        """
        Convert a bitmap character image to vector paths.

        Args:
            image: Character image (grayscale or RGBA)
            label: Character label (e.g., 'A')

        Returns:
            VectorGlyph with all contour paths
        """
        # Convert to numpy if needed
        if isinstance(image, Image.Image):
            image = np.array(image)

        # Get binary image
        binary = self._prepare_binary(image)
        h, w = binary.shape

        logger.debug(f"Vectorizing '{label}': {w}x{h} pixels")

        # Find contours with hierarchy (to identify holes)
        # Use CHAIN_APPROX_NONE to preserve all contour points for smoother curves
        # CHAIN_APPROX_SIMPLE compresses contours and loses curve detail
        approx_method = cv2.CHAIN_APPROX_NONE if self.preserve_detail else cv2.CHAIN_APPROX_SIMPLE
        contours, hierarchy = cv2.findContours(
            binary, cv2.RETR_CCOMP, approx_method
        )
        logger.debug(f"Found {len(contours) if contours else 0} contours using {'NONE' if self.preserve_detail else 'SIMPLE'} approximation")

        if not contours:
            logger.warning(f"No contours found for '{label}'")
            return VectorGlyph(label=label, width=w, height=h)

        # Process contours
        paths = self._process_contours(contours, hierarchy, w, h)

        # Create glyph
        glyph = VectorGlyph(
            label=label,
            paths=paths,
            width=float(w),
            height=float(h),
            advance_width=float(w),
        )

        # Normalize if requested
        if self.normalize_size:
            glyph = self._normalize_glyph(glyph)

        return glyph

    def _prepare_binary(self, image: np.ndarray) -> np.ndarray:
        """Prepare binary image for contour detection with preprocessing for smooth edges."""
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            if image.shape[2] == 4:
                # RGBA - use alpha or convert
                alpha = image[:, :, 3]
                if np.any(alpha < 255):
                    # Use alpha channel
                    gray = np.where(alpha > 128,
                                   cv2.cvtColor(image[:, :, :3], cv2.COLOR_RGB2GRAY),
                                   255).astype(np.uint8)
                else:
                    gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_RGB2GRAY)
            else:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.copy()

        # Apply Gaussian blur BEFORE thresholding to smooth anti-aliased edges
        # This is critical for preserving smooth curves from the source image
        if self.blur_kernel > 0:
            gray = cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), 0)
            logger.debug(f"Applied Gaussian blur with kernel {self.blur_kernel}")

        # Threshold to binary
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Apply morphological operations to smooth the binary edges
        if self.morph_kernel > 0:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (self.morph_kernel, self.morph_kernel)
            )
            # Close small gaps first
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            # Then open to remove small protrusions
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
            logger.debug(f"Applied morphological smoothing with kernel {self.morph_kernel}")

        return binary

    def _process_contours(
        self,
        contours: Tuple,
        hierarchy: np.ndarray,
        width: int,
        height: int,
    ) -> List[VectorPath]:
        """Process contours and their hierarchy into vector paths."""
        paths = []

        if hierarchy is None:
            # No hierarchy, treat all as outer contours
            for cnt in contours:
                if cv2.contourArea(cnt) >= self.min_contour_area:
                    path = self._contour_to_path(cnt, height, is_hole=False)
                    if path.segments:
                        paths.append(path)
            return paths

        hierarchy = hierarchy[0]  # Unwrap

        for idx, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            if area < self.min_contour_area:
                continue

            # Check hierarchy: [next, prev, child, parent]
            # If parent is -1, this is an outer contour
            # If parent >= 0, this is a hole (inner contour)
            parent = hierarchy[idx][3]
            is_hole = parent >= 0

            path = self._contour_to_path(cnt, height, is_hole=is_hole)
            if path.segments:
                paths.append(path)

        return paths

    def _contour_to_path(
        self,
        contour: np.ndarray,
        height: int,
        is_hole: bool = False,
    ) -> VectorPath:
        """Convert an OpenCV contour to a VectorPath.

        Args:
            contour: OpenCV contour array
            height: Image height (needed for Y-flip to font coordinates)
            is_hole: Whether this contour is a hole (inner contour)
        """
        path = VectorPath(is_hole=is_hole)

        # Simplify contour using Douglas-Peucker algorithm
        if self.epsilon_factor > 0:
            epsilon = self.epsilon_factor * cv2.arcLength(contour, True)
            contour = cv2.approxPolyDP(contour, epsilon, True)

        points = contour.squeeze()
        if len(points.shape) == 1:
            # Single point, skip
            return path

        if len(points) < 3:
            return path

        # Convert to float tuples and flip Y for font coordinate system
        # (fonts use bottom-left origin with Y-up, images use top-left with Y-down)
        points_list = [(float(p[0]), float(height - p[1])) for p in points]

        if self.use_bezier:
            # Fit Bezier curves through the points
            segments = self._fit_bezier_path(points_list)
        else:
            # Use simple polyline
            segments = self._points_to_polyline(points_list)

        path.segments = segments
        return path

    def _points_to_polyline(
        self,
        points: List[Tuple[float, float]],
    ) -> List[PathSegment]:
        """Convert points to simple line segments."""
        if not points:
            return []

        segments = [PathSegment(PathCommand.MOVE, [points[0]])]

        for point in points[1:]:
            segments.append(PathSegment(PathCommand.LINE, [point]))

        segments.append(PathSegment(PathCommand.CLOSE, []))
        return segments

    def _fit_bezier_path(
        self,
        points: List[Tuple[float, float]],
    ) -> List[PathSegment]:
        """Fit smooth Bezier curves through points."""
        if len(points) < 2:
            return []

        segments = [PathSegment(PathCommand.MOVE, [points[0]])]

        # Detect corners based on angle changes
        corners = self._detect_corners(points)

        # Split at corners and fit curves to each segment
        start_idx = 0
        for corner_idx in corners + [len(points) - 1]:
            segment_points = points[start_idx:corner_idx + 1]

            if len(segment_points) >= 2:
                curve_segments = self._fit_bezier_segment(segment_points)
                segments.extend(curve_segments)

            start_idx = corner_idx

        segments.append(PathSegment(PathCommand.CLOSE, []))
        return segments

    def _detect_corners(
        self,
        points: List[Tuple[float, float]],
    ) -> List[int]:
        """Detect corner points based on angle changes."""
        if len(points) < 3:
            return []

        corners = []
        threshold_rad = math.radians(self.corner_threshold)

        for i in range(1, len(points) - 1):
            p0 = points[i - 1]
            p1 = points[i]
            p2 = points[i + 1]

            # Calculate angle at p1
            angle = self._angle_between(p0, p1, p2)

            if angle < threshold_rad:
                corners.append(i)

        return corners

    def _angle_between(
        self,
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
    ) -> float:
        """Calculate angle at p1 between p0-p1 and p1-p2."""
        v1 = (p0[0] - p1[0], p0[1] - p1[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])

        len1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2)
        len2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2)

        if len1 == 0 or len2 == 0:
            return math.pi

        dot = v1[0] * v2[0] + v1[1] * v2[1]
        cos_angle = max(-1, min(1, dot / (len1 * len2)))

        return math.acos(cos_angle)

    def _fit_bezier_segment(
        self,
        points: List[Tuple[float, float]],
    ) -> List[PathSegment]:
        """Fit cubic Bezier curves to a sequence of points using improved algorithm."""
        if len(points) < 2:
            return []

        if len(points) == 2:
            # Just a line
            return [PathSegment(PathCommand.LINE, [points[1]])]

        if len(points) == 3:
            # Quadratic Bezier through midpoint
            return [PathSegment(PathCommand.QUAD, [points[1], points[2]])]

        # For longer sequences, use improved cubic Bezier fitting
        # Resample points for even distribution if we have many points
        if len(points) > 20:
            points = self._resample_points(points, max(8, len(points) // 3))

        segments = []
        n = len(points)

        # Use smooth cubic spline fitting
        # Calculate tangent directions at each point for C1 continuity
        tangents = self._calculate_tangents(points)

        i = 0
        while i < n - 1:
            p0 = points[i]
            p3 = points[min(i + 3, n - 1)]

            # Calculate control points based on tangent directions
            # This produces smoother curves than simple Catmull-Rom
            t0 = tangents[i]
            t3 = tangents[min(i + 3, n - 1)]

            # Distance for control point placement (1/3 of segment length works well)
            dist = math.sqrt((p3[0] - p0[0])**2 + (p3[1] - p0[1])**2) / 3

            ctrl1 = (p0[0] + t0[0] * dist, p0[1] + t0[1] * dist)
            ctrl2 = (p3[0] - t3[0] * dist, p3[1] - t3[1] * dist)

            segments.append(PathSegment(PathCommand.CURVE, [ctrl1, ctrl2, p3]))

            # Move forward - skip 3 points per curve for smoother result
            i += max(1, min(3, n - i - 1))

        return segments

    def _resample_points(
        self,
        points: List[Tuple[float, float]],
        target_count: int,
    ) -> List[Tuple[float, float]]:
        """Resample points to have roughly even spacing."""
        if len(points) <= target_count:
            return points

        # Calculate cumulative arc length
        arc_lengths = [0.0]
        for i in range(1, len(points)):
            dx = points[i][0] - points[i-1][0]
            dy = points[i][1] - points[i-1][1]
            arc_lengths.append(arc_lengths[-1] + math.sqrt(dx*dx + dy*dy))

        total_length = arc_lengths[-1]
        if total_length == 0:
            return [points[0], points[-1]]

        # Resample at even intervals
        resampled = [points[0]]
        step = total_length / (target_count - 1)

        for i in range(1, target_count - 1):
            target_length = i * step
            # Find the segment containing this length
            for j in range(1, len(arc_lengths)):
                if arc_lengths[j] >= target_length:
                    # Interpolate between points[j-1] and points[j]
                    t = (target_length - arc_lengths[j-1]) / (arc_lengths[j] - arc_lengths[j-1])
                    x = points[j-1][0] + t * (points[j][0] - points[j-1][0])
                    y = points[j-1][1] + t * (points[j][1] - points[j-1][1])
                    resampled.append((x, y))
                    break

        resampled.append(points[-1])
        return resampled

    def _calculate_tangents(
        self,
        points: List[Tuple[float, float]],
    ) -> List[Tuple[float, float]]:
        """Calculate unit tangent vectors at each point for smooth curve fitting."""
        n = len(points)
        tangents = []

        for i in range(n):
            if i == 0:
                # Forward difference
                dx = points[1][0] - points[0][0]
                dy = points[1][1] - points[0][1]
            elif i == n - 1:
                # Backward difference
                dx = points[-1][0] - points[-2][0]
                dy = points[-1][1] - points[-2][1]
            else:
                # Central difference for smoother tangents
                dx = points[i+1][0] - points[i-1][0]
                dy = points[i+1][1] - points[i-1][1]

            # Normalize to unit vector
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                tangents.append((dx/length, dy/length))
            else:
                tangents.append((1.0, 0.0))

        return tangents

    def _calculate_control_points(
        self,
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float],
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Calculate control points for cubic Bezier fitting 4 points."""
        # Use Catmull-Rom to Bezier conversion for smooth curves
        # Control point 1: based on p0, p1, p2
        ctrl1 = (
            p1[0] + (p2[0] - p0[0]) / 6,
            p1[1] + (p2[1] - p0[1]) / 6,
        )

        # Control point 2: based on p1, p2, p3
        ctrl2 = (
            p2[0] - (p3[0] - p1[0]) / 6,
            p2[1] - (p3[1] - p1[1]) / 6,
        )

        return ctrl1, ctrl2

    def _normalize_glyph(self, glyph: VectorGlyph) -> VectorGlyph:
        """Normalize glyph to standard size."""
        if not glyph.paths or glyph.height == 0 or self.normalize_size is None:
            return glyph

        scale = self.normalize_size / glyph.height

        new_paths = []
        for path in glyph.paths:
            new_segments = []
            for seg in path.segments:
                new_points = [(p[0] * scale, p[1] * scale) for p in seg.points]
                new_segments.append(PathSegment(seg.command, new_points))
            new_paths.append(VectorPath(segments=new_segments, is_hole=path.is_hole))

        return VectorGlyph(
            label=glyph.label,
            paths=new_paths,
            width=glyph.width * scale,
            height=glyph.height * scale,
            advance_width=glyph.advance_width * scale,
        )

    def vectorize_all(
        self,
        characters: List,  # List[CharacterCell] - avoid circular import
    ) -> List[VectorGlyph]:
        """
        Vectorize multiple characters.

        Args:
            characters: List of CharacterCell objects from segmentation

        Returns:
            List of VectorGlyph objects
        """
        glyphs = []
        for char in characters:
            glyph = self.vectorize(char.image, char.label)
            glyphs.append(glyph)
            logger.info(f"Vectorized '{char.label}': {len(glyph.paths)} paths")

        return glyphs


def glyphs_to_svg_font(
    glyphs: List[VectorGlyph],
    font_name: str = "CustomFont",
    units_per_em: int = 1000,
) -> str:
    """
    Convert vectorized glyphs to an SVG font.

    Note: SVG fonts are deprecated but useful for preview/testing.

    Args:
        glyphs: List of VectorGlyph objects
        font_name: Name for the font
        units_per_em: Font units per em (standard is 1000 or 2048)

    Returns:
        SVG font as string
    """
    glyph_defs = []

    for glyph in glyphs:
        # Combine all paths into single d attribute
        d = " ".join(path.to_svg_d() for path in glyph.paths)

        # SVG fonts use bottom-left origin, flip Y coordinates
        unicode_val = ord(glyph.label) if len(glyph.label) == 1 else 0

        glyph_defs.append(
            f'<glyph unicode="&#x{unicode_val:04X};" '
            f'glyph-name="{glyph.label}" '
            f'horiz-adv-x="{glyph.advance_width:.0f}" '
            f'd="{d}"/>'
        )

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg">
  <defs>
    <font id="{font_name}" horiz-adv-x="{units_per_em}">
      <font-face font-family="{font_name}" units-per-em="{units_per_em}"/>
      <missing-glyph horiz-adv-x="{units_per_em // 2}"/>
      {chr(10).join(glyph_defs)}
    </font>
  </defs>
</svg>'''

    return svg
