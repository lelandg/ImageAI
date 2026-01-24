# Vectorized Font Generation from Alphabet Images

**Last Updated:** 2026-01-19 15:41
**Status:** In Progress
**Progress:** 27/27 tasks complete (Phases 1-4 done + UX improvements)
**GitHub Issue:** #4

## Overview

Add a feature that allows users to upload an image of a full alphabet and have ImageAI automatically generate a functional typeface file (OTF/TTF or SVG font). This combines image segmentation, vector tracing, and font engineering into a single workflow.

## Prerequisites

- [x] Research and select font generation library - Using fonttools ✅
- [x] Research vector tracing options (potrace, autotrace, or custom OpenCV approach) - Using custom OpenCV + Bezier fitting ✅
- [x] Verify OpenCV and PIL are available in requirements.txt ✅

## Implementation Tasks

### Phase 1: Core Character Segmentation

- [x] Create `core/font_generator/` package structure (`core/font_generator/__init__.py:1`) ✅
- [x] Implement `core/font_generator/segmentation.py`:
  - [x] `AlphabetSegmenter` class for detecting/isolating characters (`segmentation.py:112`) ✅
  - [x] Grid-based segmentation for uniform layouts (`segmentation.py:213`) ✅
  - [x] Contour-based segmentation for irregular layouts (`segmentation.py:251`) ✅
  - [x] Character labeling/ordering (A-Z, a-z, 0-9, punctuation) (`segmentation.py:95-109`) ✅
- [x] Add character preview/validation step before processing (`segmentation.py:393`) ✅

### Phase 2: Contour Vectorization

- [x] Implement `core/font_generator/vectorizer.py`:
  - [x] `GlyphVectorizer` class for bitmap-to-vector conversion (`vectorizer.py:107`) ✅
  - [x] Custom Bezier curve fitting with Catmull-Rom conversion (`vectorizer.py:328`) ✅
  - [x] Douglas-Peucker simplification for path smoothing (`vectorizer.py:225`) ✅
  - [x] Handle inner contours via RETR_CCOMP hierarchy (`vectorizer.py:191`) ✅
- [x] Configurable smoothing via `SmoothingLevel` enum (`vectorizer.py:95`) ✅

### Phase 3: Font Metrics & Assembly

- [x] Implement `core/font_generator/metrics.py`:
  - [x] `FontMetrics` dataclass for font measurements (`metrics.py:59`) ✅
  - [x] `FontMetricsCalculator` with x-height, cap-height, ascender, descender (`metrics.py:99`) ✅
  - [x] Basic kerning pair generation (`metrics.py:290`) ✅
  - [x] Character width/advance calculation (`metrics.py:162`) ✅
- [x] Implement `core/font_generator/font_builder.py`:
  - [x] `FontBuilder` class using fonttools library (`font_builder.py:54`) ✅
  - [x] Assemble glyphs into font structure (`font_builder.py:130`) ✅
  - [x] `FontInfo` dataclass for metadata (`font_builder.py:28`) ✅
  - [x] Export to TTF format (`font_builder.py:136`) ✅
  - [x] Export to OTF/CFF format (`font_builder.py:224`) ✅

### Phase 4: GUI Integration

- [x] Create `gui/font_generator/` package (`gui/font_generator/__init__.py:1`) ✅
- [x] Implement `gui/font_generator/font_wizard.py` (700+ lines):
  - [x] `ImageUploadPage` - Step 1: Image upload and preview (`font_wizard.py:47`) ✅
  - [x] `SegmentationPage` - Step 2: Segmentation with adjustment (`font_wizard.py:186`) ✅
  - [x] `CharacterMappingPage` - Step 3: Character mapping verification (`font_wizard.py:310`) ✅
  - [x] `FontSettingsPage` - Step 4: Font metrics and naming (`font_wizard.py:400`) ✅
  - [x] `ExportPage` - Step 5: Preview and export (`font_wizard.py:510`) ✅
- [x] Add "Font Generator" menu item to main window (`main_window.py:778`) ✅
- [x] Font preview widget in export page (`font_wizard.py:530`) ✅

### Phase 4b: UX Improvements

- [x] Make Contour-based segmentation the default method (`font_wizard.py:301-302`) ✅
- [x] Auto-detect color inversion need (`segmentation.py:152-213`) ✅
- [x] Auto-detect character set from detected characters (`segmentation.py:215-280`) ✅

### Phase 5: Optional Enhancements

- [ ] AI-assisted missing glyph generation (use Gemini to generate missing characters in same style)
- [ ] Multiple sample learning (average multiple handwriting samples)
- [ ] Style transfer for consistent stroke weight

## Testing

- [ ] Unit tests for character segmentation with sample alphabet images
- [ ] Unit tests for vector tracing accuracy
- [ ] Integration test: full pipeline from image to TTF
- [ ] Manual testing with various alphabet image formats/layouts

## Dependencies to Add

```
fonttools>=4.47.0      # Font file manipulation
potrace               # Vector tracing (or use pypotrace)
Pillow>=10.0.0        # Image processing (already present)
opencv-python>=4.8.0  # Contour detection (already present)
```

## Technical Notes

### Segmentation Approaches

1. **Grid-based**: Assumes uniform character spacing (like the example image). Divide image into NxM grid based on expected character count.

2. **Contour-based**: Use OpenCV `findContours()` to detect character blobs, then sort by position. More flexible but requires clean input.

3. **AI-assisted**: Use Gemini vision to identify character positions if traditional methods fail.

### Vector Tracing

- **potrace**: Industry-standard bitmap tracing, produces clean Bezier curves
- **OpenCV + curve fitting**: More control but requires manual implementation
- Consider offering quality presets (fast/draft vs high-quality)

### Font Format Considerations

- **TTF/OTF**: Standard formats, best compatibility
- **SVG Font**: Deprecated but simpler to generate, useful as fallback
- **WOFF/WOFF2**: Web formats, can generate from TTF

### Sample Alphabet Image Requirements

Document expected input format:
- White/light background with dark characters
- Characters arranged in rows (A-Z, a-z, 0-9, punctuation)
- Consistent character size within image
- Minimum resolution: 100px per character recommended

## UI Mockup

```
+------------------------------------------+
|  Font Generator Wizard                   |
+------------------------------------------+
| Step 2 of 5: Verify Character Mapping    |
|                                          |
| +--------------------------------------+ |
| |  [A] [B] [C] [D] [E] [F] [G] ...    | |
| |  [a] [b] [c] [d] [e] [f] [g] ...    | |
| |  [0] [1] [2] [3] [4] [5] [6] ...    | |
| +--------------------------------------+ |
|                                          |
| Click a cell to reassign character       |
|                                          |
| [< Back]              [Next >] [Cancel]  |
+------------------------------------------+
```

## References

- fonttools documentation: https://fonttools.readthedocs.io/
- potrace algorithm: http://potrace.sourceforge.net/
- OpenType spec: https://docs.microsoft.com/en-us/typography/opentype/spec/
