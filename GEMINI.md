@AGENTS.md

# GEMINI.md — Gemini agent specifics

The line above imports **`AGENTS.md`**, the canonical source of truth for this
repo. General project context, structure, operational rules, the **Google Gemini
image-generation guidelines** (model selection, aspect-ratio handling, scaling,
reference images), and LLM logging/parsing conventions all live there — see
AGENTS.md §8 (LLM Integration) and §9 (Provider Notes). This file keeps only
Gemini-agent-specific preferences and memories.

## Agent Memories & Preferences (Gemini-specific)

### Code & Syntax
- **WSL C# syntax check** (no dependency build):
  `dotnet build --no-dependencies 2>&1 | grep -E "error CS|warning CS" || echo "No syntax errors found"`
- **Code reviews**: write to `Docs/GeminiCodeReview_YYYYMMDD.md`.

### Specific Fixes (History)
- Fixed critical bug in `src/services/compliance_checker.py` (metadata checks).
- Fixed `DocumentProcessor.extract_text_with_ocr`.
- Updated `src/api/compliance.py` for async compatibility.
