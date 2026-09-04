# Task 3 report: native `.aseprite` writer

## What I implemented

- `core/sprite/exporters/aseprite_native.py` — native `.aseprite` binary writer plus a
  test-only reader, transcribed verbatim from the brief's byte layouts (header 128 bytes,
  frame header 16 bytes, chunk header 6 bytes; Layer/Cel/Color-Profile/Tags/Palette chunks).
  - `export_aseprite(meta: SheetMeta, out_ase: Path) -> Path`: writes one RGBA layer named
    "Sprite" and one zlib-compressed cel (type 2) per frame. Frame 0 also carries a Color
    Profile chunk (sRGB), an optional Palette chunk (only when `meta.palette` is set), the
    Layer chunk, and a Tags chunk (only when `meta.tags` is non-empty). Frames larger than
    `cell_size` are fitted proportionally via `Image.thumbnail` and centered (never
    distorted, per the project's image-scaling rule). Writes a `.json` sidecar through
    `core.utils.write_image_sidecar`. Raises `ValueError` on empty frames or an invalid
    `cell_size`.
  - `read_aseprite_summary(path: Path) -> dict`: parses header fields, per-frame chunk
    lists, decoded cel pixels/dimensions, tag records, and decoded palette entries — used
    only by the test suite.
  - Exported constants: `HEADER_MAGIC`, `FRAME_MAGIC`, `CHUNK_LAYER`, `CHUNK_CEL`,
    `CHUNK_COLOR_PROFILE`, `CHUNK_TAGS`, `CHUNK_PALETTE`, `DIRECTIONS`.
- `tests/sprite/test_aseprite_native.py` — 10 tests transcribed verbatim from the brief:
  header fields, first-frame chunk ordering, frame-size accounting, cel pixel round-trip,
  durations/layer name, tag direction/repeat mapping, palette chunk presence/absence,
  proportional fit for an oversized frame, and the empty-frames `ValueError`.

No deviation from the brief. The byte layouts and struct formats matched the plan
prototype exactly; all tests passed on the first implementation without adjustment.

## Tests

Command:
```
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
  /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_aseprite_native.py -v
```
Result: `10 passed, 28 warnings in 2.32s` (all 28 warnings are Pillow's
`Image.fromarray(..., "RGBA")` mode-parameter deprecation notice, raised from the test
file's own `_frame_png` helper — verbatim brief code, not from the module under test; no
warnings originate from `aseprite_native.py` itself).

Gate:
```
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
  /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q
```
Result: `3 passed in 2.93s`.

Full `tests/sprite` (touched a module with siblings under `tests/sprite/`, per the
contract's "run once before committing" rule):
```
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python \
  -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite -q
```
Result: `715 passed, 30 warnings in 115.59s`. No collisions with the concurrent
`godot_tres.py` implementer's files.

Note: `tests/sprite/test_engine_presets.py` (referenced by the brief's Step 4 as a
re-check for Task 2's import) does not exist yet in this working tree — Task 2 is a
sibling/concurrent task not yet landed. Not part of this task's gate; skipped.

## Files changed

- `core/sprite/exporters/aseprite_native.py` (new, 234 lines)
- `tests/sprite/test_aseprite_native.py` (new, 121 lines)

## Self-review

- Completeness vs. brief: all interfaces present (`export_aseprite`, `read_aseprite_summary`,
  all six named constants plus `DIRECTIONS`). Names match the brief exactly.
- No Qt import: verified with `grep -n "PySide\|PyQt\|QtCore\|QtWidgets\|QtGui" core/sprite/exporters/aseprite_native.py` — no match (pure Python + PIL + stdlib struct/zlib/logging).
- No overbuilding: implementation is the brief's prototype verbatim, no extra surface added.
- Paths: `out_ase` is passed in by the caller (no path construction here); sidecar uses
  `write_image_sidecar` per the sidecar convention. `test_no_hardcoded_paths.py` stays green.
- Tests verify real behavior: byte-level assertions on header fields, chunk ordering, frame
  size accounting, zlib-decompressed pixel round-trip, tag/direction/repeat mapping, and
  palette presence/absence — not just "it ran".
- Manual Aseprite check (Step 5, optional/not gated): not performed — no Aseprite binary
  available in this environment. The byte-level test suite is the gate per the brief.

## Concerns

- Minor: the test file's own PNG-generation helper triggers a Pillow deprecation warning
  (`Image.fromarray(arr, "RGBA")` — the `mode` parameter is deprecated, removal slated for
  Pillow 13 / 2026-10-15). This is verbatim brief code and does not affect correctness now;
  flagging so the controller can decide whether a future brief revision should drop the
  explicit `mode` argument (Pillow infers it from the array shape).
- Manual Aseprite-application verification (Step 5) was not performed — no Aseprite binary
  in this environment. Byte-level reader tests are the substantive gate and all pass.
