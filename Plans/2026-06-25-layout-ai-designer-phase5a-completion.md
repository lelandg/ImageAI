# Phase 5a — AI prompt help + bundles — Completion Summary ✅
**Last Updated:** 2026-06-25 17:45

First slice of **Phase 5** (AI content & bundles) of the AI Layout Designer
redesign. Phase 5 is larger than any prior phase, so it ships as a series of PRs;
**5a** delivers the two self-contained, fully headless-testable pieces.

Branch: `feat/layout-ai-designer-phase5` (off `main`). Plan:
`Plans/2026-06-25-layout-ai-designer-phase5a-content.md`. Design source:
`Plans/2026-06-24-layout-ai-designer-design.md` §9 (F-AI) + §8 (bundles).

## What shipped

### 1. Per-region AI image-prompt help (`4356005`)
- **`core/layout/prompt_helper.py`** (NEW, pure): `build_prompt_messages(document,
  region, hint)` assembles `<context>` (content_kind, title, palette, region
  name/role/aspect) + sibling text-region content for scene context;
  `parse_prompt_response` (JSON `{"prompt"}` → fenced → plain text → "");
  `run_prompt_help(messages, completion_fn)`. Reuses `designer.run_completion`
  for the production LLM call (registry-resolved model IDs, LiteLLM, logging).
  **Never** emits a pixel/ratio token into the prompt (Gemini would render it).
- **`gui/layout/prompt_worker.py`** (NEW): `PromptSuggestWorker(QThread)`, mirrors
  `DesignerWorker` — synchronous when a `completion_fn` is injected (tests),
  threaded otherwise.
- **`ContentInspector`**: image page gains a prompt box + **Suggest with AI** /
  **Apply prompt**; loads `region.prompt` on selection; stays display-only.
- **`LayoutTab`**: `suggest_region_prompt()` orchestrates via the Designer
  panel's provider/model; re-fetches the region by id on completion (correct
  region even after a scene rebuild); logs request+response to the Designer
  console; failures auto-expand it (errors never hidden); empty result keeps the
  existing prompt; second click while running is rejected.

### 2. `.iaibundle` export/import (`39734fb`)
- **`core/layout/bundle_io.py`** (NEW): `export_bundle(doc, path, font_resolver)`
  deep-copies the doc (live one never mutated), copies every referenced image
  into `images/` (deduped by resolved source path) and rewrites refs to
  bundle-relative, embeds resolvable fonts into `fonts/` (else records the family
  "by-name"), and writes `project.iaiproj.json` + a `bundle.json` manifest
  (images/fonts/warnings). Missing images warn but don't fail.
  `import_bundle(path, dest)` extracts (with a **zip-slip guard**) and rewrites
  relative refs back to absolute under the extract dir. Font resolution is
  **injected**, so the core is unit-testable without scanning system fonts.
- **`LayoutTab`**: Export/Import Bundle… toolbar buttons + `export_bundle_to` /
  `import_bundle_from`; the production `font_resolver` lazily wraps a cached
  `FontManager` (any failure degrades to by-name — never blocks export). Dialog
  failures go through `_report_error` (logged + shown).

## Tests
`QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q`
→ **151 passed** (112 before 5a → **+39**):
- `test_prompt_helper.py` (10): context assembly, no pixel token, JSON/fenced/
  plain/empty parsing, injected-completion run.
- `test_content_inspector.py` (+5): prompt load, apply/suggest signals,
  `set_prompt_text` region-guard.
- `test_layout_tab_prompt.py` (7): suggest writes prompt + updates inspector,
  empty keeps existing, text-region/unknown-id no-ops, failure surfaces console.
- `test_bundle_io.py` (7): round-trip, relative-ref rewrite, missing-image
  warning, shared-image dedup, font embed vs by-name, zip-slip rejection.
- `test_layout_tab_bundle.py` (2): full export→import round trip; missing-image
  warning surfaced.

## Cross-cutting compliance (design §11)
- LLM request + full response logged (file + Designer console); model IDs
  registry-resolved (no hardcoding); all errors logged + surfaced; images only
  copied (fit modes untouched, scaled-not-cropped preserved); no size/ratio
  tokens injected into image prompts.

## Out of scope (Phase 5b+)
- "Send to Image tab" handoff, Batch API placement, layout-complete mode — all
  need LayoutTab↔MainWindow wiring + a GUI runtime to verify.
- Installing embedded fonts into the OS on import (we extract + reference only).
- `region.gen_settings` is carried/serialized but not yet populated (the handoff
  phase fills provider/model/size there).
