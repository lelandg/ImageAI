# Custom Styles — Design

**Status:** IMPLEMENTED — PR #35 (v0.41.0), branch feat/custom-styles, 2026-07-26

**Date:** 2026-07-26 10:52
**Status:** Approved design, pending implementation plan
**Author:** Claude (brainstormed with Leland)

## 1. Summary

A Dzine-like custom-style feature for ImageAI: the user supplies any number of
reference images, an LLM vision model derives a reusable named **style**, and
that style can be applied to any future generation — image (GUI + CLI), video
(Omni/Veo), and layout batch-fill — across all providers (Google, OpenAI,
Stability, Local SD).

**Core decisions (made during brainstorming):**

| Decision | Choice |
|---|---|
| Fidelity model | **Hybrid** — style = rich text descriptor + stored reference images; image-capable providers additionally receive exemplar refs |
| Scope in v1 | **Everywhere** — image gen (GUI + CLI), video prompts, layout batch-fill |
| UI shape | **Style Manager dialog + compact style dropdowns** in each generation surface (no new tab) |
| Application mechanism | **Both, toggleable** — plain prefix/suffix concat by default; opt-in LLM "smart merge" per generation |
| Architecture | **New self-contained `core/styles/` package** (Approach A) |

## 2. Architecture

```
core/styles/
    __init__.py        # public API: StyleStore, StyleAnalyzer, apply_style
    store.py           # StyleStore — CRUD + import/export (mirrors core/preset_loader.py)
    analyzer.py        # N-image map-reduce style derivation
    applicator.py      # apply_style(prompt, style, provider, model, smart) -> (prompt, extra_kwargs)
gui/styles/
    __init__.py
    style_manager_dialog.py   # create/edit/delete/analyze styles
    style_picker.py           # StylePickerWidget — combo + Manage… + Smart merge checkbox
cli/commands/style.py         # style management verbs (mirrors cli/commands/layout.py, video.py)
tests/styles/                 # store, analyzer, applicator, CLI, GUI smoke tests
```

Reused infrastructure (no new transport/parsing code):

- **Vision transport:** `UnifiedLLMProvider.analyze_image()`
  (`core/video/prompt_engine.py:939`) — LiteLLM, retry/backoff, per-provider
  key routing already handled.
- **Extraction prompt:** the tuned style-not-content prompt in
  `core/video/style_analyzer.py:71-89`, extended to N images + JSON output.
- **JSON parsing:** `LLMResponseParser.parse_json_response`
  (`gui/llm_utils.py:19`) — strips Markdown fences, validates type.
- **Model selection:** `resolve_model()` (`core/llm_models.py:63`) — never
  hardcode model IDs.
- **Image normalization:** the resize/re-encode helper pattern from
  `gui/reference_image_dialog.py:42` (`resize_image_for_anthropic`).
- **CRUD shape:** `core/preset_loader.py` (`PresetLoader`) — merge, slugs,
  `is_custom`/`is_builtin` runtime flags, export/import.
- **Dialog conventions:** `DialogCleanupMixin`, `OperationGuardMixin`,
  `bind_primary_action`, `set_default_button`, `DialogStatusConsole`,
  persisted splitters (`gui/common/dialog_conventions.py`, `gui/dialog_utils.py`).

## 3. Data model & persistence

### Style record (JSON)

```json
{
  "id": "watercolor-storybook",
  "name": "Watercolor Storybook",
  "description": "Soft washes, warm palette, children's-book feel",
  "descriptor": {
    "summary": "…one-paragraph canonical style description…",
    "medium": "…", "palette": "…", "lighting": "…",
    "composition": "…", "texture": "…", "line_work": "…", "mood": "…",
    "negative": "…"
  },
  "prompt_text": "…flattened ~60-80 word injection text (USER-EDITABLE)…",
  "placement": "suffix",
  "reference_images": ["refs/0001.jpg", "refs/0002.jpg"],
  "exemplars": ["refs/0001.jpg"],
  "source": {
    "provider": "openai", "model": "gpt-4o",
    "created": "2026-07-26 10:52", "image_count": 42
  },
  "version": 1,
  "is_builtin": false
}
```

Field notes:

- `prompt_text` is what actually gets injected on plain application. The
  structured `descriptor` feeds smart merge and re-derivation; `negative` is
  stored for future SD negative-prompt support (not consumed in v1).
- `placement` is `"prefix"` or `"suffix"` (default `"suffix"`), per style.
- `exemplars` is the user-starred subset (default cap 3) sent as reference
  images to providers that accept them. `reference_images` paths are relative
  to the style's directory (portable across machines — see commit `9af1680`
  for the cross-machine path lesson).
- `source` is provenance: which LLM derived it, when, from how many images.

### Persistence layout

```
<user-data>/styles/styles.json          # index: {"styles": [record, …]}
<user-data>/styles/<id>/refs/*.jpg      # copies of source images
```

- `<user-data>` = `get_user_data_dir()` (platform config dir), following the
  `BATCH_JOBS_PATH` precedent in `core/constants.py`. New constants:
  `STYLES_DIR`, `STYLES_INDEX_PATH`.
- Source images are **copied** into the style dir on import (self-contained,
  survives the originals moving) and **downscaled to max 2048 px, re-encoded
  JPEG q90** so "unlimited images" doesn't mean unlimited disk. Originals are
  never modified.
- `StyleStore` (`core/styles/store.py`) mirrors `PresetLoader`: list/get/save/
  delete, slug generation, and export/import of a single **`.zip`** containing
  the record JSON + refs, for sharing between machines.
- Deleting a style removes its directory. IDs are never reused silently: slug
  collisions get a numeric suffix (`-2`, `-3`), matching preset behavior.

## 4. Derivation pipeline (unlimited images → one style)

`StyleAnalyzer` in `core/styles/analyzer.py` (map-reduce):

1. **Normalize** — each image is downscaled/re-encoded (max 2048 px for
   storage; further downscaled per LLM-provider limits at request time, e.g.
   Anthropic's 1568 px / 1.15 MP cap).
2. **Map** — vision calls in chunks of **8 images** (module constant
   `ANALYZE_CHUNK_SIZE = 8`). Each call uses the extended style-extraction
   prompt (style, NOT content) demanding structured JSON matching the
   `descriptor` schema. Responses parsed with `LLMResponseParser`.
3. **Reduce** — if more than one chunk, a final **text-only** LLM call merges
   the per-chunk descriptors into one canonical `descriptor` + flattened
   `prompt_text`. A single chunk skips the reduce step and flattens directly.
4. **Exemplars** — the user stars up to 3 representative images in the dialog;
   if none starred, the first 3 are auto-selected.

- Transport: `UnifiedLLMProvider.analyze_image()`; model via `resolve_model()`
  with a provider/model picker in the dialog (defaults to the configured LLM).
- Per repo LLM rules (AGENTS.md §8): every request and response is logged to
  both the file log and the dialog status console, with separators.
- Re-analysis is non-destructive until saved: the new descriptor/prompt_text
  is shown for confirmation and replaces the old on Save (user edits to
  `prompt_text` are therefore overwritten only with consent).

## 5. Application

### The applicator

`core/styles/applicator.py`:

```python
def apply_style(prompt, style, provider, model,
                smart=False, llm=None,
                user_reference_count=0) -> StyledRequest
# StyledRequest = (styled_prompt: str, extra_kwargs: dict, meta: dict)
```

Called at exactly **four seams**:

| Surface | Seam |
|---|---|
| GUI image gen | `gui/main_window.py:_generate()`, immediately after `original_prompt = prompt` (line ~5209) — history/sidecars keep the clean un-styled prompt, matching the reference-prefix convention |
| CLI image gen | `cli/runner.py`, just before the generation dispatch (~line 370) |
| Video | the scene-prompt styling point in `gui/video/workspace_widget.py` (~line 2861-2876) — a selected stored style replaces the naive `"{name} style: "` prefix; the legacy name-only combo still works when no stored style is selected |
| Layout batch-fill | the region-fill prompt helper (`core/layout/prompt_helper.py` path used by GUI fill and `cli/commands/layout.py run_fill_cmd`) |

### Plain application (default)

- Suffix (default): `"{prompt}. In this style: {prompt_text}"`
- Prefix: `"In this style: {prompt_text}. {prompt}"`
- Deterministic, zero cost, works with no LLM key configured.
- Google rule respected: style text never contains dimensions/aspect strings
  (the derivation prompt forbids them; the applicator doesn't add any).

### Smart merge (opt-in, per generation)

- One LLM call (text-only, configured LLM via `resolve_model()`) fuses the
  user's prompt with the structured `descriptor` into a single coherent
  prompt, resolving conflicts (e.g. "photograph" vs a watercolor style).
- **Any failure falls back to plain concat with a logged warning** — smart
  merge can never block or fail a generation.

### Reference images (hybrid half)

- If the target provider/model supports multiple reference images, exemplars
  are attached via the existing `reference_images` kwarg:
  - Google Gemini image models — model-dependent limits (5–14, from
    `MODEL_REF_LIMITS` in `gui/imagen_reference_widget.py:449`).
  - OpenAI gpt-image family — up to 10.
- **User-supplied references take priority**; style exemplars fill only the
  remaining slots under the model's limit (dropped ones logged).
- Stability and Local SD: **text-only** styling in v1 (no style-ref support on
  their generate paths).
- Video and layout: **text-only** in v1 — video ref slots stay reserved for
  character/continuity references.

### Provenance

The image sidecar JSON records `style_id`, style `name`, and whether smart
merge was used. `original_prompt` in history stays un-styled.

## 6. UI

### Style Manager dialog (`gui/styles/style_manager_dialog.py`)

- **Left pane:** list of styles (name + first-exemplar thumbnail).
  New / Duplicate / Delete / Import / Export buttons.
- **Right pane (selected style):**
  - Name + description fields.
  - Thumbnail grid of reference images — flow-layout cards with a
    star-toggle per card (exemplar selection), remove buttons, **Add
    Files… / Add Folder…** buttons, and drag-and-drop.
  - LLM provider/model combos (seeded from `get_provider_models()`,
    persisted like other dialogs' LLM settings).
  - **Analyze / Re-analyze** button — runs the map-reduce in a `QThread`
    worker with live chunk-by-chunk progress; result shown for confirmation
    before overwriting saved fields.
  - Derived fields: editable `prompt_text` (QTextEdit), placement toggle
    (prefix/suffix), read-only structured-descriptor view.
- **Bottom:** `DialogStatusConsole` behind a persisted splitter.
- Conventions: `OperationGuardMixin` (guard Analyze), `DialogCleanupMixin`,
  Ctrl+Enter primary action, exactly one default button, `show_error`/
  `show_warning` helpers, geometry persisted via QSettings.

### StylePickerWidget (`gui/styles/style_picker.py`)

A compact reusable row: `Style: [None ▾] [Manage…] [☐ Smart merge]`

- Placements: Generate tab (beside the prompt header, ~`main_window.py:840`),
  video workspace (next to the existing style combo, which stays untouched in
  v1), layout fill UI.
- All pickers refresh from the shared `StyleStore` when the manager dialog
  closes. Selected style + smart-merge state persist in config per surface.
- "None" is always first; selecting a style shows its description as tooltip.

## 7. CLI

New "styles" argument group in `cli/parser.py` (after the video group) and
`cli/commands/style.py` following the layout/video house pattern (module
logger, `_emit()` progress to stderr, exit codes 0/2/3/4, `--json` support):

**Management verbs:**

```
--style-create NAME --style-images PATH [PATH …]   # files, dirs, or globs
    [--style-llm-provider P] [--style-llm-model M]
--style-list
--style-show NAME
--style-delete NAME
--style-export NAME --out FILE.zip
--style-import FILE.zip
```

**Use on generation** (composes with existing flags):

```
--style NAME          # image gen (-p), --video, --layout-fill
--style-smart         # opt into smart merge for this run
```

Dispatch wired lazily into the `run_cli()` ladder before the `--prompt`
branch, mirroring `--layout-*` / `--video`.

## 8. Error handling

| Condition | Behavior |
|---|---|
| No LLM key configured when creating/analyzing | Clear actionable error before any work starts (which provider, where to set the key) |
| Vision call fails on a chunk | Existing retry/backoff (3 attempts); then creation **fails** with the error logged — no half-derived style is saved |
| Smart merge fails at generation time | Fall back to plain concat, log a warning, generation proceeds |
| Style's ref files missing on disk at generation time | Degrade to text-only styling, log a warning |
| Style refs exceed model's reference limit | User refs win; overflow exemplars dropped and logged |
| Unknown `--style NAME` in CLI | Exit code 2 with the list of available style names |

All errors logged per the repo rule (every user-visible error also goes to the
file log).

## 9. Testing (`tests/styles/`)

- **Store:** CRUD round-trip, slug generation/collisions, image copy +
  downscale on import, export/import zip round-trip, missing-file resilience.
- **Analyzer:** chunking math (1, 8, 9, 42 images), reduce-step merge, JSON
  parse fallbacks — all with a mocked `UnifiedLLMProvider`.
- **Applicator:** matrix of provider × placement × smart(success/failure
  fallback) × ref-limit merging with user refs; sidecar/meta output.
- **CLI:** parser tests + dispatch tests (mirroring
  `tests/layout/test_cli_layout_parser.py` / `_dispatch.py`).
- **GUI:** dialog-construction smoke tests (existing headless smoke pattern);
  picker refresh-on-close behavior.

All headless-safe (no display required).

## 10. Out of scope (v1)

- Per-provider native training (LoRA for Local SD) — the "max fidelity" path,
  deferred.
- SD negative-prompt consumption of `descriptor.negative` (stored now, used
  later).
- Style refs for video generation (slots reserved for continuity refs).
- Consolidating the legacy video style-name combo onto the style store.
- Built-in seed styles shipped with the app (schema supports `is_builtin`).
