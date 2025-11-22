# Gemini Agent Context

**Note:** General project context, architectural rules, and operational guidelines have been moved to **`AGENTS.md`**. Please refer to that file for:
- Project Structure & Navigation
- Plan File Management
- Development Environment Details
- Credential Security
- Common Tool Usage

This file contains specific instructions and memories relevant to the **Google Gemini** agent and the Gemini provider implementation within ImageAI.

## Gemini Model Implementation Guidelines

### Image Generation (`providers/google/`)
- **Model Selection**:
    - **Production**: Use `gemini-2.5-flash-image`.
    - **Avoid**: `gemini-2.5-flash-image-preview` (deprecated/broken aspect ratios).
- **Aspect Ratio Handling**:
    - Set via `image_config={'aspect_ratio': '4:3'}` (or '16:9', '1:1', etc.).
    - **DO NOT** include aspect ratio descriptions (e.g., "4:3", "(1024x768)") in the text prompt. This causes artifacts.
    - Supported Ratios: 1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9.
- **Resolution/Scaling**:
    - The API has fixed resolutions per aspect ratio.
    - For UI targets > 1024px, request the standard size and upscale locally or via a separate upscaling step.

### LLM Interaction
- **Logging**: Log all prompt inputs and raw JSON responses to both console and file for debugging.
- **JSON Parsing**: Use robust parsing (like `LLMResponseParser` in `gui/llm_utils.py`) to handle Markdown code block wrapping often returned by Gemini.

## Agent Memories & Preferences (Gemini-Specific)

### Code & Syntax
- **WSL C# Checks**: To check syntax in WSL without building dependencies:
  `dotnet build --no-dependencies 2>&1 | grep -E "error CS|warning CS" || echo "No syntax errors found"`
- **Code Reviews**: Use the naming convention `Docs/GeminiCodeReview_YYYYMMDD.md`.

### specific Fixes (History)
- Fixed critical bug in `src/services/compliance_checker.py` (Metadata checks).
- Fixed `DocumentProcessor.extract_text_with_ocr`.
- Updated `src/api/compliance.py` for async compatibility.

*(See `AGENTS.md` for full project history and guidelines)*
