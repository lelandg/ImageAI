# Layout CLI — Design Spec

**Last Updated:** 2026-06-28 21:18
**Status:** Design approved; implementation plan pending
**Author:** Leland Green (with Claude Opus 4.8)

## 1. Problem

The Layout tab exposes ~65 user-facing features in the GUI, but **none** are
reachable from the CLI. `cli/parser.py` / `cli/runner.py` define flags only for
image generation, key management, batch API, and lyrics-to-prompts; a `grep` for
"layout" across `cli/` returns zero matches, and `cli/commands/__init__.py` is
empty. The underlying engine in `core/layout/` is GUI-agnostic and already
callable, but it is wired only through PySide6 signals/slots.

This spec adds a first, coherent CLI surface for the Layout feature so that
layouts can be **designed, filled, and rendered** from scripts/CI without
launching the GUI.

## 2. Scope

In scope (Phase 1): three commands.

| Command | Purpose | Qt required? |
|---------|---------|--------------|
| `--layout-design "<desc>"` | LLM generates a layout project from a description | No |
| `--layout-fill <project>` | Generate images for all prompted image regions | No |
| `--layout-export <project>` | Render a project to PDF/PNG | **Yes** (PySide6) |

Out of scope (deferred): standalone tiling/bundle/template/region-op commands
(internal building blocks, not user verbs); the Google Batch API fill path; any
interactive geometry/overlay editing.

## 3. Decisions (locked)

1. **Fill engine:** synchronous per-region generation via the existing provider
   pipeline (the same path `--prompt` uses). Works for any provider, returns
   immediately. (Not the Google-only async Batch API in
   `core/layout/batch_fill.py`.)
2. **CLI surface:** flat action flags in an argument group, consistent with the
   current parser (`--prompt`, `--batch`, `--lyrics-to-prompts`). No subcommands.
3. **Fill output:** in-place by default (update the project's image regions and
   save back to the same file); `-o` overrides to write a new project file.

## 4. CLI Surface

New `layout` argument group in `cli/parser.py`:

```
Actions (choose one):
  --layout-design "<description>"   Generate a layout project from a description
  --layout-export <project>         Render a project (.iaiproj.json/.layout.json) to PDF/PNG
  --layout-fill <project>           Generate images for all prompted image regions

Layout options:
  --content-kind {comic,comic_strip,childrens_book,magazine,newspaper,scientific,custom}
  --page-size <A4|Letter|A3|A5|Tabloid|Square|...>   (design; default Letter)
  --orientation {portrait,landscape}                  (design; default portrait)
  --dpi N                          (design page geometry + export resolution; default 300)
  --layout-llm-provider {openai,anthropic,google,ollama,lmstudio}   (design)
  --layout-llm-model <model>       (design; default = provider's first registry model)
```

Reused existing flags:
- `-o/--out` — design: project `.json` (required); export: `.pdf`/`.png`
  (required); fill: optional (in-place when omitted).
- `--provider` / `-m/--model` — the **image** provider/model used by `--layout-fill`
  per-region generation. Distinct from `--layout-llm-provider`/`--layout-llm-model`,
  which select the *text* LLM used by `--layout-design`. (The image `--provider`
  choices are google/openai/stability/local_sd; the layout LLM set is wider —
  includes anthropic/ollama/lmstudio — which is why design needs its own flags.)

**Export format inference:** from the `-o` extension — `.pdf` → PDF (all pages in
one document via `export_document_pdf`), `.png` → PNG. A multi-page project
exported to PNG writes `out-001.png, out-002.png, …`; a single page writes the
exact `-o` path.

## 5. Components

- **`cli/commands/layout.py`** (new) — three handlers and small private helpers:
  - `run_design_cmd(args, config) -> int`
  - `run_fill_cmd(args, config) -> int`
  - `run_export_cmd(args, config) -> int`
  - `_page_px(page_size, orientation, dpi) -> (w, h)` — resolve page geometry.
  - `_assemble_document(result, page_px, content_kind) -> DocumentSpec` — the one
    genuinely new piece of logic (see §8).
  - `_export_format(out_path) -> "pdf" | "png"` — extension inference.
  - `_with_offscreen_qapp(fn)` — headless `QGuiApplication` bootstrap for export.
- **`cli/parser.py`** — one new argument group; no other changes.
- **`cli/runner.py`** — three dispatch branches in `run_cli()`, mirroring how
  `--lyrics-to-prompts` routes to `handle_lyrics_to_prompts`.
- **`cli/commands/__init__.py`** — gets its first real content (re-export the
  handlers, or leave as a package marker; implementer's choice).

## 6. Data Flow

**design**
```
(page-size, orientation, dpi) -> page_px
designer.build_messages(content_kind, page_px, description)
  -> designer.run_completion(config, llm_provider, llm_model, messages)   # LiteLLM
  -> designer.parse_response(content, page_px) -> DesignerResult
  -> _assemble_document(result, page_px, content_kind) -> DocumentSpec
  -> project_io.save_project(doc, out)
```
Pure Python; no Qt. LLM request/response logged comprehensively (AGENTS.md §8).

**fill**
```
project_io.load_project(path) -> doc
for each image region with a non-empty prompt:
    generate via existing provider pipeline (provider/model from --provider/-m)
    save image bytes to the images dir
    region.image_ref = <saved path>
project_io.save_project(doc, out or path)   # in-place when -o omitted
print summary: filled / skipped(no prompt) / failed
```

**export**
```
project_io.load_project(path) -> doc
_with_offscreen_qapp:
    if format == pdf: qt_renderer.export_document_pdf(doc, out, dpi)
    else:             per page -> qt_renderer.save_page_png(page, out_i)
```

## 7. Error Handling (AGENTS.md "all errors logged")

- **Export without PySide6** → clear, actionable error
  (`Layout export requires PySide6 — install with: pip install PySide6`) and
  non-zero exit. Design/fill never import Qt.
- **LLM parse failure** → `designer.fallback_result` already degrades to a
  single full-page frame; logged. The project still saves so the user can edit.
- **Bad inputs** → explicit messages + non-zero exit for: missing/invalid
  project file, unknown `--page-size`, missing `-o` where required, `-o`
  extension not `.pdf`/`.png` for export.
- **Fill** → per-region failures are logged and skipped; the command exits
  non-zero if any region failed, after attempting all regions.
- All user-facing errors go through the project logger (platform-independent).

## 8. The one new piece: DesignerResult → DocumentSpec

There is no existing assembler that turns a `DesignerResult` into a standalone
`DocumentSpec` — the GUI applies results onto a live, already-constructed
document. `_assemble_document` must:

1. Build a `PageSpec` sized to `page_px` (background per content-kind default).
2. Attach `result.regions` (or `fallback_result`'s single region) and
   `result.overlays`.
3. Apply content-kind style defaults from `core/layout/styles.py` so saved
   projects open in the GUI with sensible typography.
4. Wrap in a `DocumentSpec` with one page and save via `project_io`.

This is the only component needing fresh logic + dedicated tests; everything
else is wiring to existing, already-tested functions.

## 9. Testing

Follow the existing pytest conventions (the suite is ~346 tests).

- **Parser:** new flags parse; mutual selection of an action; `-o` plumbing.
- **`_page_px`:** page-size + orientation + dpi → expected pixel dims.
- **`_export_format`:** `.pdf`/`.png`/other.
- **design handler:** `run_completion` mocked to return a known JSON →
  asserts a schema-valid project file is written with the expected regions and
  overlays; fallback path when the LLM returns junk.
- **`_assemble_document`:** regions/overlays/styles present; single-page doc.
- **fill handler:** provider mocked → `image_ref` set on prompted regions,
  no-prompt regions skipped, project saved; failure path logs, continues, and
  yields non-zero exit.
- **export handler:** guarded on PySide6 availability (skip when absent, matching
  the GUI-test convention); when present, render a tiny project to a temp
  PDF/PNG and assert the output exists and is non-empty.

## 10. Non-goals / future

- Google Batch API fill path (async, up to 24h) — could later mirror the existing
  `--batch/--batch-status/--batch-fetch` flags.
- Tiling/bundle/template/region-op standalone commands.
- Interactive geometry/overlay editing from the CLI.
