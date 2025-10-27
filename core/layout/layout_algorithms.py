"""
Smart layout algorithms for the Layout/Books module.

Provides intelligent layout computation for:
- Auto-fit text with binary search
- Text overflow handling across multiple pages
- Panel grid computation for comics
- Column flow for magazine layouts
- Safe area and bleed handling
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
from PIL import ImageDraw, ImageFont

from core.logging_config import LogManager
from .models import PageSpec, TextBlock, ImageBlock, Rect, Size, TextStyle

logger = LogManager().get_logger("layout.algorithms")


@dataclass
class FitResult:
    """Result of text fitting calculation."""
    font_size: int  # Optimal font size
    fits: bool  # Whether text fits at all
    overflow_text: Optional[str] = None  # Text that doesn't fit


@dataclass
class PanelGrid:
    """Comic panel grid specification."""
    rows: int
    cols: int
    gutter: int  # Spacing between panels in pixels
    panel_rects: List[Rect]  # Computed panel rectangles


class LayoutAlgorithms:
    """
    Collection of smart layout algorithms.
    """

    @staticmethod
    def auto_fit_text(
        text: str,
        rect: Rect,
        style: TextStyle,
        font_loader,  # FontManager.pil_font
        draw: ImageDraw.ImageDraw,
        min_size: int = 8,
        max_size: Optional[int] = None
    ) -> FitResult:
        """
        Find optimal font size to fit text in a rectangle using binary search.

        Args:
            text: Text to fit
            rect: Target rectangle (x, y, width, height)
            style: Text style configuration
            font_loader: Function to load font: font_loader(families, size) -> ImageFont
            draw: ImageDraw instance for measuring text
            min_size: Minimum font size to try
            max_size: Maximum font size to try (None = use style.size_px)

        Returns:
            FitResult with optimal size and fit status
        """
        x, y, w, h = rect
        max_size = max_size or style.size_px

        if max_size < min_size:
            logger.warning(f"max_size ({max_size}) < min_size ({min_size})")
            return FitResult(font_size=min_size, fits=False)

        # Binary search for optimal size
        low, high = min_size, max_size
        best_size = min_size
        best_fits = False

        while low <= high:
            mid = (low + high) // 2

            # Test this size
            font = font_loader(style.family, mid)
            wrapped = LayoutAlgorithms._wrap_text(text, font, w, draw)
            text_height = LayoutAlgorithms._measure_text_height(
                wrapped, font, style.line_height
            )

            if text_height <= h:
                # Fits! Try larger
                best_size = mid
                best_fits = True
                low = mid + 1
            else:
                # Too big, try smaller
                high = mid - 1

        return FitResult(font_size=best_size, fits=best_fits)

    @staticmethod
    def _wrap_text(
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
        draw: ImageDraw.ImageDraw
    ) -> List[str]:
        """Simple word wrapping."""
        words = text.split()
        lines = []
        current = ""

        for word in words:
            trial = (current + " " + word).strip()
            if draw.textlength(trial, font=font) <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word

        if current:
            lines.append(current)

        return lines

    @staticmethod
    def _measure_text_height(
        lines: List[str],
        font: ImageFont.FreeTypeFont,
        line_height: float
    ) -> int:
        """Calculate total height of text."""
        ascent, descent = font.getmetrics()
        line_px = int((ascent + descent) * line_height)
        return line_px * len(lines)

    @staticmethod
    def split_text_overflow(
        text: str,
        rect: Rect,
        style: TextStyle,
        font: ImageFont.FreeTypeFont,
        draw: ImageDraw.ImageDraw
    ) -> Tuple[str, str]:
        """
        Split text that overflows into (visible_text, overflow_text).

        Args:
            text: Full text
            rect: Available rectangle
            style: Text style
            font: Font to use
            draw: ImageDraw for measuring

        Returns:
            Tuple of (text_that_fits, overflow_text)
        """
        x, y, w, h = rect
        words = text.split()

        ascent, descent = font.getmetrics()
        line_height_px = int((ascent + descent) * style.line_height)
        max_lines = h // line_height_px

        if max_lines <= 0:
            return ("", text)

        # Wrap all text
        all_lines = LayoutAlgorithms._wrap_text(text, font, w, draw)

        if len(all_lines) <= max_lines:
            # All fits
            return (text, "")

        # Take lines that fit
        visible_lines = all_lines[:max_lines]
        overflow_lines = all_lines[max_lines:]

        visible_text = ' '.join(visible_lines)
        overflow_text = ' '.join(overflow_lines)

        return (visible_text, overflow_text)

    @staticmethod
    def compute_panel_grid(
        page_size: Size,
        margin: int,
        rows: int,
        cols: int,
        gutter: int
    ) -> PanelGrid:
        """
        Compute panel rectangles for a comic grid layout.

        Args:
            page_size: Page dimensions (width, height)
            margin: Page margin in pixels
            rows: Number of panel rows
            cols: Number of panel columns
            gutter: Space between panels in pixels

        Returns:
            PanelGrid with computed panel rectangles
        """
        page_w, page_h = page_size

        # Available space for panels
        content_w = page_w - (2 * margin)
        content_h = page_h - (2 * margin)

        # Calculate panel dimensions
        total_gutter_w = gutter * (cols - 1)
        total_gutter_h = gutter * (rows - 1)

        panel_w = (content_w - total_gutter_w) // cols
        panel_h = (content_h - total_gutter_h) // rows

        # Generate panel rectangles
        panel_rects = []

        for row in range(rows):
            for col in range(cols):
                x = margin + col * (panel_w + gutter)
                y = margin + row * (panel_h + gutter)
                panel_rects.append((x, y, panel_w, panel_h))

        logger.debug(
            f"Computed {rows}x{cols} grid: panel_size=({panel_w}x{panel_h}), "
            f"gutter={gutter}px"
        )

        return PanelGrid(
            rows=rows,
            cols=cols,
            gutter=gutter,
            panel_rects=panel_rects
        )

    @staticmethod
    def compute_column_layout(
        page_size: Size,
        margin: int,
        num_columns: int,
        column_gutter: int
    ) -> List[Rect]:
        """
        Compute column rectangles for magazine-style layout.

        Args:
            page_size: Page dimensions (width, height)
            margin: Page margin in pixels
            num_columns: Number of columns
            column_gutter: Space between columns in pixels

        Returns:
            List of column rectangles
        """
        page_w, page_h = page_size

        # Available space
        content_w = page_w - (2 * margin)
        content_h = page_h - (2 * margin)

        # Calculate column width
        total_gutter = column_gutter * (num_columns - 1)
        column_w = (content_w - total_gutter) // num_columns

        # Generate column rectangles
        columns = []
        for i in range(num_columns):
            x = margin + i * (column_w + column_gutter)
            y = margin
            columns.append((x, y, column_w, content_h))

        logger.debug(
            f"Computed {num_columns} columns: width={column_w}px, "
            f"gutter={column_gutter}px"
        )

        return columns

    @staticmethod
    def apply_safe_area(
        rect: Rect,
        margin: int,
        bleed: int = 0
    ) -> Rect:
        """
        Adjust a rectangle to respect safe area margins and bleed.

        Args:
            rect: Original rectangle (x, y, width, height)
            margin: Margin in pixels
            bleed: Bleed area in pixels (extends beyond page edge)

        Returns:
            Adjusted rectangle
        """
        x, y, w, h = rect

        # Apply margin
        x += margin
        y += margin
        w -= 2 * margin
        h -= 2 * margin

        # Ensure non-negative dimensions
        w = max(0, w)
        h = max(0, h)

        return (x, y, w, h)

    @staticmethod
    def distribute_space(
        total_space: int,
        num_elements: int,
        spacing: int
    ) -> List[Tuple[int, int]]:
        """
        Distribute space evenly among elements with spacing.

        Args:
            total_space: Total space available
            num_elements: Number of elements to distribute
            spacing: Space between elements

        Returns:
            List of (start_position, size) tuples for each element
        """
        if num_elements <= 0:
            return []

        total_spacing = spacing * (num_elements - 1)
        available = total_space - total_spacing

        if available <= 0:
            logger.warning(f"Not enough space: {total_space} for {num_elements} elements")
            # Distribute equally with overlap
            element_size = total_space // num_elements
            return [(i * element_size, element_size) for i in range(num_elements)]

        element_size = available // num_elements
        positions = []

        for i in range(num_elements):
            start = i * (element_size + spacing)
            positions.append((start, element_size))

        return positions

    @staticmethod
    def calculate_aspect_ratio(
        source_size: Size,
        target_size: Size,
        maintain_aspect: bool = True
    ) -> Size:
        """
        Calculate scaled size maintaining aspect ratio.

        Args:
            source_size: Original size (width, height)
            target_size: Target size (width, height)
            maintain_aspect: Whether to maintain aspect ratio

        Returns:
            Scaled size that fits within target
        """
        if not maintain_aspect:
            return target_size

        src_w, src_h = source_size
        tgt_w, tgt_h = target_size

        if src_w == 0 or src_h == 0:
            return target_size

        # Calculate scale factors
        scale_w = tgt_w / src_w
        scale_h = tgt_h / src_h

        # Use smaller scale to fit within target
        scale = min(scale_w, scale_h)

        new_w = int(src_w * scale)
        new_h = int(src_h * scale)

        return (new_w, new_h)
