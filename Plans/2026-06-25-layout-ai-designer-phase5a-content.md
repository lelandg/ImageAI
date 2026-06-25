# Phase 5a — AI prompt help + bundles — Implementation Plan ✅ 100%
**Last Updated:** 2026-06-25 17:45
**Author:** Leland Green + Claude (Opus 4.8)
**Design source:** `Plans/2026-06-24-layout-ai-designer-design.md` §9 (F-AI) + §8 (bundles)
**Branch:** `feat/layout-ai-designer-phase5`

Phase 5 (AI content & bundles) is larger than any prior phase, so it lands as a
series of PRs. **Phase 5a** ships the two self-contained, fully headless-testable
deliverables first:

1. **Per-region AI prompt help** — generate an image-generation prompt for an
   image region from the project theme/content_kind (spec §9 F-AI, first bullet).
2. **`.iaibundle` export/import** — a self-contained zip of project JSON +
   referenced images + embedded fonts (spec §8, Phase-5 row).

Deferred to **Phase 5b+** (later PRs): "Send to Image tab" handoff, Batch API
placement, layout-complete mode (all require LayoutTab↔MainWindow wiring and a
GUI runtime to verify).

---

## Why these two first

- Both live entirely in `core/layout/` + `gui/layout/` with **no cross-tab
  coupling** — `LayoutTab` is constructed with only `config` (`main_window.py:554`)
  and has no MainWindow reference, which the handoff/batch features need but these
  two don't.
- Both are unit-testable headless in WSL exactly like Phases 1–4
  (`QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q`).
- Prompt-help **unblocks** the rest of the AI-content chain: the prompt it writes
  to `region.prompt` is the same field "Send to Image tab" and Batch consume.

---

## Feature 1 — Per-region AI prompt help

### Goal
Select an image region → ask the LLM to draft an image-generation **prompt**
informed by the project (content_kind, title, style palette), the region (role,
name, bbox aspect), and nearby text regions → the suggestion fills the region's
`prompt` field (already on `Region`, `models.py:109`, round-tripped by
`schema.region_to_dict/from_dict`). The user can edit and keep it; later phases
send it to generation.

### Reuses (no new plumbing)
- `core.layout.designer.run_completion(config, provider, model, messages, temperature)`
  — the production LLM call (LiteLLM, key resolution, logging) — `designer.py:131`.
- `gui.llm_utils.LLMResponseParser` — robust JSON/prose extraction.
- The Designer panel's provider/model selectors (`DesignerPanel.provider_combo`,
  `.model_combo`) — one LLM config for the whole tab; no second selector.

### New module — `core/layout/prompt_helper.py` (pure, unit-tested)
```
build_prompt_messages(document, region, hint="") -> List[Dict]
    # <context>: content_kind, document.title, palette/theme, region.kind/role/
    #   name, bbox aspect ratio (w:h), and neighboring text-region content for
    #   scene context. <instructions>: return a SINGLE vivid image-generation
    #   prompt as JSON {"prompt": "..."} (robustly parsed; plain text tolerated).
    #   <example>: one worked case. Honors the repo rule: NO dimensions/ratios in
    #   the prompt text itself (Gemini renders them literally) — aspect is context
    #   only, never an instruction to embed "(1024x768)".
parse_prompt_response(content) -> str
    # LLMResponseParser → dict{"prompt"} if present, else stripped plain text;
    # empty/garbage → "" (caller keeps the existing prompt, logs).
run_prompt_help(messages, completion_fn) -> str
    # completion_fn injected in tests; production lambda wraps run_completion.
```

### GUI wiring
- **`gui/layout/content_inspector.py`** — image page gains:
  - a `prompt_edit` (`QPlainTextEdit`) showing `region.prompt`,
  - **"Suggest with AI"** → emits `regionPromptSuggestRequested(region_id, hint)`,
  - **"Apply prompt"** → emits `regionPromptChanged(region_id, prompt)`.
  - `set_region()` loads `region.prompt` into the box for image regions.
  - Inspector stays **display-only**; LayoutTab owns all mutation (Phase-4 pattern).
- **`gui/layout/prompt_worker.py`** (NEW) — `PromptSuggestWorker(QThread)` mirrors
  `DesignerWorker`: runs synchronously when a `completion_fn` is injected (tests),
  else `start()`s a thread. Emits `suggested(region_id, prompt)` / `failed(str)`.
- **`gui/layout/layout_tab.py`**:
  - `_on_region_prompt_changed(id, text)` → writes `region.prompt` (no re-render;
    prompt is metadata, not drawn).
  - `suggest_region_prompt(region_id, hint, completion_fn=None)` → builds messages
    via `prompt_helper`, runs the worker (production `completion_fn` wraps
    `designer.run_completion` with the Designer panel's provider/model), and on
    success sets `region.prompt` + pushes the text back into the inspector.
  - The Designer console logs the request + response (repo LLM-logging rule §8).

### Tests (`tests/layout/test_prompt_helper.py`, extend `test_layout_tab_content.py`)
- `build_prompt_messages` includes content_kind, title, role/name, aspect, and a
  neighboring text region's content; **never** embeds a pixel/ratio token in the
  instruction to the image model.
- `parse_prompt_response`: JSON `{"prompt"}`, fenced JSON, plain prose, empty → "".
- `run_prompt_help` with an injected `completion_fn` returns the parsed prompt.
- LayoutTab: `suggest_region_prompt(id, hint, completion_fn=fake)` writes
  `region.prompt`; `_on_region_prompt_changed` persists an edited prompt;
  a text region or unknown id is a no-op.

---

## Feature 2 — `.iaibundle` export/import

### Goal (spec §8)
A **self-contained** zip a recipient can open without the original assets:
project JSON + every referenced image + embedded fonts (license permitting),
with image references rewritten to bundle-relative paths so nothing dangles.

### New module — `core/layout/bundle_io.py`
```
export_bundle(doc, path, config=None) -> BundleManifest
    # 1. Deep-copy the doc; walk every page's regions.
    # 2. For each image region with an existing image_ref file: copy into the zip
    #    under images/<sanitized-stem>-<n><ext>, dedup identical source paths,
    #    and rewrite that region's image_ref to the RELATIVE bundle path.
    #    Missing/unreadable refs are recorded as warnings, left as-is.
    # 3. Fonts: collect families from project style roles + per-region text_style;
    #    resolve each via FontManager.select_font_file(families,...) and embed the
    #    file under fonts/<file>. Unresolved families → recorded "by-name" + warn
    #    (licensing per design §7 — embed only what resolves to a file).
    # 4. Write project.iaiproj.json (rewritten refs) + bundle.json manifest
    #    (version, title, images map, fonts map, warnings) into the zip.
import_bundle(path, dest_dir) -> DocumentSpec
    # Extract zip into dest_dir; load project.iaiproj.json; rewrite each relative
    # image_ref back to its absolute extracted path (dest_dir/images/...).
    # Return the DocumentSpec (fonts referenced by name; extracted to fonts/).
```
- **Manifest** `bundle.json`: `{schema_version, title, images:{orig→bundle},
  fonts:{family→bundle|"by-name"}, warnings:[...]}` — small, human-readable,
  the source of truth for round-trip mapping.
- **Format**: a `zipfile.ZipFile`; extension `.iaibundle`. Reuses
  `schema.document_to_dict/from_dict` for the embedded project JSON.

### GUI wiring — `gui/layout/layout_tab.py`
- Toolbar: **"Export Bundle…"** (`*.iaibundle`) / **"Import Bundle…"** with
  `QFileDialog` + the existing `_report_error` path (errors logged + shown, §6).
- Programmatic API (tested): `export_bundle_to(path)` / `import_bundle_from(path)`.
- Import adopts the returned doc via `_adopt_document` + `_refresh` (same as
  template import).

### Tests (`tests/layout/test_bundle_io.py`, extend `test_layout_tab*.py`)
- Round-trip: build a doc with 2 image regions pointing at temp PNGs, export →
  the zip contains `project.iaiproj.json`, `bundle.json`, and both images under
  `images/`; the embedded project JSON's `image_ref`s are **relative**.
- Import into a fresh dir → `image_ref`s are absolute paths that **exist**; the
  doc loads and equals the original geometry/text.
- Missing source image → warning recorded, export still succeeds, ref preserved.
- Two regions sharing one source file dedup to a single embedded image.
- (Font embedding asserted best-effort: when `select_font_file` resolves a file
  it's embedded; the test tolerates headless font absence by checking the
  manifest records either a path or "by-name".)

---

## Cross-cutting compliance (design §11)
- **LLM logging:** prompt-help request + full response shown in the Designer
  console **and** the file logger (reuses `run_completion`'s logging).
- **Model IDs** via the registry (`run_completion` already resolves) — none
  hardcoded.
- **All errors logged + surfaced** (the `_report_error` path; worker `failed`
  signal expands the Designer console).
- **Images scaled, not cropped:** unchanged — bundles only copy files; rendering
  still honors fit modes. No pixel/ratio tokens injected into image prompts.

## Out of scope (Phase 5b+)
- "Send to Image tab" handoff, Batch API placement, layout-complete mode.
- Multi-page is handled (bundle walks all pages); prompt-help still operates on
  the selected region regardless of page.
- Installing embedded fonts into the OS on import (we reference + extract only).

---

## Task checklist
1. ✅ Plan doc (this file) — committed `3d4a7c9`.
2. ✅ `core/layout/prompt_helper.py` + `tests/layout/test_prompt_helper.py` (`4356005`).
3. ✅ Inspector prompt UI + `prompt_worker.py` + LayoutTab orchestration + tests (`4356005`).
4. ✅ `core/layout/bundle_io.py` + `tests/layout/test_bundle_io.py` (`39734fb`).
5. ✅ LayoutTab bundle toolbar + programmatic API + tests (`39734fb`).
6. ✅ Full `tests/layout/` green headless — **151 passed** (112 → +39); see
   `Plans/2026-06-25-layout-ai-designer-phase5a-completion.md`.
