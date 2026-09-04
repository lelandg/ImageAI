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
