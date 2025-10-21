# Veo 3.1 Scene Batching Implementation

## Overview

This document describes the implementation of scene batching for Veo 3.1 video generation. Veo 3.1 generates 8-second video clips, so we batch consecutive scenes that total ≤8 seconds and generate cohesive video prompts for each batch.

## Implementation Details

### 1. Core Batching Logic

**File:** `core/video/storyboard_v2.py`

#### `_batch_scenes_for_veo(scenes, max_duration=8.0)`
Groups consecutive scenes into batches that fit within the 8-second limit.

**Example:**
```python
# Input scenes with durations: [2.5, 2.5, 4, 4, 2.5, 2.5, 2.5, 2.5]
# Output batches:
# Batch 0: scenes [0, 1] = 5.0s
# Batch 1: scenes [2, 3] = 8.0s
# Batch 2: scenes [4, 5, 6] = 7.5s
# Batch 3: scene [7] = 2.5s
```

#### `_generate_veo_batches(scenes, lyrics, title, style, provider, model)`
Makes a single batched LLM call to generate unified video prompts for each batch.

**Key features:**
- Creates cohesive prompts that describe the scene evolution over the full batch duration
- Includes natural transitions between lyric moments
- Maintains visual continuity with the overall theme
- Returns array of batch objects with `video_prompt` field

### 2. Storyboard Generation

**File:** `core/video/storyboard_v2.py:206`

#### `generate_storyboard(..., render_method=None)`
Modified to accept `render_method` parameter. When `render_method` contains "veo" and "3.1":
1. Generates individual scene-by-scene storyboard (existing behavior)
2. **Additionally** generates batched prompts via `_generate_veo_batches()`
3. Returns tuple: `(StyleGuide, List[Scene], Optional[List[VeoBatch]])`

**Contract:**
```python
VeoBatch = {
    'batch_id': int,
    'scene_ids': List[int],      # Which scenes are in this batch
    'duration': float,            # Total duration (e.g., 5.0, 7.5, 8.0)
    'video_prompt': str,          # Unified prompt for the entire batch
    'reasoning': str              # Why these scenes work together
}
```

### 3. Project Data Model

**File:** `core/video/project.py:501`

#### Added field: `veo_batches`
```python
@dataclass
class VideoProject:
    # ... existing fields ...

    # Veo 3.1 batched prompts (for 8-second clip generation)
    veo_batches: Optional[List[Dict[str, Any]]] = None
```

#### Helper method: `get_veo_batch_for_scene(scene_index)`
Returns the batch containing a specific scene, or None if no batched prompt available.

**Usage:**
```python
# Get batched prompt for scene 3
batch = project.get_veo_batch_for_scene(3)
if batch:
    video_prompt = batch['video_prompt']  # Use this instead of scene.prompt
    duration = batch['duration']
    scene_ids = batch['scene_ids']  # All scenes in this batch
```

### 4. GUI Integration

**File:** `gui/video/workspace_widget.py:1800-1831`

#### Enhanced Storyboard Generation
- Detects video provider and model from UI (`video_provider_combo`, `veo_model_combo`)
- Passes `render_method` to storyboard generator when Veo 3.1 is selected
- Stores `veo_batches` in project after generation
- Logs batch information to console

**Flow:**
1. User selects "Gemini Veo" and "veo-3.1-generate-001" in GUI
2. Clicks "Generate Storyboard"
3. System generates both individual scenes AND batched prompts
4. Both are saved to project file

## Usage Example

### Generating Storyboard with Batching

```python
from core.video.storyboard_v2 import EnhancedStoryboardGenerator
from core.video.prompt_engine import UnifiedLLMProvider

# Initialize
config = {'google_api_key': 'your-key'}
llm = UnifiedLLMProvider(config)
generator = EnhancedStoryboardGenerator(llm)

# Generate with batching enabled
style_guide, scenes, veo_batches = generator.generate_storyboard(
    lyrics="[Verse]\nIn the morning light\nI see your face...",
    title="My Song",
    duration=120,
    provider="gemini",
    model="gemini-2.5-pro",
    style="cinematic, high quality",
    negatives="low quality, blurry",
    render_method="veo-3.1-generate-001"  # Triggers batching
)

# Check results
print(f"Generated {len(scenes)} individual scenes")
if veo_batches:
    print(f"Generated {len(veo_batches)} batched prompts")
    for batch in veo_batches:
        print(f"Batch {batch['batch_id']}: scenes {batch['scene_ids']} ({batch['duration']:.1f}s)")
        print(f"  Prompt: {batch['video_prompt']}")
```

### Using Batched Prompts for Video Generation

```python
# When generating video for a scene
scene_index = 3
batch = project.get_veo_batch_for_scene(scene_index)

if batch and project.video_model == "veo-3.1-generate-001":
    # Use the unified batch prompt
    video_prompt = batch['video_prompt']
    duration = batch['duration']

    # Generate video using batched prompt
    # (This will produce an 8-second clip that can be trimmed to actual duration)
    veo_client.generate_video(
        prompt=video_prompt,
        duration=8.0  # Veo 3.1 generates 8s clips
    )
else:
    # Fall back to individual scene prompt
    video_prompt = scene.video_prompt or scene.prompt
    veo_client.generate_video(
        prompt=video_prompt,
        duration=scene.duration_sec
    )
```

## Benefits

1. **Better Continuity**: Unified prompts describe scene evolution, not discrete moments
2. **Temporal Context**: LLM describes how scenes flow over 5-8 seconds
3. **Visual Coherence**: Single prompt avoids conflicting visual directions
4. **Optimal for Veo 3.1**: Leverages the 8-second clip generation capability

## Testing

**File:** `test_veo_batching.py`

Run tests:
```bash
python3 test_veo_batching.py
```

Tests verify:
- ✅ Batching logic groups scenes correctly
- ✅ Project serialization saves/loads veo_batches
- ✅ Batch lookup finds correct batch for each scene

## Future Enhancements

1. **Video Generation Integration**: Update VeoClient to use batched prompts when available
2. **Batch Editing**: UI to view and edit batched prompts separately
3. **Smart Batching**: Consider scene content/transitions when batching, not just duration
4. **Preview**: Show which scenes are batched together in the UI
5. **Regenerate Batches**: Option to regenerate batched prompts without regenerating scenes

## File Changes Summary

| File | Changes |
|------|---------|
| `core/video/storyboard_v2.py` | Added `_batch_scenes_for_veo()`, `_generate_veo_batches()`, modified `generate_storyboard()` |
| `core/video/project.py` | Added `veo_batches` field, `get_veo_batch_for_scene()` method, serialization |
| `gui/video/workspace_widget.py` | Detect render method, pass to generator, store batches in project |
| `test_veo_batching.py` | **New file** - Unit tests for batching functionality |

## LLM Prompt Design

The batched prompt generation uses a carefully designed LLM prompt that:
- Emphasizes creating **one flowing scene** not discrete moments
- Includes lyric timing information for each segment
- Requests specific camera movement, lighting, and atmosphere details
- Outputs structured JSON with `video_prompt` and `reasoning` fields
- Maintains consistency with overall song theme and visual style

Example output:
```json
{
  "combined_prompts": [
    {
      "batch_id": 0,
      "scene_ids": [0, 1],
      "duration": 5.0,
      "video_prompt": "A dancer spins gracefully in a sunlit studio, her movements flowing from slow deliberate twirls into energetic leaps as the music intensifies. The camera orbits around her, capturing the evolution from contemplative stillness to explosive motion. Warm golden hour lighting streams through tall windows, casting dynamic shadows that dance across the wooden floor.",
      "reasoning": "These two lyric moments describe a progression from stillness to movement, unified by the dancer's continuous performance"
    }
  ]
}
```

## Notes

- The LLM call for batched prompts is **separate** from individual scene generation
- Both individual and batched prompts are preserved in the project
- Batching is **optional** - only triggered when `render_method` contains "veo" and "3.1"
- The implementation supports any batch duration limit (default 8.0s for Veo 3.1)
