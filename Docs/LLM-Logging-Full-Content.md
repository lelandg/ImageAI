# LLM Logging - Full Content Display

**Last Updated:** 2025-10-21

## Overview

All LLM interactions now log **FULL** prompts and responses without truncation to both the log file and status console. This ensures complete visibility into what's being sent to LLMs and what they return.

## Files Updated

### Core Video Processing

1. **`core/video/llm_sync.py`**
   - Line 324-327: System prompt now logged in full (was truncated to 200 chars)
   - Format: Shows character count and full content

2. **`core/video/llm_sync_v2.py`**
   - Line 173-176: OpenAI GPT-5 sync - full system prompt
   - Line 393-396: Anthropic sync - full system prompt
   - Line 627-630: Gemini sync - full system prompt

3. **`core/video/storyboard_v2.py`**
   - Line 282: Full prompt sent to LLM for Veo batching
   - Line 296: Full response from LLM
   - Line 308-310: Each batch prompt logged in full (was truncated to 200 chars)

4. **`core/video/style_analyzer.py`**
   - Line 92-93: Style analysis results - full content
   - Line 136-137: Transition analysis results - full content

### GUI Components

5. **`gui/video/workspace_widget.py`**
   - Line 1597: Added status console message when storyboard generation starts
   - Status console now shows "📝 Generating storyboard scenes..." immediately

6. **`gui/reference_image_dialog.py`**
   - Line 211-214: Reference image description - full response (was 200 chars)
   - Line 306-309: Second reference description handler - full response

7. **`gui/prompt_question_dialog.py`**
   - Line 155-158: Q&A answers - full response (was 200 chars)

8. **`gui/video/video_project_tab.py`**
   - Line 393-394: Style info - full content
   - Line 402-403: Transition prompts - full content

9. **`gui/video/start_prompt_dialog.py`**
   - Line 82-83: Style analysis result - full content

## Logging Format

All LLM interactions now use this consistent format:

```python
# Before (TRUNCATED):
self.logger.info(f"System prompt: {system_prompt[:200]}...")

# After (FULL):
self.logger.info(f"System prompt (FULL, {len(system_prompt)} chars):")
self.logger.info(system_prompt)
```

### Example Log Output

```
=== LLM REQUEST ===
System prompt (FULL, 1247 chars):
You are an expert music video director creating prompts for Google's Veo 3.1 AI video generator.

Veo 3.1 generates 8-second video clips at 24 FPS. You need to create cohesive video prompts...
[full content here]

User message (FULL, 532 chars):
Song: Do Math
Visual Style: Cinematic
Full Lyrics:
...
[full content here]
=== END LLM REQUEST ===

=== LLM RESPONSE ===
Response length: 2143 characters
Full response:
{
  "combined_prompts": [
    {
      "batch_id": 0,
      "scene_ids": [0, 1],
      "duration": 5.0,
      "video_prompt": "0-3s: Wide shot of character gazing at endless night sky...",
      ...
    }
  ]
}
=== END LLM RESPONSE ===
```

## Benefits

1. **Complete Debugging**: See exactly what's sent to and received from LLMs
2. **Prompt Engineering**: Understand how prompts are constructed
3. **Error Diagnosis**: Identify issues in LLM communication
4. **Transparency**: Full visibility into AI interactions
5. **Compliance**: Meet requirements for LLM interaction logging

## Status Console Messages

Users now see immediate feedback when LLM operations start:

- "📝 Generating storyboard scenes..." - When storyboard generation begins
- "🎵 Starting LLM sync with {provider}/{model}..." - When LLM sync begins
- "🚀 BATCH processing {N} scenes in 1 API call..." - When batch enhancement starts

## Files NOT Changed

The following files were checked but already log full content:

- `core/video/prompt_engine.py` - Already logs full prompts
- `core/video/end_prompt_generator.py` - Already logs full responses
- `core/prompt_enhancer_llm.py` - Already logs full prompts

## Testing

To verify full logging:

1. Click "Generate Storyboard" in Video tab
2. Check `imageai_current.log` file
3. Search for "=== LLM REQUEST ===" and "=== LLM RESPONSE ==="
4. Verify no truncation (no "..." at end of prompts/responses)
5. Check status console shows startup messages

## Related Documentation

- See `Veo-3.1-Batching-Implementation.md` for frame-accurate timing implementation
- See `CodeMap.md` for navigation to specific logging locations
