# Scene Batching Implementation

**Last Updated:** 2025-10-21

## Problem Statement

The original storyboard generator created **one scene per lyric line**, resulting in:
- Many short scenes (often 3 seconds each when lyrics were evenly distributed)
- Poor compatibility with video generators like Veo 3.1 (which work best with ~8 second clips)
- Excessive scene transitions
- Suboptimal visual storytelling (too fragmented)

**Example Before:**
```
Input: 12 lyric lines, 120 seconds total
Output: 12 scenes × 10 seconds each
Problem: Not optimal for 8-second video generation
```

If lyrics were short or numerous:
```
Input: 40 lyric lines, 120 seconds total
Output: 40 scenes × 3 seconds each
Problem: Way too many short scenes!
```

## Solution

Implemented **intelligent scene batching** that combines consecutive lyric lines into optimal-duration scenes (~8 seconds) while respecting:
1. **Section boundaries** - Don't combine across Verse/Chorus/Bridge transitions
2. **Duration targets** - Aim for ~8 seconds per scene (130% max = 10.4 seconds)
3. **Lyric coherence** - Keep related lines together

## Implementation Details

### File: `core/video/storyboard.py`

#### 1. Added Target Duration Parameter

```python
class StoryboardGenerator:
    def __init__(self, parser=None, timing=None, target_scene_duration=8.0):
        ...
        self.target_scene_duration = target_scene_duration  # Default 8.0 for Veo 3.1
```

#### 2. New Method: `_batch_scenes_for_optimal_duration()`

**Location:** Lines 441-514

**Algorithm:**
```
1. Initialize empty batch
2. For each scene:
   a. Check if adding it would exceed target * 1.3 (10.4s for 8s target)
   b. Check if section changed (Verse → Chorus, etc.)
   c. If would_exceed OR section_changed:
      - Finalize current batch
      - Start new batch with current scene
   d. Else:
      - Add scene to current batch
3. Finalize last batch
4. Return batched scenes
```

**Key Features:**
- **Greedy batching:** Accumulates scenes until reaching ~8 seconds
- **30% tolerance:** Allows up to 10.4 seconds to avoid many tiny scenes
- **Section awareness:** Detects section changes via `scene.metadata['section']`
- **Comprehensive logging:** Tracks batching decisions and statistics

#### 3. New Method: `_merge_scenes()`

**Location:** Lines 516-551

**Functionality:**
- Combines multiple Scene objects into one
- Joins source text with newlines
- Sums durations
- Preserves metadata from first scene
- Adds batching metadata:
  - `batched_count`: Number of scenes merged
  - `original_scene_ids`: IDs of original scenes

#### 4. Integration Point

**Location:** Line 625 in `generate_scenes()`

```python
# After MIDI sync, before returning
scenes = self._batch_scenes_for_optimal_duration(scenes)
return scenes
```

## Example Output

### Before Batching:
```
Generated 12 content scenes, total duration: 120.0 seconds
Scene 1: "When the night feels endless" - 10.0s
Scene 2: "I shuffle numbers like cards" - 10.0s
Scene 3: "I hum a rhythm, let the numbers dance" - 10.0s
...
```

### After Batching:
```
Batching 12 scenes to aim for ~8.0s per scene
Batched 3 scenes → 10.0s
Batched 3 scenes → 10.0s
...
Batched 12 scenes into 4 combined scenes
Scene durations - Avg: 8.5s, Min: 7.5s, Max: 10.0s (target: 8.0s)

Scene 1:
"When the night feels endless
I shuffle numbers like cards
I hum a rhythm, let the numbers dance"
Duration: 10.0s
```

## Algorithm Analysis

### Time Complexity
- **O(n)** where n = number of scenes
- Single pass through all scenes

### Space Complexity
- **O(n)** for storing batched scenes

### Edge Cases Handled

1. **Empty input:** Returns empty list
2. **Single scene:** Returns as-is
3. **All short scenes:** Batches multiple together
4. **Section boundaries:** Creates new batch at section changes
5. **Last scene leftover:** Finalizes even if below target

## Batching Logic Examples

### Example 1: Even Distribution
```
Input: 12 scenes × 3s = 36s total
Target: 8s per scene (max 10.4s)

Iteration 1: Add scene 1 (3s) → batch = 3s
Iteration 2: Add scene 2 (6s) → batch = 6s
Iteration 3: Add scene 3 (9s) → batch = 9s
Iteration 4: 9s + 3s = 12s > 10.4s → FINALIZE batch (9s), start new
...
Output: ~4 scenes averaging 9s each
```

### Example 2: Section Boundaries
```
Input:
  [Verse] 3 scenes × 3s = 9s
  [Chorus] 3 scenes × 3s = 9s

Batching:
  - Batch verse scenes: 9s (all 3 combined)
  - Section change detected at Chorus
  - Start new batch for Chorus: 9s (all 3 combined)

Output: 2 scenes (Verse=9s, Chorus=9s)
```

### Example 3: Variable Durations
```
Input: Scenes of 2s, 5s, 4s, 3s, 6s, 2s
Target: 8s (max 10.4s)

Batch 1: 2s + 5s = 7s → add 4s? 11s > 10.4s → NO → Finalize (7s)
Batch 2: 4s + 3s = 7s → add 6s? 13s > 10.4s → NO → Finalize (7s)
Batch 3: 6s + 2s = 8s → Finalize (8s)

Output: 3 scenes (7s, 7s, 8s)
```

## Configuration

### Adjusting Target Duration

Change the target scene duration when creating the generator:

```python
# For different video platforms
generator = StoryboardGenerator(target_scene_duration=5.0)  # 5-second scenes
generator = StoryboardGenerator(target_scene_duration=10.0)  # 10-second scenes
generator = StoryboardGenerator()  # Default: 8.0 seconds
```

### Adjusting Tolerance

To modify the 130% tolerance (currently hardcoded):

**Location:** Line 469 in `storyboard.py`
```python
would_exceed = current_duration + scene_duration > self.target_scene_duration * 1.3
#                                                                            ^^^^
# Change 1.3 to adjust tolerance (1.0 = strict, 1.5 = very lenient)
```

## Benefits

1. **Better for Video Generation:**
   - Scenes are ~8 seconds (optimal for Veo 3.1)
   - Fewer scene transitions
   - More coherent visual storytelling

2. **Reduced API Costs:**
   - Fewer image/video generation calls
   - Each call generates more meaningful content

3. **Improved User Experience:**
   - Cleaner storyboard table
   - Easier to review and edit
   - More natural scene flow

4. **Maintains Flexibility:**
   - Configurable target duration
   - Respects musical structure (sections)
   - Preserves original timing information in metadata

## Testing

### Manual Test Cases

1. **Short lyrics (many lines):**
   - 40 lines × 3s each
   - Should batch into ~15 scenes of ~8s each

2. **Long lyrics (few lines):**
   - 5 lines × 24s each
   - Should keep as-is (already long enough)

3. **Section boundaries:**
   - Verse (4 lines) + Chorus (3 lines)
   - Should create 2 batches (Verse batch, Chorus batch)

4. **Mixed durations:**
   - Varying line lengths
   - Should create balanced batches close to target

### Log Output Verification

Check `imageai_current.log` for:
```
Batching 40 scenes to aim for ~8.0s per scene
Batched 3 scenes → 9.0s (reason: exceed)
Batched 2 scenes → 7.5s (reason: section change)
...
Batched 40 scenes into 15 combined scenes
Scene durations - Avg: 8.0s, Min: 6.5s, Max: 10.0s (target: 8.0s)
```

## Future Enhancements

1. **Look-ahead optimization:** Instead of greedy batching, look ahead to distribute scenes more evenly
2. **User control:** Add UI option to enable/disable batching
3. **Smart splitting:** If a single scene is > 8s, consider splitting it
4. **Lyric-aware batching:** Use NLP to detect natural breaks (sentences, phrases)
5. **Dynamic targets:** Adjust target based on total duration (longer songs = longer scenes)

## Related Documentation

- `Veo-3.1-Batching-Implementation.md` - Frame-accurate timing for Veo prompts
- `LLM-Logging-Full-Content.md` - Full LLM interaction logging
- `CodeMap.md:storyboard.py` - Complete code navigation
