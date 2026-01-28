# Font Generator Row-Column Segmentation Implementation Plan

**Last Updated:** 2026-01-27
**Status:** Complete
**Progress:** 6/6 tasks complete

## Overview

Replace simple contour-based segmentation with intelligent row detection → column segmentation to handle overlapping baselines (like 'g' vs 't') and preserve column offsets for partial characters.

**Architecture:**
1. Detect text rows by analyzing horizontal projection profiles
2. Handle overlapping rows (descenders of 'g', 'j', 'p', 'q', 'y' overlap with next row)
3. Within each row, segment into columns using vertical projection
4. Send all extracted glyphs to AI in batch for identification
5. Map identified characters to the expected charset

**Tech Stack:** OpenCV, NumPy, PIL, Google Gemini API (for batch glyph identification)

---

## Background & Problem Statement

The current segmentation approach (`_segment_contour`) has fundamental limitations:

1. **Simple size filtering**: Rejects contours where `w < 20 OR h < 20 OR area < 100`
2. **Sequential label assignment**: Labels assigned by sorted position, not visual recognition
3. **No row awareness**: Doesn't understand that 'g' in row 1 may vertically overlap with 't' in row 2
4. **Single-contour focus**: Each contour treated independently, missing multi-part characters

---

## Implementation Tasks

### Task 1: Create Row Detection Module

- [x] Create: `core/font_generator/row_detector.py` ✅

```python
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

        logger.info(f"Detected {len(rows)} text rows")
        return rows

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
    ) -> List[CharacterColumn]:
        """Segment a row into individual character columns."""
        h, w = image.shape[:2]

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

        # Find columns
        threshold = row.height * 0.05

        columns = []
        in_column = False
        col_start = 0

        for x, ink_count in enumerate(projection):
            if not in_column and ink_count > threshold:
                in_column = True
                col_start = x
            elif in_column and ink_count <= threshold:
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

        # Split wide columns
        columns = self._split_wide_columns(columns, projection, row)

        logger.debug(f"Row at y={row.y}: found {len(columns)} columns")
        return columns

    def _split_wide_columns(
        self,
        columns: List[CharacterColumn],
        projection: np.ndarray,
        row: TextRow,
        width_threshold: float = 1.8,
    ) -> List[CharacterColumn]:
        """Split columns that are unusually wide."""
        if not columns:
            return columns

        widths = [c.width for c in columns]
        median_width = sorted(widths)[len(widths) // 2]

        result = []
        for col in columns:
            if col.width > median_width * width_threshold:
                splits = self._find_column_splits(
                    projection[col.x:col.x + col.width], median_width
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
                    result.append(col)
            else:
                result.append(col)

        return result

    def _find_column_splits(self, projection: np.ndarray, expected_width: float) -> List[int]:
        """Find split points in a column's projection profile."""
        if len(projection) < 10:
            return []

        min_val = np.min(projection)
        max_val = np.max(projection)

        if max_val == min_val:
            return []

        threshold = min_val + (max_val - min_val) * 0.3

        valleys = []
        in_valley = False
        valley_start = 0

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

        valleys.sort(key=lambda v: v[1])

        splits = []
        min_spacing = expected_width * 0.5

        for valley_x, _ in valleys:
            if all(abs(valley_x - s) > min_spacing for s in splits):
                splits.append(valley_x)

        return sorted(splits)
```

---

### Task 2: Add Batch AI Glyph Identification

- [x] Modify: `core/font_generator/glyph_identifier.py` ✅

Add after `GlyphIdentificationResult` dataclass:

```python
@dataclass
class BatchIdentificationResult:
    """Result of batch glyph identification."""
    identifications: List[GlyphIdentificationResult]
    total_glyphs: int
    successful_count: int
    error: Optional[str] = None
```

Add these methods to `AIGlyphIdentifier` class:

```python
def batch_identify(
    self,
    glyph_images: List[np.ndarray | Image.Image],
    expected_chars: Optional[str] = None,
    max_per_request: int = 20,
) -> List[GlyphIdentificationResult]:
    """Identify multiple glyphs in batch using a single AI request."""
    if not glyph_images:
        return []

    if not self._ensure_client():
        return [
            GlyphIdentificationResult(
                identified_char=None, confidence=0.0, alternatives=[],
                error="Gemini client not available"
            )
            for _ in glyph_images
        ]

    try:
        from google.genai import types

        pil_images = []
        for img in glyph_images:
            if isinstance(img, np.ndarray):
                pil_img = Image.fromarray(img)
            else:
                pil_img = img
            if pil_img.mode != 'RGB':
                pil_img = pil_img.convert('RGB')
            pil_images.append(pil_img)

        all_results = []
        for batch_start in range(0, len(pil_images), max_per_request):
            batch_images = pil_images[batch_start:batch_start + max_per_request]
            batch_results = self._identify_batch(batch_images, expected_chars)
            all_results.extend(batch_results)

        return all_results

    except Exception as e:
        logger.error(f"Batch identification failed: {e}")
        return [
            GlyphIdentificationResult(
                identified_char=None, confidence=0.0, alternatives=[], error=str(e)
            )
            for _ in glyph_images
        ]

def _identify_batch(
    self,
    pil_images: List[Image.Image],
    expected_chars: Optional[str],
) -> List[GlyphIdentificationResult]:
    """Identify a batch of images in a single API call."""
    from google.genai import types

    composite, positions = self._create_numbered_composite(pil_images)
    prompt = self._build_batch_prompt(len(pil_images), expected_chars)

    logger.info("=" * 60)
    logger.info("AI BATCH IDENTIFICATION REQUEST")
    logger.info(f"  Auth: {self._auth_method}")
    logger.info(f"  Model: {self.model}")
    logger.info(f"  Glyph count: {len(pil_images)}")
    logger.info("=" * 60)

    response = self._client.models.generate_content(
        model=self.model,
        contents=[composite, prompt],
        config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=500)
    )

    logger.info("AI BATCH IDENTIFICATION RESPONSE")
    if response and response.text:
        logger.info(f"  Response: {response.text[:200]}...")
        results = self._parse_batch_response(response.text, len(pil_images))
        logger.info(f"  Parsed {len(results)} identifications")
        logger.info("=" * 60)
        return results
    else:
        logger.warning("  Response: EMPTY")
        logger.info("=" * 60)
        return [
            GlyphIdentificationResult(
                identified_char=None, confidence=0.0, alternatives=[], error="Empty response"
            )
            for _ in pil_images
        ]

def _create_numbered_composite(
    self,
    images: List[Image.Image],
) -> Tuple[Image.Image, List[Tuple[int, int]]]:
    """Create a composite image with numbered glyphs arranged in a grid."""
    from PIL import ImageDraw

    n = len(images)
    cols = min(10, n)
    rows = (n + cols - 1) // cols

    max_w = max(img.width for img in images)
    max_h = max(img.height for img in images)

    cell_w = max_w + 20
    cell_h = max_h + 30

    composite_w = cols * cell_w
    composite_h = rows * cell_h
    composite = Image.new('RGB', (composite_w, composite_h), 'white')
    draw = ImageDraw.Draw(composite)

    positions = []
    for i, img in enumerate(images):
        row = i // cols
        col = i % cols

        x = col * cell_w + (cell_w - img.width) // 2
        y = row * cell_h + 20

        composite.paste(img, (x, y))
        positions.append((x, y))

        number_x = col * cell_w + cell_w // 2
        number_y = row * cell_h + 5
        draw.text((number_x, number_y), str(i + 1), fill='black', anchor='mt')

    return composite, positions

def _build_batch_prompt(self, count: int, expected_chars: Optional[str]) -> str:
    """Build prompt for batch identification."""
    prompt = f"""You are analyzing {count} numbered character glyphs for font creation.
Each glyph is numbered 1 through {count} in the image.

For EACH numbered glyph, identify the character it represents.

IMPORTANT:
- Look at each glyph carefully
- Consider both letters (uppercase/lowercase) and symbols/punctuation
- Some may be partial or unclear

Respond with EXACTLY {count} lines in this format:
1. <character> (<confidence>%)
2. <character> (<confidence>%)
...

Use "?" if you cannot identify a glyph.
"""

    if expected_chars:
        prompt += f"""
The expected characters in this font are: {expected_chars}
Each glyph should be one of these characters."""

    return prompt

def _parse_batch_response(
    self,
    response_text: str,
    expected_count: int,
) -> List[GlyphIdentificationResult]:
    """Parse the batch identification response."""
    import re

    results = []
    lines = response_text.strip().split('\n')

    for i in range(expected_count):
        if i < len(lines):
            line = lines[i].strip()
            match = re.match(r'\d+\.\s*(.+?)(?:\s*\((\d+)%?\))?$', line)
            if match:
                char = match.group(1).strip()
                confidence_str = match.group(2)
                confidence = int(confidence_str) / 100 if confidence_str else 0.7

                if len(char) > 1:
                    char = char[0]

                if char == '?':
                    results.append(GlyphIdentificationResult(
                        identified_char=None, confidence=0.0, alternatives=[],
                        error="Could not identify"
                    ))
                else:
                    results.append(GlyphIdentificationResult(
                        identified_char=char,
                        confidence=confidence,
                        alternatives=self.SIMILAR_CHARS.get(char, [])[:3]
                    ))
            else:
                results.append(GlyphIdentificationResult(
                    identified_char=None, confidence=0.0, alternatives=[],
                    error=f"Could not parse line: {line}"
                ))
        else:
            results.append(GlyphIdentificationResult(
                identified_char=None, confidence=0.0, alternatives=[],
                error="Missing in response"
            ))

    return results
```

---

### Task 3: Create Row-Column Segmenter Class

- [x] Create: `core/font_generator/row_column_segmenter.py` ✅

```python
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
        """Segment an alphabet image into individual characters."""
        img = self._load_image(image)
        gray = self._to_grayscale(img)
        binary = self._binarize(gray)

        logger.info(f"Row-column segmentation of image {img.shape[:2]}")

        rows = self.row_detector.detect_rows(binary)
        logger.info(f"Detected {len(rows)} text rows")

        if not rows:
            return SegmentationResult(
                method=SegmentationMethod.CONTOUR,
                warnings=["No text rows detected"]
            )

        all_columns: List[Tuple[CharacterColumn, int]] = []

        for row_idx, row in enumerate(rows):
            columns = self.row_detector.segment_columns(binary, row)
            for col in columns:
                col.row_index = row_idx
                all_columns.append((col, row_idx))

        logger.info(f"Detected {len(all_columns)} character columns total")

        characters = []
        for col, row_idx in all_columns:
            x1 = max(0, col.x - self.padding)
            y1 = max(0, col.y - self.padding)
            x2 = min(img.shape[1], col.x + col.width + self.padding)
            y2 = min(img.shape[0], col.y + col.height + self.padding)

            cell_img = img[y1:y2, x1:x2].copy()

            if cell_img.size > 0:
                characters.append((cell_img, col, row_idx))

        result = SegmentationResult(method=SegmentationMethod.CONTOUR)

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
```

---

### Task 4: Integrate with AlphabetSegmenter

- [x] Modify: `core/font_generator/segmentation.py` ✅

**Change 1:** Add `ROW_COLUMN` to `SegmentationMethod` enum (around line 21):

```python
class SegmentationMethod(Enum):
    """Available segmentation methods."""
    GRID = "grid"
    CONTOUR = "contour"
    AUTO = "auto"
    ROW_COLUMN = "row_column"  # NEW
```

**Change 2:** In `AlphabetSegmenter.segment()` method, add dispatch (around line 420):

```python
if method == SegmentationMethod.GRID:
    result = self._segment_grid(img, gray, binary, grid_rows, grid_cols)
elif method == SegmentationMethod.ROW_COLUMN:
    result = self._segment_row_column(img, gray, binary)
else:
    result = self._segment_contour(img, gray, binary)
```

**Change 3:** Add new method to `AlphabetSegmenter` class:

```python
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
```

---

### Task 5: Update GUI

- [x] Modify: `gui/font_generator/font_wizard.py` ✅

**Change 1:** In `SegmentationPage.init_ui()`, update method combo (around line 287):

```python
self.method_combo.addItems([
    "Contour-based",
    "Grid-based",
    "Auto Detect",
    "Row-Column",  # NEW
])
```

**Change 2:** In `run_segmentation_auto()` and `run_segmentation()`, update method mapping (around line 448):

```python
methods = [
    SegmentationMethod.CONTOUR,
    SegmentationMethod.GRID,
    SegmentationMethod.AUTO,
    SegmentationMethod.ROW_COLUMN,  # NEW at index 3
]
```

---

### Task 6: Update Package Exports

- [x] Modify: `core/font_generator/__init__.py` ✅

Add imports:

```python
from .row_detector import (
    RowDetector,
    TextRow,
    CharacterColumn,
)
from .row_column_segmenter import (
    RowColumnSegmenter,
)
```

Add to `__all__`:

```python
# Row-Column Segmentation
"RowDetector",
"TextRow",
"CharacterColumn",
"RowColumnSegmenter",
```

---

## Summary

| Task | File(s) | Description |
|------|---------|-------------|
| 1 | `row_detector.py` | Row detection + column segmentation |
| 2 | `glyph_identifier.py` | Batch AI identification |
| 3 | `row_column_segmenter.py` | Combined segmenter class |
| 4 | `segmentation.py` | Integration with existing code |
| 5 | `font_wizard.py` | GUI dropdown option |
| 6 | `__init__.py` | Package exports |
