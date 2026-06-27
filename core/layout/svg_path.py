"""Pure (Qt-free) converter between SVG path 'd' strings and PathSegments.

LLM-native curve authoring: the AI designer emits SVG path data, which this
module parses into the PathSegment model the renderer already consumes; the
inverse serializes segments back to a 'd' string (round-trip, export, and
showing current geometry back to the LLM). Supports the subset
M L H V C Q Z (absolute + relative, implicit repeats). Malformed input is
logged and degrades to whatever parsed cleanly; it never raises.
"""
from __future__ import annotations

import logging
import re
from typing import List, Tuple

from core.layout.models import PathSegment

logger = logging.getLogger(__name__)

_NUM = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"
_TOKEN_RE = re.compile(r"([MmLlHhVvCcQqZz])|(" + _NUM + r")")
_ARGC = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "Q": 4}


def _tokenize(d: str) -> List[Tuple[str, object]]:
    tokens: List[Tuple[str, object]] = []
    for m in _TOKEN_RE.finditer(d or ""):
        if m.group(1):
            tokens.append(("cmd", m.group(1)))
        else:
            tokens.append(("num", float(m.group(2))))
    return tokens


def svg_to_segments(d: str) -> List[PathSegment]:
    """Parse an SVG path 'd' string into PathSegments (subset M/L/H/V/C/Q/Z)."""
    tokens = _tokenize(d)
    segs: List[PathSegment] = []
    i, n = 0, len(tokens)
    cx = cy = sx = sy = 0.0
    cmd = ""
    while i < n:
        kind, val = tokens[i]
        if kind == "cmd":
            cmd = str(val)
            i += 1
            if cmd in ("Z", "z"):
                segs.append(PathSegment(type="close", pts=[]))
                cx, cy = sx, sy
                cmd = ""
                continue
        elif not cmd:
            logger.warning("svg_to_segments: number before any command in %r; stopping", d)
            break
        else:
            # implicit repeat of the previous command; M/m repeats as L/l
            if cmd == "M":
                cmd = "L"
            elif cmd == "m":
                cmd = "l"
        c = cmd.upper()
        rel = cmd.islower()
        argc = _ARGC.get(c)
        if argc is None:
            logger.warning("svg_to_segments: unsupported command %r; stopping", cmd)
            break
        if i + argc > n or any(tokens[j][0] != "num" for j in range(i, i + argc)):
            logger.warning("svg_to_segments: command %r needs %d args; stopping", cmd, argc)
            break
        args = [float(tokens[j][1]) for j in range(i, i + argc)]
        i += argc
        if c == "M":
            x, y = args
            if rel:
                x, y = cx + x, cy + y
            segs.append(PathSegment(type="move", pts=[(x, y)]))
            cx, cy = sx, sy = x, y
        elif c == "L":
            x, y = args
            if rel:
                x, y = cx + x, cy + y
            segs.append(PathSegment(type="line", pts=[(x, y)]))
            cx, cy = x, y
        elif c == "H":
            x = args[0] + (cx if rel else 0.0)
            segs.append(PathSegment(type="line", pts=[(x, cy)]))
            cx = x
        elif c == "V":
            y = args[0] + (cy if rel else 0.0)
            segs.append(PathSegment(type="line", pts=[(cx, y)]))
            cy = y
        elif c == "C":
            pts = []
            for k in range(0, 6, 2):
                px, py = args[k], args[k + 1]
                if rel:
                    px, py = cx + px, cy + py
                pts.append((px, py))
            segs.append(PathSegment(type="cubic", pts=pts))
            cx, cy = pts[-1]
        elif c == "Q":
            pts = []
            for k in range(0, 4, 2):
                px, py = args[k], args[k + 1]
                if rel:
                    px, py = cx + px, cy + py
                pts.append((px, py))
            segs.append(PathSegment(type="quad", pts=pts))
            cx, cy = pts[-1]
    return segs


def _fmt(n: float) -> str:
    return f"{n:g}"


def segments_to_svg(segments: List[PathSegment]) -> str:
    """Serialize PathSegments back to an absolute-coordinate SVG 'd' string."""
    parts: List[str] = []
    for s in segments:
        if s.type == "move":
            x, y = s.pts[0]
            parts.append(f"M {_fmt(x)} {_fmt(y)}")
        elif s.type == "line":
            x, y = s.pts[0]
            parts.append(f"L {_fmt(x)} {_fmt(y)}")
        elif s.type == "quad":
            (cx, cy), (x, y) = s.pts
            parts.append(f"Q {_fmt(cx)} {_fmt(cy)} {_fmt(x)} {_fmt(y)}")
        elif s.type == "cubic":
            (c1x, c1y), (c2x, c2y), (x, y) = s.pts
            parts.append(f"C {_fmt(c1x)} {_fmt(c1y)} {_fmt(c2x)} {_fmt(c2y)} {_fmt(x)} {_fmt(y)}")
        elif s.type == "close":
            parts.append("Z")
    return " ".join(parts)
