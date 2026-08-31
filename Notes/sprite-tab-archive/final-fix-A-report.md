# Fix wave A report — engine presets (fix-ir-A)

Scope: `core/sprite/exporters/engine_presets.py`, `tests/sprite/test_engine_presets.py`,
`tests/sprite/test_godot_tres.py`. No other files touched. No git commands run (override 1).

## Important 1 — `_write_png_sequence` returns an incomplete manifest

`core/sprite/exporters/engine_presets.py`, `_write_png_sequence` (was lines 168-169):

```python
def _write_png_sequence(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    pngs = list(export_png_sequence(meta, out_dir / "frames", template=preset.name_template))
    return [p for png in pngs for p in (png, sidecar_path(png))]
```

Now returns each PNG plus its `sidecar_path(png)` sidecar, matching the shape of the sibling
writers (`_write_godot_tres`, `_write_aseprite_native`, `_write_gif`).

**Reversion check:** reverted to the original one-line body (`return
list(export_png_sequence(...))`), ran
`test_manifest_matches_every_file_on_disk_for_web_preview_preset` — **FAILED**
(`AssertionError`, reported list missing the four `frames/*.png.json` entries that are on disk).
Restored the fix, re-ran — **PASSED**.

## Important 2 — GIF sidecar frame count wrong for non-forward tags

`core/sprite/exporters/engine_presets.py`, `_write_gif`:

```python
def _write_gif(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    paths: List[Path] = []
    for tag in meta.tags:
        out = export_gif(meta, tag, out_dir / f"{title}_{tag.name}.gif")
        # export_gif already wrote a sidecar with the correct unrolled frame
        # count plus durations_ms/loop/warnings/timestamp -- merge the preset
        # fields into it instead of overwriting, and derive "frames" the same
        # way the exporter did (ordered_frame_indices), so a pingpong/reverse
        # tag's sidecar never disagrees with the GIF it describes.
        sidecar = read_image_sidecar(out) or {}
        sidecar.update({
            "format": "gif", "title": meta.title, "tag": tag.name, "profile": meta.profile,
            "frames": len(ordered_frame_indices(tag)), "direction": tag.direction,
            "app": meta.app, "version": meta.version,
        })
        write_image_sidecar(out, sidecar)
        paths.extend([out, sidecar_path(out)])
    return paths
```

Checked: `_write_gif` does overwrite the sidecar `export_gif` already wrote (same `sidecar_path(out)`
target) — fixed by reading it back with `read_image_sidecar` and merging the preset fields in, so
`durations_ms`, `loop`, `warnings` and `timestamp` from `export_gif` survive. `ordered_frame_indices`
was already imported at the top of the module (line 12), used as instructed. Added `read_image_sidecar`
to the `core.utils` import line.

**Reversion check:** reverted `_write_gif` to the original body (`"frames": tag.to_index -
tag.from_index + 1`, no merge), ran `test_gif_sidecar_frame_count_reflects_pingpong_unrolling` —
**FAILED** (`assert 4 == 6`). Restored the fix, re-ran — **PASSED**.

## Minor 4 — golden `.tres` comparison collapsed newlines

`tests/sprite/test_godot_tres.py`: replaced `_norm` (`" ".join(text.split())`) and the test
`test_export_matches_golden_after_whitespace_normalization` with:

```python
def _lines(text: str) -> list:
    return [line.rstrip() for line in text.splitlines()]


def test_export_matches_golden_line_by_line(tmp_path):
    out = export_godot_tres(_meta(), tmp_path / "hero.tres", atlas_res_path="res://hero.png")
    assert out.exists()
    assert _lines(out.read_text(encoding="utf-8")) == _lines(GOLDEN.read_text(encoding="utf-8"))
```

Renamed the test to `test_export_matches_golden_line_by_line` since it no longer normalizes
whitespace. `_norm` was used nowhere else in the file, so it was removed rather than left dead.
`golden/godot.tres` was not touched — current output matches it line for line (verified by the
passing test).

**Discriminating check** (no source change to revert here — `godot_tres.py` is out of my file list
and the fix is test-only, so I verified discriminating power directly): rendered the real
`.tres` text, collapsed it to one line the way the reviewer's regression probe did (`"
".join(text.split("\n"))`, i.e. same tokens, no line breaks), and compared it against golden with
both methods:

```
OLD (_norm) comparison on regressed text vs golden: True   <- blind to the regression
NEW (line-by-line) comparison on regressed text vs golden: False  <- catches it
NEW (line-by-line) comparison on GOOD text vs golden: True  <- still passes real output
```

This confirms the old whitespace-normalized comparison would have shipped a line-structure
regression, and the new line-by-line comparison rejects it while still passing the real exporter
output.

## New tests added (per dispatch)

1. `test_manifest_matches_every_file_on_disk_for_web_preview_preset` — mirrors
   `test_manifest_matches_every_file_on_disk_for_atlas_preset` but exercises `web_preview` (which
   contains `png_sequence`, not just atlas formats). Asserts the returned manifest equals a
   recursive disk listing and explicitly checks two `frames/*.png.json` sidecars are present.
2. `test_gif_sidecar_frame_count_reflects_pingpong_unrolling` — builds a single `pingpong` tag over
   4 frames (`from_index=0, to_index=3`), exports `web_preview`, and asserts the sidecar's
   `"frames"` is 6 (4 forward + 2 reflected middle frames from `ordered_frames`/
   `ordered_frame_indices`), not the naive `to_index - from_index + 1 == 4`. Also pins
   `direction`, `title`, `tag`, `profile`, `app`, `version`, and that `export_gif`'s own
   `durations_ms`/`timestamp` fields survived the merge. Added `import json` to the test file's
   imports for this.

Both are discriminating (see reversion checks above).

## Gate commands and output

```
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
  /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_engine_presets.py \
  /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_godot_tres.py -q -p no:cacheprovider
........................                                                 [100%]
24 passed in 2.51s
```

```
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
  /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q -p no:cacheprovider
...                                                                      [100%]
3 passed in 2.83s
```

Also re-ran the engine_presets/godot_tres suite with `-W error::DeprecationWarning` to confirm zero
warnings escape silently — still 24 passed.

`Image.fromarray` calls in the test file (`_png` helper) already omit the deprecated `mode`
argument; no change needed there.

## Files changed

- `core/sprite/exporters/engine_presets.py` — `_write_png_sequence`, `_write_gif`, one import line
  (`read_image_sidecar` added).
- `tests/sprite/test_engine_presets.py` — `import json` added; two new tests added.
- `tests/sprite/test_godot_tres.py` — `_norm` replaced with `_lines`; one test renamed and its body
  changed to line-by-line comparison.

## Self-review

- Names match the dispatch's cited symbols and file paths.
- No file outside the three owned files was touched.
- No scratch file was written inside the repo; scratch copies used for reversion checks lived under
  the session scratchpad and were not committed anywhere.
- Did not commit, stage, or run any git-mutating command.
- `golden/godot.tres` left untouched, as instructed.

## Concerns

None. All three findings fixed as specified, both new tests are discriminating, both gate commands
are pristine (zero warnings), and the golden `.tres` genuinely matches line for line so no
Minor-4-adjacent finding needs reporting.
