# Veo 3 Duration Update Summary

## Changes Implemented (2025-10-24)

### Background
Google Veo 3.0 and 3.1 now **ONLY support 8-second video generation** (no longer 4s or 6s options). All scenes must be batched to exactly 8 seconds, with short scenes represented as brief moments within the 8-second timeline.

### Code Changes

#### 1. **Veo Client Updates** (`core/video/veo_client.py`)
- Updated `VeoGenerationConfig.__post_init__()` to enforce 8-second only for Veo 3.0 and 3.1
- Added `fixed_duration: 8` to MODEL_CONSTRAINTS for Veo 3.0 and 3.1
- Veo 3 Fast still supports 4s, 6s, 8s durations

```python
if self.model in [VeoModel.VEO_3_GENERATE, VeoModel.VEO_3_1_GENERATE]:
    if self.duration != 8:
        raise ValueError(
            f"Veo 3.0 and 3.1 now ONLY support 8-second clips, got {self.duration}. "
            f"All scenes must be batched to exactly 8 seconds."
        )
```

#### 2. **Video Prompt Generator Updates** (`core/video/video_prompt_generator.py`)

##### Duration Formatting
All prompts now include explicit duration information with descriptors:
- **< 0.5s**: "ultra-brief moment" / "ultra-brief flash"
- **0.5-1s**: "brief moment"
- **1-2s**: "quick moment"
- **≥ 2s**: Standard duration

##### System Prompts Updated
All three system prompts now emphasize:
- Explicit time markers (e.g., "0-2s:", "2-2.5s:", "2.5-8s:")
- Special descriptors for short durations
- 8-second Veo generation constraint
- Format examples for batched scenes

##### User Prompt Enhancements
- Added duration string formatting based on scene length
- Included "Note: This will be part of an 8-second Veo generation"
- Enhanced timing breakdown with descriptors for short segments
- Added guidance for ultra-brief moments

#### 3. **Batch Generation Updates**
- Each scene in batch now shows duration with appropriate descriptor
- Timing breakdowns include [ultra-brief] / [brief] tags
- All batches noted as "Part of 8-second Veo generation"

### Example Output

#### For 0.2-second Scene
```
Duration: 0.2 seconds (ultra-brief moment)
Note: This will be part of an 8-second Veo generation

Timing breakdown (within 8-second Veo clip):
  6.0-6.2s: "and I'm wide awake" [ultra-brief flash]
```

#### Generated Video Prompt Format
```
0-6s: Character at desk, tapping pencil rhythmically
6-6.2s: Ultra-brief flash - eyes widen slightly
6.2-8s: Returns to tapping with renewed focus
```

### Testing

Created `test_veo_duration_prompts.py` to verify:
- ✅ Veo 3.0/3.1 reject non-8-second durations
- ✅ Veo 3 Fast still accepts 4s, 6s, 8s
- ✅ Duration descriptors properly formatted
- ✅ Time markers included for batched scenes

### Impact on Your Project

Your 0.2-second Scene 2 will now:
1. **Always be batched** with adjacent scenes to reach 8 seconds
2. **Include precise time marker** (e.g., "6.0-6.2s")
3. **Use appropriate descriptor** ("ultra-brief flash" or "brief moment")
4. **Be clearly marked** as part of an 8-second Veo generation

### Best Practices

1. **All scenes < 8s** must be batched for Veo 3.0/3.1
2. **Use precise timing** for sub-second scenes (0.1s precision)
3. **Include descriptors** to guide visual interpretation
4. **Emphasize transitions** between brief and normal segments

### Files Modified
- `core/video/veo_client.py` - Duration validation and constraints
- `core/video/video_prompt_generator.py` - Prompt formatting with time markers
- `Docs/Short-Scene-Duration-Handling.md` - Updated documentation
- `Docs/Veo-3.1-Batching-Implementation.md` - Clarified 8-second requirement

### Files Created
- `test_veo_duration_prompts.py` - Test script for validation
- `Docs/Veo3-Duration-Update-Summary.md` - This summary

## Conclusion

The system now properly handles Veo 3's 8-second-only constraint and ensures that very short scenes (like 0.2s) are represented with appropriate time markers and descriptors within the 8-second generation window.