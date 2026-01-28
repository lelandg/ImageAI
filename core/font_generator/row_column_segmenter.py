"""
Row-column based segmentation for alphabet images.
"""

import logging
from pathlib import Path
from typing import Optional, List, Tuple

import cv2
import numpy as np
from PIL import Image

from .row_detector import RowDetector, TextRow, CharacterColumn
from .segmentation import (
    CharacterCell,
    SegmentationResult,
    SegmentationMethod,
    UPPERCASE,
)

logger = logging.getLogger(__name__)


class RowColumnSegmenter:
    """Segments alphabet images using row detection followed by column segmentation."""

    def __init__(
        self,
        expected_chars: str = UPPERCASE,
        min_char_size: int = 15,
        padding: int = 2,
        invert: bool = False,
        use_ai: bool = False,
    ):
        self.expected_chars = expected_chars
        self.min_char_size = min_char_size
        self.padding = padding
        self.invert = invert
        self.use_ai = use_ai
        self.row_detector = RowDetector(min_row_height=min_char_size)

    def segment(
        self,
        image: np.ndarray | Image.Image | str | Path,
    ) -> SegmentationResult:
        """Segment an alphabet image into individual characters.

        APPROACH: Row projection + contours within rows.
        1. Use row projection to find text row boundaries (reliable)
        2. Within each row, find contours (complete glyphs, never split)
        3. Merge horizontally-aligned contours (for i, j dots with stems)
        4. Sort left-to-right within each row
        """
        img = self._load_image(image)
        gray = self._to_grayscale(img)
        binary = self._binarize(gray)

        logger.info(f"Row-column segmentation of image {img.shape[:2]}")

        # Step 1: Use row detector to find text row boundaries
        rows = self.row_detector.detect_rows(binary)
        logger.info(f"Detected {len(rows)} text rows via projection")

        if not rows:
            return SegmentationResult(
                method=SegmentationMethod.ROW_COLUMN,
                warnings=["No text rows detected"]
            )

        # Prepare binary for contour detection (white glyphs on black)
        binary_inv = cv2.bitwise_not(binary)

        # Step 2: Find ALL contours in the full image (not per-row)
        # This ensures tall/slanted characters like /\() aren't chopped at row boundaries
        all_contours, _ = cv2.findContours(
            binary_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Get bounding boxes for all contours
        all_boxes = []
        for contour in all_contours:
            x, y, w, h = cv2.boundingRect(contour)
            # Filter tiny noise but keep dots
            if w * h >= 9:  # Reduced from 16 to allow small punctuation
                all_boxes.append((x, y, w, h))

        logger.info(f"Found {len(all_boxes)} contours in full image")

        # Assign each box to a row based on vertical center position
        all_glyph_boxes = []
        for box in all_boxes:
            x, y, w, h = box
            center_y = y + h / 2

            # Find which row this glyph belongs to
            assigned_row = -1
            for row_idx, row in enumerate(rows):
                row_y1 = row.y
                row_y2 = row.y + row.height
                # Assign to row if center is within row bounds (with margin)
                if row_y1 - h/4 <= center_y <= row_y2 + h/4:
                    assigned_row = row_idx
                    break

            if assigned_row >= 0:
                all_glyph_boxes.append((x, y, w, h, assigned_row))
            else:
                # Try to assign based on overlap
                best_overlap = 0
                best_row = 0
                for row_idx, row in enumerate(rows):
                    row_y1 = row.y
                    row_y2 = row.y + row.height
                    overlap = max(0, min(y + h, row_y2) - max(y, row_y1))
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_row = row_idx
                all_glyph_boxes.append((x, y, w, h, best_row))

        # Group by row and merge aligned contours (i, j dots)
        rows_boxes = {}
        for x, y, w, h, row_idx in all_glyph_boxes:
            if row_idx not in rows_boxes:
                rows_boxes[row_idx] = []
            rows_boxes[row_idx].append((x, y, w, h))

        # Rebuild with merged boxes
        all_glyph_boxes = []
        for row_idx in sorted(rows_boxes.keys()):
            row_boxes = self._merge_aligned_in_row(rows_boxes[row_idx])
            row_boxes.sort(key=lambda b: b[0])
            for box in row_boxes:
                all_glyph_boxes.append((*box, row_idx))
            logger.debug(f"Row {row_idx}: {len(row_boxes)} glyphs")

        logger.info(f"Total glyphs after row processing: {len(all_glyph_boxes)}")

        # Extract characters
        characters = []
        for idx, (x, y, w, h, row_idx) in enumerate(all_glyph_boxes):
            # Add padding
            x1 = max(0, x - self.padding)
            y1 = max(0, y - self.padding)
            x2 = min(img.shape[1], x + w + self.padding)
            y2 = min(img.shape[0], y + h + self.padding)

            cell_img = img[y1:y2, x1:x2].copy()

            if cell_img.size > 0:
                col = CharacterColumn(
                    x=x1, width=x2-x1, y=y1, height=y2-y1, row_index=row_idx
                )
                characters.append((cell_img, col, row_idx))

        result = SegmentationResult(method=SegmentationMethod.ROW_COLUMN)

        if self.use_ai and len(characters) > 0:
            result = self._identify_with_ai(characters, img)
        else:
            for idx, (cell_img, col, row_idx) in enumerate(characters):
                if idx < len(self.expected_chars):
                    label = self.expected_chars[idx]
                else:
                    label = '?'
                    result.warnings.append(f"Extra character at column {idx}")

                char = CharacterCell(
                    label=label,
                    bbox=(col.x, col.y, col.width, col.height),
                    image=cell_img,
                    row=row_idx,
                    col=idx,
                )
                result.characters.append(char)

        if len(result.characters) != len(self.expected_chars):
            diff = len(result.characters) - len(self.expected_chars)
            if diff > 0:
                result.warnings.append(
                    f"Found {len(result.characters)} but expected {len(self.expected_chars)} (+{diff} extra)"
                )
            else:
                result.warnings.append(
                    f"Found {len(result.characters)} but expected {len(self.expected_chars)} ({abs(diff)} missing)"
                )

        result.image_size = (img.shape[1], img.shape[0])
        return result

    def _identify_with_ai(
        self,
        characters: List[Tuple[np.ndarray, CharacterColumn, int]],
        original_image: np.ndarray,
    ) -> SegmentationResult:
        """Use AI to identify all extracted glyphs."""
        from .glyph_identifier import AIGlyphIdentifier

        result = SegmentationResult(method=SegmentationMethod.CONTOUR)

        try:
            identifier = AIGlyphIdentifier()
            glyph_images = [cell_img for cell_img, _, _ in characters]
            identifications = identifier.batch_identify(glyph_images, expected_chars=self.expected_chars)

            for idx, ((cell_img, col, row_idx), ident) in enumerate(zip(characters, identifications)):
                if ident.identified_char:
                    label = ident.identified_char
                elif idx < len(self.expected_chars):
                    label = self.expected_chars[idx]
                    result.warnings.append(f"AI could not identify glyph {idx}, using sequential label")
                else:
                    label = '?'

                char = CharacterCell(
                    label=label,
                    bbox=(col.x, col.y, col.width, col.height),
                    image=cell_img,
                    confidence=ident.confidence,
                    row=row_idx,
                    col=idx,
                )
                result.characters.append(char)

            logger.info(f"AI identified {len(result.characters)} characters")

        except Exception as e:
            logger.error(f"AI identification failed: {e}")
            result.warnings.append(f"AI identification failed: {e}")

            for idx, (cell_img, col, row_idx) in enumerate(characters):
                label = self.expected_chars[idx] if idx < len(self.expected_chars) else '?'
                char = CharacterCell(
                    label=label,
                    bbox=(col.x, col.y, col.width, col.height),
                    image=cell_img,
                    row=row_idx,
                    col=idx,
                )
                result.characters.append(char)

        return result

    def _load_image(self, image: np.ndarray | Image.Image | str | Path) -> np.ndarray:
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image), cv2.IMREAD_UNCHANGED)
            if img is None:
                raise ValueError(f"Could not load image from {image}")
            if len(img.shape) == 3:
                if img.shape[2] == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                elif img.shape[2] == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
            return img
        elif isinstance(image, Image.Image):
            return np.array(image)
        elif isinstance(image, np.ndarray):
            return image.copy()
        else:
            raise TypeError(f"Unsupported image type: {type(image)}")

    def _to_grayscale(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 2:
            return img
        elif img.shape[2] == 4:
            return cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY)
        else:
            return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    def _binarize(self, gray: np.ndarray) -> np.ndarray:
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        if self.invert:
            binary = cv2.bitwise_not(binary)

        if np.sum(binary == 0) > np.sum(binary == 255):
            binary = cv2.bitwise_not(binary)

        return binary

    def _merge_aligned_in_row(
        self,
        boxes: List[Tuple[int, int, int, int]],
    ) -> List[Tuple[int, int, int, int]]:
        """Merge boxes that are horizontally aligned within a single row.

        This handles multi-part glyphs like:
        - 'i' and 'j' where the dot is above the stem (similar x-centers)
        - '"' and ':' where parts are side-by-side (adjacent narrow boxes)
        """
        if len(boxes) < 2:
            return list(boxes)

        # Calculate median width for "narrow box" detection
        widths = [w for _, _, w, _ in boxes]
        median_width = sorted(widths)[len(widths) // 2]

        # A box is "narrow" if width is less than 75% of median
        # This catches quotation marks, colons, semicolons, etc.
        narrow_threshold = median_width * 0.75

        def is_narrow(w):
            return w < narrow_threshold

        # Sort by x position (left to right) for proper gap calculation
        boxes_sorted = sorted(boxes, key=lambda b: b[0])

        # First pass: merge adjacent narrow boxes (for ", :, ;, etc.)
        # Only merge if BOTH boxes are narrow and gap is small
        # But NOT if they look like separate characters (e.g., parentheses)
        merged_narrow = []
        i = 0

        # Calculate median height for baseline detection
        heights = [h for _, _, _, h in boxes]
        median_height = sorted(heights)[len(heights) // 2] if heights else median_width

        while i < len(boxes_sorted):
            x1, y1, w1, h1 = boxes_sorted[i]

            if is_narrow(w1):
                # Look ahead for adjacent narrow boxes to merge
                group_x_min = x1
                group_y_min = y1
                group_x_max = x1 + w1
                group_y_max = y1 + h1
                group_width = w1
                group_height = h1

                j = i + 1
                while j < len(boxes_sorted):
                    x2, y2, w2, h2 = boxes_sorted[j]
                    if is_narrow(w2):
                        gap = x2 - group_x_max

                        # Check vertical alignment - are boxes at similar y-positions?
                        # This helps merge " and : while keeping () separate
                        y_overlap = not (y1 + h1 < y2 or y2 + h2 < y1)
                        y_centers_close = abs((y1 + h1/2) - (y2 + h2/2)) < median_height * 0.3

                        # Both boxes are SHORT (not spanning full row) - likely punctuation parts
                        both_short = h1 < median_height * 0.6 and h2 < median_height * 0.6

                        # Both boxes are TALL (spanning most of row) - likely separate chars like ()
                        both_tall = h1 > median_height * 0.7 and h2 > median_height * 0.7

                        # Combined width check
                        combined_width = (x2 + w2) - group_x_min
                        would_be_too_wide = combined_width > median_width * 1.3

                        # Gap thresholds differ based on box characteristics
                        if both_short and y_centers_close:
                            # Short marks at same height (like ") - allow larger gap
                            max_gap = min(w1, w2) * 1.5
                            logger.debug(f"Short marks at same y: allowing gap up to {max_gap:.0f}")
                        else:
                            # Normal case - conservative gap
                            max_gap = min(group_width, w2) * 0.6

                        # Don't merge if boxes look like separate tall characters
                        if both_tall and would_be_too_wide:
                            logger.debug(f"NOT merging: both tall ({h1}, {h2}), combined_w={combined_width}, median_h={median_height}")
                            break

                        if 0 <= gap <= max_gap:
                            logger.debug(f"Merging narrow boxes: gap={gap}, max_gap={max_gap:.0f}, w1={group_width}, w2={w2}, both_short={both_short}")
                            group_x_min = min(group_x_min, x2)
                            group_y_min = min(group_y_min, y2)
                            group_x_max = max(group_x_max, x2 + w2)
                            group_y_max = max(group_y_max, y2 + h2)
                            group_width = group_x_max - group_x_min
                            group_height = group_y_max - group_y_min
                            j += 1
                            continue
                    break

                merged_narrow.append((
                    group_x_min,
                    group_y_min,
                    group_x_max - group_x_min,
                    group_y_max - group_y_min
                ))
                i = j
            else:
                merged_narrow.append((x1, y1, w1, h1))
                i += 1

        # Second pass: merge vertically aligned boxes (for i, j dots above stems)
        # This handles cases where a dot is above a stem (like 'i' and 'j')
        # Sort by x-center for this pass
        boxes_with_center = [(x, y, w, h, x + w // 2) for x, y, w, h in merged_narrow]
        boxes_with_center.sort(key=lambda b: b[4])

        merged_vertical = []
        used = set()

        for i, (x1, y1, w1, h1, cx1) in enumerate(boxes_with_center):
            if i in used:
                continue

            group_x_min = x1
            group_y_min = y1
            group_x_max = x1 + w1
            group_y_max = y1 + h1

            for j, (x2, y2, w2, h2, cx2) in enumerate(boxes_with_center):
                if j <= i or j in used:
                    continue

                # Check if x-centers are close enough to merge
                min_width = min(w1, w2)
                x_threshold = min_width * 0.8

                if abs(cx1 - cx2) <= x_threshold:
                    # Additional checks to prevent over-merging:
                    min_height = min(h1, h2)
                    max_height = max(h1, h2)
                    height_ratio = min_height / max_height if max_height > 0 else 1

                    # Check for horizontal overlap to prevent merging side-by-side chars like ()
                    x1_end = x1 + w1
                    x2_end = x2 + w2
                    has_x_overlap = not (x1_end <= x2 or x2_end <= x1)

                    # Merge if:
                    # 1. Height ratio < 0.40 (dot + stem relationship), OR
                    # 2. x-centers are nearly identical (< 10px) AND boxes have horizontal overlap
                    #    (this prevents merging side-by-side characters like parentheses)
                    should_merge = height_ratio < 0.40 or (abs(cx1 - cx2) < 10 and has_x_overlap)

                    if should_merge:
                        logger.debug(f"Merging x-aligned boxes: cx_diff={abs(cx1-cx2)}, h_ratio={height_ratio:.2f}, w1={w1}, w2={w2}")
                        group_x_min = min(group_x_min, x2)
                        group_y_min = min(group_y_min, y2)
                        group_x_max = max(group_x_max, x2 + w2)
                        group_y_max = max(group_y_max, y2 + h2)
                        used.add(j)

            used.add(i)
            merged_vertical.append((
                group_x_min,
                group_y_min,
                group_x_max - group_x_min,
                group_y_max - group_y_min
            ))

        # Third pass: merge diagonally positioned small boxes into larger boxes
        # This handles '%' where circles are at diagonal corners of the main stroke
        merged = self._merge_diagonal_components(merged_vertical)

        return merged

    def _merge_diagonal_components(
        self,
        boxes: List[Tuple[int, int, int, int]],
    ) -> List[Tuple[int, int, int, int]]:
        """Merge boxes that have significant horizontal overlap.

        This handles multi-part glyphs like '%' where components
        (two circles and diagonal stroke) overlap horizontally but
        are separated vertically.
        """
        if len(boxes) < 2:
            return list(boxes)

        # Calculate median width to determine overlap threshold
        widths = [w for _, _, w, _ in boxes]
        median_width = sorted(widths)[len(widths) // 2]

        def get_x_range(box):
            x, _, w, _ = box
            return x, x + w

        def horizontal_overlap(box1, box2):
            """Calculate horizontal overlap ratio between two boxes."""
            x1_min, x1_max = get_x_range(box1)
            x2_min, x2_max = get_x_range(box2)

            overlap_start = max(x1_min, x2_min)
            overlap_end = min(x1_max, x2_max)

            if overlap_end <= overlap_start:
                return 0.0

            overlap = overlap_end - overlap_start
            min_width = min(x1_max - x1_min, x2_max - x2_min)
            return overlap / min_width if min_width > 0 else 0.0

        # Use union-find to group overlapping boxes
        n = len(boxes)
        parent = list(range(n))

        def find(i):
            if parent[i] != i:
                parent[i] = find(parent[i])
            return parent[i]

        def union(i, j):
            pi, pj = find(i), find(j)
            if pi != pj:
                parent[pi] = pj

        # Group boxes with significant horizontal overlap (> 50%)
        for i in range(n):
            for j in range(i + 1, n):
                overlap = horizontal_overlap(boxes[i], boxes[j])
                if overlap > 0.5:
                    # Also check they're not too far apart vertically
                    # (should be within 2x the median width vertically)
                    _, y1, _, h1 = boxes[i]
                    _, y2, _, h2 = boxes[j]
                    cy1, cy2 = y1 + h1 // 2, y2 + h2 // 2
                    vertical_dist = abs(cy1 - cy2)

                    if vertical_dist < median_width * 2:
                        logger.info(
                            f"Merging overlapping boxes: {boxes[i]} + {boxes[j]}, "
                            f"overlap={overlap:.2f}, v_dist={vertical_dist}"
                        )
                        union(i, j)

        # Group boxes by their root parent
        groups = {}
        for i in range(n):
            root = find(i)
            if root not in groups:
                groups[root] = []
            groups[root].append(boxes[i])

        # Merge each group into a single bounding box
        merged = []
        for group in groups.values():
            if len(group) == 1:
                merged.append(group[0])
            else:
                x_min = min(b[0] for b in group)
                y_min = min(b[1] for b in group)
                x_max = max(b[0] + b[2] for b in group)
                y_max = max(b[1] + b[3] for b in group)
                merged.append((x_min, y_min, x_max - x_min, y_max - y_min))
                logger.info(f"Merged {len(group)} components into one glyph")

        return merged
