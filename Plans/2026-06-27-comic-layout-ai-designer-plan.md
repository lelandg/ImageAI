# Comic Layout — AI Designer Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the AI layout designer so it can emit the full geometry surface from sub-projects #1–#3 — curved/path panels (via SVG) + bleed/stroke, tiling presets, and region-relative overlays — and render that AI output on the canvas.

**Architecture:** A new pure module `core/layout/svg_path.py` converts SVG path `d` strings ⇄ `PathSegment`s. `core/layout/designer.py` gains a richer LLM prompt and a `parse_response` that fully resolves the response into concrete `Region`s + `Overlay`s (SVG→segments, tiling preset→panels, region-relative overlay anchors→pixels). `gui/layout/layout_tab.py` writes the resolved overlays onto the page so the existing Qt renderer draws them. The designer "fully resolves"; the GUI just assigns.

**Tech Stack:** Python 3.12, pytest, PySide6 (GUI apply task only). Reuses `PathSegment`/`Region`/`Overlay`/`PageSpec` (`core/layout/models.py`), `schema.region_from_dict`/`normalize_region` (`core/layout/schema.py`), the tiling presets + `tile()` (`core/layout/tiling.py`), and the existing `designer.py` prompt/parse/`DesignerResult` scaffolding.

## Global Constraints

- Test interpreter: `.venv_linux/bin/python`. Run tests with `QT_QPA_PLATFORM=offscreen` prefixed (required for the GUI apply test in Task 5; harmless for the pure tests).
- Full layout suite must stay green: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` (currently **250 passed** on branch `feat/comic-layout-geometry-core`).
- **No new third-party dependency** — the SVG parser is hand-rolled in `core/layout/svg_path.py` (no `svgpathtools`, no `lxml`).
- `core/layout/svg_path.py` and `core/layout/designer.py` must be **Qt-free** (importable headless). Only `gui/layout/layout_tab.py` (Task 5) and its test touch Qt.
- **All errors logged** (`logging.getLogger(__name__)` in `svg_path.py`; the existing `logging.getLogger("imageai.layout.designer")` in `designer.py`): malformed SVG, unknown tiling preset, unknown `anchor_region`/`tail_to_region`, and unknown overlay `kind` are each logged and degrade (skip the bad item / fall back), **never crash**.
- **Backward compatibility:** today's `{questions?, layout:{regions:[rect/polygon...]}}` responses must parse exactly as before. A response with no overlays yields `DesignerResult.overlays == []`.
- `DesignerResult` gains `overlays: List[Overlay] = field(default_factory=list)`; the existing `questions`/`regions`/`raw` fields and `fallback_result` are unchanged.
- Coordinates are page pixels. SVG subset supported: `M m L l H h V v C c Q q Z z` (absolute + relative; implicit repeats; `M`/`m` repeats become `L`/`l`).
- Conventional Commits (`feat(layout): …`). Commit after each task.
- **Branch:** continue on `feat/comic-layout-geometry-core` (all 5 comic-layout sub-projects share one branch). **Do NOT open a pull request** — the single PR comes only after sub-project #5.

### Names used across tasks (keep identical)
- `svg_to_segments(d: str) -> List[PathSegment]`, `segments_to_svg(segments: List[PathSegment]) -> str` (Task 1).
- `DesignerResult.overlays: List[Overlay]` (Task 2).
- `_build_overlay(od: dict, regions_by_id: dict, page_px, idx) -> Optional[Overlay]` and `_resolve_overlay_anchor(od, regions_by_id, page_px) -> Optional[Tuple[Tuple[float,float], str, Optional[Tuple[float,float]]]]` (Task 2).
- `_regions_from_tiling(tspec, page_px) -> List[Region]` and `_normalize_region_dict(rd: dict) -> dict` (Task 3).

---

### Task 1: `core/layout/svg_path.py` — SVG `d` ⇄ PathSegments

**Files:**
- Create: `core/layout/svg_path.py`
- Test: `tests/layout/test_svg_path.py` (create)

**Interfaces:**
- Consumes: `PathSegment` (`core.layout.models`).
- Produces: `svg_to_segments(d: str) -> List[PathSegment]`; `segments_to_svg(segments: List[PathSegment]) -> str`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_svg_path.py`:

```python
from core.layout.models import PathSegment
from core.layout.svg_path import svg_to_segments, segments_to_svg


def test_parse_basic_absolute_commands():
    segs = svg_to_segments("M10 10 L90 10 L90 90 Z")
    assert [s.type for s in segs] == ["move", "line", "line", "close"]
    assert segs[0].pts == [(10.0, 10.0)]
    assert segs[2].pts == [(90.0, 90.0)]


def test_h_and_v_commands():
    segs = svg_to_segments("M10 10 H50 V40")
    assert segs[1].type == "line" and segs[1].pts == [(50.0, 10.0)]
    assert segs[2].type == "line" and segs[2].pts == [(50.0, 40.0)]


def test_relative_commands_accumulate():
    segs = svg_to_segments("m10 10 l20 0 l0 20 z")
    assert segs[0].pts == [(10.0, 10.0)]
    assert segs[1].pts == [(30.0, 10.0)]
    assert segs[2].pts == [(30.0, 30.0)]
    assert segs[3].type == "close"


def test_implicit_line_after_moveto():
    # extra coordinate pairs after M are implicit L
    segs = svg_to_segments("M0 0 10 0 10 10")
    assert [s.type for s in segs] == ["move", "line", "line"]
    assert segs[2].pts == [(10.0, 10.0)]


def test_cubic_command():
    segs = svg_to_segments("M0 0 C1 2 3 4 5 6")
    assert segs[1].type == "cubic"
    assert segs[1].pts == [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]


def test_quad_command():
    segs = svg_to_segments("M0 0 Q1 2 3 4")
    assert segs[1].type == "quad"
    assert segs[1].pts == [(1.0, 2.0), (3.0, 4.0)]


def test_round_trip_segments_to_svg_to_segments():
    segs = [
        PathSegment(type="move", pts=[(10.0, 10.0)]),
        PathSegment(type="line", pts=[(90.0, 10.0)]),
        PathSegment(type="cubic", pts=[(95.0, 10.0), (95.0, 15.0), (95.0, 20.0)]),
        PathSegment(type="quad", pts=[(50.0, 80.0), (10.0, 20.0)]),
        PathSegment(type="close", pts=[]),
    ]
    assert svg_to_segments(segments_to_svg(segs)) == segs


def test_malformed_input_degrades_without_raising():
    # 'C' needs 6 args; only 3 given -> keep the valid move, stop, no crash
    segs = svg_to_segments("M0 0 C1 2 3")
    assert segs == [PathSegment(type="move", pts=[(0.0, 0.0)])]


def test_number_before_command_returns_empty():
    assert svg_to_segments("10 10 L20 20") == []


def test_empty_string_returns_empty():
    assert svg_to_segments("") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_svg_path.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.layout.svg_path'`.

- [ ] **Step 3: Implement `svg_path.py`**

Create `core/layout/svg_path.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_svg_path.py -q`
Expected: PASS (10 passed). Then full suite green: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` (expect 260).

- [ ] **Step 5: Commit**

```bash
git add core/layout/svg_path.py tests/layout/test_svg_path.py
git commit -m "feat(layout): svg_path.py SVG-d <-> PathSegment converter"
```

---

### Task 2: `DesignerResult.overlays` + overlay parsing (region-relative + raw pixel)

**Files:**
- Modify: `core/layout/designer.py`
- Test: `tests/layout/test_designer.py` (extend)

**Interfaces:**
- Consumes: `Overlay` (`core.layout.models`); the existing `parse_response`/`DesignerResult`.
- Produces: `DesignerResult.overlays: List[Overlay]`; `_resolve_overlay_anchor(od, regions_by_id, page_px)`; `_build_overlay(od, regions_by_id, page_px, idx)`. `parse_response` now also parses `layout["overlays"]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/layout/test_designer.py`:

```python
def test_designer_result_overlays_defaults_empty():
    res = designer.parse_response(
        '{"layout": {"regions": [{"id":"a","kind":"image","bbox":[0,0,100,100]}]}}',
        (200, 200))
    assert res.overlays == []


def test_parse_overlay_raw_pixel_anchor():
    content = ('{"layout": {"regions": [{"id":"p1","kind":"image","bbox":[0,0,200,200]}],'
               ' "overlays": [{"id":"o1","kind":"speech","text":"Hi",'
               ' "anchor":[50,40],"tail_target":[50,120]}]}}')
    res = designer.parse_response(content, (300, 300))
    assert len(res.overlays) == 1
    ov = res.overlays[0]
    assert ov.kind == "speech" and ov.text == "Hi"
    assert ov.anchor == (50.0, 40.0)
    assert ov.tail_target == (50.0, 120.0)


def test_parse_overlay_region_relative_anchor_resolves_to_pixels():
    content = ('{"layout": {"regions": [{"id":"p1","kind":"image","bbox":[100,100,200,100]}],'
               ' "overlays": [{"id":"o1","kind":"speech","text":"Yo","anchor_region":"p1",'
               ' "anchor_offset":[0.5,0.5],"tail_to_region":"p1"}]}}')
    res = designer.parse_response(content, (500, 500))
    ov = res.overlays[0]
    assert ov.anchor == (200.0, 150.0)        # 100 + 0.5*200, 100 + 0.5*100
    assert ov.tail_target == (200.0, 150.0)   # region center


def test_parse_overlay_unknown_region_dropped_but_others_kept():
    content = ('{"layout": {"regions": [{"id":"p1","kind":"image","bbox":[0,0,100,100]}],'
               ' "overlays": [{"id":"bad","kind":"speech","text":"x","anchor_region":"nope"},'
               ' {"id":"ok","kind":"sfx","text":"BOOM","anchor":[50,50]}]}}')
    res = designer.parse_response(content, (200, 200))
    assert [o.id for o in res.overlays] == ["ok"]


def test_parse_overlay_unknown_kind_skipped():
    content = ('{"layout": {"regions": [{"id":"p1","kind":"image","bbox":[0,0,100,100]}],'
               ' "overlays": [{"id":"o1","kind":"bubble","text":"x","anchor":[10,10]}]}}')
    res = designer.parse_response(content, (200, 200))
    assert res.overlays == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_designer.py -k overlay -q`
Expected: FAIL — `AttributeError: 'DesignerResult' object has no attribute 'overlays'`.

- [ ] **Step 3: Implement overlays in `designer.py`**

In `core/layout/designer.py`, change the models import to add `Overlay`:

```python
from core.layout.models import Region, Overlay
```

Add `overlays` to `DesignerResult` (place after `regions`):

```python
@dataclass
class DesignerResult:
    questions: List[str] = field(default_factory=list)
    regions: Optional[List[Region]] = None
    overlays: List[Overlay] = field(default_factory=list)
    raw: str = ""
```

Add the two helpers (place them just above `parse_response`):

```python
def _resolve_overlay_anchor(od: Dict, regions_by_id: Dict, page_px: Tuple[int, int]):
    """Resolve an overlay dict's placement to (anchor_px, anchor_mode, tail_px|None).

    Raw-pixel "anchor"/"tail_target" win; otherwise "anchor_region"+"anchor_offset"
    (0..1 within the region bbox) and "tail_to_region" (region center) are resolved
    against the already-parsed regions. Returns None (drop the overlay) if no anchor
    can be resolved. All resolution is logged on failure; never raises.
    """
    pw, ph = page_px
    anchor_mode = od.get("anchor_mode", "center")
    anchor = None
    raw = od.get("anchor")
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        anchor = (float(raw[0]), float(raw[1]))
    else:
        rid = od.get("anchor_region")
        if rid is not None and rid in regions_by_id:
            bx, by, bw, bh = regions_by_id[rid].bbox
            off = od.get("anchor_offset", [0.5, 0.5])
            if isinstance(off, (list, tuple)) and len(off) == 2:
                ox, oy = float(off[0]), float(off[1])
            else:
                ox, oy = 0.5, 0.5
            anchor = (bx + ox * bw, by + oy * bh)
        elif rid is not None:
            logger.warning("Designer overlay %r: unknown anchor_region %r; skipped",
                           od.get("id"), rid)
            return None
    if anchor is None:
        logger.warning("Designer overlay %r: no anchor or anchor_region; skipped", od.get("id"))
        return None
    anchor = (min(max(anchor[0], 0.0), float(pw)), min(max(anchor[1], 0.0), float(ph)))

    tail = None
    traw = od.get("tail_target")
    if isinstance(traw, (list, tuple)) and len(traw) == 2:
        tail = (float(traw[0]), float(traw[1]))
    else:
        trid = od.get("tail_to_region")
        if trid is not None and trid in regions_by_id:
            bx, by, bw, bh = regions_by_id[trid].bbox
            tail = (bx + bw / 2.0, by + bh / 2.0)
        elif trid is not None:
            logger.warning("Designer overlay %r: unknown tail_to_region %r; tail dropped",
                           od.get("id"), trid)
    return anchor, anchor_mode, tail


def _build_overlay(od: Dict, regions_by_id: Dict, page_px: Tuple[int, int], idx: int):
    """Build one Overlay from an LLM overlay dict, or None to skip it."""
    kind = od.get("kind")
    if kind not in ("speech", "thought", "caption", "sfx"):
        logger.warning("Designer overlay %r: unknown kind %r; skipped", od.get("id"), kind)
        return None
    resolved = _resolve_overlay_anchor(od, regions_by_id, page_px)
    if resolved is None:
        return None
    anchor, anchor_mode, tail = resolved
    return Overlay(
        id=od.get("id", f"ov{idx + 1}"), kind=kind, text=str(od.get("text", "")),
        anchor=anchor, anchor_mode=anchor_mode, tail_target=tail,
        z=int(od.get("z", 0)), role=od.get("role", ""),
    )
```

Replace the body of `parse_response` (from the `regions = None` line through the final `return`) with the version below. This preserves the existing region parsing and adds overlay parsing + the `overlays` field:

```python
    regions = None
    overlays: List[Overlay] = []
    layout = data.get("layout")
    if isinstance(layout, dict):
        if isinstance(layout.get("regions"), list):
            collected = []
            for i, rd in enumerate(layout["regions"]):
                if not isinstance(rd, dict):
                    continue
                rd = dict(rd)  # don't mutate the parsed dict
                rd.setdefault("id", f"region{i + 1}")
                rd.setdefault("kind", "image")
                region = schema.region_from_dict(rd)
                collected.append(schema.normalize_region(region, page_px))
            if collected:
                regions = collected
        if isinstance(layout.get("overlays"), list):
            by_id = {r.id: r for r in (regions or [])}
            for i, od in enumerate(layout["overlays"]):
                if isinstance(od, dict):
                    ov = _build_overlay(od, by_id, page_px, i)
                    if ov is not None:
                        overlays.append(ov)
    if regions is None and not questions and not overlays:
        return fallback_result(page_px)
    return DesignerResult(questions=questions, regions=regions, overlays=overlays, raw=content)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_designer.py -q`
Expected: PASS (existing designer tests + 5 new). Then full suite green (expect 265).

- [ ] **Step 5: Commit**

```bash
git add core/layout/designer.py tests/layout/test_designer.py
git commit -m "feat(layout): designer parses overlays (region-relative + raw-pixel)"
```

---

### Task 3: `parse_response` geometry — SVG-path regions, bleed/stroke, tiling presets

**Files:**
- Modify: `core/layout/designer.py`
- Test: `tests/layout/test_designer.py` (extend)

**Interfaces:**
- Consumes: `svg_to_segments` (`core.layout.svg_path`, Task 1); the tiling presets + `tile()` (`core.layout.tiling`); the Task-2 `parse_response`.
- Produces: `_regions_from_tiling(tspec, page_px) -> List[Region]`; `_normalize_region_dict(rd) -> dict`. `parse_response` now expands `layout["tiling"]` to panels and converts `shape:"path"` + `svg` regions (plus `stroke_px` → image_style).

- [ ] **Step 1: Write the failing test**

Append to `tests/layout/test_designer.py`:

```python
def test_parse_svg_path_region():
    content = ('{"layout": {"regions": [{"id":"p1","kind":"image","shape":"path",'
               ' "svg":"M10 10 L90 10 L90 90 Z","bleed":true}]}}')
    res = designer.parse_response(content, (200, 200))
    r = res.regions[0]
    assert r.shape == "path"
    assert [s.type for s in r.segments] == ["move", "line", "line", "close"]
    assert r.bleed is True


def test_parse_region_stroke_px_maps_to_image_style():
    content = ('{"layout": {"regions": [{"id":"p1","kind":"image","shape":"rect",'
               ' "bbox":[0,0,100,100],"stroke_px":6}]}}')
    res = designer.parse_response(content, (200, 200))
    assert res.regions[0].image_style is not None
    assert res.regions[0].image_style.stroke_px == 6


def test_parse_tiling_preset_expands_to_panels():
    content = '{"layout": {"tiling": {"preset":"grid","params":{"rows":2,"cols":2,"gutter_px":10}}}}'
    res = designer.parse_response(content, (400, 400))
    assert res.regions is not None and len(res.regions) == 4
    assert all(r.shape == "path" for r in res.regions)


def test_unknown_tiling_preset_degrades_keeps_explicit_regions():
    content = ('{"layout": {"tiling": {"preset":"spiral"},'
               ' "regions":[{"id":"a","kind":"image","bbox":[0,0,50,50]}]}}')
    res = designer.parse_response(content, (200, 200))
    assert [r.id for r in res.regions] == ["a"]  # unknown preset ignored; explicit region kept


def test_tiling_and_explicit_regions_coexist():
    content = ('{"layout": {"tiling": {"preset":"three_tiers"},'
               ' "regions":[{"id":"x","kind":"text","bbox":[0,0,40,20],"role":"caption"}]}}')
    res = designer.parse_response(content, (300, 300))
    ids = [r.id for r in res.regions]
    assert "x" in ids and len(ids) == 4  # 3 tiers + 1 explicit region
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_designer.py -k "svg or tiling or stroke" -q`
Expected: FAIL — the `svg` key is ignored (region falls back to bbox so it has no segments) and `tiling` is ignored (no panels generated).

- [ ] **Step 3: Implement geometry handling in `designer.py`**

Add the two helpers (place them above `parse_response`, near the Task-2 helpers):

```python
def _regions_from_tiling(tspec, page_px: Tuple[int, int]) -> List[Region]:
    """Expand a tiling-preset request into gap-free panel Regions (or [] on failure)."""
    if not isinstance(tspec, dict):
        return []
    from core.layout import tiling
    preset = tspec.get("preset")
    params = tspec.get("params") or {}
    pw, ph = page_px
    try:
        if preset == "grid":
            tree = tiling.grid(int(params.get("rows", 2)), int(params.get("cols", 2)))
        elif preset == "three_tiers":
            tree = tiling.three_tiers()
        elif preset == "splash_with_strip":
            tree = tiling.splash_with_strip()
        elif preset == "diagonal_action":
            tree = tiling.diagonal_action()
        elif preset == "feature_L":
            tree = tiling.feature_L()
        else:
            logger.warning("Designer: unknown tiling preset %r; ignored", preset)
            return []
        gutter = float(params.get("gutter_px", 12))
        margin = float(params.get("margin_px", 24))
        return tiling.tile(tree, (0, 0, pw, ph), gutter=gutter, margin=margin)
    except Exception as e:  # noqa: BLE001 - degrade, never crash
        logger.warning("Designer: tiling preset %r failed: %s", preset, e)
        return []


def _normalize_region_dict(rd: Dict) -> Dict:
    """Map LLM region shorthands onto schema.region_from_dict's expected keys.

    "svg" -> shape="path" + "segments"; top-level "stroke_px" -> image_style.stroke_px.
    Returns a new dict; the caller's parsed dict is not mutated.
    """
    rd = dict(rd)
    svg = rd.pop("svg", None)
    if svg:
        from core.layout.svg_path import svg_to_segments
        segs = svg_to_segments(str(svg))
        rd["shape"] = "path"
        rd["segments"] = [{"type": s.type, "pts": [list(p) for p in s.pts]} for s in segs]
    stroke = rd.pop("stroke_px", None)
    if stroke is not None:
        istyle = dict(rd.get("image_style") or {})
        istyle.setdefault("stroke_px", stroke)
        rd["image_style"] = istyle
    return rd
```

Then update the region-collection block inside `parse_response` (the `if isinstance(layout, dict):` body from Task 2). Replace the region collection so it (a) prepends tiled panels and (b) preprocesses each region dict:

```python
    if isinstance(layout, dict):
        collected = []
        collected.extend(_regions_from_tiling(layout.get("tiling"), page_px))
        if isinstance(layout.get("regions"), list):
            for i, rd in enumerate(layout["regions"]):
                if not isinstance(rd, dict):
                    continue
                rd = _normalize_region_dict(rd)
                rd.setdefault("id", f"region{i + 1}")
                rd.setdefault("kind", "image")
                region = schema.region_from_dict(rd)
                collected.append(schema.normalize_region(region, page_px))
        if collected:
            regions = collected
        if isinstance(layout.get("overlays"), list):
            by_id = {r.id: r for r in (regions or [])}
            for i, od in enumerate(layout["overlays"]):
                if isinstance(od, dict):
                    ov = _build_overlay(od, by_id, page_px, i)
                    if ov is not None:
                        overlays.append(ov)
```

(`_normalize_region_dict` already copies the dict, so the previous `rd = dict(rd)` line is replaced by the `rd = _normalize_region_dict(rd)` call.)

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_designer.py -q`
Expected: PASS (all designer tests). Full suite green (expect 270). If `test_parse_tiling_preset_expands_to_panels` finds a count other than 4, confirm `tiling.grid(2, 2)` is built and `tile(...)` is called with `(0, 0, pw, ph)`.

- [ ] **Step 5: Commit**

```bash
git add core/layout/designer.py tests/layout/test_designer.py
git commit -m "feat(layout): designer emits svg-path regions, bleed/stroke, tiling presets"
```

---

### Task 4: `build_messages` prompt extension (document the new capabilities)

**Files:**
- Modify: `core/layout/designer.py`
- Test: `tests/layout/test_designer.py` (extend)

**Interfaces:**
- Consumes: the existing `build_messages(content_kind, page_px, user_text, current_regions)` signature and its role-name listing.
- Produces: same signature; the `<instructions>` now document `shape:"path"`+`svg`, `bleed`/`stroke_px`, the `tiling` block + preset names, and the `overlays` array (region-relative + raw-pixel).

- [ ] **Step 1: Write the failing test**

Append to `tests/layout/test_designer.py`:

```python
def test_build_messages_documents_new_capabilities():
    msgs = designer.build_messages("comic", (1000, 800), "a dynamic comic page")
    joined = " ".join(m["content"] for m in msgs)
    for token in ("svg", "tiling", "grid", "overlays", "speech", "anchor_region", "bleed"):
        assert token in joined, token
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_designer.py::test_build_messages_documents_new_capabilities -q`
Expected: FAIL — the current prompt mentions none of `svg`/`tiling`/`overlays`/etc.

- [ ] **Step 3: Extend the prompt in `build_messages`**

In `core/layout/designer.py`, replace the `user = ( ... )` instruction string in `build_messages` with the version below (keep everything above it — the `pw, ph` unpack, the `role_names`/`roles` lines, and the `current` block — unchanged):

```python
    user = (
        f"<context>\n"
        f"content_kind: {content_kind}\n"
        f"page_pixels: {pw} x {ph} (x,y origin top-left; all coordinates in pixels)\n"
        f"</context>\n"
        f"{current}"
        f"<request>\n{user_text}\n</request>\n"
        f"<instructions>\n"
        f"Return a SINGLE JSON object with optional keys:\n"
        f'  "questions": [strings]   // ask for missing detail if needed\n'
        f'  "layout": {{\n'
        f'    "tiling": {{ "preset": "grid"|"three_tiers"|"splash_with_strip"|'
        f'"diagonal_action"|"feature_L",\n'
        f'                "params": {{ "rows": int, "cols": int, "gutter_px": number,'
        f' "margin_px": number }} }},\n'
        f"        // optional; generates gap-free panels. rows/cols apply to \"grid\".\n"
        f'    "regions": [ {{ "id": string, "kind": "image"|"text",\n'
        f'        "shape": "rect"|"polygon"|"path",\n'
        f'        "bbox": [x,y,w,h], "points": [[x,y],...] (polygon only),\n'
        f'        "svg": "M.. L.. C.. Z" (path only; SVG path data in page pixels),\n'
        f'        "bleed": bool, "stroke_px": number,\n'
        f'        "z": int, "role": string, "text": string (text only) }} ],\n'
        f'    "overlays": [ {{ "id": string,\n'
        f'        "kind": "speech"|"thought"|"caption"|"sfx", "text": string,\n'
        f'        "anchor_region": string, "anchor_offset": [fx,fy] (0..1 within region),\n'
        f'        "tail_to_region": string,            // tail points at that region center\n'
        f'        "anchor": [x,y], "tail_target": [x,y], // raw-pixel alternative\n'
        f'        "role": string }} ]\n'
        f'  }}\n'
        f"All coordinates MUST be within the page ({pw} x {ph}). Prefer \"rect\" for simple\n"
        f"panels; use \"tiling\" for clean gap-free grids/strips; use \"shape\":\"path\" with\n"
        f"\"svg\" for curved or angled panels; use \"polygon\" for straight-edged non-rect panels.\n"
        f"Each text region MUST set \"role\" to one of: {roles}.\n"
        f"Overlays float above panels: prefer \"anchor_region\"+\"anchor_offset\" (and\n"
        f"\"tail_to_region\") so balloons sit inside a panel; use raw \"anchor\"/\"tail_target\"\n"
        f"pixels only for free placement. You may return questions, a layout, or both.\n"
        f"</instructions>"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_designer.py -q`
Expected: PASS — the new token test passes and the existing prompt tests (`...includes_context_and_json_instruction`, `...instructs_role_with_kind_roles`) still pass (the prompt still contains `regions`, `JSON`, the page size, the request text, `"role"`, and `dialogue`). Full suite green (expect 271).

- [ ] **Step 5: Commit**

```bash
git add core/layout/designer.py tests/layout/test_designer.py
git commit -m "feat(layout): designer prompt documents svg/tiling/overlays capabilities"
```

---

### Task 5: GUI apply wiring — write resolved overlays onto the page

**Files:**
- Modify: `gui/layout/layout_tab.py` (`apply_designer_result`, ~line 398) and `gui/layout/designer_panel.py` (`_on_proposed` log line, ~line 148)
- Test: `tests/layout/test_layout_tab_designer_overlays.py` (create)

**Interfaces:**
- Consumes: `DesignerResult` with `.regions` and `.overlays` (Tasks 2–3); `PageSpec.overlays` (the field already exists); the existing `LayoutTab.apply_designer_result`.
- Produces: `apply_designer_result` writes `result.overlays` into `pages[0].overlays` so the Qt renderer draws them.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_layout_tab_designer_overlays.py`:

```python
from gui.layout.layout_tab import LayoutTab
from core.layout import designer
from core.layout.models import Overlay


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def test_apply_designer_result_writes_overlays(qapp):
    tab = LayoutTab(config=FakeConfig())
    res = designer.DesignerResult(
        regions=[designer.Region(id="p1", kind="image", bbox=(0, 0, 200, 200))],
        overlays=[Overlay(id="o1", kind="speech", text="Hi", anchor=(50.0, 40.0))],
    )
    tab.apply_designer_result(res, user_text="v1")
    page = tab.document.pages[0]
    assert [r.id for r in page.regions] == ["p1"]
    assert [o.id for o in page.overlays] == ["o1"]


def test_apply_designer_result_overlays_only(qapp):
    tab = LayoutTab(config=FakeConfig())
    res = designer.DesignerResult(
        regions=None,
        overlays=[Overlay(id="o1", kind="sfx", text="BOOM", anchor=(20.0, 20.0))],
    )
    tab.apply_designer_result(res, user_text="add sfx")
    assert [o.id for o in tab.document.pages[0].overlays] == ["o1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_layout_tab_designer_overlays.py -q`
Expected: FAIL — `apply_designer_result` ignores `result.overlays`, so `page.overlays` stays empty.

- [ ] **Step 3: Wire overlays into `apply_designer_result`**

In `gui/layout/layout_tab.py`, replace the tail of `apply_designer_result` (the `if result.regions: ... elif result.questions: ...` block) with:

```python
        applied = False
        if result.regions:
            self.document.pages[0].regions = list(result.regions)
            applied = True
        if getattr(result, "overlays", None):
            self.document.pages[0].overlays = list(result.overlays)
            applied = True
        if applied:
            self.history.append(user_text or "design")
            self._refresh()
        elif result.questions:
            self.status.setText(
                f"Designer asked {len(result.questions)} question(s) — see the Designer console.")
```

In `gui/layout/designer_panel.py`, update the `_on_proposed` summary log line to mention overlays. Replace:

```python
        n = len(result.regions) if result.regions else 0
        self.console.log(f"Proposed layout: {n} regions; {len(result.questions)} question(s).",
                         "SUCCESS")
```

with:

```python
        n = len(result.regions) if result.regions else 0
        nov = len(getattr(result, "overlays", []) or [])
        self.console.log(
            f"Proposed layout: {n} regions; {nov} overlay(s); {len(result.questions)} question(s).",
            "SUCCESS")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_layout_tab_designer_overlays.py -q`
Expected: PASS (2 passed). Then the FULL suite: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` → all green (expect 273).

- [ ] **Step 5: Commit**

```bash
git add gui/layout/layout_tab.py gui/layout/designer_panel.py tests/layout/test_layout_tab_designer_overlays.py
git commit -m "feat(layout): apply AI-designed overlays onto the page (rendered on canvas)"
```

---

## Notes / deliberately deferred (not gaps)
- **Manual drag-edit / authoring** of the emitted geometry is sub-project #5 (knife/split, vertex & curve-handle drag, bleed/borderless toggles, balloon placement, tail→region snapping, SFX rotation, contour-aware wrapping).
- **Page-resize reflow** of resolved overlays: anchors resolve to pixels at parse time (same as regions today); reflow is an editor concern for #5.
- **PIL export still bypasses overlays** (carried from #1–#3): AI-emitted overlays render in the live editor + Qt export, not the PIL `export_dialog.py`. Migrating export onto the Qt renderer is the biggest cross-cutting follow-up for the final feature PR (after #5).
- **The live `run_completion` LLM call** stays network/untested, as today.
- **`tiling`/explicit-region z overlap:** tiled panels get z 0..n and explicit regions carry their own z; z collisions are harmless (equal z = unspecified order). Not worth a z-offset pass now.

## Self-Review (completed by plan author)
- **Spec coverage:** `svg_path.py` converter (T1); overlays model field + region-relative/raw-pixel resolution (T2); svg-path regions + bleed/stroke + tiling presets, with free-draw/preset coexistence (T3); prompt documenting every new capability (T4); GUI apply wiring so AI output renders (T5). Every design §2–§7 decision and the §8 task list maps to a task; error-handling rows (§6) are each exercised by a degradation test (malformed svg in T1; unknown preset, unknown region, unknown kind in T2/T3).
- **Placeholder scan:** no TBD/TODO; every code step shows complete code; degradation paths are concrete (`return []`, `return None`, `logger.warning`), not "handle errors."
- **Type/name consistency:** `svg_to_segments`/`segments_to_svg` (T1) consumed by `_normalize_region_dict` (T3); `DesignerResult.overlays`, `_build_overlay`, `_resolve_overlay_anchor` (T2) consumed by `parse_response` (T2/T3) and the GUI (T5); `_regions_from_tiling`/`_normalize_region_dict` (T3) used in `parse_response`; `PathSegment(type=…, pts=…)`, `Region(... image_style=ImageStyle(stroke_px=…))`, `Overlay(id,kind,text,anchor,anchor_mode,tail_target,z,role)`, and `tiling.grid/three_tiers/splash_with_strip/diagonal_action/feature_L` + `tiling.tile(tree,(0,0,pw,ph),gutter=,margin=)` all match the real signatures in `core/layout/`.
- **Test interpreter/baseline:** all tasks use `.venv_linux/bin/python` under `QT_QPA_PLATFORM=offscreen`; suite 250 → ~273 across tasks (10+5+5+1+2 = 23 new tests; counts are approximate and reconciled by the executor — the binding check is "all new tests pass and the full suite stays green").
