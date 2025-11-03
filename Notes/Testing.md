# Testing Guide - Video Storyboard & Performance Fixes

*Last Updated: 2025-11-02*

This document tracks all features and fixes that need testing from the November 2, 2025 development session.

---

## 🎬 Video Prompt Generation Fixes

### 1️⃣ Gemini + LiteLLM None Response Bug Fix

**What Was Fixed:**
- Gemini 2.5 Pro via LiteLLM was returning `None` content instead of actual prompts
- Known bug: https://github.com/BerriAI/litellm/issues/10721
- Added None checks, finish_reason logging, and increased token limits

**Files Modified:**
- `core/video/video_prompt_generator.py:300-353` (individual generation)
- `core/video/video_prompt_generator.py:498-583` (batch generation)

**How to Test:**

1. **Open Video Project tab**
2. **Load lyrics and MIDI:**
   - Click "Load MIDI File"
   - Click "Extract Lyrics" button
3. **Set LLM provider to Gemini:**
   - LLM Provider: `Google`
   - LLM Model: `gemini-2.5-pro`
   - Temperature: `0.7`
4. **Generate Storyboard:**
   - Click "Generate Storyboard" button
   - Watch status console for logs
5. **Check the log file** (`imageai_current.log`)

**Expected Results:**
✅ Should see in logs:
```
Batch generating 23 video prompts with google/gemini-2.5-pro
Batch LLM Response (finish_reason=stop, 6912 chars):
```

✅ All 23 video prompts should be generated successfully

✅ No crashes with `'NoneType' object has no attribute 'strip'`

❌ If content is still None:
```
❌ LLM returned None content (finish_reason: MAX_TOKENS)
Falling back to individual generation
```

**Known Issues:**
- Gemini 2.5 Pro + LiteLLM still has intermittent None responses
- If this happens, try Claude/Anthropic instead: `claude-3-5-sonnet-20241022`

---

### 2️⃣ Gemini Multi-Segment Timing Fix

**What Was Fixed:**
- Gemini was generating ONE time marker for multi-segment scenes (e.g., `0-0.4s`)
- GPT generates MULTIPLE markers (e.g., `0-0.1s: ..., 0.1-0.3s: ..., 0.3-0.4s: ...`)
- Root cause: GPT is better at implicit multi-step instructions; Gemini needs explicit rules

**Files Modified:**
- `core/video/video_prompt_generator.py:219-231` (individual prompts)
- `core/video/video_prompt_generator.py:467-480` (batch prompts)
- `core/video/video_prompt_generator.py:486-501` (batch rules)

**Changes Made:**
- Added ⚠️ visual markers: `"⚠️ MULTI-SEGMENT TIMING (MUST use MULTIPLE time markers):"`
- Added explicit count: `f"⚠️ REQUIRED FORMAT: Break this into {len(ctx.lyric_timings)} segments"`
- Added numbered rules with concrete examples
- Changed from "Use explicit time markers" to "IF/THEN" conditional logic

**How to Test:**

1. **Create project with multi-segment lyrics:**
   ```
   I shuffle numbers like cards
   I hum a rhythm, let the numbers dance
   And suddenly it's not so hard
   ```
2. **Load MIDI and extract lyrics** (timing breakdown will create segments)
3. **Generate with Gemini:**
   - Provider: `Google`
   - Model: `gemini-2.5-pro`
4. **Check generated video prompts in storyboard table**

**Expected Results:**

✅ **GOOD** (multi-segment):
```
Scene 2: 0-0.1s: Hi-res Cartoon style: flash of glowing cards shuffling,
         0.1-0.3s: cards arrange into rhythmic dancing pattern,
         0.3-0.4s: pattern settles into harmonious formation
```

❌ **BAD** (old behavior - single segment):
```
Scene 2: 0-0.4s: Hi-res Cartoon style: glimpse of glowing numbers shuffling
```

**Compare to GPT:**
- Test same lyrics with `gpt-5-chat-latest` or `gpt-4o`
- Gemini output should now match GPT's multi-segment structure

**Success Criteria:**
- When lyrics have 3+ timing segments, video prompts should have 3+ time markers
- Format: `0-Xs: [action1], X-Ys: [action2], Y-Zs: [action3]`

---

## ⚠️ MIDI Without Lyrics Warning

**What Was Fixed:**
- User could generate storyboard with MIDI loaded but NO lyrics extracted
- This caused incorrect timing (e.g., 125-second song compressed to 0.14s, 0.43s, 0.57s scenes)
- Now warns user BEFORE generating storyboard

**Files Modified:**
- `gui/video/workspace_widget.py:2019-2038`

**How to Test:**

1. **Create new video project**
2. **Load MIDI file:**
   - Click "Load MIDI File" button
   - Select a MIDI file (e.g., `Do Math v2.mid`)
3. **DO NOT extract lyrics** (skip "Extract Lyrics" button)
4. **Try to generate storyboard:**
   - Click "Generate Storyboard" button
5. **Dialog should appear:**

**Expected Dialog:**
```
Title: "MIDI Without Lyrics"

Message:
You have a MIDI file loaded, but you haven't extracted lyrics from it yet.

Without lyric extraction, scene timing will be INCORRECT (may be 126s song compressed into a few seconds).

Would you like to:
• Click 'Extract Lyrics' button first (RECOMMENDED)
• Or continue anyway with incorrect timing?

Buttons: [Cancel] [Continue Anyway]
```

**Test Scenarios:**

| Action | Expected Result |
|--------|----------------|
| Click "Cancel" | ✅ Storyboard generation cancelled, status console shows warning |
| Click "Continue Anyway" | ⚠️ Storyboard generates with wrong timing (as expected) |
| Extract lyrics FIRST, then generate | ✅ No warning, correct timing |
| No MIDI loaded | ✅ No warning (normal generation) |

**Verify Timing:**
- **Without lyrics:** Scenes are ~0.1-0.6s each (WRONG)
- **With lyrics:** Scenes span full song duration with correct lyric sync (CORRECT)

---

## 🚀 History Loading Performance Optimization

**What Was Fixed:**
- History widget loaded ALL items from JSON at startup (slow with 1000s of items)
- Now loads only 100 most recent items initially
- "Load More" button loads 25 additional items at a time

**Files Modified:**
- `gui/history_widget.py:26-32` (initialization)
- `gui/history_widget.py:73-77` (UI button)
- `gui/history_widget.py:136-139` (pagination-aware rendering)
- `gui/history_widget.py:238-276` (loading logic)

**How to Test:**

### Setup (Create Large History):
```python
# Run this in Python to create test history:
import json
from pathlib import Path
from datetime import datetime, timedelta

history_file = Path.home() / "AppData/Roaming/ImageAI/dialog_history.json"
history = []
for i in range(500):
    history.append({
        "timestamp": (datetime.now() - timedelta(days=i)).isoformat(),
        "input": f"Test prompt {i}",
        "response": f"Test response {i}",
        "provider": "OpenAI",
        "model": "gpt-4o"
    })
with open(history_file, 'w') as f:
    json.dump(history, f)
```

### Test Startup Performance:

1. **Launch ImageAI**
2. **Open any dialog with history** (e.g., Enhanced Prompt dialog)
3. **Time how long it takes to open**

**Expected Results:**

✅ **Fast startup** (< 1 second even with 500 items)

✅ **History label shows:**
```
History (100 of 500 items shown)
```

✅ **"Load More" button visible:**
```
[Load 25 More Items (400 remaining)]
```

### Test Pagination:

4. **Click "Load 25 More Items" button**

**Expected Results:**

✅ Label updates: `History (125 of 500 items shown)`

✅ Button updates: `Load 25 More Items (375 remaining)`

✅ Table now shows 125 rows

5. **Keep clicking until all loaded**

**Expected Results:**

✅ When all loaded: `History (500 items)`

✅ "Load More" button disappears

### Test New Entry Addition:

6. **Add new history entry** (use the dialog normally)

**Expected Results:**

✅ New item appears at top immediately

✅ Displayed count increments: `History (101 of 501 items shown)`

### Test Clear History:

7. **Click "Clear History" button**

**Expected Results:**

✅ All items cleared

✅ Label shows: `History (0 items)`

✅ "Load More" button disappears

---

## 📊 Comparison Testing: Timing Accuracy

**Test Case:** Compare timing between two projects

**Projects to Compare:**
1. `Do_Math_v2_MIDI_Sync_2` (no test suffix) - Created 2025-11-02 15:18
2. `Do_Math_v2_MIDI_Sync_2_test` (with test suffix) - Created 2025-11-02 20:23

**Location:**
```
C:\Users\aboog\AppData\Roaming\ImageAI\video_projects\
```

**How to Test:**

1. **Load the NON-test project:**
   - File → Open Project
   - Select `Do_Math_v2_MIDI_Sync_2_20251102_151817/project.iaproj.json`

2. **Check scene timings:**
   - Look at storyboard table
   - Note: Duration column, LLM Start/End times

3. **Load the TEST project:**
   - File → Open Project
   - Select `Do_Math_v2_MIDI_Sync_2_test_20251102_202334/project.iaproj.json`

4. **Compare scene timings:**
   - Same lyrics/MIDI
   - Different timing results?

**Expected Analysis:**

| Project | MIDI | Karaoke | Scene Timings | Status |
|---------|------|---------|---------------|--------|
| Non-test | ❌ None | ❌ None | Empty scenes[] | 🔴 Never generated |
| Test | ✅ Yes | ❌ None | 0.14s, 0.43s, 0.57s | 🔴 WRONG (no lyrics) |

**Action Required:**
- Both need lyrics extracted first
- Then regenerate storyboard
- Should get correct timing spanning full 125.57s song

---

## 🧪 Provider Comparison Tests

### Test Different LLM Providers for Video Prompts

**Goal:** Compare quality, timing accuracy, and detail level across providers

**Test Matrix:**

| Provider | Model | Temperature | Batch? | Notes |
|----------|-------|-------------|--------|-------|
| Google | gemini-2.5-pro | 0.7 | ✅ Yes | May return None, needs explicit timing rules |
| Google | gemini-2.5-flash | 0.7 | ✅ Yes | Faster, cheaper, may be more reliable |
| OpenAI | gpt-5-chat-latest | 1.0 | ✅ Yes | Best instruction following, most detailed |
| OpenAI | gpt-4o | 1.0 | ✅ Yes | Reliable, proven |
| Anthropic | claude-3-5-sonnet-20241022 | 1.0 | ✅ Yes | Excellent structured output, no LiteLLM bugs |

**Test Procedure:**

1. **Use same project/lyrics for all tests:**
   - Load "Do Math v2" lyrics
   - Load MIDI and extract lyrics
   - Same prompt style (e.g., "Hi-res Cartoon")

2. **For each provider:**
   - Set LLM provider and model
   - Set temperature
   - Generate storyboard
   - **Save project with provider name in title**

3. **Compare results:**

**Metrics to Compare:**

| Metric | How to Check | Good Example | Bad Example |
|--------|--------------|--------------|-------------|
| **Multi-segment timing** | Check video prompts | `0-0.1s: ..., 0.1-0.3s: ..., 0.3-0.4s: ...` | `0-0.4s: ...` |
| **Detail level** | Count words per prompt | 40-60 words | 10-20 words |
| **Timing accuracy** | Match lyric segments | 3 segments → 3 time markers | 3 segments → 1 marker |
| **Generation time** | Check logs | Batch: 5-10s total | Individual: 45+ seconds |
| **Reliability** | No errors/None responses | All 23 prompts generated | Fallback to individual |
| **Tempo integration** | Check for energy descriptors | "energetic", "upbeat", "dynamic" | No tempo words |
| **Style preservation** | Check for original style | "Hi-res Cartoon style:" in output | Style missing |

**Expected Rankings:**

🥇 **GPT-5** - Best instruction following, most detailed, reliable batch processing

🥈 **Claude 3.5 Sonnet** - Excellent structured output, creative, no bugs

🥉 **GPT-4o** - Solid reliable choice, proven

🏅 **Gemini 2.5 Flash** - Fast/cheap, may be more reliable than Pro

⚠️ **Gemini 2.5 Pro** - Good quality BUT has LiteLLM bugs (None responses)

---

## 🐛 Known Issues to Watch For

### Issue: Gemini Returns None Content
**Symptom:** Log shows `finish_reason=stop` but `content=None`
**Workaround:** Switch to Claude or GPT
**Tracking:** https://github.com/BerriAI/litellm/issues/10721

### Issue: Timing Still Single Marker
**Symptom:** Gemini uses `0-0.4s` instead of `0-0.1s, 0.1-0.3s, 0.3-0.4s`
**Solution:** Check that prompts have "⚠️ MULTI-SEGMENT TIMING" in logs
**Debug:** Try temperature=1.0 for better instruction following

### Issue: History Button Not Appearing
**Symptom:** "Load More" button never shows
**Check:** Does history have > 100 items?
**Debug:** Check `self.displayed_count` in logs

### Issue: Slow Startup Still
**Symptom:** Takes > 3 seconds to open history dialog
**Check:** How many history items total?
**Solution:** May need to reduce `initial_load_count` from 100 to 50

---

## ✅ Testing Checklist

Copy this checklist when testing:

### Video Prompt Generation:
- [ ] Gemini batch generation completes without None errors
- [ ] Multi-segment timing produces multiple time markers
- [ ] Video prompts preserve style descriptors (e.g., "Hi-res Cartoon style:")
- [ ] Tempo BPM converted to natural descriptors (not "120 BPM" in output)
- [ ] Batch processing uses ONE API call (check logs)
- [ ] Compare Gemini vs GPT output quality

### MIDI Warnings:
- [ ] Warning appears when MIDI loaded but no lyrics extracted
- [ ] "Cancel" button stops storyboard generation
- [ ] "Continue Anyway" generates with wrong timing (as expected)
- [ ] No warning when lyrics already extracted
- [ ] No warning when no MIDI loaded

### History Performance:
- [ ] Startup loads only first 100 items
- [ ] "Load More" button appears when > 100 items exist
- [ ] Button text shows remaining count correctly
- [ ] Clicking loads 25 more items
- [ ] Button disappears when all loaded
- [ ] New entries appear immediately at top
- [ ] Clear history resets pagination

### Cross-Provider Testing:
- [ ] Test with Gemini 2.5 Pro
- [ ] Test with Gemini 2.5 Flash
- [ ] Test with GPT-5 or GPT-4o
- [ ] Test with Claude 3.5 Sonnet
- [ ] Compare timing accuracy
- [ ] Compare detail/quality
- [ ] Compare generation speed

---

## 📝 Test Results Log

Record your test results here:

### Test Run: [DATE]

**Tester:** [NAME]

**Test: Video Prompt Generation - Gemini**
- Model: `gemini-2.5-pro`
- Result: ✅ / ❌
- Notes:

**Test: Multi-Segment Timing**
- Provider:
- Expected segments: 3
- Actual segments:
- Result: ✅ / ❌
- Sample output:

**Test: MIDI Warning**
- Warning appeared: ✅ / ❌
- Cancel worked: ✅ / ❌
- Extract lyrics first worked: ✅ / ❌

**Test: History Loading**
- Total items:
- Initial loaded:
- Load time: ___ seconds
- "Load More" worked: ✅ / ❌

**Overall Result:** ✅ All tests passed / ⚠️ Some issues / ❌ Major problems

**Issues Found:**
1.
2.
3.

---

*End of Testing Guide* 🎯
