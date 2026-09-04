### Task 3: Native `.aseprite` writer (+ minimal reader for tests)

**Files:**
- Create: `core/sprite/exporters/aseprite_native.py`
- Test: `tests/sprite/test_aseprite_native.py`

**Interfaces:**
- Consumes: `SheetMeta`, `FrameMeta` (frames point at RGBA PNGs), `write_image_sidecar`.
- Produces: `export_aseprite(meta: SheetMeta, out_ase: Path) -> Path`; `read_aseprite_summary(path: Path) -> dict` (test-only reader); constants `HEADER_MAGIC`, `FRAME_MAGIC`, `CHUNK_LAYER`, `CHUNK_CEL`, `CHUNK_COLOR_PROFILE`, `CHUNK_TAGS`, `CHUNK_PALETTE`, `DIRECTIONS`.

#### Byte layouts (copied from `docs/ase-file-specs.md`, fetched 2026-08-29 from github.com/aseprite/aseprite)

All values little-endian. Types: `BYTE` u8, `WORD` u16, `SHORT` i16, `DWORD` u32, `LONG` i32, `FIXED` 32-bit 16.16, `STRING` = `WORD` length + `BYTE[length]` UTF-8, `PIXEL` (RGBA) = `BYTE[4]`.

```
Header (128 bytes)
DWORD  File size
WORD   Magic number (0xA5E0)
WORD   Frames
WORD   Width in pixels
WORD   Height in pixels
WORD   Color depth (32 = RGBA, 16 = Grayscale, 8 = Indexed)
DWORD  Flags (1 = Layer opacity has valid value, 2 = layer blend/opacity valid for groups, 4 = layers have UUID)
WORD   Speed (ms between frames; DEPRECATED, use frame duration)
DWORD  Set to 0
DWORD  Set to 0
BYTE   Palette entry (index) for transparent color
BYTE[3] Ignore
WORD   Number of colors (0 means 256 for old sprites)
BYTE   Pixel width
BYTE   Pixel height
SHORT  X position of the grid
SHORT  Y position of the grid
WORD   Grid width (0 = no grid)
WORD   Grid height (0 = no grid)
BYTE[84] For future (set to zero)

Frame header (16 bytes)
DWORD  Bytes in this frame
WORD   Magic number (always 0xF1FA)
WORD   Old field: number of chunks (0xFFFF = use new field)
WORD   Frame duration (ms)
BYTE[2] For future (set to zero)
DWORD  New field: number of chunks (0 = use old field)

Chunk header
DWORD  Chunk size (includes this DWORD and the WORD type; >= 6)
WORD   Chunk type
BYTE[] Chunk data

Layer Chunk (0x2004)
WORD   Flags (1 Visible, 2 Editable, 4 Lock movement, 8 Background, 16 Prefer linked cels, 32 Group collapsed, 64 Reference)
WORD   Layer type (0 Normal image, 1 Group, 2 Tilemap)
WORD   Layer child level
WORD   Default layer width (ignored)
WORD   Default layer height (ignored)
WORD   Blend mode (0 = Normal)
BYTE   Opacity
BYTE[3] For future (set to zero)
STRING Layer name
(+ DWORD tileset index if type = 2; + UUID if header flag 4)

Cel Chunk (0x2005)
WORD   Layer index
SHORT  X position
SHORT  Y position
BYTE   Opacity level
WORD   Cel type (0 Raw, 1 Linked, 2 Compressed Image, 3 Compressed Tilemap)
SHORT  Z-Index
BYTE[5] For future (set to zero)
  type 2: WORD width, WORD height, PIXEL[] raw cel data compressed with ZLIB

Color Profile Chunk (0x2007)
WORD   Type (0 none, 1 sRGB, 2 embedded ICC)
WORD   Flags (1 = use special fixed gamma)
FIXED  Fixed gamma (1.0 = linear)
BYTE[8] Reserved (set to zero)
(+ DWORD length + BYTE[] ICC data if type = 2)

Tags Chunk (0x2018)
WORD   Number of tags
BYTE[8] For future (set to zero)
  per tag:
  WORD   From frame
  WORD   To frame
  BYTE   Loop direction (0 Forward, 1 Reverse, 2 Ping-pong, 3 Ping-pong Reverse)
  WORD   Repeat N times (0 = not specified, 1 = once, n = N times)
  BYTE[6] For future (set to zero)
  BYTE[3] RGB tag color (deprecated)
  BYTE   Extra byte (zero)
  STRING Tag name

Palette Chunk (0x2019)
DWORD  New palette size (total entries)
DWORD  First color index to change
DWORD  Last color index to change
BYTE[8] For future (set to zero)
  per entry in [first, last]:
  WORD   Entry flags (1 = has name)
  BYTE   Red, BYTE Green, BYTE Blue, BYTE Alpha
  (+ STRING color name if flag 1)

Old palette chunks 0x0004 / 0x0011: ignore when 0x2019 is present (not written here).
```

Struct formats derived from the layout (sizes checked: header 128, frame header 16, chunk header 6, layer 16 + name, cel 16 + 4 + zlib, color profile 16, tag 17 + name, palette head 20, palette entry 6):

| Struct | Format |
|---|---|
| header | `<IHHHHHIHIIB3xHBBhhHH84x` |
| frame header | `<IHHH2xI` |
| chunk header | `<IH` |
| layer | `<HHHHHHB3x` + STRING |
| cel | `<HhhBHh5x` + `<HH` + zlib |
| color profile | `<HHI8x` |
| tags head / tag | `<H8x` / `<HHBH6xBBBB` + STRING |
| palette head / entry | `<III8x` / `<HBBBB` |

- [ ] **Step 1: Write the failing test**

Create `tests/sprite/test_aseprite_native.py`:

```python
# tests/sprite/test_aseprite_native.py
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.sprite.exporters.aseprite_native import (
    CHUNK_CEL, CHUNK_COLOR_PROFILE, CHUNK_LAYER, CHUNK_PALETTE, CHUNK_TAGS,
    FRAME_MAGIC, HEADER_MAGIC, export_aseprite, read_aseprite_summary,
)
from core.sprite.models import FrameMeta, SheetMeta, TagMeta


def _frame_png(path: Path, seed: int, size=(8, 8)) -> bytes:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=(size[1], size[0], 4), dtype=np.uint8)
    Image.fromarray(arr, "RGBA").save(path)
    return arr.tobytes()


def _meta(tmp_path: Path, palette=None):
    frames, raw = [], []
    for i in range(3):
        p = tmp_path / f"{i + 1:04d}.png"
        raw.append(_frame_png(p, i))
        frames.append(FrameMeta(name=f"hero_{i}", source_path=p, frame=(0, 0, 8, 8),
                                sprite_source_size=(0, 0, 8, 8), source_size=(8, 8),
                                duration_ms=100 + 50 * i))
    tags = [TagMeta(name="walk", from_index=0, to_index=1, direction="pingpong"),
            TagMeta(name="idle", from_index=2, to_index=2, repeat=1)]
    return SheetMeta(title="hero", frames=frames, tags=tags, cell_size=(8, 8), palette=palette), raw


def test_header_fields(tmp_path):
    meta, _ = _meta(tmp_path)
    out = export_aseprite(meta, tmp_path / "hero.aseprite")
    s = read_aseprite_summary(out)
    assert s["magic"] == HEADER_MAGIC
    assert s["frames"] == 3 and s["width"] == 8 and s["height"] == 8 and s["depth"] == 32
    assert s["file_size"] == s["actual_size"]
    assert s["frame_magics"] == [FRAME_MAGIC] * 3
    assert (tmp_path / "hero.aseprite.json").exists()


def test_chunk_layout_first_frame_carries_metadata(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    first = [ctype for ctype, _size in s["chunks"][0]]
    assert first == [CHUNK_COLOR_PROFILE, CHUNK_LAYER, CHUNK_TAGS, CHUNK_CEL]
    assert [[c for c, _ in frame] for frame in s["chunks"][1:]] == [[CHUNK_CEL], [CHUNK_CEL]]
    assert all(size >= 6 for frame in s["chunks"] for _c, size in frame)


def test_frame_sizes_sum_to_file_size(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert 128 + sum(s["frame_sizes"]) == s["actual_size"]
    for frame_size, chunks in zip(s["frame_sizes"], s["chunks"]):
        assert frame_size == 16 + sum(size for _c, size in chunks)


def test_cel_pixels_round_trip(tmp_path):
    meta, raw = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert [c["pixels"] for c in s["cels"]] == raw
    assert all(c["type"] == 2 and c["width"] == 8 and c["height"] == 8 and c["layer"] == 0 for c in s["cels"])


def test_durations_and_layer_name(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert s["frame_durations"] == [100, 150, 200]
    assert s["layers"] == ["Sprite"]


def test_tags_directions_and_repeat(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert s["tags"] == [
        {"name": "walk", "from": 0, "to": 1, "direction": 2, "repeat": 0},
        {"name": "idle", "from": 2, "to": 2, "direction": 0, "repeat": 1},
    ]


def test_palette_chunk_when_quantized(tmp_path):
    meta, _ = _meta(tmp_path, palette=["#FF0000", "#00FF00", "#0000FF"])
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    first = [ctype for ctype, _ in s["chunks"][0]]
    assert first == [CHUNK_COLOR_PROFILE, CHUNK_PALETTE, CHUNK_LAYER, CHUNK_TAGS, CHUNK_CEL]
    assert s["palette"] == ["#FF0000", "#00FF00", "#0000FF"]
    assert s["ncolors"] == 3


def test_no_palette_chunk_without_palette(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert CHUNK_PALETTE not in [c for c, _ in s["chunks"][0]]
    assert s["ncolors"] == 0


def test_oversized_frame_is_fit_proportionally(tmp_path):
    meta, _ = _meta(tmp_path)
    wide = tmp_path / "wide.png"
    _frame_png(wide, 9, size=(16, 8))
    meta.frames[1].source_path = wide
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    cel = s["cels"][1]
    assert (cel["width"], cel["height"]) == (8, 4)
    assert (cel["x"], cel["y"]) == (0, 2)


def test_requires_frames(tmp_path):
    with pytest.raises(ValueError):
        export_aseprite(SheetMeta(title="x", frames=[], tags=[]), tmp_path / "x.aseprite")
```

- [ ] **Step 2: Run the test to see it fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_aseprite_native.py -v` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement the writer and reader**

Create `core/sprite/exporters/aseprite_native.py`:

```python
"""Native ``.aseprite`` writer plus a minimal reader used by the tests.

Byte layout follows docs/ase-file-specs.md (Aseprite repository, fetched
2026-08-29; the layouts are copied into the implementation plan). One RGBA
layer, one zlib-compressed cel (type 2) per frame, one Tags chunk, an
optional Palette chunk, and an sRGB Color Profile chunk. Little-endian.
"""
from __future__ import annotations

import logging
import struct
import zlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.sprite.models import FrameMeta, SheetMeta
from core.utils import write_image_sidecar

logger = logging.getLogger(__name__)

HEADER_MAGIC = 0xA5E0
FRAME_MAGIC = 0xF1FA
CHUNK_LAYER = 0x2004
CHUNK_CEL = 0x2005
CHUNK_COLOR_PROFILE = 0x2007
CHUNK_TAGS = 0x2018
CHUNK_PALETTE = 0x2019
HEADER_SIZE = 128
FRAME_HEADER_SIZE = 16
COLOR_DEPTH_RGBA = 32
HEADER_FLAG_LAYER_OPACITY_VALID = 1
LAYER_FLAGS_VISIBLE_EDITABLE = 1 | 2
CEL_TYPE_COMPRESSED_IMAGE = 2
COLOR_PROFILE_SRGB = 1
DIRECTIONS = {"forward": 0, "reverse": 1, "pingpong": 2, "pingpong_reverse": 3}

_HEADER = struct.Struct("<IHHHHHIHIIB3xHBBhhHH84x")   # 128 bytes
_FRAME_HEADER = struct.Struct("<IHHH2xI")               # 16 bytes
_CHUNK_HEADER = struct.Struct("<IH")                     # 6 bytes
_LAYER = struct.Struct("<HHHHHHB3x")                     # + STRING name
_CEL = struct.Struct("<HhhBHh5x")                        # + WORD w, WORD h, zlib pixels
_CEL_SIZE = struct.Struct("<HH")
_COLOR_PROFILE = struct.Struct("<HHI8x")
_TAGS_HEAD = struct.Struct("<H8x")
_TAG = struct.Struct("<HHBH6xBBBB")                      # + STRING name
_PALETTE_HEAD = struct.Struct("<III8x")
_PALETTE_ENTRY = struct.Struct("<HBBBB")
_WORD = struct.Struct("<H")

assert _HEADER.size == HEADER_SIZE and _FRAME_HEADER.size == FRAME_HEADER_SIZE


def _string(text: str) -> bytes:
    raw = text.encode("utf-8")
    return _WORD.pack(len(raw)) + raw


def _read_string(data: bytes, pos: int) -> Tuple[str, int]:
    (length,) = _WORD.unpack_from(data, pos)
    start = pos + _WORD.size
    return data[start:start + length].decode("utf-8"), start + length


def _chunk(chunk_type: int, payload: bytes) -> bytes:
    return _CHUNK_HEADER.pack(_CHUNK_HEADER.size + len(payload), chunk_type) + payload


def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
    c = color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _frame_image(frame: FrameMeta, cell: Tuple[int, int]) -> Tuple[Image.Image, int, int]:
    """Load the frame as RGBA fitted proportionally into ``cell``; return (image, x, y)."""
    if frame.source_path is None:
        raise ValueError(f"frame {frame.name!r} has no source_path")
    with Image.open(frame.source_path) as src:
        img = src.convert("RGBA")
    if img.size == cell:
        return img, 0, 0
    fitted = img.copy()
    fitted.thumbnail(cell, Image.LANCZOS)          # proportional; never distorts
    x = (cell[0] - fitted.width) // 2
    y = (cell[1] - fitted.height) // 2
    return fitted, x, y


def _layer_chunk(name: str) -> bytes:
    return _chunk(CHUNK_LAYER, _LAYER.pack(LAYER_FLAGS_VISIBLE_EDITABLE, 0, 0, 0, 0, 0, 255) + _string(name))


def _cel_chunk(img: Image.Image, x: int, y: int) -> bytes:
    payload = (_CEL.pack(0, x, y, 255, CEL_TYPE_COMPRESSED_IMAGE, 0)
               + _CEL_SIZE.pack(img.width, img.height)
               + zlib.compress(img.tobytes()))
    return _chunk(CHUNK_CEL, payload)


def _color_profile_chunk() -> bytes:
    return _chunk(CHUNK_COLOR_PROFILE, _COLOR_PROFILE.pack(COLOR_PROFILE_SRGB, 0, 0))


def _tags_chunk(meta: SheetMeta) -> bytes:
    body = _TAGS_HEAD.pack(len(meta.tags))
    for tag in meta.tags:
        direction = DIRECTIONS.get(tag.direction, 0)
        body += _TAG.pack(tag.from_index, tag.to_index, direction, tag.repeat, 0, 0, 0, 0) + _string(tag.name)
    return _chunk(CHUNK_TAGS, body)


def _palette_chunk(palette: List[str]) -> bytes:
    body = _PALETTE_HEAD.pack(len(palette), 0, len(palette) - 1)
    for color in palette:
        r, g, b = _hex_to_rgb(color)
        body += _PALETTE_ENTRY.pack(0, r, g, b, 255)
    return _chunk(CHUNK_PALETTE, body)


def _frame_bytes(duration_ms: int, chunks: List[bytes]) -> bytes:
    body = b"".join(chunks)
    count = len(chunks)
    old_count = count if count < 0xFFFF else 0xFFFF
    duration = max(1, min(int(duration_ms), 0xFFFF))
    return _FRAME_HEADER.pack(_FRAME_HEADER.size + len(body), FRAME_MAGIC, old_count, duration, count) + body


def export_aseprite(meta: SheetMeta, out_ase: Path) -> Path:
    """Write ``meta`` as a native Aseprite file (one layer, one cel per frame)."""
    if not meta.frames:
        raise ValueError("SheetMeta has no frames")
    cell = (int(meta.cell_size[0]), int(meta.cell_size[1]))
    if cell[0] <= 0 or cell[1] <= 0:
        raise ValueError(f"invalid cell_size {meta.cell_size}")
    palette = list(meta.palette) if meta.palette else []
    frames_blob = b""
    for index, frame in enumerate(meta.frames):
        img, x, y = _frame_image(frame, cell)
        chunks: List[bytes] = []
        if index == 0:
            chunks.append(_color_profile_chunk())
            if palette:
                chunks.append(_palette_chunk(palette))
            chunks.append(_layer_chunk("Sprite"))
            if meta.tags:
                chunks.append(_tags_chunk(meta))
        chunks.append(_cel_chunk(img, x, y))
        frames_blob += _frame_bytes(frame.duration_ms, chunks)
    header = _HEADER.pack(
        HEADER_SIZE + len(frames_blob), HEADER_MAGIC, len(meta.frames), cell[0], cell[1],
        COLOR_DEPTH_RGBA, HEADER_FLAG_LAYER_OPACITY_VALID,
        max(1, min(meta.frames[0].duration_ms, 0xFFFF)), 0, 0,
        0, len(palette), 1, 1, 0, 0, 0, 0,
    )
    out_ase = Path(out_ase)
    out_ase.parent.mkdir(parents=True, exist_ok=True)
    out_ase.write_bytes(header + frames_blob)
    write_image_sidecar(out_ase, {
        "format": "aseprite", "title": meta.title, "profile": meta.profile,
        "frames": len(meta.frames), "cell_size": list(cell), "palette": palette or None,
        "tags": [t.name for t in meta.tags], "app": meta.app, "version": meta.version,
    })
    logger.info("Aseprite file written: %s (%d frames, %dx%d)", out_ase, len(meta.frames), cell[0], cell[1])
    return out_ase


def read_aseprite_summary(path: Path) -> Dict[str, Any]:
    """Parse header, frame headers, and the chunks this writer emits. Test helper."""
    data = Path(path).read_bytes()
    (size, magic, frames, width, height, depth, flags, _speed, _z1, _z2,
     _transparent, ncolors, _pw, _ph, _gx, _gy, _gw, _gh) = _HEADER.unpack_from(data, 0)
    summary: Dict[str, Any] = {
        "file_size": size, "actual_size": len(data), "magic": magic, "frames": frames,
        "width": width, "height": height, "depth": depth, "flags": flags, "ncolors": ncolors,
        "frame_magics": [], "frame_durations": [], "frame_sizes": [], "chunks": [],
        "layers": [], "tags": [], "palette": [], "cels": [],
    }
    pos = HEADER_SIZE
    for frame_index in range(frames):
        frame_size, frame_magic, old_count, duration, new_count = _FRAME_HEADER.unpack_from(data, pos)
        count = old_count if new_count == 0 else new_count
        summary["frame_magics"].append(frame_magic)
        summary["frame_durations"].append(duration)
        summary["frame_sizes"].append(frame_size)
        chunk_pos = pos + FRAME_HEADER_SIZE
        types: List[Tuple[int, int]] = []
        for _ in range(count):
            chunk_size, chunk_type = _CHUNK_HEADER.unpack_from(data, chunk_pos)
            payload = data[chunk_pos + _CHUNK_HEADER.size: chunk_pos + chunk_size]
            types.append((chunk_type, chunk_size))
            if chunk_type == CHUNK_LAYER:
                name, _ = _read_string(payload, _LAYER.size)
                summary["layers"].append(name)
            elif chunk_type == CHUNK_CEL:
                layer, x, y, _opacity, cel_type, _z = _CEL.unpack_from(payload, 0)
                w, h = _CEL_SIZE.unpack_from(payload, _CEL.size)
                pixels = zlib.decompress(payload[_CEL.size + _CEL_SIZE.size:]) if cel_type == CEL_TYPE_COMPRESSED_IMAGE else b""
                summary["cels"].append({"frame": frame_index, "layer": layer, "x": x, "y": y,
                                        "type": cel_type, "width": w, "height": h, "pixels": pixels})
            elif chunk_type == CHUNK_TAGS:
                (ntags,) = _TAGS_HEAD.unpack_from(payload, 0)
                tpos = _TAGS_HEAD.size
                for _ in range(ntags):
                    frm, to, direction, repeat, _r, _g, _b, _extra = _TAG.unpack_from(payload, tpos)
                    name, tpos = _read_string(payload, tpos + _TAG.size)
                    summary["tags"].append({"name": name, "from": frm, "to": to, "direction": direction, "repeat": repeat})
            elif chunk_type == CHUNK_PALETTE:
                _psize, first, last = _PALETTE_HEAD.unpack_from(payload, 0)
                epos = _PALETTE_HEAD.size
                for _ in range(last - first + 1):
                    eflags, r, g, b, _a = _PALETTE_ENTRY.unpack_from(payload, epos)
                    epos += _PALETTE_ENTRY.size
                    if eflags & 1:
                        _name, epos = _read_string(payload, epos)
                    summary["palette"].append(f"#{r:02X}{g:02X}{b:02X}")
            chunk_pos += chunk_size
        summary["chunks"].append(types)
        pos += frame_size
    return summary
```

- [ ] **Step 4: Run the test to see it pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_aseprite_native.py -v` → 10 passed. Then run `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_engine_presets.py -q` again (the `aseprite_native` writer import in Task 2 now resolves).

- [ ] **Step 5: Manual check (optional, not gated)**

Open the produced file in Aseprite (or `aseprite -b hero.aseprite --list-tags`) once, and record the result in the commit body. The byte-level test is the gate.

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/exporters/aseprite_native.py tests/sprite/test_aseprite_native.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): native .aseprite writer (layer, zlib cels, tags, palette, sRGB) with byte-level reader test"
```

---

