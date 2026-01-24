# Discord RPC Dialog Updates

**Last Updated:** 2026-01-08 08:27
**Status:** Complete

## Overview

Updated Discord Rich Presence to display specific dialog names when using AI features, replacing the generic "Chatting with AI" message.

## Changes Made

### Core Logic (`core/discord_rpc.py:398-403`)
- Modified `_build_presence_data()` to use "AI {dialog_name}" format for `CHATTING_WITH_AI` state
- Other activity states still use the "{activity}: {details}" format

### Dialogs with Discord RPC (9 total)

| File | Window Title | Discord Display |
|------|--------------|-----------------|
| `gui/enhanced_prompt_dialog.py:831` | "Enhance Prompt with AI" | **AI Enhance Prompt** |
| `gui/layout/text_gen_dialog.py:618` | "Generate Text with LLM" | **AI Generate Text** |
| `gui/prompt_generation_dialog.py:1499` | "AI Prompt Generator" | **AI Prompt Generator** |
| `gui/prompt_question_dialog.py:906` | "Ask AI Anything" | **AI Ask Anything** |
| `gui/video/start_prompt_dialog.py:376` | "Generate Start Frame Prompt" | **AI Start Frame Prompt** |
| `gui/reference_image_dialog.py:1160` | "Ask About Files with AI" | **AI Ask About Files** |
| `gui/video/end_prompt_dialog.py:223` | "Generate End Frame Prompt" | **AI End Frame Prompt** |
| `gui/video/video_prompt_dialog.py:227` | "Generate Video Prompt" | **AI Video Prompt** |
| `gui/video/reference_generation_dialog.py:924` | "Generate Character References" | **AI Generate References** |

## Implementation Pattern

Each dialog implements:
```python
def showEvent(self, event):
    """Handle show event - update Discord presence."""
    super().showEvent(event)
    discord_rpc.update_presence(
        ActivityState.CHATTING_WITH_AI,
        details="Dialog Name"
    )

def closeEvent(self, event):
    """Handle close event."""
    discord_rpc.update_presence(ActivityState.IDLE)
    # ... existing cleanup code ...
    super().closeEvent(event)
```

## Notes
- Dialog names are shortened to match UI while staying recognizable on Discord
- Avoided "AI AI" duplication by removing "AI" prefix from dialog detail strings
- All dialogs reset to IDLE state on close
