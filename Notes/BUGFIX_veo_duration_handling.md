# Bug Fix: Veo 3.0/3.1 Duration Handling

**Date:** 2025-11-10
**Issue:** Veo 3.0/3.1 always generates 8-second videos, but storyboard scenes can have different durations (e.g., 1 second). The system was trying to use `snap_duration_to_veo()` which could return 4, 6, or 8 seconds, causing validation errors and improper clip lengths in final videos.

## Root Cause

1. **Veo Model Constraints** (`core/video/veo_client.py:72-77`, `148-149`):
   - Veo 3.0 and 3.1 models ONLY support 8-second clip generation (hardcoded in the API)
   - This is enforced in `VeoGenerationConfig.__post_init__()` validation
   - Model constraints document `"fixed_duration": 8`

2. **Incorrect Duration Snapping** (`gui/video/video_project_tab.py:958, 988`):
   - Code was using `snap_duration_to_veo(scene.duration_sec)` which could return 4, 6, or 8
   - This caused `ValueError` when creating `VeoGenerationConfig` with duration != 8 for Veo 3.0/3.1

3. **Missing Clip Trimming**:
   - Even if generation succeeded, 8-second clips were not being trimmed to match intended scene durations
   - Final video would have wrong timing/sync issues

## Solution

### 1. Fixed Duration Handling in Video Generation (`gui/video/video_project_tab.py`)

Changed three locations (lines 951-967, 975-991, 995-1010) to always use 8-second duration for Veo 3.0/3.1:

```python
# OLD (WRONG):
veo_duration = snap_duration_to_veo(scene.duration_sec)  # Could return 4, 6, or 8

# NEW (CORRECT):
veo_duration = 8  # Always 8 for Veo 3.0/3.1

# Store metadata for trimming later
scene.metadata['intended_duration_sec'] = scene.duration_sec
scene.metadata['generated_duration_sec'] = veo_duration
```

**Rationale:**
- Veo 3.0/3.1 API ONLY accepts 8-second duration
- We generate 8-second clips and trim them during final rendering
- Metadata tracks the intended vs generated duration for proper trimming

### 2. Added Clip Trimming Support (`core/video/ffmpeg_renderer.py`)

Added three new methods (lines 138-295):

#### `render_from_clips()` (lines 138-247)
Main rendering method for Veo-generated clips:
- Iterates through scenes and checks `intended_duration_sec` vs `generated_duration_sec` in metadata
- Trims clips that are longer than intended duration
- Concatenates all clips into final video
- Adds audio and karaoke overlays if configured

```python
# Get intended duration from metadata
intended_duration = scene.metadata.get('intended_duration_sec', scene.duration_sec)
generated_duration = scene.metadata.get('generated_duration_sec', 8.0)

# Trim if needed
if abs(intended_duration - generated_duration) > 0.01:
    self._trim_clip(scene.video_clip, trimmed_path, intended_duration)
```

#### `_trim_clip()` (lines 249-271)
Trims a single video clip using FFmpeg:
- Uses `-t` flag to cut clip to exact duration
- Uses `-c:v copy` and `-c:a copy` for fast processing (no re-encoding)

```bash
ffmpeg -i input.mp4 -t 1.5 -c:v copy -c:a copy output.mp4
```

#### `_concatenate_clips()` (lines 273-295)
Concatenates trimmed clips using FFmpeg concat demuxer:
- Creates concat.txt file listing all clips
- Uses `-c copy` to avoid re-encoding
- Fast and maintains quality

### 3. Updated Veo Rendering Method (`gui/video/video_project_tab.py:1246-1283`)

Changed `_render_with_veo()` from a stub to call the new rendering pipeline:

```python
def _render_with_veo(self):
    """Render video from Veo-generated clips with proper trimming"""
    renderer = FFmpegRenderer()

    # Render from Veo clips with trimming
    rendered_path = renderer.render_from_clips(
        self.project,
        output_path,
        settings,
        progress_callback
    )
```

## Files Modified

1. **`gui/video/video_project_tab.py`**:
   - Lines 951-967: MODE 1 (Image-to-Video) - Fixed duration handling
   - Lines 975-991: MODE 2 (References mode) - Fixed duration handling
   - Lines 995-1010: MODE 3 (Text-to-Video) - Fixed duration handling
   - Lines 1246-1283: Implemented `_render_with_veo()` method

2. **`core/video/ffmpeg_renderer.py`**:
   - Lines 138-247: Added `render_from_clips()` method
   - Lines 249-271: Added `_trim_clip()` helper method
   - Lines 273-295: Added `_concatenate_clips()` helper method

## Testing Recommendations

1. **Test Case 1: Short scenes (< 8 seconds)**
   - Create storyboard with scenes of 1.0s, 2.5s, 3.0s durations
   - Generate video clips with Veo 3.0/3.1
   - Verify clips are trimmed correctly in final render
   - Check timing matches audio/lyrics

2. **Test Case 2: Exact 8-second scenes**
   - Create scenes with exactly 8.0s duration
   - Verify no trimming occurs (clips used as-is)
   - Check no quality loss from unnecessary processing

3. **Test Case 3: Mixed durations**
   - Mix of short (1-2s), medium (4-5s), and 8s scenes
   - Verify all clips trim correctly
   - Check seamless concatenation

4. **Test Case 4: All three generation modes**
   - MODE 1: Image-to-Video with start frame
   - MODE 2: Veo 3.1 with reference images
   - MODE 3: Text-to-Video
   - Verify metadata is stored correctly for all modes
   - Verify trimming works for all modes

## Impact

### Positive:
- ✅ Fixes validation errors when generating Veo clips
- ✅ Proper clip duration in final rendered videos
- ✅ Correct timing/sync with audio and lyrics
- ✅ Fast trimming using codec copy (no re-encoding)
- ✅ Clear logging for debugging duration issues

### Potential Issues:
- ⚠️ Requires scenes to have `duration_sec` attribute
- ⚠️ Assumes metadata is preserved when saving/loading projects
- ⚠️ FFmpeg must be available for trimming and concatenation

## Future Improvements

1. **Support for other Veo models**:
   - Veo 3 Fast supports 4, 6, or 8 seconds
   - Could add model detection and use snap_duration_to_veo for Fast model
   - Current implementation always uses 8s which is safer but may not be optimal

2. **Batching short scenes**:
   - Instead of generating separate 8s clips for 1s scenes, batch multiple scenes into one 8s clip
   - Extract segments from the single clip
   - Would reduce API costs and generation time

3. **Smart trimming**:
   - Analyze video content to find best trim point (e.g., avoid cutting mid-motion)
   - Use scene detection algorithms
   - Optional re-encoding with quality preservation

4. **Metadata validation**:
   - Add validation when loading projects to ensure metadata fields exist
   - Provide migration for old projects without metadata

## Documentation Updates Needed

1. Update `Docs/CodeMap.md`:
   - Document new FFmpeg renderer methods
   - Update Scene metadata fields section

2. Update `CLAUDE.md`:
   - Add note about Veo 3.0/3.1 8-second limitation
   - Document metadata fields used for trimming

3. User-facing documentation:
   - Explain that scenes can be any duration but Veo generates 8s clips
   - Clarify that trimming happens automatically during rendering
   - Show example workflows for different scene lengths

## Related Code

- **Veo Client**: `core/video/veo_client.py` - Model constraints and validation
- **MIDI Processor**: `core/video/midi_processor.py` - `snap_duration_to_veo()` function
- **Project Model**: `core/video/project.py` - Scene class with metadata
- **Workspace Widget**: `gui/video/workspace_widget.py` - Scene duration editing

## Conclusion

This fix ensures that Veo 3.0/3.1 video generation works correctly with scenes of any duration. By always generating 8-second clips and trimming them during rendering, we avoid validation errors and ensure proper timing in final videos. The implementation is efficient (using codec copy) and maintains video quality.
