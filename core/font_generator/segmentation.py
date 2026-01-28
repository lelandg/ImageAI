"""
Character segmentation for alphabet images.

This module provides functionality to detect and isolate individual characters
from alphabet images, supporting both grid-based and contour-based segmentation.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Tuple, Dict

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class SegmentationMethod(Enum):
    """Available segmentation methods."""
    GRID = "grid"
    CONTOUR = "contour"
    AUTO = "auto"
    ROW_COLUMN = "row_column"


@dataclass
class CharacterCell:
    """Represents a single segmented character."""

    # The character label (e.g., 'A', 'a', '0')
    label: str

    # Bounding box in original image (x, y, width, height)
    bbox: Tuple[int, int, int, int]

    # The extracted character image as numpy array (grayscale or RGBA)
    image: np.ndarray

    # Confidence score (0.0 to 1.0) for this segmentation
    confidence: float = 1.0

    # Row and column index in the grid (if grid-based)
    row: int = 0
    col: int = 0

    @property
    def x(self) -> int:
        return self.bbox[0]

    @property
    def y(self) -> int:
        return self.bbox[1]

    @property
    def width(self) -> int:
        return self.bbox[2]

    @property
    def height(self) -> int:
        return self.bbox[3]

    def to_pil(self) -> Image.Image:
        """Convert the character image to PIL Image."""
        if len(self.image.shape) == 2:
            return Image.fromarray(self.image, mode='L')
        elif self.image.shape[2] == 4:
            return Image.fromarray(self.image, mode='RGBA')
        else:
            return Image.fromarray(self.image, mode='RGB')


@dataclass
class SegmentationResult:
    """Result of alphabet segmentation."""

    # List of segmented characters
    characters: List[CharacterCell] = field(default_factory=list)

    # Method used for segmentation
    method: SegmentationMethod = SegmentationMethod.AUTO

    # Grid dimensions if grid-based (rows, cols)
    grid_size: Optional[Tuple[int, int]] = None

    # Original image dimensions
    image_size: Tuple[int, int] = (0, 0)

    # Any warnings or issues encountered
    warnings: List[str] = field(default_factory=list)

    def get_character(self, label: str) -> Optional[CharacterCell]:
        """Get a character by its label."""
        for char in self.characters:
            if char.label == label:
                return char
        return None

    def get_missing_characters(self, expected: str) -> List[str]:
        """Return list of expected characters that weren't found."""
        found = {c.label for c in self.characters}
        return [c for c in expected if c not in found]


# Standard character sets for alphabet images
UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWERCASE = "abcdefghijklmnopqrstuvwxyz"
DIGITS = "0123456789"
# Extended punctuation covering common symbols found in handwriting samples
PUNCTUATION = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~\\"
FULL_ALPHABET = UPPERCASE + LOWERCASE + DIGITS + PUNCTUATION


class AlphabetSegmenter:
    """
    Segments an alphabet image into individual character cells.

    Supports two primary methods:
    - Grid-based: For uniformly spaced character grids
    - Contour-based: For irregular layouts or hand-drawn alphabets
    """

    def __init__(
        self,
        method: SegmentationMethod = SegmentationMethod.AUTO,
        expected_chars: str = UPPERCASE,
        min_char_size: int = 20,
        padding: int = 2,
        threshold_value: int = 127,
        invert: bool = False,
        include_small_glyphs: bool = False,
        min_small_glyph_size: int = 3,
        use_ai: bool = False,
    ):
        """
        Initialize the segmenter.

        Args:
            method: Segmentation method to use
            expected_chars: String of expected characters in order
            min_char_size: Minimum character size in pixels for main characters
            padding: Padding around each character cell
            threshold_value: Threshold for binarization (0-255)
            invert: If True, invert the image (dark bg, light chars)
            include_small_glyphs: If True, preserve small standalone glyphs (punctuation)
            min_small_glyph_size: Minimum size for small glyphs (default 3px)
            use_ai: If True, use AI (Gemini) to help with ambiguous segmentation
        """
        self.method = method
        self.expected_chars = expected_chars
        self.min_char_size = min_char_size
        self.padding = padding
        self.threshold_value = threshold_value
        self.invert = invert
        self.include_small_glyphs = include_small_glyphs
        self.min_small_glyph_size = min_small_glyph_size
        self.use_ai = use_ai

    @staticmethod
    def detect_needs_inversion(image: np.ndarray | Image.Image | str | Path) -> bool:
        """
        Detect if an image needs color inversion for proper segmentation.

        Returns True if the image appears to have light text on dark background
        (needs inversion), False if dark text on light background (no inversion needed).

        Args:
            image: Input image (numpy array, PIL Image, or path)

        Returns:
            True if inversion is recommended, False otherwise
        """
        # Load image
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image), cv2.IMREAD_GRAYSCALE)
            if img is None:
                return False
        elif isinstance(image, Image.Image):
            img = np.array(image.convert("L"))
        elif isinstance(image, np.ndarray):
            if len(image.shape) == 3:
                img = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                img = image.copy()
        else:
            return False

        # Sample the edges/borders of the image (likely background)
        h, w = img.shape
        border_size = max(10, min(h, w) // 20)

        # Get border pixels
        top = img[:border_size, :].flatten()
        bottom = img[-border_size:, :].flatten()
        left = img[:, :border_size].flatten()
        right = img[:, -border_size:].flatten()
        border_pixels = np.concatenate([top, bottom, left, right])

        # Get center region pixels (likely contains characters)
        center_y1, center_y2 = h // 4, 3 * h // 4
        center_x1, center_x2 = w // 4, 3 * w // 4
        center_pixels = img[center_y1:center_y2, center_x1:center_x2].flatten()

        # Calculate mean intensities
        border_mean = np.mean(border_pixels)
        center_mean = np.mean(center_pixels)

        # If background (border) is darker than center, it's likely light text on dark
        # Standard case: dark text on light background -> border_mean > center_mean
        # Inverted case: light text on dark background -> border_mean < center_mean

        # Also check overall brightness
        overall_mean = np.mean(img)

        logger.debug(f"Inversion detection - border: {border_mean:.1f}, center: {center_mean:.1f}, overall: {overall_mean:.1f}")

        # Needs inversion if background is significantly darker than center
        # or if the overall image is very dark
        needs_invert = bool(border_mean < 100 or (border_mean < center_mean - 30))

        logger.info(f"Auto-detected inversion: {'needed' if needs_invert else 'not needed'}")
        return needs_invert

    @staticmethod
    def detect_character_set(num_characters: int) -> Tuple[str, str]:
        """
        Determine the most likely character set based on detected character count.

        Args:
            num_characters: Number of characters detected in the image

        Returns:
            Tuple of (character_string, description) for the detected set
        """
        # Common character set sizes:
        # 26 = uppercase or lowercase only
        # 36 = uppercase + digits OR lowercase + digits
        # 52 = uppercase + lowercase
        # 62 = uppercase + lowercase + digits
        # 72+ = full set with punctuation

        if num_characters <= 10:
            return DIGITS, "Digits (0-9)"
        elif num_characters <= 26:
            # Could be uppercase or lowercase - default to uppercase
            return UPPERCASE, "Uppercase (A-Z)"
        elif num_characters <= 36:
            # Uppercase + digits or lowercase + digits
            return UPPERCASE + DIGITS, "Uppercase + Digits"
        elif num_characters <= 52:
            return UPPERCASE + LOWERCASE, "Uppercase + Lowercase"
        elif num_characters <= 62:
            return UPPERCASE + LOWERCASE + DIGITS, "Full (A-Z, a-z, 0-9)"
        else:
            return FULL_ALPHABET, "Full Alphabet + Punctuation"

    @staticmethod
    def validate_character_count(num_detected: int, expected_chars: str) -> List[str]:
        """
        Validate detected character count against expected set and return warnings.

        Args:
            num_detected: Number of characters detected
            expected_chars: The expected character set string

        Returns:
            List of warning messages (empty if count matches)
        """
        warnings = []
        expected_count = len(expected_chars)

        if num_detected != expected_count:
            diff = num_detected - expected_count

            if diff > 0:
                warnings.append(
                    f"⚠️ EXTRA CHARACTERS: Detected {num_detected} but expected {expected_count} "
                    f"(+{diff} extra). Source image may have duplicate characters."
                )
            else:
                warnings.append(
                    f"⚠️ MISSING CHARACTERS: Detected {num_detected} but expected {expected_count} "
                    f"({abs(diff)} missing). Source image may be incomplete."
                )

            # Provide guidance on standard counts
            warnings.append(
                "Standard character sets: 26 (A-Z), 52 (A-Z + a-z), 62 (A-Z + a-z + 0-9)"
            )
            warnings.append(
                "TIP: Check your source image for missing, duplicate, or malformed characters. "
                "Use Step 3 (Character Mapping) to manually correct labels if needed."
            )

            logger.warning(f"Character count mismatch: detected {num_detected}, expected {expected_count}")

        return warnings

    def segment_auto_detect(
        self,
        image: np.ndarray | Image.Image | str | Path,
        grid_rows: Optional[int] = None,
        grid_cols: Optional[int] = None,
    ) -> Tuple[SegmentationResult, str, str]:
        """
        Segment an image and auto-detect the character set.

        First detects all characters, then determines the appropriate character set
        based on the number of characters found.

        Args:
            image: Input image (numpy array, PIL Image, or path)
            grid_rows: Number of rows (for grid method, or auto-detect)
            grid_cols: Number of columns (for grid method, or auto-detect)

        Returns:
            Tuple of (SegmentationResult, detected_charset, charset_description)
        """
        # Load and preprocess image
        img = self._load_image(image)
        gray = self._to_grayscale(img)
        binary = self._binarize(gray)

        logger.info(f"Auto-detecting characters in image of size {img.shape[:2]}")

        # Use contour-based detection to count characters first
        contours, _ = cv2.findContours(
            cv2.bitwise_not(binary), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Get bounding boxes - keep small components for dot merging
        bboxes = []
        small_bboxes = []

        # Adaptive minimum size based on small glyph setting
        if self.include_small_glyphs:
            min_dot_size = self.min_small_glyph_size
            min_area = self.min_small_glyph_size ** 2
        else:
            min_dot_size = 5
            min_area = 25

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = cv2.contourArea(cnt)

            if w < min_dot_size or h < min_dot_size or area < min_area:
                continue
            elif w >= self.min_char_size and h >= self.min_char_size and area > 100:
                bboxes.append((x, y, w, h, cnt))
            else:
                # Keep ALL small components for merging (dots for i/j)
                small_bboxes.append((x, y, w, h, cnt))

        # Combine and merge (handles 'i', 'j' dots)
        all_bboxes = bboxes + small_bboxes
        if all_bboxes:
            merged = self._merge_component_bboxes(all_bboxes, img)

            # Separate large from orphaned small
            large_bboxes = [b for b in merged
                           if b[2] >= self.min_char_size and b[3] >= self.min_char_size]
            orphan_small = [b for b in merged
                           if b[2] < self.min_char_size or b[3] < self.min_char_size]

            # Keep orphans that look like punctuation (if enabled)
            if self.include_small_glyphs:
                punctuation_bboxes = []
                for x, y, w, h, cnt in orphan_small:
                    area = cv2.contourArea(cnt)
                    if self._is_likely_punctuation(cnt, w, h, area):
                        punctuation_bboxes.append((x, y, w, h, cnt))
                bboxes = large_bboxes + punctuation_bboxes
            else:
                bboxes = large_bboxes

        num_detected = len(bboxes)
        logger.info(f"Detected {num_detected} character bboxes (after merging)")

        # Determine character set
        charset, description = self.detect_character_set(num_detected)

        # Update expected chars and run full segmentation
        self.expected_chars = charset
        result = self.segment(image, grid_rows, grid_cols)

        return result, charset, description

    def segment(
        self,
        image: np.ndarray | Image.Image | str | Path,
        grid_rows: Optional[int] = None,
        grid_cols: Optional[int] = None,
    ) -> SegmentationResult:
        """
        Segment an alphabet image into individual characters.

        Args:
            image: Input image (numpy array, PIL Image, or path)
            grid_rows: Number of rows (for grid method, or auto-detect)
            grid_cols: Number of columns (for grid method, or auto-detect)

        Returns:
            SegmentationResult with extracted characters
        """
        # Load and preprocess image
        img = self._load_image(image)
        gray = self._to_grayscale(img)
        binary = self._binarize(gray)

        logger.info(f"Segmenting image of size {img.shape[:2]} with method {self.method.value}")

        # Choose segmentation method
        method = self.method
        if method == SegmentationMethod.AUTO:
            method = self._detect_best_method(binary, grid_rows, grid_cols)
            logger.info(f"Auto-detected segmentation method: {method.value}")

        if method == SegmentationMethod.GRID:
            result = self._segment_grid(img, gray, binary, grid_rows, grid_cols)
        elif method == SegmentationMethod.ROW_COLUMN:
            result = self._segment_row_column(img, gray, binary)
        else:
            result = self._segment_contour(img, gray, binary)

        result.image_size = (img.shape[1], img.shape[0])
        return result

    def _segment_row_column(
        self,
        img: np.ndarray,
        gray: np.ndarray,
        binary: np.ndarray,
    ) -> SegmentationResult:
        """Segment using row detection followed by column segmentation."""
        from .row_column_segmenter import RowColumnSegmenter

        segmenter = RowColumnSegmenter(
            expected_chars=self.expected_chars,
            min_char_size=self.min_char_size,
            padding=self.padding,
            invert=self.invert,
            use_ai=self.use_ai,
        )

        return segmenter.segment(img)

    def _load_image(self, image: np.ndarray | Image.Image | str | Path) -> np.ndarray:
        """Load image from various sources into numpy array."""
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image), cv2.IMREAD_UNCHANGED)
            if img is None:
                raise ValueError(f"Could not load image from {image}")
            # Convert BGR to RGB if needed
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
        """Convert image to grayscale."""
        if len(img.shape) == 2:
            return img
        elif img.shape[2] == 4:
            # Use alpha channel if available and meaningful
            alpha = img[:, :, 3]
            if np.any(alpha < 255):
                # Has transparency - use alpha as mask
                rgb = cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY)
                # Where alpha is low, make white (background)
                result = np.where(alpha > 128, rgb, 255).astype(np.uint8)
                return result
            return cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY)
        else:
            return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    def _binarize(self, gray: np.ndarray) -> np.ndarray:
        """Convert grayscale to binary image."""
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Use Otsu's method for automatic thresholding
        _, binary = cv2.threshold(
            blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        if self.invert:
            binary = cv2.bitwise_not(binary)

        # Ensure characters are black on white background
        # Count pixels - if more black than white, invert
        if np.sum(binary == 0) > np.sum(binary == 255):
            binary = cv2.bitwise_not(binary)

        return binary

    def _detect_best_method(
        self,
        binary: np.ndarray,
        grid_rows: Optional[int],
        grid_cols: Optional[int],
    ) -> SegmentationMethod:
        """Detect the best segmentation method based on image analysis."""
        if grid_rows is not None and grid_cols is not None:
            return SegmentationMethod.GRID

        # Find contours to analyze layout
        contours, _ = cv2.findContours(
            cv2.bitwise_not(binary), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if len(contours) < 5:
            # Too few contours, try grid
            return SegmentationMethod.GRID

        # Filter contours by size
        valid_contours = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w >= self.min_char_size and h >= self.min_char_size:
                valid_contours.append((x, y, w, h))

        if len(valid_contours) < 5:
            return SegmentationMethod.GRID

        # Check if contours form a regular grid pattern
        # by analyzing x and y coordinates
        xs = sorted(set(x for x, y, w, h in valid_contours))
        ys = sorted(set(y for x, y, w, h in valid_contours))

        # If we have clear row/column patterns, use grid
        if len(ys) <= 6 and len(valid_contours) >= len(self.expected_chars) * 0.8:
            return SegmentationMethod.CONTOUR

        return SegmentationMethod.GRID

    def _segment_grid(
        self,
        img: np.ndarray,
        gray: np.ndarray,
        binary: np.ndarray,
        grid_rows: Optional[int],
        grid_cols: Optional[int],
    ) -> SegmentationResult:
        """Segment using grid-based method."""
        result = SegmentationResult(method=SegmentationMethod.GRID)

        h, w = img.shape[:2]

        # Auto-detect grid size if not provided
        if grid_rows is None or grid_cols is None:
            grid_rows, grid_cols = self._detect_grid_size(binary)

        result.grid_size = (grid_rows, grid_cols)
        logger.info(f"Using grid size: {grid_rows} rows x {grid_cols} cols")

        cell_w = w // grid_cols
        cell_h = h // grid_rows

        char_idx = 0
        for row in range(grid_rows):
            for col in range(grid_cols):
                if char_idx >= len(self.expected_chars):
                    break

                # Calculate cell bounds
                x1 = col * cell_w
                y1 = row * cell_h
                x2 = x1 + cell_w
                y2 = y1 + cell_h

                # Extract cell from original image
                cell_img = self._extract_cell(img, gray, x1, y1, x2, y2)

                if cell_img is not None:
                    char = CharacterCell(
                        label=self.expected_chars[char_idx],
                        bbox=(x1, y1, cell_w, cell_h),
                        image=cell_img,
                        row=row,
                        col=col,
                    )
                    result.characters.append(char)
                else:
                    result.warnings.append(
                        f"Empty cell at row {row}, col {col} for char '{self.expected_chars[char_idx]}'"
                    )

                char_idx += 1

        return result

    def _segment_contour(
        self,
        img: np.ndarray,
        gray: np.ndarray,
        binary: np.ndarray,
    ) -> SegmentationResult:
        """Segment using contour-based method."""
        result = SegmentationResult(method=SegmentationMethod.CONTOUR)

        # Find contours (characters are black, so invert for findContours)
        contours, _ = cv2.findContours(
            cv2.bitwise_not(binary), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Get bounding boxes - keep small components for dot merging
        # We'll filter by size AFTER merging to handle 'i', 'j' dots
        bboxes = []
        small_bboxes = []  # Potential dots for 'i'/'j' OR standalone punctuation

        # Adaptive minimum size based on whether we're including small glyphs
        if self.include_small_glyphs:
            min_dot_size = self.min_small_glyph_size  # Lower threshold for punctuation
            min_area = self.min_small_glyph_size ** 2  # Minimum area (e.g., 3x3=9)
        else:
            min_dot_size = 5   # Default minimum to filter noise
            min_area = 25

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = cv2.contourArea(cnt)

            if w < min_dot_size or h < min_dot_size or area < min_area:
                # Too small - likely noise
                continue
            elif w >= self.min_char_size and h >= self.min_char_size and area > 100:
                # Normal character size
                bboxes.append((x, y, w, h, cnt))
            else:
                # Small component - could be a dot for 'i'/'j' OR standalone punctuation
                # Keep ALL small components for now - we'll classify after merging
                small_bboxes.append((x, y, w, h, cnt))

        if not bboxes and not small_bboxes:
            result.warnings.append("No valid contours found")
            return result

        # Combine for merging - ALL small components participate in merging
        # This ensures 'i' and 'j' dots get merged with their stems
        all_bboxes = bboxes + small_bboxes
        logger.info(f"Found {len(bboxes)} main contours + {len(small_bboxes)} small components (potential dots)")

        # Merge component bboxes (handles 'i', 'j' dots, etc.)
        merged_bboxes = self._merge_component_bboxes(all_bboxes, img)

        # After merging, separate large chars from orphaned small components
        large_bboxes = []
        orphan_small_bboxes = []
        for b in merged_bboxes:
            if b[2] >= self.min_char_size and b[3] >= self.min_char_size:
                large_bboxes.append(b)
            else:
                orphan_small_bboxes.append(b)

        # Now classify orphaned small components
        if self.include_small_glyphs:
            # Keep orphans that look like valid punctuation
            punctuation_bboxes = []
            for x, y, w, h, cnt in orphan_small_bboxes:
                area = cv2.contourArea(cnt)
                if self._is_likely_punctuation(cnt, w, h, area):
                    punctuation_bboxes.append((x, y, w, h, cnt))

            bboxes = large_bboxes + punctuation_bboxes
            logger.info(f"After filtering: {len(large_bboxes)} main chars + {len(punctuation_bboxes)} punctuation (from {len(orphan_small_bboxes)} orphans)")
        else:
            # Original behavior: discard all orphaned small components
            bboxes = large_bboxes
            logger.info(f"After filtering: {len(large_bboxes)} main chars ({len(orphan_small_bboxes)} small orphans discarded)")

        if not bboxes:
            result.warnings.append("No valid characters after merging")
            return result

        # Sort by position (top-to-bottom, left-to-right)
        bboxes = self._sort_bboxes_reading_order(bboxes)

        # Try to split wide bboxes that might contain multiple characters
        # This handles cases where characters are touching in the source image
        if len(bboxes) < len(self.expected_chars):
            bboxes_before = len(bboxes)
            # Use AI for splitting if enabled (more accurate for ambiguous cases)
            bboxes = self._split_wide_bboxes(
                bboxes, binary, img,
                use_ai=self.use_ai
            )
            if len(bboxes) > bboxes_before:
                # Re-sort after splitting
                bboxes = self._sort_bboxes_reading_order(bboxes)

        logger.info(f"Found {len(bboxes)} character bboxes")

        # Assign labels to sorted bboxes
        for idx, (x, y, w, h, cnt) in enumerate(bboxes):
            if idx >= len(self.expected_chars):
                result.warnings.append(
                    f"More contours ({len(bboxes)}) than expected characters ({len(self.expected_chars)})"
                )
                break

            # Extract character with some padding
            x1 = max(0, x - self.padding)
            y1 = max(0, y - self.padding)
            x2 = min(img.shape[1], x + w + self.padding)
            y2 = min(img.shape[0], y + h + self.padding)

            cell_img = self._extract_cell(img, gray, x1, y1, x2, y2, cnt)

            if cell_img is not None:
                # Calculate row based on y position
                avg_height = np.mean([b[3] for b in bboxes])
                row = int(y / (avg_height * 1.5)) if avg_height > 0 else 0

                char = CharacterCell(
                    label=self.expected_chars[idx],
                    bbox=(x, y, w, h),
                    image=cell_img,
                    row=row,
                    col=idx,
                )
                result.characters.append(char)

        # Validate character count and add warnings
        validation_warnings = self.validate_character_count(
            len(result.characters), self.expected_chars
        )
        result.warnings.extend(validation_warnings)

        if len(result.characters) < len(self.expected_chars):
            missing = len(self.expected_chars) - len(result.characters)
            result.warnings.append(f"Only found {len(result.characters)} of {len(self.expected_chars)} expected characters")

        return result

    def _sort_bboxes_reading_order(
        self,
        bboxes: List[Tuple[int, int, int, int, np.ndarray]],
    ) -> List[Tuple[int, int, int, int, np.ndarray]]:
        """Sort bounding boxes in reading order (top-to-bottom, left-to-right)."""
        if not bboxes:
            return bboxes

        # Group by rows based on y-coordinate clustering
        sorted_by_y = sorted(bboxes, key=lambda b: b[1])

        # Determine row height threshold (half the average height)
        avg_height = np.mean([b[3] for b in bboxes])
        row_threshold = avg_height * 0.5

        rows = []
        current_row = [sorted_by_y[0]]
        current_y = sorted_by_y[0][1]

        for bbox in sorted_by_y[1:]:
            if abs(bbox[1] - current_y) < row_threshold:
                current_row.append(bbox)
            else:
                rows.append(sorted(current_row, key=lambda b: b[0]))
                current_row = [bbox]
                current_y = bbox[1]

        rows.append(sorted(current_row, key=lambda b: b[0]))

        # Flatten rows back to list
        result = []
        for row in rows:
            result.extend(row)

        return result

    def _merge_component_bboxes(
        self,
        bboxes: List[Tuple[int, int, int, int, np.ndarray]],
        img: np.ndarray,
    ) -> List[Tuple[int, int, int, int, np.ndarray]]:
        """
        Merge bounding boxes that belong to the same character.

        This handles characters like 'i' and 'j' where the dot is detected
        as a separate contour. Only merges when:
        - Boxes have significant horizontal overlap (not just close)
        - One box is much smaller than the other (like a dot)
        - Boxes are vertically separated (not side-by-side)

        Args:
            bboxes: List of (x, y, w, h, contour) tuples
            img: Original image for reference

        Returns:
            Merged list of bboxes
        """
        if len(bboxes) < 2:
            return bboxes

        # Calculate average character dimensions for thresholds
        avg_width = np.mean([b[2] for b in bboxes])
        avg_height = np.mean([b[3] for b in bboxes])
        avg_area = avg_width * avg_height

        # Track which bboxes have been merged
        merged = [False] * len(bboxes)
        result = []

        for i, (x1, y1, w1, h1, cnt1) in enumerate(bboxes):
            if merged[i]:
                continue

            area1 = w1 * h1
            merge_indices = [i]
            combined_x1, combined_y1 = x1, y1
            combined_x2, combined_y2 = x1 + w1, y1 + h1

            for j, (x2, y2, w2, h2, cnt2) in enumerate(bboxes):
                if i == j or merged[j]:
                    continue

                area2 = w2 * h2

                # Check if one is much smaller than the other (like a dot vs stem)
                # Use multiple criteria: area ratio OR height ratio (dots are short)
                size_ratio = min(area1, area2) / max(area1, area2)
                height_ratio = min(h1, h2) / max(h1, h2)

                # A dot typically has: area < 50% of stem OR height < 50% of stem
                one_is_small = size_ratio < 0.5 or height_ratio < 0.5

                if not one_is_small:
                    # Both are similar size AND similar height - don't merge (likely adjacent chars)
                    logger.debug(f"Merge skipped: size_ratio={size_ratio:.1%}, height_ratio={height_ratio:.1%} (both similar)")
                    continue

                # Check for horizontal alignment (for dots over stems like 'i', 'j')
                box1_x1, box1_x2 = x1, x1 + w1
                box2_x1, box2_x2 = x2, x2 + w2

                # Calculate overlap amount
                overlap_x1 = max(box1_x1, box2_x1)
                overlap_x2 = min(box1_x2, box2_x2)
                overlap_width = max(0, overlap_x2 - overlap_x1)

                # Require some overlap relative to the smaller box's width
                smaller_width = min(w1, w2)
                overlap_ratio = overlap_width / smaller_width if smaller_width > 0 else 0

                # Alternative check: is the smaller component's center within the larger's bounds?
                # This helps with handwritten 'i' and 'j' where dots may be offset
                if w1 < w2:
                    small_center_x = x1 + w1 / 2
                    center_within_bounds = box2_x1 <= small_center_x <= box2_x2
                else:
                    small_center_x = x2 + w2 / 2
                    center_within_bounds = box1_x1 <= small_center_x <= box1_x2

                # Accept if either: 30% overlap OR center is within bounds
                if overlap_ratio < 0.3 and not center_within_bounds:
                    logger.debug(f"Dot merge rejected: overlap={overlap_ratio:.1%}, center_in_bounds={center_within_bounds}")
                    continue

                # Check vertical separation (should NOT be side-by-side)
                box1_y1, box1_y2 = y1, y1 + h1
                box2_y1, box2_y2 = y2, y2 + h2

                # Calculate vertical gap
                if box1_y2 < box2_y1:
                    v_gap = box2_y1 - box1_y2
                elif box2_y2 < box1_y1:
                    v_gap = box1_y1 - box2_y2
                else:
                    v_gap = 0  # Overlapping vertically - unusual for dot, but ok

                # Allow vertical gap up to 50% of average height (dots can be far from stems)
                if v_gap > avg_height * 0.5:
                    logger.debug(f"Merge rejected: v_gap={v_gap:.0f} > {avg_height * 0.5:.0f} (50% of avg height)")
                    continue

                logger.debug(f"Merge candidate found: size_ratio={size_ratio:.1%}, overlap={overlap_ratio:.1%}, v_gap={v_gap:.0f}")

                # All criteria met - merge this box
                merge_indices.append(j)
                combined_x1 = min(combined_x1, x2)
                combined_y1 = min(combined_y1, y2)
                combined_x2 = max(combined_x2, x2 + w2)
                combined_y2 = max(combined_y2, y2 + h2)

                # Limit to max 2 components per merge (stem + dot)
                # Prevents over-merging adjacent characters
                if len(merge_indices) >= 2:
                    break

            # Mark all merged boxes
            for idx in merge_indices:
                merged[idx] = True

            # Create combined bbox
            combined_w = combined_x2 - combined_x1
            combined_h = combined_y2 - combined_y1

            # Use the largest contour as the representative
            largest_cnt = max([bboxes[idx][4] for idx in merge_indices],
                            key=cv2.contourArea)

            result.append((combined_x1, combined_y1, combined_w, combined_h, largest_cnt))

            if len(merge_indices) > 1:
                logger.info(f"Merged {len(merge_indices)} components at x={combined_x1} (likely 'i' or 'j' dot)")

        logger.info(f"After merging: {len(result)} character bboxes (from {len(bboxes)} contours)")
        return result

    def _split_wide_bboxes(
        self,
        bboxes: List[Tuple[int, int, int, int, np.ndarray]],
        binary: np.ndarray,
        img: np.ndarray,
        width_threshold: float = 1.8,
        use_ai: bool = False,
    ) -> List[Tuple[int, int, int, int, np.ndarray]]:
        """
        Split bounding boxes that are unusually wide (likely containing multiple characters).

        Uses vertical projection analysis (or AI if enabled) to find natural split points
        between characters that are touching or very close together.

        Args:
            bboxes: List of (x, y, w, h, contour) tuples
            binary: Binary image for projection analysis
            img: Original image for AI analysis
            width_threshold: Split bboxes wider than this multiple of average width
            use_ai: If True, use AI to analyze wide regions

        Returns:
            List of bboxes with wide ones split
        """
        if len(bboxes) < 3:
            return bboxes

        # Calculate average width (excluding outliers)
        widths = sorted([b[2] for b in bboxes])
        # Use median to be robust to outliers
        median_width = widths[len(widths) // 2]

        # Initialize AI identifier if needed
        ai_identifier = None
        if use_ai:
            try:
                from core.font_generator.glyph_identifier import AIGlyphIdentifier
                ai_identifier = AIGlyphIdentifier()
                logger.info("AI-assisted splitting enabled")
            except Exception as e:
                logger.warning(f"Could not initialize AI for splitting: {e}")

        result = []
        split_count = 0

        for x, y, w, h, cnt in bboxes:
            # Check if this bbox is unusually wide
            if w > median_width * width_threshold:
                splits = None

                # Try AI first if enabled
                if ai_identifier:
                    splits = self._find_split_points_ai(
                        ai_identifier, img, x, y, w, h, median_width
                    )

                # Fall back to projection analysis only if AI couldn't determine
                # (None = couldn't analyze, [] = AI says single char, don't split)
                if splits is None:
                    splits = self._find_split_points(binary, x, y, w, h, median_width)

                if splits:
                    # Split the bbox at the identified points
                    split_bboxes = self._apply_splits(x, y, w, h, cnt, splits, binary)
                    result.extend(split_bboxes)
                    split_count += len(split_bboxes) - 1
                    logger.info(f"Split wide bbox (w={w}) at x={x} into {len(split_bboxes)} parts")
                else:
                    # Couldn't find good split points, keep as is
                    result.append((x, y, w, h, cnt))
            else:
                result.append((x, y, w, h, cnt))

        if split_count > 0:
            logger.info(f"Split {split_count} combined characters")

        return result

    def _find_split_points_ai(
        self,
        ai_identifier,
        img: np.ndarray,
        x: int, y: int, w: int, h: int,
        expected_width: float,
    ) -> Optional[List[int]]:
        """
        Use AI to find split points in a wide bounding box.

        Args:
            ai_identifier: AIGlyphIdentifier instance
            img: Original image
            x, y, w, h: Bounding box coordinates
            expected_width: Expected width of a single character

        Returns:
            List of x-coordinates where splits should occur (relative to bbox),
            empty list [] if AI determined single character (no split needed),
            or None if AI couldn't determine (triggers fallback)
        """
        try:
            # Extract the region from the image
            region = img[y:y+h, x:x+w]

            # Ask AI to analyze
            char_count, split_ratios = ai_identifier.analyze_region_for_splitting(
                region, expected_width
            )

            if char_count <= 1 or not split_ratios:
                # AI says single character - return empty list (don't split)
                # This is different from None (couldn't determine)
                logger.info(f"AI determined single character (count={char_count}), no split needed")
                return []

            # Convert ratios to pixel positions
            splits = [int(ratio * w) for ratio in split_ratios]
            logger.info(f"AI suggested {char_count} characters, splits at {splits}")
            return splits

        except Exception as e:
            logger.warning(f"AI split analysis failed: {e}")
            return None

    def _find_split_points(
        self,
        binary: np.ndarray,
        x: int, y: int, w: int, h: int,
        expected_width: float,
    ) -> List[int]:
        """
        Find vertical split points in a wide bounding box using projection analysis.

        Args:
            binary: Binary image
            x, y, w, h: Bounding box coordinates
            expected_width: Expected width of a single character

        Returns:
            List of x-coordinates where splits should occur (relative to bbox)
        """
        # Extract the region
        region = binary[y:y+h, x:x+w]

        # Calculate vertical projection (sum of black pixels in each column)
        # In binary image, black=0, white=255, so we count where pixels are black
        projection = np.sum(region == 0, axis=0)

        # Find valleys (local minima) in the projection
        # These are potential split points between characters
        splits = []

        # Estimate how many characters might be in this bbox
        num_expected = max(2, int(round(w / expected_width)))

        # Find the deepest valleys
        min_projection = np.min(projection)
        max_projection = np.max(projection)
        threshold = min_projection + (max_projection - min_projection) * 0.3

        # Look for valleys below threshold
        in_valley = False
        valley_start = 0
        valleys = []

        for i, val in enumerate(projection):
            if val <= threshold:
                if not in_valley:
                    valley_start = i
                    in_valley = True
            else:
                if in_valley:
                    valley_center = (valley_start + i) // 2
                    valley_depth = np.min(projection[valley_start:i])
                    valleys.append((valley_center, valley_depth))
                    in_valley = False

        if not valleys:
            return []

        # Sort by depth (shallowest = best split point)
        valleys.sort(key=lambda v: v[1])

        # Take the best split points, spaced appropriately
        min_spacing = expected_width * 0.5

        for valley_x, _ in valleys:
            # Check if this split point is far enough from existing ones
            if all(abs(valley_x - s) > min_spacing for s in splits):
                splits.append(valley_x)
                if len(splits) >= num_expected - 1:
                    break

        return sorted(splits)

    def _apply_splits(
        self,
        x: int, y: int, w: int, h: int,
        cnt: np.ndarray,
        splits: List[int],
        binary: np.ndarray,
    ) -> List[Tuple[int, int, int, int, np.ndarray]]:
        """
        Apply split points to create multiple bounding boxes.

        Args:
            x, y, w, h: Original bounding box
            cnt: Original contour
            splits: List of split x-coordinates (relative to bbox)
            binary: Binary image for creating new contours

        Returns:
            List of new bounding boxes
        """
        result = []

        # Add boundaries
        boundaries = [0] + splits + [w]

        for i in range(len(boundaries) - 1):
            new_x = x + boundaries[i]
            new_w = boundaries[i + 1] - boundaries[i]

            # Skip very thin slices
            if new_w < 3:
                continue

            # Create a simple rectangular contour for the split region
            # (We lose the original contour shape, but that's OK for font generation)
            new_cnt = np.array([
                [[new_x, y]],
                [[new_x + new_w, y]],
                [[new_x + new_w, y + h]],
                [[new_x, y + h]]
            ], dtype=np.int32)

            result.append((new_x, y, new_w, h, new_cnt))

        return result if result else [(x, y, w, h, cnt)]

    def _is_likely_punctuation(
        self,
        contour: np.ndarray,
        width: int,
        height: int,
        area: float,
    ) -> bool:
        """
        Determine if a small contour is likely a punctuation mark rather than noise.

        Uses shape analysis to distinguish punctuation from image artifacts:
        - Punctuation tends to have regular, compact shapes
        - Noise tends to be irregular and fragmented

        Args:
            contour: OpenCV contour
            width: Bounding box width
            height: Bounding box height
            area: Contour area

        Returns:
            True if the contour appears to be a valid punctuation character
        """
        # Filter out extremely small components (likely noise)
        if width < self.min_small_glyph_size or height < self.min_small_glyph_size:
            return False

        # Check shape regularity using solidity (area / convex hull area)
        # Punctuation marks tend to be fairly solid (compact shapes)
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)

        if hull_area == 0:
            return False

        solidity = area / hull_area

        # Punctuation typically has high solidity (> 0.4)
        # Noise and artifacts tend to have irregular, fragmented shapes (low solidity)
        if solidity < 0.35:
            logger.debug(f"Rejected small glyph: solidity={solidity:.2f} < 0.35 (too irregular)")
            return False

        # Check aspect ratio - most punctuation has reasonable proportions
        aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else 999
        # Allow elongated shapes if they have substantial size (likely underscore, hyphen, equals)
        # Small elongated shapes are likely noise/artifacts
        is_substantial = width >= 30 or height >= 30  # At least 30px in one dimension
        if aspect_ratio > 8 and not is_substantial:
            # Very elongated AND tiny - probably a line artifact, not punctuation
            logger.debug(f"Rejected small glyph: aspect_ratio={aspect_ratio:.1f} > 8 and not substantial (artifact)")
            return False
        if aspect_ratio > 20:
            # Extreme aspect ratio even for substantial shapes - likely a stray line
            logger.debug(f"Rejected small glyph: aspect_ratio={aspect_ratio:.1f} > 20 (extreme elongation)")
            return False

        # Check extent (ratio of contour area to bounding box area)
        # Helps filter out very sparse/hollow shapes
        bbox_area = width * height
        extent = area / bbox_area if bbox_area > 0 else 0

        if extent < 0.15:
            logger.debug(f"Rejected small glyph: extent={extent:.2f} < 0.15 (too sparse)")
            return False

        # Additional check: contour must have reasonable number of points
        # Very few points = simple noise, too many = complex artifact
        num_points = len(contour)
        if num_points < 4 or num_points > 500:
            logger.debug(f"Rejected small glyph: num_points={num_points} out of range [4, 500]")
            return False

        logger.debug(f"Accepted small glyph: w={width}, h={height}, solidity={solidity:.2f}, aspect={aspect_ratio:.1f}")
        return True

    def _detect_grid_size(self, binary: np.ndarray) -> Tuple[int, int]:
        """Auto-detect grid size from binary image."""
        h, w = binary.shape

        # Project to rows and columns
        row_proj = np.sum(binary == 0, axis=1)
        col_proj = np.sum(binary == 0, axis=0)

        # Find gaps (rows/cols with few black pixels)
        row_threshold = w * 0.05
        col_threshold = h * 0.05

        row_gaps = np.where(row_proj < row_threshold)[0]
        col_gaps = np.where(col_proj < col_threshold)[0]

        # Count transitions to estimate grid size
        def count_groups(gaps: np.ndarray) -> int:
            if len(gaps) == 0:
                return 1
            groups = 1
            for i in range(1, len(gaps)):
                if gaps[i] - gaps[i-1] > 5:
                    groups += 1
            return groups

        estimated_rows = count_groups(row_gaps)
        estimated_cols = count_groups(col_gaps)

        # Use expected characters to refine estimate
        num_chars = len(self.expected_chars)

        # Try to find a good fit
        if estimated_rows * estimated_cols < num_chars:
            # Need more cells - try common layouts
            for rows in range(1, 10):
                cols = (num_chars + rows - 1) // rows
                if rows * cols >= num_chars:
                    estimated_rows = rows
                    estimated_cols = cols
                    break

        return max(1, estimated_rows), max(1, estimated_cols)

    def _extract_cell(
        self,
        img: np.ndarray,
        gray: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        contour: Optional[np.ndarray] = None,
    ) -> Optional[np.ndarray]:
        """Extract a character cell from the image.

        Uses the contour's own bounding box for tight extraction,
        ignoring the padded cell region to avoid capturing neighbors.
        """
        if contour is not None:
            # Use the contour's own bounding box for tight extraction
            # This avoids issues with merged bboxes that don't match the contour
            cnt_x, cnt_y, cnt_w, cnt_h = cv2.boundingRect(contour)

            # Add minimal padding
            pad = 2
            ext_x1 = max(0, cnt_x - pad)
            ext_y1 = max(0, cnt_y - pad)
            ext_x2 = min(img.shape[1], cnt_x + cnt_w + pad)
            ext_y2 = min(img.shape[0], cnt_y + cnt_h + pad)

            # Check for valid region
            if ext_x2 <= ext_x1 or ext_y2 <= ext_y1:
                return None

            # Extract from original image
            if len(img.shape) == 3:
                return img[ext_y1:ext_y2, ext_x1:ext_x2].copy()
            else:
                return gray[ext_y1:ext_y2, ext_x1:ext_x2].copy()

        # Fallback for grid-based segmentation (no contour)
        cell_gray = gray[y1:y2, x1:x2]

        if cell_gray.size == 0:
            return None

        cell_h, cell_w = cell_gray.shape[:2]

        # Find dark pixels using threshold
        _, binary = cv2.threshold(cell_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.sum(binary == 0) > np.sum(binary == 255):
            binary = cv2.bitwise_not(binary)
        coords = np.column_stack(np.where(binary < 128))

        if len(coords) < 10:
            return None

        # Get tight bounding box
        y_min, x_min = coords.min(axis=0)
        y_max, x_max = coords.max(axis=0)

        # Add small padding
        y_min = max(0, y_min - 1)
        x_min = max(0, x_min - 1)
        y_max = min(cell_h, y_max + 2)
        x_max = min(cell_w, x_max + 2)

        if len(img.shape) == 3:
            return img[y1 + y_min:y1 + y_max, x1 + x_min:x1 + x_max].copy()
        else:
            return gray[y1 + y_min:y1 + y_max, x1 + x_min:x1 + x_max].copy()

    def preview_segmentation(
        self,
        image: np.ndarray | Image.Image | str | Path,
        result: Optional[SegmentationResult] = None,
    ) -> np.ndarray:
        """
        Create a preview image showing segmentation results.

        Args:
            image: Original image
            result: Segmentation result (or None to run segmentation)

        Returns:
            Preview image with bounding boxes and labels
        """
        img = self._load_image(image)

        if result is None:
            result = self.segment(image)

        # Convert to BGR for OpenCV drawing
        if len(img.shape) == 2:
            preview = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            preview = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        else:
            preview = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        # Draw bounding boxes and labels
        for char in result.characters:
            x, y, w, h = char.bbox

            # Draw rectangle
            cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Draw label
            label_pos = (x, y - 5) if y > 20 else (x, y + h + 15)
            cv2.putText(
                preview, char.label, label_pos,
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1
            )

        # Convert back to RGB
        preview = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        return preview
