# Layout tab — UX fixes (2026-06-25)

Four user-reported fixes to the Layout tab, on `feat/layout-ai-designer-phase4`.

## 1. Designer output collapsed by default
`gui/layout/designer_panel.py` — the LLM status console now starts hidden behind a
`▶ Show designer output` toggle button; clicking expands it (`▼ Hide…`). It still
**auto-expands on failure** (`_on_failed`) so errors are never hidden — satisfies the
"all LLM errors shown to the user" rule.

## 2. Fonts populated with system fonts (in the background)
- New `gui/layout/font_loader.py` — `FontLoader(QThread)` enumerates
  `QFontDatabase.families()` off the GUI thread and caches the list process-wide
  (`cached_families()`); emits `loaded(list)` once. Failure → logs + empty list.
- `gui/layout/content_inspector.py` — the text editor now has a **Font** (editable
  combo, system fonts) + **Size** spin. Combo fills from the background loader; a
  family typed before the list arrives is preserved.

## 3. Text boxes always visible in the editor (and editor-only)
`core/layout/qt_renderer.py` — the text-region guide box used a 1px dashed pen that
vanished once fit-to-view shrank a 300-DPI page; only Qt's selection outline made it
visible. Pen is now **cosmetic** (`pen.setCosmetic(True)`, constant on-screen width at
any zoom) and a touch darker, so empty text boxes are always visible in the editor.
The dashed guide is now **editor-only**: `_add_text_region` draws it only when
`selectable=True`, so it no longer appears in exported PNG/PDF (those call
`build_scene(selectable=False)`). The text itself still renders in export.

## 4. Applied text was invisible / tiny
Root cause: a text region with no explicit `text_style` and no resolvable role left the
`QFont` at its ~16px default — invisible on a multi-thousand-pixel page.
- `core/layout/qt_renderer.py` — always pins a pixel size; falls back to a readable
  `_DEFAULT_TEXT_PX = 48` when nothing resolves.
- `core/layout/styles.py` — extracted `effective_text_style(region, project_style)`
  (explicit style > role > default role > None); shared by the renderer and inspector
  so they can't drift.
- The inspector now shows each text box's **resolved** family/size on selection (via
  `LayoutTab._on_region_selected` passing the resolved style), and "Apply text" emits
  `regionTextStyleChanged(region_id, family, size_px)`. `LayoutTab._on_region_text_style_changed`
  writes it as an explicit per-region `text_style` and re-renders, so the user can make
  text any size they want.

## Tests
+15 tests (112 total in `tests/layout/`, all green): styles resolver precedence;
renderer cosmetic pen + fallback size; inspector font controls + style signal; designer
console collapse/auto-expand; layout-tab font-style apply path.

Note: `tests/test_ltx_video.py` (untracked WIP) fails to import `providers.ltx_video` —
pre-existing, unrelated to these changes.
