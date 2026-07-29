# Curved Text for Layout Overlays — Design

**Date:** 2026-07-29
**Status:** Implemented
**Branch:** `feat/layout-curved-text`

## Goal

Let layout overlays render their text along an editable curve — the classic
arched book-cover title — with the curve creatable and editable by dragging
handles on the GUI canvas, hand-editable in the project JSON, and authorable
by the AI designer. First consumer: the NISF book-cover layout ("Nobody Is
Switching Faces"), which needs two gently arched title lines and a script
byline over full-bleed art.

Out of scope (explicitly deferred): warped/distorted letterforms
(WordArt-style arch/bulge), curved text inside speech/thought balloon bodies,
text on closed paths or multi-subpath curves.

## Decision

**Approach A — an optional `text_path` field on the existing `Overlay`
model, honored for `caption` and `sfx` kinds.** A single open quadratic
Bézier (start, control "bow", end) is the only curve shape in v1.

Rejected alternatives:

- **New overlay kind `curved_text`** — the kind literal is validated in five
  places (`models.py`, `schema.py`, `designer.py`, `balloons.py`,
  `layout_tab.py`); a field on existing kinds is strictly less churn for the
  same capability.
- **Parametric arc (chord + bow amount)** — simpler math but invents a new
  geometry vocabulary instead of reusing `PathSegment`/SVG path data, cannot
  express S-curves, and is awkward for the AI designer. The quad Bézier's
  middle control point *is* the bow control, so approach A gets the same UX.

## Schema & model

- `Overlay.text_path: Optional[List[PathSegment]] = None` in
  `core/layout/models.py`. Exactly one `move` + one `quad` segment in v1;
  `core.layout.geometry.validate_segments` plus a new
  `validate_text_path(segments)` guard (open path, 2 segments, finite
  coords) applied on load and on editor commit.
- Serialized in `core/layout/schema.py` as an SVG d-string —
  `"text_path": "M x y Q cx cy x y"` — via the existing
  `svg_path.segments_to_svg` / `svg_to_segments`. Absent/None → key omitted,
  so old files round-trip byte-identical. Older builds drop the key on load
  (existing `overlay_from_dict` behavior) — acceptable degradation to
  straight text.
- `OVERLAY_JSON_SCHEMA` gains the optional `text_path` string property (and
  the already-shipped-but-undocumented `rotation`, fixing that drift).
- `TextStyle` gains `outline_px: float = 0.0` and
  `outline_color: str = "#000000"` (`core/layout/models.py`), serialized via
  the already-forgiving `_filtered` loader. Applied only by the curved-text
  renderer in v1 (straight text keeps QTextDocument rendering untouched).
- Coordinates are page pixels, same space as region paths and overlay
  anchors. `anchor` stays meaningful as the fallback position when
  `text_path` is removed and for inspector nudging; the curve itself is
  authoritative for placement while set.

## Rendering (`core/layout/qt_renderer.py`)

New branch at the top of `_add_overlay`: if `ov.text_path` is set (and kind
is `caption`/`sfx`), render curved text and skip the balloon body entirely.

- Build a `QPainterPath` from the segments (`segments_to_painter_path`).
- Lay out per glyph (grapheme cluster) with `QFontMetricsF`: advance widths
  plus `text_style.letter_spacing` (this field is currently dead in the Qt
  renderer; curved text honors it).
- Alignment from `text_style.align`: starting arc-length offset 0 (left),
  `(pathLen − textLen)/2` (center, default), `pathLen − textLen` (right).
  Text longer than the path renders anyway (glyphs past the end continue
  along the exit tangent) — no silent truncation.
- Each glyph: distance at its advance midpoint → `percentAtLength` →
  `pointAtPercent` + `angleAtPercent`; add the glyph outline to one combined
  path with `QPainterPath.addText` under a rotate+translate transform, so
  the glyph's horizontal center-baseline point sits on the curve.
- Emit a single `QGraphicsPathItem`: brush = `text_style.color`, pen =
  `outline_px`/`outline_color` (no pen when 0). One item → selection,
  z-order, opacity, and `rotation` (about the anchor, unchanged semantics)
  all behave like today's overlays, and PNG/PDF export is identical to the
  canvas because both use this one renderer.

## GUI editing

- **Create:** the overlay inspector (`gui/layout/`) gets a "Curve text"
  toggle for caption/sfx overlays. On: seed a gentle default arc — chord
  centered on the current anchor, width ≈ the text's straight advance,
  bow ≈ 12% of chord (flatter than the sample cover, per Leland). Off:
  `text_path = None` (text falls back to the straight block at `anchor`);
  the path is kept in the undo snapshot but not in the model.
- **Edit:** `OverlayEditor` (`gui/layout/overlay_editor.py`) grows three
  `_OvHandle`s (`tp0` start, `tpc` bow, `tp1` end), added alongside the
  existing body/tail handles. Dragging a handle updates its own position
  live and writes the new coordinate into `ov.text_path` immediately, but
  the scene refresh is suspended for the duration of the drag (matching the
  existing overlay/geometry editor UX) — so the rendered curved-text item
  itself does not redraw until mouse release, when `commit()` re-enables
  refresh, validates the path, and calls `snapshot_and_refresh`. Numeric X/Y
  spinboxes for the three points were dropped in favor of this drag-handle +
  hand-editable-JSON combination.
- Inspector shows the "Curve text" toggle plus the outline controls,
  following the existing overlay-inspector patterns.

## AI designer & CLI

- `core/layout/designer.py`: prompt contract documents the optional
  `"text_path": "M .. Q .."` key on caption/sfx overlays (same SVG-path
  dialect it already emits for region `svg`); `_build_overlay` parses it
  with `svg_to_segments`, validates, and drops it with a warning on bad
  data. While here, `_build_overlay` also stops silently discarding
  `rotation` — pre-existing drift adjacent to this feature.
- CLI: no new flags. `--layout-design` may emit curved overlays;
  `--layout-export` renders them; hand-editing the project JSON works
  because the d-string is human-writable.

## Error handling

- Malformed `text_path` on load (bad d-string, closed path, wrong segment
  count): log a warning, treat as None — never crash a project open.
- Empty text with a path: render nothing (no crash), keep the path.
- Missing font family: existing Qt font-DB fallback applies unchanged.

## Testing (`tests/layout/`)

- `test_overlay_text_path_schema.py`: to/from dict round-trip, omitted key
  for None, malformed d-string → None + warning, old-file load unaffected.
- `test_text_path_layout.py`: pure-math checks on glyph placement —
  arc-length offsets monotonic, center alignment symmetric, letter_spacing
  shifts offsets, tangent angles match the curve.
- `test_overlay_text_path_render.py`: Qt smoke test à la
  `test_overlay_render.py` — pixels darken along the arc, not at the chord
  midpoint; outline_px widens coverage.
- `test_overlay_editor_text_path.py`: handle count, drag writes back,
  commit validates — à la `test_geometry_editor_drag.py`.
- Designer: `_build_overlay` accepts/rejects `text_path` correctly.

## Consumer deliverable (separate repo)

After the feature merges to the working branch, create
`NISF/Layouts/cover-layout.json` (schema 2.0): 2475×3300 px page (8.25×11"
@ 300 dpi), full-bleed image region → `Images/Generated/cover/Cover-no-text.png`,
three curved overlays — "NOBODY IS" and "SWITCHING FACES" (with the word
space the sample lacks) on gentle downward arcs (~⅓ the sample's bow),
"By Janelle G." on a near-flat arc — gold `#F2D48A` fill, dark-brown
outline, serif title face (Cinzel/EB Garamond fallback chain) + script
byline face, all left live for editing in the GUI. Verify with
`--layout-export … -o preview.png` and visual inspection before handoff.
