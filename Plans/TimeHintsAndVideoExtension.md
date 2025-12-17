# Time Hints & Video Extension Implementation Checklist

**Last Updated:** 2025-12-10 09:23
**Status:** Complete
**Progress:** 18/18 tasks complete

## Overview
Add time hint tags to the video tab input, integrate Whisper timing data into storyboard generation, add video extension UI for Veo 3.1, and expand tag insertion options.

## Prerequisites
- [x] Whisper analyzer exists (`core/video/whisper_analyzer.py`)
- [x] Timing models exist (`core/video/timing_models.py`)
- [x] Video extension backend exists (`core/video/veo_client.py:644-805`)
- [x] Tag parser exists (`core/video/tag_parser.py`)

---

## Implementation Tasks

### 1. Add TIME Tag Type to Parser
- [x] Add `TIME = "time"` to `TagType` enum (`core/video/tag_parser.py:27`)
- [x] Add 'time', 'timestamp', 't' to `TAG_TYPE_MAP` (`core/video/tag_parser.py:112-114`)
- [x] Add `parse_time_value()` function (`core/video/tag_parser.py:311-350`)
- [x] Add `format_time_value()` function (`core/video/tag_parser.py:353-378`)
- [x] Update `extract_scene_metadata()` to handle time tags (`core/video/tag_parser.py:406-410`)
- [x] Supports formats: `{time: 0:15}`, `{time: 15.5}`, `{time: 0:00:15.5}`

### 2. Whisper Timing Display in Input Text
- [x] Add `inject_whisper_timestamps()` function (`core/video/tag_parser.py:415-482`)
- [x] Add `extract_time_tags()` function (`core/video/tag_parser.py:485-502`)
- [x] Add "Show Time Hints" checkbox (`gui/video/workspace_widget.py:955-964`)
- [x] Add "Inject Timestamps" button (`gui/video/workspace_widget.py:966-974`)
- [x] Implement `_toggle_time_hints()` method (`gui/video/workspace_widget.py:2202-2217`)
- [x] Implement `_inject_whisper_timestamps()` method (`gui/video/workspace_widget.py:2219-2284`)
- [x] Implement `_update_whisper_ui_state()` method (`gui/video/workspace_widget.py:2286-2304`)
- [x] Call `_update_whisper_ui_state()` on project load (`gui/video/workspace_widget.py:7690-7691`)

### 3. Integrate Whisper Timing into Storyboard Generation
- [x] Add `word_timestamps` parameter to `generate_storyboard()` (`core/video/storyboard_v2.py:431`)
- [x] Implement `_apply_whisper_timing()` method (`core/video/storyboard_v2.py:894-975`)
- [x] Implement `_apply_time_tags()` method (`core/video/storyboard_v2.py:977-1039`)
- [x] Pass Whisper data in workspace widget (`gui/video/workspace_widget.py:3019-3035`)

### 4. Video Extension UI (Veo 3.1)
- [x] Add `extend_requested` signal to VideoButton (`gui/video/video_button.py:40`)
- [x] Add "Extend Video" context menu item (`gui/video/video_button.py:192-202`)
- [x] Connect signal in workspace widget (`gui/video/workspace_widget.py:3661`)
- [x] Implement `_extend_video_clip()` method (`gui/video/workspace_widget.py:4614-4696`)

### 5. Expand Insert Tag Options
- [x] Add QMenu import (`gui/video/workspace_widget.py:25`)
- [x] Replace "Insert Scene Marker" with dropdown menu (`gui/video/workspace_widget.py:928-953`)
- [x] Add `_setup_insert_tag_menu()` method (`gui/video/workspace_widget.py:2077-2100`)
- [x] Implement `_insert_tag()` method (`gui/video/workspace_widget.py:2102-2134`)
- [x] Update `_delete_scene_marker()` to handle all tag types (`gui/video/workspace_widget.py:2140-2179`)
- [x] Remove newlines from insertion (insert tag only)

---

## Testing
- [ ] Test time tag parsing with various formats
- [ ] Test Whisper timing injection into input text
- [ ] Test storyboard generation with Whisper timing vs without
- [ ] Test video extension with Veo 3.1 model
- [ ] Test insert tag dropdown with all tag types

---

## Notes

### Time Tag Format Specification
```
{time: MM:SS}      - Minutes:Seconds (e.g., {time: 1:30})
{time: SS.s}       - Seconds with decimal (e.g., {time: 90.5})
{time: HH:MM:SS}   - Hours:Minutes:Seconds (rare, for long content)
{time: HH:MM:SS.s} - Full precision with decimals
```

### Whisper Data Structure (from project.py:507)
```python
word_timestamps: List[Dict[str, Any]] = [
    {"text": "word", "start_time": 0.0, "end_time": 0.5, "confidence": 0.95},
    ...
]
```

### Video Extension Constraints (from Veo 3.1 API)
- Only works with: `veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview`
- Each hop adds 7 seconds, max 20 hops = 148 seconds total
- Resolution drops to 720p for extensions
- Final second of previous video used as seed
- Voice continuation requires voice in last 1 second

### Implementation Summary

**Files Modified:**
1. `core/video/tag_parser.py` - Added TIME tag type, time parsing functions, Whisper timestamp injection
2. `core/video/storyboard_v2.py` - Added Whisper timing integration, time tag application
3. `gui/video/workspace_widget.py` - Added tag insertion menu, time hints UI, video extension UI
4. `gui/video/video_button.py` - Added extend_requested signal and menu item

**Key Features Implemented:**
- `{time: MM:SS}` tag for marking timestamps in lyrics
- Inject Whisper timestamps button (adds time tags from audio analysis)
- Storyboard uses Whisper timing when available for accurate scene durations
- Video extension UI in VideoButton context menu (Veo 3.1 only)
- Expanded tag insertion dropdown with all tag types (scene, camera, mood, focus, transition, style, tempo, time, lipsync)
- Tag insertion no longer adds extra whitespace
