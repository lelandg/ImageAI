# LLM Scene Suggestion Feature - Implementation Checklist

**Last Updated:** 2025-12-08 15:53
**Status:** In Progress
**Progress:** 14/18 tasks complete

## Overview

Add an LLM-powered "Suggest Scenes" button that analyzes lyrics/text and automatically inserts scene markers, camera directions, mood indicators, and other video storyboard metadata. Uses a structured tag format that's distinct from existing `[Section]` markers.

## Tag Format Decision

**Chosen format**: Curly braces `{tag: value}`

**Rationale**:
- Distinct from `[Verse]`, `[Chorus]` section markers
- Familiar JSON/template-like syntax
- Easy for LLMs to generate consistently
- Clear visual hierarchy in text

### Supported Tags

| Tag | Description | Examples |
|-----|-------------|----------|
| `{scene: env}` | Scene/environment change | `{scene: bedroom}`, `{scene: neon city}` |
| `{camera: move}` | Camera movement | `{camera: slow pan}`, `{camera: dolly in}` |
| `{mood: atmosphere}` | Emotional tone | `{mood: melancholy}`, `{mood: euphoric}` |
| `{focus: subject}` | Visual focus | `{focus: singer}`, `{focus: hands on piano}` |
| `{transition: type}` | Scene transition | `{transition: fade}`, `{transition: cut}` |
| `{style: visual}` | Visual style hint | `{style: noir}`, `{style: dreamlike}` |
| `{lipsync}` | Mark for lip-sync | `{lipsync}` (boolean, no value) |
| `{tempo: descriptor}` | Tempo indication | `{tempo: building}`, `{tempo: breakdown}` |

## Prerequisites

- [x] Existing scene marker parsing (`storyboard_v2.py:20-77`)
- [x] LLM integration via UnifiedLLMProvider
- [x] Whisper extraction button exists

## Implementation Tasks

### Section 1: Tag Parser Update

- [x] Create `core/video/tag_parser.py` (~250 lines) (`core/video/tag_parser.py:1`) ✅
  - [x] `TagParser` class for parsing curly brace tags ✅
  - [x] `parse(text) -> ParseResult` - extract tags and clean text ✅
  - [x] `insert_tag(text, tag_type, value, line)` - insert tags at positions ✅
  - [x] `has_tags(text) -> bool` - check if any tags exist ✅
  - [x] Support all tag types from table above ✅
  - [x] Maintain backward compatibility with `=== NEW SCENE ===` format ✅

- [x] Update `core/video/storyboard_v2.py` (`core/video/storyboard_v2.py:20`) ✅
  - [x] Import and use new TagParser ✅
  - [x] Convert parsed tags to scene metadata ✅
  - [x] Deprecate `=== ===` format (support but warn) ✅

### Section 2: LLM Scene Suggestion

- [x] Create `core/video/scene_suggester.py` (~300 lines) (`core/video/scene_suggester.py:1`) ✅
  - [x] `SceneSuggester` class with LLM integration ✅
  - [x] `suggest_scenes(lyrics, provider, model, ...) -> SuggestionResult` ✅
  - [x] LLM prompt template for scene analysis ✅
  - [x] Support tempo/BPM info from MIDI/audio ✅
  - [x] Support style preferences from project settings ✅
  - [x] Lyrics preservation verification ✅

### Section 3: UI Integration

- [x] Add "Suggest Scenes" button to workspace widget (`gui/video/workspace_widget.py:943`) ✅
  - [x] Place next to scene marker controls ✅
  - [x] Tooltip with description ✅

- [x] Add confirmation dialog before running (`gui/video/workspace_widget.py:2113`) ✅
  - [x] If tags already exist: "Tags found in lyrics. Replace existing tags?" ✅
  - [x] Options: "Replace All", "Keep + Add New", "Cancel" ✅

- [x] Add progress indicator ✅
  - [x] Show "Analyzing..." during LLM call ✅
  - [x] Update status console with suggestions made ✅

- [x] Add checkbox: "Auto-suggest" after Whisper extraction (`gui/video/workspace_widget.py:1362`) ✅
  - [x] Trigger scene suggestion after Whisper completes ✅

### Section 4: Storyboard Integration

- [x] Update storyboard generation to use new tags (`core/video/storyboard_v2.py:20`) ✅
  - [x] Convert `{scene: X}` to scene environment ✅
  - [x] Include metadata from other tags via `extract_scene_metadata()` ✅

- [ ] Add tag preview in storyboard table
  - [ ] Show extracted tags per scene in a column or tooltip

## Testing

- [ ] Test tag parser with various formats and edge cases
- [ ] Test LLM prompt produces correctly formatted tags
- [ ] Test lyrics preservation (no modifications to original text)
- [ ] Test backward compatibility with `=== ===` format
- [ ] Test auto-suggest after Whisper extraction
- [ ] Test tag conflict detection and warning dialog

## Migration Plan

1. **Phase 1**: Add new `{tag:}` format support alongside `===` format ✅
2. **Phase 2**: Show deprecation warning when `===` format detected ✅
3. **Phase 3** (future): Remove `===` format support

## UI Mockup

### Before LLM Suggestion
```
[Verse 1]
When the night feels endless and I'm wide awake
I shuffle numbers like cards
I hum a rhythm, let the numbers dance

[Chorus]
I'm doin' math, I do math
```

### After LLM Suggestion
```
{scene: bedroom, dim lighting}
{mood: contemplative}
[Verse 1]
When the night feels endless and I'm wide awake
{camera: slow pan across desk}
I shuffle numbers like cards
{focus: hands writing equations}
I hum a rhythm, let the numbers dance

{scene: abstract mathematical space}
{transition: dissolve}
{mood: uplifting}
[Chorus]
{lipsync}
I'm doin' math, I do math
```

## Files Created/Modified

### New Files
- `core/video/tag_parser.py` - Tag parsing with curly brace format
- `core/video/scene_suggester.py` - LLM-powered scene suggestion

### Modified Files
- `core/video/storyboard_v2.py` - Updated `parse_scene_markers()` to use TagParser
- `gui/video/workspace_widget.py` - Added Suggest Scenes button, auto-suggest checkbox

## Notes

- Curly braces chosen over `===` for cleaner syntax and JSON familiarity
- Tags on separate lines to avoid cluttering lyric text
- `[Section]` markers preserved (they're different from our `{tag:}` format)
- LLM contract explicitly requires preserving original lyrics
- Auto-suggest checkbox provides smooth workflow with Whisper extraction
- 2025-12-08: Implementation complete for core functionality
  - TagParser supports both new `{tag:}` and legacy `=== ===` formats
  - SceneSuggester uses LiteLLM for provider-agnostic LLM calls
  - UI integrated with warning dialog for existing tags
  - Auto-suggest triggers after Whisper extraction if checkbox enabled
