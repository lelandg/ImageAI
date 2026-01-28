"""
Row detection for alphabet images.

Detects horizontal text rows by analyzing horizontal projection profiles,
handling overlapping rows where descenders extend into the next row.
"""

import logging
from dataclasses import dataclass
from typing import List

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TextRow:
    """Represents a detected row of text."""
    y: int  # Top Y coordinate
    height: int  # Row height
    baseline: int  # Estimated baseline Y position (relative to image top)

    @property
    def bottom(self) -> int:
        """Bottom Y coordinate of the row."""
        return self.y + self.height


@dataclass
class CharacterColumn:
    """Represents a detected character column within a row."""
    x: int  # Left X coordinate (relative to original image)
    width: int  # Column width
    y: int  # Top Y coordinate (from row)
    height: int  # Column height (from row)
    row_index: int = 0  # Which row this column belongs to

    @property
    def right(self) -> int:
        """Right X coordinate."""
        return self.x + self.width

    @property
    def center_x(self) -> int:
        """Center X coordinate."""
        return self.x + self.width // 2


class RowDetector:
    """
    Detects rows of text in alphabet images using horizontal projection analysis.

    Handles overlapping rows where character descenders (g, j, p, q, y) extend
    into the next row.
    """

    def __init__(
        self,
        min_row_height: int = 20,
        gap_threshold_ratio: float = 0.05,
        descender_ratio: float = 0.3,
    ):
        self.min_row_height = min_row_height
        self.gap_threshold_ratio = gap_threshold_ratio
        self.descender_ratio = descender_ratio

    def detect_rows(self, binary_image: np.ndarray) -> List[TextRow]:
        """Detect text rows in a binary image."""
        h, w = binary_image.shape[:2]

        # Ensure binary (handle grayscale input)
        if len(binary_image.shape) == 3:
            gray = cv2.cvtColor(binary_image, cv2.COLOR_RGB2GRAY)
        else:
            gray = binary_image

        # Binarize if not already
        if gray.max() > 1:
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            binary = gray

        # Ensure black text on white bg
        if np.sum(binary == 0) > np.sum(binary == 255):
            binary = cv2.bitwise_not(binary)

        # Calculate horizontal projection (sum of black pixels per row)
        projection = np.sum(binary < 128, axis=1)

        # Find rows by detecting regions with ink
        gap_threshold = w * self.gap_threshold_ratio

        rows = []
        in_row = False
        row_start = 0

        for y, ink_count in enumerate(projection):
            if not in_row and ink_count > gap_threshold:
                in_row = True
                row_start = y
            elif in_row and ink_count <= gap_threshold:
                row_height = y - row_start
                if row_height >= self.min_row_height:
                    baseline = row_start + int(row_height * (1 - self.descender_ratio))
                    rows.append(TextRow(y=row_start, height=row_height, baseline=baseline))
                in_row = False

        # Handle row at bottom edge
        if in_row:
            row_height = h - row_start
            if row_height >= self.min_row_height:
                baseline = row_start + int(row_height * (1 - self.descender_ratio))
                rows.append(TextRow(y=row_start, height=row_height, baseline=baseline))

        # Merge overlapping rows
        rows = self._merge_overlapping_rows(rows, projection, w)

        # Merge small rows (descenders, punctuation fragments) into adjacent rows
        rows = self._merge_small_rows(rows)

        logger.info(f"Detected {len(rows)} text rows")
        return rows

    def _merge_small_rows(self, rows: List[TextRow]) -> List[TextRow]:
        """Merge rows that are too small relative to the median row height.

        Small rows are typically descenders (g, j, p, q, y) that got separated
        from their main row body, or punctuation fragments.
        """
        if len(rows) < 2:
            return rows

        # Calculate median row height
        heights = [r.height for r in rows]
        median_height = sorted(heights)[len(heights) // 2]

        # Threshold: rows smaller than 30% of median are considered "small"
        small_threshold = median_height * 0.30

        logger.debug(f"Median row height: {median_height}, small threshold: {small_threshold:.1f}")

        # Iteratively merge small rows until no changes
        merged = list(rows)
        changed = True
        iterations = 0
        max_iterations = len(rows)  # Safety limit

        while changed and iterations < max_iterations:
            changed = False
            iterations += 1
            new_merged = []
            i = 0

            while i < len(merged):
                current = merged[i]

                if current.height < small_threshold:
                    # This row is too small - merge with the closer adjacent row
                    prev_row = new_merged[-1] if new_merged else None
                    next_row = merged[i + 1] if i + 1 < len(merged) else None

                    # Calculate gaps to adjacent rows
                    gap_to_prev = (current.y - prev_row.bottom) if prev_row else float('inf')
                    gap_to_next = (next_row.y - current.bottom) if next_row else float('inf')

                    if prev_row and gap_to_prev <= gap_to_next:
                        # Merge with previous row (extend it down)
                        new_bottom = max(prev_row.bottom, current.bottom)
                        new_height = new_bottom - prev_row.y
                        new_baseline = prev_row.y + int(new_height * (1 - self.descender_ratio))
                        new_merged[-1] = TextRow(
                            y=prev_row.y,
                            height=new_height,
                            baseline=new_baseline
                        )
                        logger.debug(f"Merged small row (h={current.height}) into prev row at y={prev_row.y}")
                        changed = True
                    elif next_row:
                        # Merge with next row (extend it up)
                        new_top = min(current.y, next_row.y)
                        new_bottom = next_row.bottom
                        new_height = new_bottom - new_top
                        new_baseline = new_top + int(new_height * (1 - self.descender_ratio))
                        # Replace next_row with merged version
                        merged[i + 1] = TextRow(
                            y=new_top,
                            height=new_height,
                            baseline=new_baseline
                        )
                        logger.debug(f"Merged small row (h={current.height}) into next row at y={next_row.y}")
                        changed = True
                    else:
                        # No adjacent row to merge with - keep it
                        new_merged.append(current)
                else:
                    new_merged.append(current)

                i += 1

            merged = new_merged

        return merged

    def _merge_overlapping_rows(
        self,
        rows: List[TextRow],
        projection: np.ndarray,
        image_width: int,
    ) -> List[TextRow]:
        """Handle overlapping rows where descenders extend into the next row."""
        if len(rows) < 2:
            return rows

        merged = []
        i = 0

        while i < len(rows):
            current = rows[i]

            if i + 1 < len(rows):
                next_row = rows[i + 1]
                gap = next_row.y - current.bottom

                if gap < 0:
                    # True overlap - check projection for valley
                    overlap_start = max(0, next_row.y)
                    overlap_end = min(len(projection), current.bottom)

                    if overlap_start < overlap_end:
                        overlap_proj = projection[overlap_start:overlap_end]
                        min_ink = np.min(overlap_proj)
                        max_ink = max(
                            np.max(projection[current.y:overlap_start]) if overlap_start > current.y else 0,
                            np.max(projection[overlap_end:next_row.bottom]) if overlap_end < next_row.bottom else 0
                        )

                        if max_ink > 0 and min_ink < max_ink * 0.3:
                            merged.append(current)
                            i += 1
                            continue

                    merged.append(current)
                else:
                    merged.append(current)
            else:
                merged.append(current)

            i += 1

        return merged

    def segment_columns(
        self,
        image: np.ndarray,
        row: TextRow,
        min_column_width: int = 5,
        gap_threshold_pct: float = 0.03,  # 3% of row height = gap
    ) -> List[CharacterColumn]:
        """Segment a row into individual character columns.

        Uses a small threshold (3% of row height) to find gaps between glyphs.
        The contour-aware extraction in RowColumnSegmenter will then expand
        any cells where glyphs touch the edges, ensuring no glyph is split.
        """
        _, w = image.shape[:2]

        # Extract row region
        row_img = image[row.y:row.y + row.height, :]

        # Ensure binary
        if len(row_img.shape) == 3:
            row_gray = cv2.cvtColor(row_img, cv2.COLOR_RGB2GRAY)
        else:
            row_gray = row_img

        if row_gray.max() > 1:
            _, row_binary = cv2.threshold(row_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            row_binary = row_gray

        if np.sum(row_binary == 0) > np.sum(row_binary == 255):
            row_binary = cv2.bitwise_not(row_binary)

        # Calculate vertical projection
        projection = np.sum(row_binary < 128, axis=0)

        # Gap threshold: small percentage of row height
        # This finds actual gaps while allowing for minor anti-aliasing
        gap_threshold = max(2, int(row.height * gap_threshold_pct))

        columns = []
        in_column = False
        col_start = 0

        for x, ink_count in enumerate(projection):
            if not in_column and ink_count > gap_threshold:
                # Starting a new glyph region
                in_column = True
                col_start = x
            elif in_column and ink_count <= gap_threshold:
                # Found a gap - end of glyph
                col_width = x - col_start
                if col_width >= min_column_width:
                    columns.append(CharacterColumn(
                        x=col_start, width=col_width, y=row.y, height=row.height
                    ))
                in_column = False

        if in_column:
            col_width = w - col_start
            if col_width >= min_column_width:
                columns.append(CharacterColumn(
                    x=col_start, width=col_width, y=row.y, height=row.height
                ))

        # Split wide columns only at clear gaps
        columns = self._split_wide_columns(columns, projection, row, gap_threshold)

        logger.debug(f"Row at y={row.y}: found {len(columns)} columns (gap_threshold={gap_threshold})")
        return columns

    def _split_wide_columns(
        self,
        columns: List[CharacterColumn],
        projection: np.ndarray,
        row: TextRow,
        gap_threshold: int = 2,
        width_threshold: float = 1.8,
    ) -> List[CharacterColumn]:
        """Split columns that are unusually wide at clear gaps.

        Only splits where there's a clear gap (ink below threshold).
        The contour-aware extraction will handle any edge cases.
        """
        if not columns:
            return columns

        widths = [c.width for c in columns]
        median_width = sorted(widths)[len(widths) // 2]

        result = []
        for col in columns:
            if col.width > median_width * width_threshold:
                # Find splits at clear gaps
                splits = self._find_gap_splits(
                    projection[col.x:col.x + col.width], gap_threshold
                )

                if splits:
                    boundaries = [0] + splits + [col.width]
                    for i in range(len(boundaries) - 1):
                        new_width = boundaries[i + 1] - boundaries[i]
                        if new_width >= 5:
                            result.append(CharacterColumn(
                                x=col.x + boundaries[i],
                                width=new_width,
                                y=col.y,
                                height=col.height,
                            ))
                else:
                    # No clear gap found - keep column intact
                    result.append(col)
            else:
                result.append(col)

        return result

    def _find_gap_splits(
        self,
        projection: np.ndarray,
        gap_threshold: int = 2,
    ) -> List[int]:
        """Find split points where there's a clear gap (ink below threshold)."""
        if len(projection) < 10:
            return []

        # Find runs of low-ink values
        gaps = []
        in_gap = False
        gap_start = 0

        for i, val in enumerate(projection):
            if val <= gap_threshold:
                if not in_gap:
                    gap_start = i
                    in_gap = True
            else:
                if in_gap:
                    gap_end = i
                    gap_width = gap_end - gap_start
                    # Only consider gaps that are at least 2 pixels wide
                    if gap_width >= 2:
                        gap_center = (gap_start + gap_end) // 2
                        gaps.append(gap_center)
                    in_gap = False

        return gaps
