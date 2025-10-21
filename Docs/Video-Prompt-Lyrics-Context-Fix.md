# Video Prompt Lyrics Context Fix

**Last Updated:** 2025-10-21

## Problem Statement

When generating video prompts with "Generate Video Prompts" button, the LLM was only receiving the **enhanced image description** and NOT the **actual batched lyrics** that the scene visualizes.

### Example Problem:

**Scene 1 Source (Batched Lyrics):**
```
When the night feels endless and I'm wide awake
I shuffle numbers like cards
I hum a rhythm, let the numbers dance
And suddenly it's not so hard
```

**What LLM Received (Before Fix):**
```
1. A lone figure sits at a desk under warm lamplight, with indigo city glowing through the window...
```

**What LLM Generated:**
```
The camera begins at a low angle, slowly dollying toward the lone figure...
```

**Problem:** The video prompt describes the visual scene BUT doesn't reference all the lyrics! It only uses partial context from the first line.

---

## Root Cause Analysis

### Issue 1: No Logging
The `batch_enhance_for_video` function in `core/video/prompt_engine.py` did NOT log:
- The full prompt sent to LLM
- The full response received from LLM

This made debugging impossible.

### Issue 2: Missing Lyrics Context
At `gui/video/video_project_tab.py:208`, the code passed only:
- `scene.prompt` (enhanced image description)

But NOT:
- `scene.source` (the actual batched lyrics)

So the LLM had NO CONTEXT about what lyrics each scene was supposed to visualize.

---

## Solution

### 1. Added Full Logging

**File:** `core/video/prompt_engine.py:676-693`

Added comprehensive logging before and after the LLM call:

```python
# Log the full request
self.logger.info("=== VIDEO PROMPT ENHANCEMENT REQUEST ===")
self.logger.info(f"System prompt (FULL, {len(system_prompt)} chars):")
self.logger.info(system_prompt)
self.logger.info(f"User prompt (FULL, {len(batch_prompt)} chars):")
self.logger.info(batch_prompt)
self.logger.info("=== END VIDEO PROMPT REQUEST ===")

response = self.litellm.completion(**kwargs)

# Parse the response
enhanced_text = response.choices[0].message.content.strip()

# Log the full response
self.logger.info("=== VIDEO PROMPT ENHANCEMENT RESPONSE ===")
self.logger.info(f"Response (FULL, {len(enhanced_text)} chars):")
self.logger.info(enhanced_text)
self.logger.info("=== END VIDEO PROMPT RESPONSE ===")
```

### 2. Added `source_lyrics` Parameter

**File:** `core/video/prompt_engine.py:582`

Updated function signature:

```python
def batch_enhance_for_video(self,
                            texts: List[str],
                            provider: str,
                            model: str,
                            style: PromptStyle = PromptStyle.CINEMATIC,
                            temperature: float = 0.7,
                            console_callback=None,
                            source_lyrics: Optional[List[str]] = None) -> List[str]:
```

### 3. Enhanced Prompt with Lyrics Context

**File:** `core/video/prompt_engine.py:631-649`

**Before:**
```python
batch_prompt = f"""Transform these {len(texts)} image descriptions...

Image descriptions:
1. A lone figure sits at a desk...
2. Character shuffles cards...
```

**After:**
```python
batch_prompt = f"""Transform these {len(texts)} image descriptions...

LYRICS CONTEXT (what this scene visualizes):

1. LYRICS: When the night feels endless and I'm wide awake
   I shuffle numbers like cards
   I hum a rhythm, let the numbers dance
   And suddenly it's not so hard
   IMAGE DESCRIPTION: A lone figure sits at a desk under warm lamplight...

2. LYRICS: I'm doin' math, I do math, I do math
   I'm tap-tap-tappin' in my head
   IMAGE DESCRIPTION: Character shuffles cards with rhythmic hand movements...
```

Now the LLM sees:
- ✅ The full batched lyrics for each scene
- ✅ The enhanced image description
- ✅ Clear instruction to incorporate lyric meaning

### 4. Updated Caller to Pass Lyrics

**File:** `gui/video/video_project_tab.py:211-225`

```python
# Collect source lyrics for context (helps LLM understand what each scene visualizes)
source_lyrics = [scene.source for scene in self.project.scenes]

video_prompts = llm.batch_enhance_for_video(
    base_texts,
    provider=llm_provider,
    model=llm_model,
    style=style,
    temperature=0.7,
    console_callback=None,
    source_lyrics=source_lyrics  # Provide lyric context ✅
)
```

---

## Result

### Before Fix:

**Video Prompt for Scene 1:**
```
The camera begins at a low angle, slowly dollying toward the lone figure at the desk
while panning upward slightly to reveal the indigo city gleaming through the window.
```

**Issue:** Only references "lone figure" and "desk" - doesn't mention:
- Numbers/cards
- Rhythm/dance
- Mathematical concepts
- The emotional progression through the lyrics

### After Fix:

**Video Prompt for Scene 1 (Expected):**
```
The camera begins at a low angle, slowly dollying toward the lone figure at the desk
as they shuffle numbers like playing cards. The subject's hands move in rhythmic
patterns, letting the numbers dance across the surface. As the camera pans upward to
reveal the indigo city, the subject's expression shifts from frustration to wonder,
showing how suddenly it's not so hard when numbers become playful companions in the
endless night.
```

**Improvement:** Now includes:
- ✅ "shuffle numbers like cards" (lyric 2)
- ✅ "rhythmic patterns" / "numbers dance" (lyric 3)
- ✅ Emotional transition "not so hard" (lyric 4)
- ✅ "endless night" context (lyric 1)

---

## Testing

### Verify the Fix Works:

1. **Generate storyboard** with batched lyrics
2. Click **"Generate Video Prompts"**
3. Check `imageai_current.log` for:

```
=== VIDEO PROMPT ENHANCEMENT REQUEST ===
System prompt (FULL, ... chars):
...
User prompt (FULL, ... chars):
LYRICS CONTEXT (what this scene visualizes):

1. LYRICS: When the night feels endless and I'm wide awake
   I shuffle numbers like cards
   I hum a rhythm, let the numbers dance
   And suddenly it's not so hard
   IMAGE DESCRIPTION: A lone figure sits at a desk...

=== END VIDEO PROMPT REQUEST ===
```

4. Check the **video_prompt** column in storyboard table
5. Verify prompts now reference ALL the batched lyrics, not just the first line

---

## Benefits

1. **Full Lyric Coverage:** Video prompts now incorporate ALL lyrics in each batched scene
2. **Better Visual Storytelling:** LLM understands the narrative arc across multiple lyric lines
3. **Complete Logging:** Can now debug exactly what's sent to/received from LLM
4. **Transparency:** Users can see full LLM interactions in log file

---

## Files Changed

1. **`core/video/prompt_engine.py`**
   - Line 582: Added `source_lyrics` parameter
   - Lines 631-649: Enhanced prompt construction with lyrics context
   - Lines 676-693: Added full request/response logging

2. **`gui/video/video_project_tab.py`**
   - Line 212: Collect source lyrics from scenes
   - Line 225: Pass `source_lyrics` to enhancement function

---

## Related Documentation

- `Scene-Batching-Implementation.md` - How lyrics are combined into batched scenes
- `LLM-Logging-Full-Content.md` - Full LLM interaction logging
- `Veo-3.1-Batching-Implementation.md` - Frame-accurate timing for Veo
