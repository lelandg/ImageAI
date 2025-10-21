# Frame-Accurate Video Prompt Transitions

**Last Updated:** 2025-10-21

## Overview

Video prompts now include **explicit time markers** for transitions between lyric lines within batched scenes, enabling frame-accurate visual storytelling that matches the temporal structure of the music.

## Problem Solved

### Before:
**Scene 1 (8 seconds, 4 batched lyric lines):**
```
Video Prompt: "Camera dollies toward figure at desk, indigo city glowing through window..."
```

❌ **Issues:**
- No temporal structure
- Doesn't specify WHEN things happen
- All 4 lyric lines lumped together
- No guidance on transitions between lyrics

### After:
**Scene 1 (8 seconds, 4 batched lyric lines with timing):**
```
Video Prompt: "0-3s: Camera starts at low angle on lone figure staring into endless night
through window. 3-5s: Camera dollies in as hands begin shuffling numbers like playing cards.
5-7s: Hands move in rhythmic patterns, numbers dancing across desk surface. 7-8s: Expression
shifts from concentration to wonder as difficulty melts away."
```

✅ **Improvements:**
- Explicit time markers (0-3s, 3-5s, 5-7s, 7-8s)
- Each lyric line gets its visual moment
- Smooth transitions at exact timestamps
- Frame-accurate storytelling (24 FPS = 0.042s per frame)

---

## How It Works

### 1. Scene Batching Stores Timing

**File:** `core/video/storyboard.py:538-550`

When lyrics are batched, `_merge_scenes()` now calculates and stores timing for each line:

```python
lyric_timings = []
cumulative_time = 0.0
for scene in scenes:
    start_time = cumulative_time
    end_time = cumulative_time + scene.duration_sec
    lyric_timings.append({
        'text': scene.source,
        'start_sec': round(start_time, 1),
        'end_sec': round(end_time, 1),
        'duration_sec': round(scene.duration_sec, 1)
    })
    cumulative_time = end_time

merged_scene.metadata['lyric_timings'] = lyric_timings
```

**Example Output:**
```python
scene.metadata['lyric_timings'] = [
    {'text': 'When the night feels endless...', 'start_sec': 0.0, 'end_sec': 3.0, 'duration_sec': 3.0},
    {'text': 'I shuffle numbers like cards', 'start_sec': 3.0, 'end_sec': 5.0, 'duration_sec': 2.0},
    {'text': 'I hum a rhythm...', 'start_sec': 5.0, 'end_sec': 7.0, 'duration_sec': 2.0},
    {'text': 'And suddenly it\'s not so hard', 'start_sec': 7.0, 'end_sec': 8.0, 'duration_sec': 1.0}
]
```

### 2. Timing Data Passed to LLM

**File:** `gui/video/video_project_tab.py:214-233`

```python
# Collect lyric timings for frame-accurate transitions
lyric_timings = [scene.metadata.get('lyric_timings') for scene in self.project.scenes]
scene_durations = [scene.duration_sec for scene in self.project.scenes]

video_prompts = llm.batch_enhance_for_video(
    base_texts,
    provider=llm_provider,
    model=llm_model,
    style=style,
    temperature=0.7,
    console_callback=None,
    source_lyrics=source_lyrics,
    lyric_timings=lyric_timings,  # ✅ Frame-accurate timing
    scene_durations=scene_durations
)
```

### 3. Enhanced LLM Prompt with Timeline

**File:** `core/video/prompt_engine.py:636-671`

The LLM receives a detailed timeline:

```
FRAME-ACCURATE TIMING (Veo 3 generates at 24 FPS):

1. SCENE DURATION: 8.0s
   IMAGE DESCRIPTION: A lone figure sits at a desk under warm lamplight...
   LYRIC TIMELINE (describe visual evolution matching these timestamps):
     • 0.0s-3.0s (3.0s): "When the night feels endless and I'm wide awake"
     • 3.0s-5.0s (2.0s): "I shuffle numbers like cards"
     • 5.0s-7.0s (2.0s): "I hum a rhythm, let the numbers dance"
     • 7.0s-8.0s (1.0s): "And suddenly it's not so hard"

Return numbered video prompts with:
- For batched scenes: Use explicit time markers (e.g., "0-3s: ..., 3-5s: ..., 5-8s: ...")
  to describe visual evolution that matches the lyric timeline
- Describe smooth transitions between lyric moments at their exact timestamps
- NO cuts, NO scene changes - describe ONE continuous camera movement with evolving action
```

### 4. LLM Generates Time-Aware Prompts

The LLM responds with temporally structured descriptions:

```
1. 0-3s: Camera begins at a low angle on lone figure gazing through window at endless
night, city lights twinkling in the distance. 3-5s: Camera smoothly dollies forward as
figure's hands reach for scattered numbers, shuffling them like playing cards across the
desk surface. 5-7s: Hands move in deliberate rhythmic patterns, numbers seeming to dance
and float between fingers as subject hums softly. 7-8s: Camera pushes in on subject's face
as expression shifts from furrowed concentration to gentle wonder, difficulty dissolving.
```

---

## Benefits

### 1. **Frame-Accurate Synchronization**
- Veo 3 renders at 24 FPS
- Time markers ensure visuals sync with lyrics at sub-second precision
- Example: At 3.0s exactly, the action transitions from "endless night" to "shuffling numbers"

### 2. **Natural Temporal Flow**
- Each lyric gets its visual moment
- Transitions happen at musically meaningful points
- Maintains single-shot continuity (no cuts)

### 3. **Richer Storytelling**
- 4 lyric lines = 4 distinct visual beats
- Camera and subject evolve together
- Emotional arc unfolds across the timeline

### 4. **Better for Music Videos**
- Visuals match lyrical pacing
- Important words get emphasis at their timestamp
- Creates cinematic progression within each scene

---

## Example Scenarios

### Scenario 1: Fast Chorus (Multiple Quick Lines)

**Input:**
```
Lyric Timeline:
  • 0-2s: "I'm doin' math"
  • 2-4s: "I do math"
  • 4-6s: "I do math"
  • 6-8s: "I'm tap-tap-tappin' in my head"
```

**LLM Output:**
```
0-2s: Close-up of hands tapping numbers on desk in rhythm. 2-4s: Camera pulls back
revealing subject's focused expression as hands continue rhythmic tapping. 4-6s: Wider
shot shows full workspace, numbers scattered everywhere, hands still moving to the beat.
6-8s: Camera slowly dollies around subject's head as finger tapping intensifies on temple,
lost in mathematical rhythm.
```

### Scenario 2: Slow Verse (Longer Lines)

**Input:**
```
Lyric Timeline:
  • 0-4s: "Square a little laughter, divide it into time"
  • 4-8s: "Juggle all the fractions 'til the music swings"
```

**LLM Output:**
```
0-4s: Camera starts on subject's smiling face as hands sketch mathematical symbols in
the air, fingers tracing squares and division signs that seem to shimmer with warmth.
4-8s: Camera slowly circles as hands begin juggling invisible fractions, movements becoming
more fluid and dance-like as jazz music manifests in the swaying motion.
```

### Scenario 3: Single Line (No Batching)

**Input:**
```
LYRICS: "Let geometry and jazz give me wings"
(No timing breakdown - single 4s scene)
```

**LLM Output:**
```
Camera starts low and sweeps upward as subject rises from chair, arms spreading wide
with geometric shapes and musical notes swirling around them, creating the illusion of
wings lifting them into creative flight.
```

---

## Technical Details

### Frame Rate Math
- **Veo 3/3.1:** 24 FPS (frames per second)
- **1 second:** 24 frames
- **0.1 second precision:** ~2.4 frames
- **Example:** Transition at 3.0s = frame 72

### Timestamp Rounding
All timestamps rounded to 1 decimal place (0.1s precision) for:
- Clean log output
- LLM readability
- Sufficient precision (2-3 frames at 24 FPS)

### Metadata Structure
```python
scene.metadata = {
    'batched_count': 4,  # Number of original scenes merged
    'original_scene_ids': [0, 1, 2, 3],  # Original scene IDs
    'lyric_timings': [  # ✅ NEW: Frame-accurate timing
        {'text': '...', 'start_sec': 0.0, 'end_sec': 3.0, 'duration_sec': 3.0},
        {'text': '...', 'start_sec': 3.0, 'end_sec': 5.0, 'duration_sec': 2.0},
        ...
    ]
}
```

---

## Testing

### Verify Timing Storage

1. Generate storyboard (scenes will be batched)
2. Check log for:
```
Batched 3 scenes → 9.0s
```

3. Open project file (`imageai_current_project.json`)
4. Find a batched scene and check:
```json
"metadata": {
  "batched_count": 3,
  "lyric_timings": [
    {"text": "...", "start_sec": 0.0, "end_sec": 3.0, "duration_sec": 3.0},
    {"text": "...", "start_sec": 3.0, "end_sec": 6.0, "duration_sec": 3.0},
    {"text": "...", "start_sec": 6.0, "end_sec": 9.0, "duration_sec": 3.0}
  ]
}
```

### Verify LLM Receives Timing

1. Generate video prompts
2. Check `imageai_current.log` for:
```
=== VIDEO PROMPT ENHANCEMENT REQUEST ===
FRAME-ACCURATE TIMING (Veo 3 generates at 24 FPS):

1. SCENE DURATION: 8.0s
   IMAGE DESCRIPTION: ...
   LYRIC TIMELINE (describe visual evolution matching these timestamps):
     • 0.0s-3.0s (3.0s): "When the night feels endless..."
     • 3.0s-5.0s (2.0s): "I shuffle numbers like cards"
     ...
```

### Verify LLM Output

Check the video_prompt column in the storyboard table for time markers:
```
0-3s: ... 3-5s: ... 5-7s: ... 7-8s: ...
```

---

## Files Modified

1. **`core/video/storyboard.py`**
   - Line 538-550: Calculate and store lyric timings in `_merge_scenes()`
   - Line 564: Add `lyric_timings` to merged scene metadata

2. **`gui/video/video_project_tab.py`**
   - Lines 214-218: Collect timing data from scenes
   - Lines 232-233: Pass timing data to enhancement function

3. **`core/video/prompt_engine.py`**
   - Lines 583-584: Add timing parameters to function signature
   - Lines 636-671: Enhanced prompt with frame-accurate timeline
   - Lines 666-669: Instructions for time-aware prompts

---

## Related Documentation

- `Scene-Batching-Implementation.md` - How lyrics are combined into scenes
- `Video-Prompt-Lyrics-Context-Fix.md` - Adding full lyric context
- `Veo-3.1-Batching-Implementation.md` - Veo-specific timing considerations
- `LLM-Logging-Full-Content.md` - Full LLM interaction logging
