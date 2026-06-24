# AI Layout Designer — Design Spec

**Last Updated:** 2026-06-24 12:15
**Status:** Approved design → implementation plan next (writing-plans)
**Author:** Leland Green + Claude (Opus 4.8)
**Supersedes:** `Plans/ImageAI_Layout_Implementation_Plan.md` (template-driven approach) and the
"⚠️ Development in Progress" state of the current `gui/layout/` tab.

---

## 1. Goal & paradigm shift

Completely change how the **Layout** tab works: replace the **template-picker** paradigm
("pick a blank layout, fill it") with an **AI-first designer** paradigm:

> Describe what you want (a children's storybook with one big illustration; a 9-panel comic
> whose panels flow into each other; a magazine spread) → the AI asks for more detail and/or
> proposes a layout rendered on the page → iterate in a loop → save, share, and fill with
> content.

The AI designs **any** kind of page — comic, storybook, scientific paper, magazine, newspaper,
or freeform — at **any page size and orientation**. Templates do not disappear: they demote to
(a) an optional starting point and (b) a lightweight shareable artifact.

This is a **refactor-in-place** of the existing `core/layout/` + `gui/layout/`, not a greenfield
rewrite — the structured-document model and rendering helpers are salvageable; the
template-centric paradigm and the broken canvas are not.

---

## 2. Locked decisions

These were settled with the user during brainstorming and are not open for re-litigation in the
implementation plan:

| Decision | Choice |
|---|---|
| **Spec scope** | Spec the **whole vision**, organized into phases (this document). |
| **Layout representation** | **Structured document + native Qt render.** Typed doc (page + regions; regions have `shape: rect\|polygon`, position/size, kind, style, content). Rendered in a `QGraphicsScene`; every region individually selectable/editable. |
| **Final render & export** | **Unify on Qt (WYSIWYG).** The scene is the single source of truth; export high-res PNG-per-page and **PDF via `QPdfWriter`** from the same scene. No second renderer → no editor/export drift. |
| **Share model** | **Both, phased.** (1) Lightweight **layout template** (structure + shapes + styles + prompt scaffolding, no content) shared first; (2) full self-contained **bundle** (images + fonts + content) later. |
| **Codebase strategy** | **Extend & refactor** existing `core/layout` + `gui/layout` in place; reuse `FontManager`, image-fit, text-wrap/hyphenation, sidecars, LiteLLM plumbing; fix known bugs; retire the template-picker UI. |
| **Designer "AI"** | The **text LLM** (LiteLLM provider/model already selectable in the layout tab). Image *generation* providers remain separate and are only invoked during content filling. |

---

## 3. Architecture overview

**One structured document, two render targets, native Qt throughout.**

```
DocumentSpec
 ├─ content_kind         ("children" | "comic" | "comic_strip" | "magazine" |
 │                         "newspaper" | "scientific" | <freeform string>)
 ├─ style: ProjectStyle  (font roles, color palette/roles — §7)
 ├─ history: [Snapshot]  (iteration history — §6)
 └─ pages: [PageSpec]
        ├─ page_size: PageSize   (width, height, unit, orientation, dpi — §5)
        ├─ margin / bleed / background
        └─ regions: [Region]
               ├─ id, z, kind ("image" | "text"), name
               ├─ shape ("rect" | "polygon"), bbox:[x,y,w,h], points:[[x,y]…]
               ├─ style (TextStyle | ImageStyle; font role refs project style)
               └─ content
                    ├─ image: { image_ref, prompt, gen_settings }   (kind=image)
                    └─ text:  { text, role }                        (kind=text)
```

- **Live editor** — `qt_renderer` builds a `QGraphicsScene` from the document. Each `Region`
  becomes a selectable / draggable / resizable `QGraphicsItem` (rectangles **and** polygons, so
  comic panels can "flow into each other"). Selection drives the inspector.
- **Export (WYSIWYG)** — the *same* scene renders to high-res PNG (per page) and to **PDF via
  `QPdfWriter`**. One render path guarantees what-you-see-is-what-you-get.
- **Reused** from existing code: `FontManager` (discovery + fallback), image-fit modes
  (`ImageProcessor`), text-wrap + hyphenation (`text_renderer`, ported into Qt drawing where
  needed), sidecar read/write (`core/utils.py`), `gui/llm_utils.py`
  (`LLMResponseParser`, `DialogStatusConsole`, `LiteLLMHandler`), and the `ConfigManager`
  helpers already present (`get_layout_export_dpi` default 300, `get_layout_llm_provider`,
  `get_templates_dir`, `get_fonts_dir`).

### Module map (extend-in-place)

| Module | Status | Purpose |
|---|---|---|
| `core/layout/models.py` | extend | `Region` (shape/points/kind/content), `ProjectStyle`, `FontRole`, `PageSize`, `Snapshot`; keep `DocumentSpec`/`PageSpec` lineage. |
| `core/layout/schema.py` | **new** | JSON Schema + validate/normalize for **both** AI output and templates (clamp geometry to page, default fills, id assignment). |
| `core/layout/designer.py` | **new** | `LayoutDesigner`: build prompt → call LLM (LiteLLM) → parse structured layout / questions. |
| `core/layout/qt_renderer.py` | **new** | DocumentSpec → `QGraphicsScene`; scene → PNG/PDF (`QPdfWriter`). Single source of truth. |
| `core/layout/history.py` | **new** | Snapshot store: append, list, restore, branch; persisted with project. |
| `core/layout/page_sizes.py` | **new** | Preset catalog (seeded from `Plans/common-sizes.md`), unit conversion, custom-preset persistence. |
| `core/layout/engine.py` | retire/trim | PIL render engine demoted; salvage text/image helpers, drop as export source of truth. |
| `gui/layout/layout_tab.py` | rework | AI-first orchestration; remove dev/info banners; host page-setup + designer + canvas + inspector + status console. |
| `gui/layout/page_setup_widget.py` | **new** | Orientation / size / unit / DPI (subsystem A). |
| `gui/layout/designer_panel.py` | **new** | Description input + iterate prompt + status console + `QThread` worker (B). |
| `gui/layout/history_window.py` | **new** | Separate browsable iteration-history window (C). |
| `gui/layout/style_panel.py` | **new** | Project fonts / colors / roles (D). |
| `gui/layout/canvas_widget.py` | rework | Functional `QGraphicsScene` view; selectable rect + polygon items; drag/resize; page nav. |
| `gui/layout/inspector_widget.py` | rework | Per-region editing + content import (F-MVP); fix `self.canvas`/`self.inspector` wiring bug. |
| `gui/layout/export_dialog.py` | rework | Drive Qt export (PNG/PDF); fix broken `LayoutEngine` construction. |
| `gui/layout/template_selector.py` | demote | Optional starting point / template-share import. |
| `gui/layout/text_gen_dialog.py` | reuse | Text generation for text regions (already LiteLLM-based). |

---

## 4. Subsystem A — Page setup

A compact setup strip (top of the tab) and/or dialog:

- **Orientation** toggle: portrait / landscape (swaps W↔H).
- **Size**: editable combobox — common presets **and** freeform custom entry. Presets seeded from
  `Plans/common-sizes.md` (Letter, Legal, Tabloid, A4, A5; US Comic 6.625×10.25"; photo sizes;
  1080² / 1080×1350 / 1920×1080 social & screen). **No size limits.**
- **Unit** selector: in / mm / px / pt.
- **DPI**: default 300 (print); reuses `get_layout_export_dpi`.
- **Canonical store** = physical size + unit + DPI; pixels derived as `round(size × dpi)` (px unit
  stores pixels directly). Bleed default 0 (offer 0.125"/37px @ 300 helper).
- **Custom sizes persist** to user config (new `layout_custom_page_sizes`) and reappear in the
  combobox across sessions.

**Acceptance:** user sets any size/orientation/unit/DPI, sees the page at correct proportions on
the canvas; a custom size entered once is offered next session.

---

## 5. Subsystem B — AI layout designer + iteration loop

- **Designer = text LLM** via LiteLLM, using the tab's existing provider/model selector
  (Google / Anthropic / OpenAI / Ollama / LM Studio). Model IDs resolve via `resolve_model()` —
  **no hardcoded model IDs**.
- **Prompt contract** (`<context>` page spec + content_kind + project style + current layout;
  `<instructions>` return JSON to our region schema and/or clarifying questions; `<examples>`
  the three canonical cases). Output: a JSON object `{ questions?: [...], layout?: <DocumentSpec
  page schema> }` — supporting "asks for more detail, presents a layout, **or both**."
- **Robust parsing** with `LLMResponseParser` (strips ```json fences, extracts from prose);
  `schema.py` validates + normalizes (assign ids, clamp regions to the page, default styles).
  On total failure → a sensible **fallback layout** derived from content_kind (e.g. single
  full-page region) plus an error surfaced in the console **and** logged.
- **Iteration loop**: description → proposal rendered on canvas → user types a **modification
  prompt** ("make the top panel full-bleed", "9 panels flowing diagonally", "equal 3×3 grid") →
  revised layout. Each turn = one **Snapshot** (§6).
- **Threading & logging**: runs on a `QThread` worker (mirror `TextGenerationWorker`). A **status
  console at the bottom** shows every prompt sent and full response received, in real time —
  satisfying the repo LLM-logging rule (console **and** file logger, including LiteLLM internals).
- **Canonical examples handled**: (1) full-page storybook with one top illustration; (2) 9 panels
  arranged dynamically and shaped to flow into each other (polygon regions); (3) equally sized
  comic grid.

**Acceptance:** from a one-line description the AI produces a rendered layout within one turn;
follow-up modification prompts visibly change the layout; everything sent/received appears in the
console and log.

---

## 6. Subsystem C — Iteration history

- Each designer turn appends a **Snapshot** = `{ id, parent_id, timestamp, prompt, document_json,
  thumbnail }`. Images are **referenced by path**, never embedded, so snapshots stay small.
- A **separate History window** (not a modal blocking the tab) lists snapshots with thumbnails and
  the prompt that produced each. Actions: **preview**, **restore** (load snapshot as current),
  **branch** (restore + keep iterating → new lineage via `parent_id`).
- History is **persisted with the project**, so reopening a project restores the full browsable
  timeline.

**Acceptance:** after several iterations the user opens the History window, browses back and
forth, restores an earlier layout, and continues — producing a new branch without losing prior
snapshots.

---

## 7. Subsystem D — Project style system

- Per-project, seeded by `content_kind`. **Font roles** whose *set varies by kind*:
  - children → { title, narration }
  - comic / comic_strip → { logo_title, dialogue, sfx, caption }
  - magazine / newspaper → { masthead, headline, body, caption, pull_quote }
  - scientific → { title, heading, body, caption }
- **Project-wide consistency**: e.g. one `dialogue` font applies to all dialogue. User can **add
  custom roles** ("emphasis", "cover-only") and **label what each is for**. Regions reference a
  role; role → concrete font resolved via `FontManager` (family + fallback chain).
- **Colors**: a palette plus named roles (background, accent, text, …).
- **AI assist**: the designer may *suggest* fonts/colors appropriate to the kind; the user always
  overrides. The available choices may be filtered by content kind.
- **Fonts in sharing**: templates reference fonts **by family name**; full bundles **embed font
  files** (license permitting; warn otherwise).

**Acceptance:** changing the project's `dialogue` font updates every dialogue region; a user-added
"emphasis" role with its own font is selectable per text region.

---

## 8. Subsystem E — Save / export / import

| Artifact | Format | Contains | Phase |
|---|---|---|---|
| **Project** | `.iaiproj.json` | `DocumentSpec` + `ProjectStyle` + history | 1 |
| **Layout template** | `.iailayout.json` | structure + shapes + styles + prompt scaffolding, **no content** | 3 |
| **Full bundle** | `.iaibundle` (zip) | project JSON + referenced images + embedded fonts | 5 |
| **Final output** | PNG-per-page, **PDF** | rendered pages (WYSIWYG from scene via `QPdfWriter`) | 4 |

- Project save/load extends the current `.layout.json` round-trip (dataclass (de)serialize),
  adding style + history + region shape/content. Provide a one-time migration for any existing
  `.layout.json`.
- Template export strips content, keeps geometry/shape/style + per-region `prompt` scaffolding so
  a recipient can apply it and fill their own content.

**Acceptance:** save a project and reload it byte-faithfully (incl. history); export a template,
import it into a fresh project, and get the same structure with empty content; export a page to
PDF that matches the on-screen layout.

---

## 9. Subsystem F — Content filling (phased)

- **F-MVP (Phase 4):** select an image region → **import an image file** *or* pick from the
  existing generated-image history (`ImageHistoryDialog`) → fills the placeholder honoring fit
  mode. Select a text region → **edit text** (inline / inspector). This alone yields a finished,
  exportable page.
- **F-AI (Phase 5):** per-region **AI prompt help from the project theme**; **"Send to Image
  tab"** pre-configures the Generate tab (size derived from region px + DPI, prompt,
  provider/model) and places the result back into the region by a pending-region id; **batch** all
  image-region prompts via the existing Batch API and auto-place by region id; **"layout-complete
  mode"** = a task dropdown that populates the Image tab per region.

**Acceptance (F-MVP):** a user fills every region of an AI-designed page with imported images and
typed text and exports a correct PDF, with **no** AI content features required.

---

## 10. Phase plan

> The whole vision is specced here; implementation lands in order. Each phase is independently
> demoable. Phase 1's modules (`page_sizes`, `schema`, `qt_renderer`) are largely independent and
> are good candidates to fan out to parallel agents at implementation time (the "dynamic
> workflow" the user requested).

1. **Phase 1 — Foundation.** `models`/`schema`/`page_sizes` refactor; `qt_renderer` (scene + PNG/PDF);
   functional `canvas_widget` (rect + polygon); page setup (A); project save/load.
   *Outcome:* create/edit/save/render a page by hand, any size/orientation.
2. **Phase 2 — AI designer.** `LayoutDesigner` + `designer_panel` + iterate loop + status console
   (B); `history_window` (C).
   *Outcome:* describe → AI designs → iterate → browse/restore history.
3. **Phase 3 — Style & sharing.** Project style system (D); template export/import (E, templates).
   *Outcome:* per-project fonts/colors/roles; share layouts.
4. **Phase 4 — Content MVP.** Import images + edit text (F-MVP); PNG/PDF export polish.
   *Outcome:* finished publications end-to-end.
5. **Phase 5 — AI content & bundles.** Prompt-gen, Image-tab handoff, batch, layout-complete mode
   (F-AI); full `.iaibundle` export/import (E, bundles).
   *Outcome:* AI-assisted content production and full self-contained sharing.

---

## 11. Cross-cutting requirements

- **LLM logging (repo rule §8):** every request (provider, model, temperature, full prompt) and
  full response shown in the status console **and** written to the file logger, including LiteLLM
  internals. Empty responses handled with fallbacks; JSON parsed robustly.
- **Error logging:** all errors, including any shown to the user, logged per-user in a
  platform-independent way.
- **Model IDs:** resolve via `resolve_model()`; never hardcode `claude-*`/`gpt-*`/`gemini-*`.
- **Images:** always **scaled, not cropped** (honor fit modes).
- **Gemini specifics** (when used downstream for content): aspect ratio via `image_config`, never
  in prompt text; production model `gemini-2.5-flash-image`.
- **Config access:** via `ConfigManager` (`config.get_api_key()`), never raw dict.

---

## 12. Risks & mitigations

- **Polygon editing UX is non-trivial.** Mitigate: Phase 1 ships rect editing + polygon *render*;
  polygon vertex-editing handles can land late in Phase 1 / early Phase 2. AI can still *emit*
  polygons before manual vertex editing exists.
- **WYSIWYG text fidelity** (Qt text metrics vs. desired wrapping/hyphenation). Mitigate: port the
  existing wrap/hyphenation logic into the Qt path; snapshot-test a few reference pages.
- **AI emitting invalid geometry.** Mitigate: `schema.py` clamps/normalizes; fallback layout.
- **Font embedding licensing** in bundles. Mitigate: embed only when permitted; otherwise warn and
  reference by name.
- **Migration of existing `.layout.json`.** Mitigate: one-time loader shim.

---

## 13. Out of scope (this spec)

- Multi-user real-time collaboration.
- Cloud sync of projects/templates.
- CMYK/print-shop color management (RGB export only; note bleed helper).
- Non-page media (the existing video subsystem is untouched).
