# Comic Layout — AI Designer Extension (sub-project #4 of 5)

**Status:** Design approved 2026-06-27. Ready for implementation plan.
**Branch:** `feat/comic-layout-geometry-core` (all 5 comic-layout sub-projects share one branch).
**PR gate:** Do NOT open a PR — the single PR comes only after sub-project #5.

## 1. Goal

Extend the AI layout designer so it can emit the full geometry surface built by
sub-projects #1–#3, instead of only axis-aligned `rect`/`polygon` regions:

- **Curved / path panels + bleed / borderless** (#1) — via SVG path `d` strings.
- **Tiling presets / gap-free partitions** (#2) — the LLM may request a named
  preset, or free-draw panels.
- **Overlays** (#3) — speech / thought balloons, captions, SFX — placed
  **region-relative** (panel id + normalized offset; tail aimed at a panel) with
  a raw-pixel fallback, resolved to pixels by the designer.

Plus the **`svg⇄segments` converter** that makes curve authoring LLM-native and
round-trippable.

The manual editor (#5) drag-edits whatever #4 emits; #4 makes the AI output
appear end-to-end on the canvas.

## 2. Scope decisions (user-approved)

| Decision | Choice |
|----------|--------|
| Capabilities the AI gains | **All three**: curved/path panels + bleed/borderless, tiling presets, overlays |
| How the LLM expresses curves | **SVG path `d` strings** + a bidirectional `svg_path.py` converter |
| How the AI uses tiling | **Hybrid**: named preset + params **or** free-draw panels per page |
| Overlay placement | **Region-relative** (`anchor_region` + `anchor_offset`; `tail_to_region`) with **raw-pixel fallback**; designer resolves to pixels |
| GUI reach | **Core + minimal apply wiring**: `DesignerResult.overlays` + `apply_designer_result` writes regions+overlays onto the page so AI output renders on the canvas. No new editor controls (those are #5) |

## 3. Architecture

**Approach — "the designer fully resolves."** `parse_response` performs all
expansion — SVG → `PathSegment`s, tiling preset → panel `Region`s,
region-relative anchors → pixel `anchor`/`tail_target` — and returns a
`DesignerResult` carrying concrete `Region`s and `Overlay`s ready to drop onto
the page. The GUI just assigns them. This mirrors how `parse_response` already
returns normalized `Region`s, keeps every hard part **pure and unit-testable**,
and means the canvas (which already renders path regions + overlays via the Qt
renderer) needs **no new rendering code**.

> Rejected alternative: return a high-level intermediate (preset names,
> region-relative overlays) and expand at apply-time. Adds a layer and buys only
> page-resize reflow, which #5's manual editor handles anyway. YAGNI.

### Modules

| Module | Change | Qt? |
|--------|--------|-----|
| `core/layout/svg_path.py` | **NEW** — bidirectional SVG `d` ⇄ `PathSegment` converter | No (pure) |
| `core/layout/designer.py` | **EXTEND** — richer prompt; `parse_response` handles svg-path / tiling / overlays + region-relative anchor resolution; `DesignerResult.overlays` | No (pure) |
| `gui/layout/layout_tab.py` | **EXTEND** — `apply_designer_result` writes `result.overlays` into `pages[0].overlays` | Yes (existing) |

`svg_path.py` and `designer.py` stay Qt-free and headless-importable, consistent
with #1–#3. Only the existing GUI file touches Qt.

## 4. The LLM JSON contract

Extends today's `{ questions?, layout: { regions: [...] } }`. All keys optional;
the LLM may still return `questions`, a `layout`, or both.

```jsonc
"layout": {
  // (A) Optional tiling preset — engine generates gap-free panels:
  "tiling": {
    "preset": "grid | three_tiers | splash_with_strip | diagonal_action | feature_L",
    "params": { "rows": 3, "cols": 2, "gutter_px": 12 }   // preset-specific
  },

  // (B) Regions — rect/polygon as today, PLUS shape:"path" via SVG, plus bleed/stroke.
  //     Coexists with tiling (preset panels + extra free panels) or stands alone.
  "regions": [
    { "id": "p1", "kind": "image", "shape": "path",
      "svg": "M40 40 L380 40 C400 40 400 60 400 80 L400 300 Z",
      "bleed": true, "stroke_px": 6 },
    { "id": "t1", "kind": "text", "shape": "rect", "bbox": [40, 320, 360, 80],
      "role": "caption", "text": "" }
  ],

  // (C) Overlays — region-relative placement resolved to pixels by the designer.
  "overlays": [
    { "id": "o1", "kind": "speech", "text": "Look out!",
      "anchor_region": "p1", "anchor_offset": [0.5, 0.2],  // 0..1 within p1's bbox
      "tail_to_region": "p1",                              // tail aims at p1's center
      "role": "dialogue" },
    { "id": "o2", "kind": "sfx", "text": "BOOM", "anchor": [620, 240] }  // raw-pixel fallback
  ]
}
```

- **Free-draw and presets coexist.** A page may give `tiling`, hand-authored
  `regions`, or both.
- **Raw-pixel `anchor`/`tail_target` remain accepted everywhere** as the
  fallback when the LLM gives explicit pixels.
- **Backward compatible.** Today's `rect`/`polygon` + `bbox`/`points` responses
  parse exactly as before.

## 5. Components & data flow

### 5.1 `core/layout/svg_path.py` (pure)

- `svg_to_segments(d: str) -> List[PathSegment]` — tokenize a path `d` string;
  support `M/m L/l H/h V/v C/c Q/q Z/z` (absolute + relative); track current
  point and subpath start (for `Z` and relative commands). Emit exactly the
  `PathSegment` types the model + renderer already consume
  (`move/line/quad/cubic/close`). Unknown command or malformed number → log a
  warning and return what parsed cleanly (or `[]`); never raise.
- `segments_to_svg(segments: List[PathSegment]) -> str` — inverse, for
  round-trip, export, and showing current geometry back to the LLM on iterate.

### 5.2 `core/layout/designer.py` (extend)

- `build_messages` — document the new contract in `<instructions>`:
  `shape:"path"` + `svg`; `bleed` / `stroke_px`; the `tiling` block with the
  five preset names + params; the `overlays` array with `kind` ∈
  speech/thought/caption/sfx, region-relative placement
  (`anchor_region` + `anchor_offset`, `tail_to_region`), and the raw-pixel
  fallback. Reuses the existing role-name listing.
- `parse_response` — order of operations:
  1. If `tiling` present, call the preset fn (`core/layout/tiling.py`) →
     panel `Region`s.
  2. Parse `regions`: rect/polygon as today; `shape:"path"` → `svg_to_segments`;
     carry `bleed` / `stroke_px`. Append/merge with the tiled panels.
  3. `normalize_region` each resolved region.
  4. Parse `overlays`: resolve `anchor_region` + `anchor_offset` and
     `tail_to_region` against the resolved regions' bboxes into pixel `anchor` /
     `tail_target`; fall back to raw-pixel `anchor` / `tail_target`. Build
     `Overlay`s.
- `_resolve_overlay_anchor(...)` — small pure helper (region-id + normalized
  offset → pixel point). Unknown id → log + drop that one overlay (keep the
  rest); never crash.
- `DesignerResult` gains `overlays: List[Overlay] = field(default_factory=list)`.
  `fallback_result` unchanged (no overlays).

### 5.3 `gui/layout/layout_tab.py` (extend)

- `apply_designer_result`: when `result.overlays`, set
  `pages[0].overlays = list(result.overlays)`, alongside the existing region
  assignment + history append + refresh. (Designer-panel log line mentions the
  overlay count — minor.)

### 5.4 Data flow

```
panel → build_messages → LLM → parse_response
        (resolves SVG→segments, tiling→panels, region-relative anchors→pixels)
      → DesignerResult{regions, overlays, questions}
      → apply_designer_result writes regions + overlays onto pages[0]
      → _refresh → Qt renderer draws them (no new render code)
```

## 6. Error handling (per project rules — all errors logged, never crash)

| Failure | Behavior |
|---------|----------|
| Malformed SVG `d` | Log warning; emit what parsed cleanly or `[]`; region falls back to bbox via the existing renderer guard |
| Unknown tiling preset | Log warning; skip tiling (use explicit regions / fallback) |
| Unknown `anchor_region` / `tail_to_region` id | Log warning; drop that overlay, keep the rest |
| Out-of-page coords | `normalize_region` clamps regions; overlays clamp anchor into page |
| Entirely unparseable response | Existing `fallback_result` (single full-page frame + question) |

All resolution is pure and headless-testable; the live `run_completion` LLM call
stays network/untested as today.

## 7. Testing

Interpreter `.venv_linux/bin/python`; run with `QT_QPA_PLATFORM=offscreen`.
Full layout suite currently **250 passed** on `feat/comic-layout-geometry-core`.

- `tests/layout/test_svg_path.py` (NEW) — round-trips (`segments_to_svg ∘
  svg_to_segments` and back), each command, relative coords, `Z` close,
  malformed-input degradation.
- `tests/layout/test_designer.py` (extend) — parse `shape:"path"` + `svg`
  region; tiling request → expanded gap-free panels; overlays with
  region-relative anchor resolution; raw-pixel fallback; unknown-id / malformed
  degradation; **backward-compat** (today's rect/polygon response unchanged);
  `build_messages` output contains the new capability docs.
- GUI apply test (`qapp`) — a `DesignerResult` carrying overlays lands on
  `pages[0].overlays` and survives a `_refresh` (mirrors existing
  designer/layout_tab tests).

## 8. Provisional task breakdown

(The implementation plan formalizes these; each is a TDD task that keeps the full
suite green and commits with `feat(layout): …`.)

1. `core/layout/svg_path.py` converter (pure, TDD): `svg_to_segments` +
   `segments_to_svg`, malformed-input degradation, round-trip.
2. `DesignerResult.overlays` + overlay parsing + region-relative anchor
   resolution (`_resolve_overlay_anchor`), raw-pixel fallback.
3. `parse_response` geometry: `shape:"path"` + `svg` regions and `bleed` /
   `stroke_px`; tiling-preset request → expanded panels (merge with explicit
   regions).
4. `build_messages` prompt extension documenting all new capabilities +
   prompt-content assertion test.
5. GUI apply wiring (`apply_designer_result` writes regions + overlays) +
   integration test; designer-panel overlay-count log line.

## 9. Out of scope / deferred (not gaps)

- **Manual drag-edit / authoring of the emitted geometry** — sub-project #5
  (knife/split, vertex & curve-handle drag, bleed/borderless toggles, balloon
  placement, tail→region snapping, SFX rotation, contour-aware wrapping).
- **Page-resize reflow of resolved overlays** — anchors resolve to pixels at
  parse time (same as regions today); reflow is an editor concern for #5.
- **PIL export still bypasses overlays** — carried from #1–#3: overlays render in
  the live editor + Qt export, not the PIL `export_dialog.py`. Migrating export
  onto the Qt renderer remains the biggest cross-cutting follow-up for the final
  feature PR.
- **The live `run_completion` LLM call** stays network/untested.

## 10. Self-review

- **Spec coverage:** every approved scope decision (§2) maps to a component
  (§5) and a test (§7); all three new-engine capabilities + the SVG converter +
  the GUI apply wiring are covered. The 5 provisional tasks (§8) cover the whole
  surface with no stub/placeholder left.
- **Internal consistency:** the LLM contract (§4) matches the `parse_response`
  order of operations (§5.2) and the error table (§6); the "designer fully
  resolves" approach (§3) is consistent with the GUI staying a dumb assigner
  (§5.3).
- **Scope:** focused enough for one implementation plan (5 tasks); larger
  authoring work is explicitly deferred to #5 (§9).
- **Ambiguity:** region-relative vs raw-pixel placement is made explicit (both
  accepted; region-relative resolved first, pixel as fallback); tiling and
  free-draw explicitly coexist.
