# Task 1 report: Godot 4 `SpriteFrames` `.tres` exporter

## What I implemented

Transcribed the brief's verified prototype verbatim, no deviations:

- `core/sprite/exporters/godot_tres.py` — `export_godot_tres(meta, out_tres, *, atlas_res_path) -> Path`,
  `render_godot_tres(meta, *, atlas_res_path) -> str`, `ordered_frame_indices(tag) -> List[int]`.
  Pure stdlib (`pathlib`, `logging`), imports `FrameMeta`/`SheetMeta`/`TagMeta` from
  `core.sprite.models`, `ms_to_fps` from `core.sprite.timing`, `write_image_sidecar` from
  `core.utils`. No Qt import (verified with grep, see below).
- `tests/sprite/golden/godot.tres` — golden fixture, exact content from the brief.
- `tests/sprite/test_godot_tres.py` — 8 tests, exact content from the brief.

Behavior: one `AtlasTexture` sub-resource per frame (`region` from `frame`, `margin` only when
`trimmed` and the margin tuple is non-zero); `load_steps = 1 (ext) + len(frames) (sub) + 1
(resource)`; per-tag `animations` entries use `ordered_frame_indices` to unroll `reverse` /
`pingpong` / `pingpong_reverse` directions into an explicit frame sequence (SpriteFrames has no
direction field), then `ms_to_fps` to derive `speed` (fps) and per-frame `duration` multipliers;
`loop` is `false` when `tag.repeat != 0`, else `true`. `render_godot_tres` raises `ValueError` on
empty frames or an unfilled `sheet_size == (0, 0)` (i.e. before `export_grid` has run).
`export_godot_tres` writes the `.tres` text then a JSON sidecar via `write_image_sidecar`
(`format: "godot_tres"` plus atlas path, title, profile, frame/tag counts, app, version).

## Tests + results

Target suite:
```
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_godot_tres.py -v
```
```
tests/sprite/test_godot_tres.py::test_export_matches_golden_after_whitespace_normalization PASSED
tests/sprite/test_godot_tres.py::test_export_writes_json_sidecar PASSED
tests/sprite/test_godot_tres.py::test_load_steps_is_ext_plus_subs_plus_resource PASSED
tests/sprite/test_godot_tres.py::test_margin_only_on_trimmed_frames PASSED
tests/sprite/test_godot_tres.py::test_loop_false_when_repeat_set PASSED
tests/sprite/test_godot_tres.py::test_pingpong_and_reverse_are_unrolled PASSED
tests/sprite/test_godot_tres.py::test_requires_filled_grid_rects PASSED
tests/sprite/test_godot_tres.py::test_requires_frames PASSED
8 passed in 2.39s
```

Path guard (contract gate):
```
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q
```
```
3 passed in 2.68s
```

Full `tests/sprite` (module I touched has other tests under `tests/sprite/`, per contract §Gate),
excluding the concurrent implementer's in-progress `test_aseprite_native.py` (imports
`core.sprite.exporters.aseprite_native`, which does not exist yet on this branch — not my file,
not committed by that task yet, correctly out of scope):
```
QT_QPA_PLATFORM=offscreen $PY -m pytest tests/sprite -q --ignore=tests/sprite/test_aseprite_native.py
```
```
705 passed, 2 warnings in 117.06s
```
The 2 warnings are pre-existing `DeprecationWarning`s from `google._upb._message` inside
`tests/sprite/gui/test_main_window_sprite_wiring.py`, unrelated to this module.

No-Qt check:
```
grep -n -iE "qt|PySide|PyQt" core/sprite/exporters/godot_tres.py
```
No matches (exit 1).

## Files changed

- `core/sprite/exporters/godot_tres.py` (new)
- `tests/sprite/golden/godot.tres` (new)
- `tests/sprite/test_godot_tres.py` (new)

Commit: `a6ea74c feat(sprite): Godot 4 SpriteFrames .tres exporter with golden test`

## Self-review

- Completeness vs. brief: all three interfaces present with the brief's exact signatures; golden
  file byte-for-byte from the brief; test file byte-for-byte from the brief.
- Names match the brief exactly (`export_godot_tres`, `render_godot_tres`,
  `ordered_frame_indices`, `GODOT_FORMAT`).
- No overbuilding — implementation is the brief's prototype, unmodified.
- Tests verify real behavior: golden-file match (whitespace-normalized), sidecar presence and
  content, `load_steps` arithmetic, margin-only-on-trim, loop flag from `repeat`, direction
  unrolling (all four directions incl. degenerate single-frame ping-pong), and both `ValueError`
  guard paths.
- Test output pristine: no warnings from this module's own tests.

## Concerns

None. Working tree left with only the pre-existing unrelated changes (deleted root `*.md`,
untracked `Notes/*.md`, `feature-documenter.skill.zip`, `.superpowers/`) plus the other
implementer's in-progress `core/sprite/exporters/aseprite_native.py` /
`tests/sprite/test_aseprite_native.py`, none of which I touched or staged.

## Fix round 1: escape strings embedded in the .tres output

**Finding (plan-mandated Important, ruled FIX):** `render_godot_tres` interpolated `tag.name`
and `atlas_res_path` into the `.tres` text unescaped. A tag name or path containing `"` or `\`
produced a syntactically broken Godot resource (an unterminated string literal).

**What changed** — `core/sprite/exporters/godot_tres.py`:
- Added `_escape(text: str) -> str`: replaces `\` with `\\`, then `"` with `\"` (order matters —
  escaping the backslash first prevents double-escaping the quote's backslash).
- Applied `_escape` to `tag.name` in `_animation_block`'s `"name": &"..."` field.
- Applied `_escape` to `atlas_res_path` in the `[ext_resource ... path="..."]` line.
- Checked the rest of the file for other user-text interpolation: the sidecar JSON (`title`,
  `profile`, `tags`, `app`, `version`) goes through `json.dumps` inside `write_image_sidecar`,
  which already escapes correctly — no `.tres`-text interpolation there. No other user-controlled
  string reaches the `.tres` body (frame `name` fields are not emitted; only numeric rect/margin
  values and the tag name / atlas path are).

**Test added** — `tests/sprite/test_godot_tres.py::test_tag_name_with_quotes_and_backslash_is_escaped`:
builds a `SheetMeta` with a tag named `he said "run"\now`, asserts the rendered text contains the
escaped form `he said \"run\"\\now`, and asserts `export_godot_tres` still succeeds (writes the
file without raising).

**Golden file / existing tests:** unchanged — `tests/sprite/golden/godot.tres` contains no quotes
or backslashes in its interpolated fields (`res://hero.png`, `walk`, `idle`), so escaping is a
no-op there and the golden-comparison test stays byte-identical.

**Gate:**
```
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
  /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_godot_tres.py \
  /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py \
  -q -p no:cacheprovider
```
```
............                                                             [100%]
12 passed in 4.27s
```
Pristine — no warnings.

**Files changed:** `core/sprite/exporters/godot_tres.py`, `tests/sprite/test_godot_tres.py`
(2 files, 16 insertions, 2 deletions).

**Commit:** `142839b fix(sprite): escape strings embedded in the Godot .tres output`

**Working tree after commit:** only my two files staged/committed. Other implementers' concurrent
untracked work (`core/sprite/exporters/aseprite_native.py`, `engine_presets.py`,
`tests/sprite/test_aseprite_native.py`, `test_engine_presets.py`, `test_pose_steps.py`) left
untouched, plus the pre-existing unrelated root-doc changes.
