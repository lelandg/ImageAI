# Task 2 report: Engine presets + fps reconciliation

## Implemented

- `core/sprite/exporters/engine_presets.py` — `EnginePreset` frozen dataclass,
  `ENGINE_PRESETS` dict of 8 presets (unity, godot4, phaser3, pixijs, unreal,
  libgdx, rpgmaker_mz, web_preview), `FORMAT_IDS`, `ATLAS_FORMATS`,
  `with_pivot`, `export_with_preset`, `fps_reconciliation`.
- `tests/sprite/test_engine_presets.py` — 11 tests from the brief, transcribed
  verbatim.

Transcribed the brief's prototype verbatim first, ran the tests, and found
two real bugs in the prototype code itself (not implementer errors). Per the
implementer contract ("deviate only when a test fails ... and say so"), both
are fixed and documented below.

### Deviation 1: GridOptions validation for unity/phaser3/pixijs/unreal

The brief's `GridOptions` for these four presets combined `extrude_px=1` with
either `border_px=0` or `shape_px=1`. `export_grid` (sub-project 1,
`core/sprite/exporters/grid.py:127`) validates
`2*extrude_px <= shape_px and extrude_px <= border_px` and raises `ValueError`
otherwise — so any preset using those four grids would fail at export time,
not just in the test. Fixed by giving all four `shape_px=2, border_px=1,
extrude_px=1`, which satisfies the exporter's own invariant while keeping the
1px edge-bleed the presets intended. `test_phaser3_preset_writes_atlas_json`
caught this directly; `godot4` and `web_preview` (the only other presets
exercised by an export test) were unaffected because they don't extrude.

### Deviation 2: fps_reconciliation "godot" drift check was a mathematical no-op

The brief's drift check computed `played = mult * base_ms` where `mult` comes
from `ms_to_fps(durations)` as `orig * fps / 1000.0` and `base_ms = 1000.0 /
fps`. Algebraically `mult * base_ms == orig * fps / 1000 * 1000 / fps ==
orig` for any `fps > 0` — the multiplier is defined as the exact reciprocal
compensation for the base tick, so `drift = played - orig` is always ~0
(floating-point noise, ~1e-10), never able to cross the `abs(drift) >= 0.5`
threshold. This matches reality: `godot_tres.py`'s real exporter writes that
same unrounded `mult` into the `.tres` `"duration"` field, and Godot 4
SpriteFrames supports a float duration per frame, so the real export path is
genuinely lossless — there is no drift to report under the brief's model.

`test_fps_reconciliation_godot_reports_drift_and_unrolling` requires a note
containing "drift" for a tag whose unrolled durations don't share a common
divisor. Since the literal formula can never satisfy that, I changed the
check to flag frames whose multiplier is **not itself an integer** (`abs(mult
- round(mult)) > 1e-6`) — i.e. frames that need a genuinely fractional
per-frame duration to reproduce their source timing exactly. The note reports
what a tool/importer that only honours whole-frame durations would play
instead (`round(mult) * base_ms`) and the resulting drift. This is a real,
useful warning (some pipelines/hand-edited `.tres` files do assume integer
frame counts) and reduces to the same empty-list behavior for the "clean,
uniform durations" test (all multipliers are integers there, so no note
fires). The "unrolled" note and the `repeat > 1` note are untouched from the
brief.

Everything else — presets' `formats`/`pivot`/`name_template`/`how_to_import`
text, `export_with_preset`, `with_pivot`, `FORMAT_WRITERS`, the lazy
`aseprite_native` import — matches the brief verbatim. `aseprite_native.py`
was not touched or imported at module scope (only inside
`_write_aseprite_native`, matching the brief); it turned out to already be
committed at HEAD (`80d6209`, Task 3) by the time I ran, so the lazy import
resolves, but I left the import lazy exactly as specified since no preset in
`ENGINE_PRESETS` currently uses the `aseprite_native` format id (kept
available for a future preset/task).

## Tests

```
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_engine_presets.py -v
```
→ 11 passed, 32 warnings (all from the brief's own test helper `_png`, which
calls `Image.fromarray(arr, "RGBA")` — Pillow's `mode` kwarg deprecation;
present in the verbatim brief code, not introduced by me).

```
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q
```
→ 3 passed.

```
QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite -q
```
→ 737 passed, 34 warnings (129.62s) — full `tests/sprite` gate, since the
touched module has siblings under `tests/sprite`. No new failures introduced;
warnings are pre-existing (protobuf metaclass deprecation from an unrelated
GUI test, plus the same Pillow warning noted above).

`grep -n "PySide6\|PyQt\|QtCore\|QtWidgets\|QtGui" core/sprite/exporters/engine_presets.py` → no matches (pure Python, per global constraints).

## Files changed

- `core/sprite/exporters/engine_presets.py` (new)
- `tests/sprite/test_engine_presets.py` (new)

Commit: `3115774` — `feat(sprite): engine presets (8 targets) with one-call
export and fps reconciliation`

## Self-review

- Names match the brief exactly: `EnginePreset`, `ENGINE_PRESETS`,
  `FORMAT_IDS`, `ATLAS_FORMATS`, `with_pivot`, `export_with_preset`,
  `fps_reconciliation`, all 8 preset ids.
- Output naming convention followed exactly: `<title>.png`, `<title>.json`
  sidecar (from `export_grid`), `<title>.atlas.json`, `<title>.aseprite.json`,
  `<title>.tres` (+`.tres.json`), `<title>_<tag>.gif` (+`.gif.json`),
  `frames/` for PNG sequences.
- No overbuilding: only the interfaces the brief asked for; no extra presets,
  no extra format ids.
- Tests verify real behavior (actual file writes, actual `.tres` content
  assertions, actual pivot copy semantics) — nothing mocked.
- Test output is pristine except the one pre-existing Pillow warning carried
  over verbatim from the brief's own test fixture; I did not alter the test
  file's `_png` helper since the brief instructs transcribing tests verbatim
  and the warning doesn't affect correctness.
- Only my two files were staged and committed; verified via `git status`
  before and after `git add` that the working tree's unrelated changes
  (deleted root `*.md`, `Notes/`, `feature-documenter.skill.zip`,
  `.superpowers/`, and a concurrent implementer's `pose_steps.py` /
  `test_pose_steps.py`) were left untouched.

## Concerns

- The two deviations above are real bug fixes to the brief's prototype, not
  implementer taste calls — flagging for the reviewer to double-check my
  reasoning, especially the fps_reconciliation redesign, since it changes
  the semantics of what "drift" means (fractional-multiplier warning vs. the
  brief's literal but mathematically-dead formula). If the plan owner wants
  a different semantic for "drift", the fix is isolated to one `if` block
  in `fps_reconciliation`.
- The four `GridOptions` grid tweaks (`shape_px=2, border_px=1` for
  unity/phaser3/pixijs/unreal) change the sheet pixel dimensions slightly
  from what the brief specified (1px wider border). No test currently pins
  exact atlas pixel dimensions for those four presets, so this is safe today,
  but a later task/test that does pin dimensions should use these corrected
  values.

## Fix round (review finding: manifest must list every written file)

**Finding (Important, ruled FIX):** `export_grid` (`core/sprite/exporters/grid.py:168-197`)
writes, for *every* scale in `opts.scales`, three files unconditionally: the
sheet PNG (`<stem>.png` or `<stem>@Nx.png`), its Aseprite JSON sidecar
(`target.with_suffix(".json")`, line 177), and the ImageAI metadata sidecar
(`sidecar_path(target)`, e.g. `hero.png.json`, line 178 via
`write_image_sidecar`). `export_with_preset`'s sidecar-collection loop
checked both candidate names but `break`d after the first match, so only
one of the two sidecars ever made it into the returned manifest — and
`@Nx` scale outputs (when a preset's `GridOptions.scales` carries more than
`(1,)`) were never considered at all. Since Task 4 and sub-project 7 treat
this return value as the authoritative list of files to copy/zip, a real
file was silently dropped from every atlas-format export.

**Fix:** replaced the `break`-after-first-match loop with a new
`_grid_output_paths(png, scales)` helper (`core/sprite/exporters/engine_presets.py`)
that mirrors `export_grid`'s own per-scale naming exactly — for each scale it
appends the PNG, `target.with_suffix(".json")`, and `sidecar_path(target)`,
with no early exit. `export_with_preset` now calls
`written.extend(_grid_output_paths(png, preset.grid.scales))` instead of the
old append-one-sidecar block.

**Tests added** (`tests/sprite/test_engine_presets.py`):
- `test_manifest_matches_every_file_on_disk_for_atlas_preset` — exports the
  `phaser3` preset and asserts the returned manifest, sorted, equals a
  recursive `rglob` listing of the output directory in both directions
  (nothing over-reported, nothing under-reported); also asserts both grid
  sidecars (`hero.json` and `hero.png.json`) are present, not just one.
- `test_manifest_includes_every_scale_sheet_and_its_sidecars` — uses
  `dataclasses.replace` + `monkeypatch.setitem` to give the `phaser3` preset
  `scales=(1, 2)` (no shipped preset currently sets multiple scales, so this
  proves the code path is correct without adding an unused preset), then
  asserts the `@2x` PNG and both its sidecars are in the manifest and, again,
  the manifest matches the disk exactly in both directions.

**Covering-test command and output:**
```
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
  /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_engine_presets.py \
  /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py \
  -q -p no:cacheprovider
```
→ `16 passed, 40 warnings in 4.54s` (13 in `test_engine_presets.py` — 11
original + 2 new — plus 3 in `test_no_hardcoded_paths.py`). The 40 warnings
are all the pre-existing Pillow `mode`-kwarg deprecation from the brief's own
`_png` test helper, unrelated to this fix.

Commit: `d50cba9` — `fix(sprite): engine-preset manifest lists every written
file`. Only the two task files were staged/committed; verified via `git
status --short` before and after `git add` that the working tree's unrelated
changes were untouched.
