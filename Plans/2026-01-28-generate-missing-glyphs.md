# Generate Missing Glyphs Feature - Implementation Checklist

**Last Updated:** 2026-01-28 06:45
**Status:** In Progress
**Progress:** 8/12 tasks complete

## Overview

Add a feature to the Font Generator wizard that generates missing glyphs using the main window's selected AI image model. When segmentation detects missing characters (e.g., `~` and `\`), users can generate them with AI that matches the style of existing detected glyphs.

## Design Decisions

| Decision | Choice |
|----------|--------|
| Style reference | Automatic selection of 3-5 existing glyphs |
| UI location | Character Mapping page (Page 3) |
| Generation flow | Direct insertion (no preview dialog) |
| Model selection | Inherit from main window's current provider/model |
| Image sizing | Match detected glyph dimensions, auto-crop |

## Prerequisites

- [x] Verify main window exposes `current_provider`, `current_model`, and `config.get_api_key()` (`gui/main_window.py:245-250`)

## Implementation Tasks

### Core Module: `core/font_generator/glyph_generator.py`

- [x] Create `GlyphGenerator` class with `__init__(provider, model, api_key)` (`glyph_generator.py:49`)
- [x] Implement `_select_references(char, available, count=5)` - select best style reference glyphs (`glyph_generator.py:166`)
- [x] Implement `_build_prompt(char)` - construct AI prompt (no dimensions in text for Gemini) (`glyph_generator.py:214`)
- [x] Implement `_process_image(raw_image, target_height)` - auto-crop and scale (`glyph_generator.py:256`)
- [x] Implement `generate_glyph(char, reference_glyphs, target_height)` - main generation method (`glyph_generator.py:78`)
- [x] Add comprehensive logging for all operations (prompts, responses, processing steps)

### Package Export: `core/font_generator/__init__.py`

- [x] Export `GlyphGenerator` class (`__init__.py:51-53`)

### UI Changes: `gui/font_generator/font_wizard.py`

- [x] Add missing characters section to `CharacterMappingPage` (placeholder cards with dashed borders) (`font_wizard.py:798-814`)
- [x] Add "Generate Missing" button to top bar next to "Identify with AI" (`font_wizard.py:780-791`)
- [x] Implement `_generate_missing_glyphs()` method with QThread for non-blocking generation (`font_wizard.py:1011-1095`)
- [x] Add progress feedback (spinner on placeholder cards during generation) (`font_wizard.py:1097-1112`)
- [x] Handle generation errors gracefully (log, show message, don't block wizard) (`font_wizard.py:1145-1154`)

## Technical Specifications

### Gemini-Specific Handling

- Use `image_config={'aspect_ratio': '1:1'}` for square output
- Do NOT include dimensions in prompt text (renders as literal text in image)
- Works with both `gemini-2.5-flash-image` and `gemini-3` models
- Generate at 1024x1024, then auto-crop and scale

### Prompt Template

```
Generate a single handwritten character '{char}' that matches the style of these reference characters.
The character should be:
- Isolated on a pure white background
- Black ink/stroke color matching the references
- Similar stroke width and weight to the references
Output ONLY the character, no borders, no labels, centered in the image.
```

### Image Processing Pipeline

1. AI generates image at 1:1 aspect ratio (1024x1024)
2. Convert to grayscale
3. Apply threshold for clean black/white
4. Auto-crop: find bounding box of non-white pixels
5. Scale to match average glyph height from existing set
6. Create `CharacterCell` with processed image and correct label

### Logging Requirements

All operations logged to both file and console:
- Selected reference glyphs and their labels
- Full prompt sent to AI (with separator formatting)
- Provider, model, and generation parameters
- Raw response from AI
- Image processing steps (threshold values, crop bounds, final dimensions)
- Success/failure status for each glyph

### Reference Selection Heuristics

- For punctuation marks: prefer glyphs with similar visual characteristics
- Default diverse sample: pick from (A, a, m, 0, g) for broad style coverage
- Always include at least one uppercase, one lowercase if available

### Error Handling

- If generation fails: log error, show message, but don't block wizard
- User can proceed without the missing glyph or retry
- Network errors: show retry option

## Testing

- [ ] Test with Gemini 2.5 model
- [ ] Test with Gemini 3 model
- [ ] Test with OpenAI model (if supported)
- [ ] Test generation of punctuation characters (`~`, `\`, `@`, etc.)
- [ ] Verify generated glyphs match style of existing glyphs
- [ ] Verify logging output is comprehensive

## Files Changed

| File | Change Type |
|------|-------------|
| `core/font_generator/glyph_generator.py` | Create (~200 lines) |
| `core/font_generator/__init__.py` | Modify (add export) |
| `gui/font_generator/font_wizard.py` | Modify (~100 lines) |

## Notes

- Feature requested to handle missing glyphs that segmentation fails to detect (like `~` and `\` which are small/unusual shapes)
- Main window already tracks current provider/model, so wizard just needs parent reference
- Generation runs in QThread to keep UI responsive
