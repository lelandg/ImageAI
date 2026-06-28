# Comic Layout — Geometry & Render Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give layout regions a path-based geometry (straight **and** curved edges) that clips placed images to the panel's exact shape, with per-region stroke control (incl. borderless) and a bleed flag — the foundation for comic-style pages.

**Architecture:** Add a `PathSegment` model and `Region.shape="path"`/`segments`/`bleed`. A pure `core/layout/geometry.py` validates segments and computes a bbox. The Qt renderer (`core/layout/qt_renderer.py`) builds a `QPainterPath` per region and uses `ItemClipsChildrenToShape` so the image/text child is clipped to the panel interior; stroke comes from `ImageStyle.stroke_px`/`stroke_color` (0 ⇒ borderless); bleed renders onto an extended canvas. Serialization round-trips the new fields.

**Tech Stack:** Python 3.12, PySide6 (Qt Graphics), pytest. Renderer tests run headless under `QT_QPA_PLATFORM=offscreen`.

## Global Constraints

- Python interpreter for tests: `.venv_linux/bin/python` (WSL). Run tests with `QT_QPA_PLATFORM=offscreen`.
- Full layout suite must stay green: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` (currently **166 passed**).
- **All errors must be logged** (platform-independent) — use `logging.getLogger(__name__)`; a malformed path falls back to the bbox rectangle and logs.
- Images are **scaled, not cropped at generation/save**; at *layout placement* the fit modes apply (`cover` crops overflow via the shape clip — this is existing engine behavior).
- Reuse existing `ImageStyle.fit` / `stroke_px` / `stroke_color` — **do not** add new style fields.
- No backward-compat machinery for old projects (none exist); keep `rect`/`polygon` shape kinds working so existing tests/designer are untouched.
- Conventional Commits (`feat(layout): …`). Commit after each task.
- **Do NOT open a pull request.** This is sub-project #1 of 5; per the project rule, the PR is opened only after all five comic-layout sub-projects are finished. Keep all work on branch `feat/comic-layout-geometry-core`.

---

### Task 1: Region path geometry model

**Files:**
- Modify: `core/layout/models.py` (add `PathSegment`; extend `Region`)
- Test: `tests/layout/test_region_path_fields.py` (create)

**Interfaces:**
- Produces: `PathSegment(type: Literal["move","line","quad","cubic","close"], pts: List[Tuple[float,float]])`; `Region.shape` now includes `"path"`; `Region.segments: List[PathSegment]`; `Region.bleed: bool`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_region_path_fields.py`:

```python
from core.layout.models import Region, PathSegment


def test_region_defaults_have_empty_segments_and_no_bleed():
    r = Region(id="r", kind="image")
    assert r.shape == "rect"
    assert r.segments == []
    assert r.bleed is False


def test_region_accepts_path_shape_and_segments():
    segs = [
        PathSegment(type="move", pts=[(0.0, 0.0)]),
        PathSegment(type="line", pts=[(10.0, 0.0)]),
        PathSegment(type="cubic", pts=[(10.0, 5.0), (5.0, 10.0), (0.0, 10.0)]),
        PathSegment(type="close", pts=[]),
    ]
    r = Region(id="r", kind="image", shape="path", segments=segs, bleed=True)
    assert r.shape == "path"
    assert r.segments[2].type == "cubic"
    assert len(r.segments[2].pts) == 3
    assert r.bleed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_path_fields.py -q`
Expected: FAIL — `ImportError: cannot import name 'PathSegment'`.

- [ ] **Step 3: Implement the model changes**

In `core/layout/models.py`, add the `PathSegment` dataclass immediately **before** `class Region` (after `ImageBlock`):

```python
@dataclass
class PathSegment:
    """One command of a region's vector outline (page-pixel coords).

    Point counts by type: move=1, line=1, quad=2 (control, end),
    cubic=3 (c1, c2, end), close=0. A valid path starts with a 'move'.
    """

    type: Literal["move", "line", "quad", "cubic", "close"]
    pts: List[Tuple[float, float]] = field(default_factory=list)
```

In `class Region`, change the `shape` annotation and add two fields right after `points`:

```python
    shape: Literal["rect", "polygon", "path"] = "rect"
    bbox: Rect = (0, 0, 100, 100)
    points: List[Tuple[int, int]] = field(default_factory=list)  # polygon vertices, page px
    segments: List["PathSegment"] = field(default_factory=list)  # used when shape == "path"
    bleed: bool = False
```

(All Region call sites use keyword arguments, so inserting fields is safe.)

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_path_fields.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add core/layout/models.py tests/layout/test_region_path_fields.py
git commit -m "feat(layout): add PathSegment model + Region path/segments/bleed fields"
```

---

### Task 2: Pure geometry helpers (`geometry.py`)

**Files:**
- Create: `core/layout/geometry.py`
- Test: `tests/layout/test_geometry.py` (create)

**Interfaces:**
- Consumes: `PathSegment` (Task 1).
- Produces: `validate_segments(segments) -> list[str]` (empty = valid); `segments_bbox(segments) -> tuple[float,float,float,float]` `(x,y,w,h)`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_geometry.py`:

```python
import math
from core.layout.models import PathSegment
from core.layout.geometry import validate_segments, segments_bbox


def _triangle():
    return [
        PathSegment(type="move", pts=[(0.0, 0.0)]),
        PathSegment(type="line", pts=[(10.0, 0.0)]),
        PathSegment(type="line", pts=[(5.0, 8.0)]),
        PathSegment(type="close", pts=[]),
    ]


def test_valid_path_has_no_issues():
    assert validate_segments(_triangle()) == []


def test_empty_is_invalid():
    assert validate_segments([]) == ["empty segment list"]


def test_must_start_with_move():
    segs = [PathSegment(type="line", pts=[(1.0, 1.0)])]
    assert any("must start with a 'move'" in m for m in validate_segments(segs))


def test_wrong_point_count_flagged():
    segs = [PathSegment(type="move", pts=[(0.0, 0.0)]),
            PathSegment(type="cubic", pts=[(1.0, 1.0)])]  # cubic needs 3
    assert any("cubic expects 3" in m for m in validate_segments(segs))


def test_non_finite_flagged():
    segs = [PathSegment(type="move", pts=[(0.0, float("nan"))])]
    assert any("non-finite" in m for m in validate_segments(segs))


def test_bbox_of_triangle():
    assert segments_bbox(_triangle()) == (0.0, 0.0, 10.0, 8.0)


def test_bbox_includes_cubic_control_points():
    segs = [PathSegment(type="move", pts=[(0.0, 0.0)]),
            PathSegment(type="cubic", pts=[(0.0, 20.0), (20.0, 20.0), (10.0, 0.0)])]
    # superset using control points: x in [0,20], y in [0,20]
    assert segments_bbox(segs) == (0.0, 0.0, 20.0, 20.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_geometry.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.layout.geometry'`.

- [ ] **Step 3: Implement `geometry.py`**

Create `core/layout/geometry.py`:

```python
"""Pure geometry helpers for path-based regions (no Qt dependency)."""
from __future__ import annotations

import math
from typing import List, Tuple

from core.layout.models import PathSegment

_EXPECTED_PTS = {"move": 1, "line": 1, "quad": 2, "cubic": 3, "close": 0}


def validate_segments(segments: List[PathSegment]) -> List[str]:
    """Return a list of problem descriptions; empty list means valid."""
    if not segments:
        return ["empty segment list"]
    issues: List[str] = []
    if segments[0].type != "move":
        issues.append("path must start with a 'move' segment")
    for i, seg in enumerate(segments):
        expected = _EXPECTED_PTS.get(seg.type)
        if expected is None:
            issues.append(f"segment {i}: unknown type {seg.type!r}")
            continue
        if len(seg.pts) != expected:
            issues.append(
                f"segment {i}: {seg.type} expects {expected} point(s), got {len(seg.pts)}"
            )
        for (px, py) in seg.pts:
            if not (math.isfinite(px) and math.isfinite(py)):
                issues.append(f"segment {i}: non-finite coordinate")
                break
    return issues


def segments_bbox(segments: List[PathSegment]) -> Tuple[float, float, float, float]:
    """Bounding box (x, y, w, h) of all segment points.

    For curves this uses the control points, i.e. a safe superset of the visual
    extent. bbox is positioning-only, never used for clipping, so the superset is
    acceptable.
    """
    xs: List[float] = []
    ys: List[float] = []
    for seg in segments:
        for (px, py) in seg.pts:
            xs.append(px)
            ys.append(py)
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_geometry.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add core/layout/geometry.py tests/layout/test_geometry.py
git commit -m "feat(layout): pure geometry helpers (validate_segments, segments_bbox)"
```

---

### Task 3: Serialize segments + bleed; schema + normalize

**Files:**
- Modify: `core/layout/schema.py` (`REGION_JSON_SCHEMA`, `region_to_dict`, `region_from_dict`, `normalize_region`)
- Test: `tests/layout/test_schema_path.py` (create)

**Interfaces:**
- Consumes: `PathSegment` (Task 1), `segments_bbox` (Task 2).
- Produces: `region_to_dict`/`region_from_dict` round-trip `segments` (`[{"type","pts"}]`) and `bleed`; `normalize_region` derives bbox from segments for `shape="path"`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_schema_path.py`:

```python
from core.layout.models import Region, PathSegment
from core.layout.schema import (
    region_to_dict, region_from_dict, normalize_region, REGION_JSON_SCHEMA,
)


def _segs():
    return [
        PathSegment(type="move", pts=[(10.0, 10.0)]),
        PathSegment(type="line", pts=[(90.0, 10.0)]),
        PathSegment(type="line", pts=[(50.0, 80.0)]),
        PathSegment(type="close", pts=[]),
    ]


def test_path_region_round_trips():
    r = Region(id="p", kind="image", shape="path", segments=_segs(), bleed=True)
    r2 = region_from_dict(region_to_dict(r))
    assert r2.shape == "path"
    assert r2.bleed is True
    assert [s.type for s in r2.segments] == ["move", "line", "line", "close"]
    assert r2.segments[1].pts == [(90.0, 10.0)]


def test_schema_advertises_path_segments_bleed():
    assert "path" in REGION_JSON_SCHEMA["properties"]["shape"]["enum"]
    assert "segments" in REGION_JSON_SCHEMA["properties"]
    assert "bleed" in REGION_JSON_SCHEMA["properties"]


def test_normalize_region_derives_bbox_from_segments():
    r = Region(id="p", kind="image", shape="path", segments=_segs())
    n = normalize_region(r, (200, 200))
    # bbox = bounding box of points (10,10)-(90,80)
    assert n.bbox == (10, 10, 80, 70)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_schema_path.py -q`
Expected: FAIL — round-trip drops `segments`/`bleed`; schema lacks the new keys.

- [ ] **Step 3: Implement schema changes**

In `core/layout/schema.py`, add `PathSegment` to the model import:

```python
from core.layout.models import (
    Region, PageSpec, DocumentSpec, PageSize, TextStyle, ImageStyle, Snapshot, ProjectStyle,
    migrate_legacy_blocks, TextBlock, ImageBlock, PathSegment,
)
```

Update `REGION_JSON_SCHEMA` `shape` enum and add `segments`/`bleed` properties:

```python
        "shape": {"enum": ["rect", "polygon", "path"]},
        "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
        "points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
        "segments": {"type": "array", "items": {
            "type": "object",
            "required": ["type", "pts"],
            "properties": {
                "type": {"enum": ["move", "line", "quad", "cubic", "close"]},
                "pts": {"type": "array", "items": {
                    "type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}},
            },
        }},
        "bleed": {"type": "boolean"},
        "z": {"type": "integer"},
```

In `region_to_dict`, add the two keys (before `text_style`):

```python
        "image_ref": r.image_ref, "prompt": r.prompt, "gen_settings": dict(r.gen_settings),
        "segments": [{"type": s.type, "pts": [list(p) for p in s.pts]} for s in r.segments],
        "bleed": r.bleed,
        "text_style": _style_to_dict(r.text_style),
        "image_style": _style_to_dict(r.image_style),
```

In `region_from_dict`, parse them (before the `text_style=` line):

```python
        gen_settings=dict(d.get("gen_settings", {})),
        segments=[PathSegment(type=s.get("type", "line"),
                              pts=[tuple(p) for p in s.get("pts", [])])
                  for s in d.get("segments", [])],
        bleed=bool(d.get("bleed", False)),
        text_style=TextStyle(**_filtered(TextStyle, ts)) if ts else None,
```

In `normalize_region`, add a `path` branch and round to int:

```python
def normalize_region(r: Region, page_px: Tuple[int, int]) -> Region:
    pw, ph = page_px
    if r.shape == "polygon" and r.points:
        xs = [p[0] for p in r.points]
        ys = [p[1] for p in r.points]
        bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    elif r.shape == "path" and r.segments:
        from core.layout.geometry import segments_bbox
        bbox = tuple(round(v) for v in segments_bbox(r.segments))
    else:
        bbox = r.bbox
    x, y, w, h = bbox
    x = max(0, min(x, pw - 1))
    y = max(0, min(y, ph - 1))
    w = max(1, min(w, pw - x))
    h = max(1, min(h, ph - y))
    return replace(r, bbox=(x, y, w, h))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_schema_path.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add core/layout/schema.py tests/layout/test_schema_path.py
git commit -m "feat(layout): serialize path segments + bleed; bbox-from-segments in normalize"
```

---

### Task 4: `region_to_painter_path` builder

**Files:**
- Modify: `core/layout/qt_renderer.py` (imports, module logger, new function)
- Test: `tests/layout/test_region_path_builder.py` (create)

**Interfaces:**
- Consumes: `validate_segments` (Task 2), `Region` (Task 1).
- Produces: `qt_renderer.region_to_painter_path(region) -> QPainterPath` (rect/polygon/path; invalid path falls back to bbox rect + logs).

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_region_path_builder.py`:

```python
from core.layout.models import Region, PathSegment
from core.layout import qt_renderer


def test_rect_region_path_matches_bbox(qapp):
    r = Region(id="r", kind="image", shape="rect", bbox=(10, 20, 30, 40))
    p = qt_renderer.region_to_painter_path(r)
    b = p.boundingRect()
    assert (round(b.x()), round(b.y()), round(b.width()), round(b.height())) == (10, 20, 30, 40)


def test_polygon_region_path_matches_points(qapp):
    r = Region(id="r", kind="image", shape="polygon", points=[(0, 0), (50, 0), (25, 40)])
    b = qt_renderer.region_to_painter_path(r).boundingRect()
    assert (round(b.x()), round(b.y()), round(b.width()), round(b.height())) == (0, 0, 50, 40)


def test_path_region_builds_from_segments(qapp):
    segs = [PathSegment(type="move", pts=[(0.0, 0.0)]),
            PathSegment(type="line", pts=[(60.0, 0.0)]),
            PathSegment(type="line", pts=[(30.0, 50.0)]),
            PathSegment(type="close", pts=[])]
    b = qt_renderer.region_to_painter_path(
        Region(id="r", kind="image", shape="path", segments=segs)).boundingRect()
    assert (round(b.x()), round(b.y()), round(b.width()), round(b.height())) == (0, 0, 60, 50)


def test_invalid_segments_fall_back_to_bbox(qapp):
    # cubic with too few points -> invalid -> bbox rect
    segs = [PathSegment(type="move", pts=[(0.0, 0.0)]),
            PathSegment(type="cubic", pts=[(1.0, 1.0)])]
    r = Region(id="r", kind="image", shape="path", segments=segs, bbox=(5, 5, 20, 20))
    b = qt_renderer.region_to_painter_path(r).boundingRect()
    assert (round(b.x()), round(b.y()), round(b.width()), round(b.height())) == (5, 5, 20, 20)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_path_builder.py -q`
Expected: FAIL — `AttributeError: module 'core.layout.qt_renderer' has no attribute 'region_to_painter_path'`.

- [ ] **Step 3: Implement the builder**

In `core/layout/qt_renderer.py`, extend the `QtGui` import to include `QPainterPath`, add a logger, import the validator, and add the function. Update the import line:

```python
from PySide6.QtGui import (
    QColor, QBrush, QPen, QPolygonF, QImage, QPainter, QFont, QPixmap,
    QPdfWriter, QPageSize, QPageLayout, QPainterPath,
)
```

Add near the top (after the existing imports):

```python
import logging

from core.layout.geometry import validate_segments

logger = logging.getLogger(__name__)
```

Add the builder (place it after `_resolve_bg`):

```python
def region_to_painter_path(r: Region) -> QPainterPath:
    """Build a QPainterPath for a region (rect | polygon | path).

    Invalid path segments are logged and the region falls back to its bbox
    rectangle, so a region never renders as nothing.
    """
    path = QPainterPath()
    if r.shape == "path" and r.segments:
        issues = validate_segments(r.segments)
        if issues:
            logger.error("Region %s has invalid path segments; falling back to bbox: %s",
                         r.id, "; ".join(issues))
        else:
            for seg in r.segments:
                if seg.type == "move":
                    path.moveTo(*seg.pts[0])
                elif seg.type == "line":
                    path.lineTo(*seg.pts[0])
                elif seg.type == "quad":
                    (cx, cy), (ex, ey) = seg.pts
                    path.quadTo(cx, cy, ex, ey)
                elif seg.type == "cubic":
                    (c1x, c1y), (c2x, c2y), (ex, ey) = seg.pts
                    path.cubicTo(c1x, c1y, c2x, c2y, ex, ey)
                elif seg.type == "close":
                    path.closeSubpath()
            if not path.isEmpty():
                return path
    elif r.shape == "polygon" and r.points:
        path.addPolygon(QPolygonF([QPointF(px, py) for px, py in r.points]))
        path.closeSubpath()
        return path
    x, y, w, h = r.bbox
    path.addRect(QRectF(x, y, w, h))
    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_path_builder.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add core/layout/qt_renderer.py tests/layout/test_region_path_builder.py
git commit -m "feat(layout): region_to_painter_path builder (rect/polygon/path + fallback)"
```

---

### Task 5: Clip image to shape + honor stroke (borderless)

**Files:**
- Modify: `core/layout/qt_renderer.py` (`_RegionPathItem` class; rewrite `_add_image_region`)
- Test: `tests/layout/test_image_clip_stroke.py` (create)

**Interfaces:**
- Consumes: `region_to_painter_path` (Task 4).
- Produces: image regions render via a clip-parent `_RegionPathItem` (filled = clipped pixmap child; empty = placeholder fill); stroke from `ImageStyle.stroke_px`/`stroke_color` (0 ⇒ `Qt.NoPen`); fit `cover` (default) vs `contain`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_image_clip_stroke.py`:

```python
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem
from PySide6.QtCore import Qt

from core.layout.models import Region, PageSpec, PathSegment, ImageStyle
from core.layout import qt_renderer


def _solid_png(tmp_path, color, name="src.png", size=(80, 80)):
    im = QImage(size[0], size[1], QImage.Format_RGB32)
    im.fill(color)
    p = tmp_path / name
    assert im.save(str(p))
    return str(p)


def _triangle_segments():
    # apex at bottom-center, wide top edge; bbox (100,10,90,80)
    return [PathSegment(type="move", pts=[(100.0, 10.0)]),
            PathSegment(type="line", pts=[(190.0, 10.0)]),
            PathSegment(type="line", pts=[(145.0, 90.0)]),
            PathSegment(type="close", pts=[])]


def test_image_is_clipped_to_triangle(qapp, tmp_path):
    ref = _solid_png(tmp_path, Qt.red, size=(90, 80))
    page = PageSpec(page_size_px=(200, 150), background="#FFFFFF", regions=[
        Region(id="t", kind="image", shape="path", segments=_triangle_segments(),
               bbox=(100, 10, 90, 80), image_ref=ref)])
    img = qt_renderer.render_page_to_image(page)
    inside = img.pixelColor(145, 30)     # near top-center of triangle
    outside = img.pixelColor(105, 85)    # bbox corner OUTSIDE the triangle
    assert inside.red() > 200 and inside.green() < 80      # red image
    assert outside.red() > 200 and outside.green() > 200   # white page bg (clipped away)


def test_concave_notch_is_background(qapp, tmp_path):
    ref = _solid_png(tmp_path, Qt.red, size=(100, 100))
    # L-shape (concave): outer 0..100 square with a notch cut out of the top-right
    segs = [PathSegment(type="move", pts=[(0.0, 0.0)]),
            PathSegment(type="line", pts=[(50.0, 0.0)]),
            PathSegment(type="line", pts=[(50.0, 50.0)]),
            PathSegment(type="line", pts=[(100.0, 50.0)]),
            PathSegment(type="line", pts=[(100.0, 100.0)]),
            PathSegment(type="line", pts=[(0.0, 100.0)]),
            PathSegment(type="close", pts=[])]
    page = PageSpec(page_size_px=(120, 120), background="#FFFFFF", regions=[
        Region(id="L", kind="image", shape="path", segments=segs,
               bbox=(0, 0, 100, 100), image_ref=ref)])
    img = qt_renderer.render_page_to_image(page)
    notch = img.pixelColor(75, 25)   # inside bbox, inside the removed notch
    body = img.pixelColor(25, 25)    # solid part of the L
    assert notch.red() > 200 and notch.green() > 200   # background
    assert body.red() > 200 and body.green() < 80      # red image


def test_borderless_when_stroke_zero(qapp, tmp_path):
    page = PageSpec(page_size_px=(200, 150), regions=[
        Region(id="e", kind="image", bbox=(10, 10, 80, 80),
               image_style=ImageStyle(stroke_px=0))])
    scene = qt_renderer.build_scene(page)
    frame = [it for it in scene.items()
             if it.data(0) == "e" and hasattr(it, "path")][0]
    assert frame.pen().style() == Qt.NoPen


def test_stroke_pen_when_stroke_positive(qapp):
    page = PageSpec(page_size_px=(200, 150), regions=[
        Region(id="e", kind="image", bbox=(10, 10, 80, 80),
               image_style=ImageStyle(stroke_px=4, stroke_color="#FF0000"))])
    scene = qt_renderer.build_scene(page)
    frame = [it for it in scene.items()
             if it.data(0) == "e" and hasattr(it, "path")][0]
    assert frame.pen().widthF() == 4
    assert frame.pen().color().red() == 255


def test_filled_image_region_still_selectable(qapp, tmp_path):
    ref = _solid_png(tmp_path, Qt.white)
    page = PageSpec(page_size_px=(200, 150), regions=[
        Region(id="img1", kind="image", bbox=(10, 10, 80, 80), image_ref=ref)])
    scene = qt_renderer.build_scene(page, selectable=True)
    pix = [it for it in scene.items() if isinstance(it, QGraphicsPixmapItem)]
    assert pix and (pix[0].flags() & QGraphicsItem.ItemIsSelectable)
    assert pix[0].data(0) == "img1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_image_clip_stroke.py -q`
Expected: FAIL — current `_add_image_region` does not clip to shape (triangle/notch assertions fail) and ignores `stroke_px`.

- [ ] **Step 3: Implement clip-parent rendering**

In `core/layout/qt_renderer.py`, add `QGraphicsPathItem` to the widgets import:

```python
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsRectItem, QGraphicsPolygonItem,
    QGraphicsSimpleTextItem, QGraphicsItem, QGraphicsPixmapItem, QGraphicsPathItem,
)
```

Add the clip-parent item class after `_RegionPixmapItem`:

```python
class _RegionPathItem(_RegionMoveMixin, QGraphicsPathItem):
    def __init__(self, path: QPainterPath, region: Region):
        super().__init__(path)
        self._bind_region(region)

    def shape(self):
        # Clip children to the FILLED interior, not the stroked outline (the
        # default QGraphicsPathItem.shape() would return just the pen outline).
        return self.path()
```

Replace the entire `_add_image_region` function with:

```python
def _add_image_region(scene: QGraphicsScene, r: Region, selectable: bool,
                      *, locked: bool = True) -> None:
    # Image frames are ALWAYS locked in position (only text follows the lock
    # toggle); they stay selectable so the region can be picked.
    movable = False
    istyle = r.image_style
    stroke_px = istyle.stroke_px if istyle else 0
    stroke_color = istyle.stroke_color if istyle else "#000000"
    fit = istyle.fit if istyle else "cover"

    path = region_to_painter_path(r)
    frame = _RegionPathItem(path, r)
    frame.setFlag(QGraphicsItem.ItemClipsChildrenToShape, True)
    frame.setPen(QPen(QColor(stroke_color), stroke_px) if stroke_px > 0 else QPen(Qt.NoPen))

    pix = QPixmap(r.image_ref) if r.image_ref else None
    filled = pix is not None and not pix.isNull()

    if filled:
        frame.setBrush(QBrush(Qt.transparent))
        x, y, w, h = r.bbox
        mode = Qt.KeepAspectRatioByExpanding if fit == "cover" else Qt.KeepAspectRatio
        scaled = pix.scaled(int(w), int(h), mode, Qt.SmoothTransformation)
        child = _RegionPixmapItem(scaled, r)
        # Center the scaled pixmap in the bbox; the parent shape clip crops the
        # overflow (cover) or reveals panel bg in the letterbox (contain).
        child.setOffset(x + (w - scaled.width()) / 2.0, y + (h - scaled.height()) / 2.0)
        child.setParentItem(frame)
        _apply_flags(child, selectable, r.id, movable=movable)
    else:
        frame.setBrush(QBrush(_PLACEHOLDER_FILL))
        lx, ly, _, _ = r.bbox
        label = QGraphicsSimpleTextItem(r.name or "[image]", frame)
        label.setPos(lx + 4, ly + 4)
        label.setBrush(QBrush(QColor("#6C757D")))

    _apply_flags(frame, selectable, r.id, movable=movable)
    scene.addItem(frame)
```

- [ ] **Step 4: Run the new test, then the full suite**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_image_clip_stroke.py -q`
Expected: PASS (6 passed).

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q`
Expected: PASS (all green; `test_filled_image_region_is_selectable` in `test_qt_renderer.py` still passes — the pixmap child is selectable and carries the id).

- [ ] **Step 5: Commit**

```bash
git add core/layout/qt_renderer.py tests/layout/test_image_clip_stroke.py
git commit -m "feat(layout): clip image regions to shape + honor stroke (0=borderless)"
```

---

### Task 6: Clip text to the region shape

**Files:**
- Modify: `core/layout/qt_renderer.py` (rewrite `_add_text_region`)
- Test: `tests/layout/test_text_clip.py` (create)

**Interfaces:**
- Consumes: `region_to_painter_path` (Task 4), `_RegionPathItem` (Task 5).
- Produces: text is a child of a clip `_RegionPathItem` (with `ItemClipsChildrenToShape`), so it cannot spill past a shaped panel; the editor-only dashed guide box and font resolution are preserved.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_text_clip.py`:

```python
from PySide6.QtWidgets import QGraphicsItem, QGraphicsSimpleTextItem
from core.layout.models import Region, PageSpec
from core.layout import qt_renderer


def test_text_is_child_of_a_clipping_path_item(qapp):
    page = PageSpec(page_size_px=(400, 200), regions=[
        Region(id="t", kind="text", bbox=(0, 0, 100, 40), text="Hello world")])
    scene = qt_renderer.build_scene(page)  # export path (selectable=False)
    texts = [it for it in scene.items() if isinstance(it, QGraphicsSimpleTextItem)]
    assert texts, "expected a text item"
    parent = texts[0].parentItem()
    assert parent is not None
    assert bool(parent.flags() & QGraphicsItem.ItemClipsChildrenToShape)


def test_guide_box_still_editor_only(qapp):
    from PySide6.QtWidgets import QGraphicsRectItem
    page = PageSpec(page_size_px=(400, 200), regions=[
        Region(id="t", kind="text", bbox=(0, 0, 100, 40), text="Hi")])
    editor = qt_renderer.build_scene(page, selectable=True)
    assert any(isinstance(it, QGraphicsRectItem) and it.data(0) == "t" for it in editor.items())
    export = qt_renderer.build_scene(page, selectable=False)
    assert not any(isinstance(it, QGraphicsRectItem) and it.data(0) == "t" for it in export.items())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_text_clip.py -q`
Expected: FAIL — text is currently top-level (export) or a child of the rect box, not a clip path item.

- [ ] **Step 3: Rewrite `_add_text_region`**

Replace the entire `_add_text_region` function in `core/layout/qt_renderer.py` with:

```python
def _add_text_region(scene: QGraphicsScene, r: Region, selectable: bool, project_style=None,
                     *, locked: bool = True) -> None:
    x, y, w, h = r.bbox

    # Editor-only dashed guide box doubles as the region's selectable/movable
    # handle; export paths (selectable=False) omit it.
    box = None
    if selectable:
        box = _RegionRectItem(QRectF(x, y, w, h), r)
        box.setBrush(QBrush(Qt.transparent))
        pen = QPen(_TEXT_GUIDE_PEN, 1.5, Qt.DashLine)
        pen.setCosmetic(True)
        box.setPen(pen)
        _apply_flags(box, selectable, r.id, movable=(selectable and not locked))
        scene.addItem(box)

    # Clip item: text is parented here so it cannot spill past the panel shape.
    # When a guide box exists, the clip rides under it so a drag moves both.
    clip = _RegionPathItem(region_to_painter_path(r), r)
    clip.setPen(QPen(Qt.NoPen))
    clip.setBrush(QBrush(Qt.transparent))
    clip.setFlag(QGraphicsItem.ItemClipsChildrenToShape, True)
    if box is not None:
        clip.setParentItem(box)
    else:
        scene.addItem(clip)

    text = QGraphicsSimpleTextItem(r.text or "")
    ts = effective_text_style(r, project_style)
    font = QFont()
    if ts:
        if ts.family:
            font.setFamily(ts.family[0])
        font.setBold(ts.weight in ("bold", "black", "semibold"))
        font.setItalic(ts.italic)
        text.setBrush(QBrush(QColor(ts.color)))
    font.setPixelSize(ts.size_px if ts and ts.size_px else _DEFAULT_TEXT_PX)
    text.setFont(font)
    text.setParentItem(clip)
    text.setPos(x + 2, y + 2)
```

- [ ] **Step 4: Run the new test, then the full suite**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_text_clip.py -q`
Expected: PASS (2 passed).

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q`
Expected: PASS (all green; the font-resolution and guide-box tests in `test_qt_renderer.py` still pass — the text item and the editor-only rect box are both still present).

- [ ] **Step 5: Commit**

```bash
git add core/layout/qt_renderer.py tests/layout/test_text_clip.py
git commit -m "feat(layout): clip text regions to the panel shape"
```

---

### Task 7: Bleed rendering (extended canvas)

**Files:**
- Modify: `core/layout/qt_renderer.py` (`build_scene` gains `region_filter`; `render_page_to_image` honors `bleed_px`)
- Test: `tests/layout/test_bleed_render.py` (create)

**Interfaces:**
- Consumes: existing `build_scene`/`render_page_to_image`.
- Produces: when `page.bleed_px > 0`, the rendered image is `(pw+2b)×(ph+2b)`; non-`bleed` regions are clipped to the trim box, `bleed` regions may paint into the surrounding margin. `b == 0` is unchanged (all existing tests).

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_bleed_render.py`:

```python
from PySide6.QtGui import QImage
from PySide6.QtCore import Qt
from core.layout.models import Region, PageSpec
from core.layout import qt_renderer


def _solid_png(tmp_path, color, size=(200, 60)):
    im = QImage(size[0], size[1], QImage.Format_RGB32)
    im.fill(color)
    p = tmp_path / "ref.png"
    assert im.save(str(p))
    return str(p)


def test_canvas_grows_by_bleed(qapp):
    page = PageSpec(page_size_px=(200, 150), bleed_px=20, background="#FFFFFF")
    img = qt_renderer.render_page_to_image(page)
    assert img.width() == 240 and img.height() == 190


def test_bleed_region_paints_into_margin(qapp, tmp_path):
    ref = _solid_png(tmp_path, Qt.red)
    # geometry spans y in [-20, 20] (into the top bleed) across the full width
    page = PageSpec(page_size_px=(200, 150), bleed_px=20, background="#FFFFFF", regions=[
        Region(id="b", kind="image", bbox=(0, -20, 200, 40), image_ref=ref, bleed=True)])
    img = qt_renderer.render_page_to_image(page)
    # device (100, 5) is inside the top bleed band [0,20)
    c = img.pixelColor(100, 5)
    assert c.red() > 200 and c.green() < 80


def test_non_bleed_region_is_clipped_at_trim(qapp, tmp_path):
    ref = _solid_png(tmp_path, Qt.red)
    page = PageSpec(page_size_px=(200, 150), bleed_px=20, background="#FFFFFF", regions=[
        Region(id="n", kind="image", bbox=(0, -20, 200, 40), image_ref=ref, bleed=False)])
    img = qt_renderer.render_page_to_image(page)
    margin = img.pixelColor(100, 5)    # top bleed band -> clipped away -> bg
    inside = img.pixelColor(100, 25)   # within trim (device y >= 20) -> red
    assert margin.red() > 200 and margin.green() > 200
    assert inside.red() > 200 and inside.green() < 80
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_bleed_render.py -q`
Expected: FAIL — canvas is currently `200×150` and bleed is ignored.

- [ ] **Step 3: Implement bleed-aware rendering**

In `core/layout/qt_renderer.py`, give `build_scene` an optional `region_filter`:

```python
def build_scene(page: PageSpec, *, selectable: bool = False, style=None,
                locked: bool = True, region_filter=None) -> QGraphicsScene:
    pw, ph = page.page_size_px
    scene = QGraphicsScene(0, 0, pw, ph)
    scene.setBackgroundBrush(QBrush(QColor(_resolve_bg(page))))
    regions = page.regions if region_filter is None else [r for r in page.regions if region_filter(r)]
    for r in sorted(regions, key=lambda rr: rr.z):
        if r.kind == "image":
            _add_image_region(scene, r, selectable, locked=locked)
        else:
            _add_text_region(scene, r, selectable, project_style=style, locked=locked)
    return scene
```

Replace `render_page_to_image` with a bleed-aware version:

```python
def render_page_to_image(page: PageSpec, *, style=None) -> QImage:
    pw, ph = page.page_size_px
    b = max(0, int(getattr(page, "bleed_px", 0) or 0))
    cw, ch = pw + 2 * b, ph + 2 * b
    img = QImage(cw, ch, QImage.Format_ARGB32)
    img.fill(QColor(_resolve_bg(page)))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)
    if b == 0:
        scene = build_scene(page, style=style)
        scene.render(painter, QRectF(0, 0, pw, ph), QRectF(0, 0, pw, ph))
        painter.end()
        return img
    # Non-bleed regions are clipped to the trim box, offset into the bleed canvas.
    painter.save()
    painter.setClipRect(QRectF(b, b, pw, ph))
    non_bleed = build_scene(page, style=style, region_filter=lambda r: not r.bleed)
    non_bleed.render(painter, QRectF(b, b, pw, ph), QRectF(0, 0, pw, ph))
    painter.restore()
    # Bleed regions may extend into the surrounding margin: map the full bleed box
    # in scene coords onto the whole canvas.
    bleed_scene = build_scene(page, style=style, region_filter=lambda r: r.bleed)
    bleed_scene.render(painter, QRectF(0, 0, cw, ch), QRectF(-b, -b, cw, ch))
    painter.end()
    return img
```

- [ ] **Step 4: Run the new test, then the full suite**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_bleed_render.py -q`
Expected: PASS (3 passed).

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q`
Expected: PASS — all green, including the original 166 (existing pages default `bleed_px=0`, so they hit the unchanged `b == 0` branch).

- [ ] **Step 5: Commit**

```bash
git add core/layout/qt_renderer.py tests/layout/test_bleed_render.py
git commit -m "feat(layout): bleed-aware rendering on an extended canvas"
```

---

## Notes / deliberately deferred (not gaps)
- **PDF bleed:** `export_document_pdf` is left at trim size in #1; applying bleed to the PDF path is folded into the later page/export work. (PNG/`QImage` bleed — the testable acceptance criterion — is implemented here.)
- **GUI export still uses the PIL engine, not this Qt renderer (whole-branch review, Important #2).** `gui/layout/export_dialog.py` renders PNG/PDF via `core/layout/engine.py` (`LayoutEngine.render_page`), which has **none** of #1's shape-clipping / per-region stroke / bleed. The live editor canvas (`gui/layout/canvas_widget.py`) *does* use the Qt `build_scene`, so the new rendering is visible in-editor — but real exports diverge. **Sub-project #2 (or a dedicated export task) must consciously pick the source of truth:** migrate export to the Qt path or port the features. This is the single biggest follow-up for the renderer to actually reach exported output.
- **Canvas growth on `PageSpec.bleed_px`:** `render_page_to_image` grows the export canvas whenever `bleed_px > 0` (print-bleed semantics — see the design doc's bleed decision), independent of whether any region is `bleed=True`. Deliberate; revisit only if a "grow only when a region bleeds" semantics is preferred.
- **Editor authoring** of curves/vertices, **tiling/inset gutters**, **balloons**, and the **AI designer** emitting `path`/`segments` are sub-projects #2–#5 per the spec.
- **`contain` centering:** the scaled pixmap is centered in the bbox for both fits; arbitrary alignment is not in scope.
- **Path-region drag writeback (#5):** `_writeback_move` persists drags into `bbox`/`points` only, not `segments`; image frames are `movable=False` today so this is not a live bug, but the manual editor (#5) must handle segment writeback.

## Self-Review (completed by plan author)
- **Spec coverage:** path geometry (T1), pure helpers (T2), serialization + normalize (T3), path builder (T4), image clip-to-shape + stroke/borderless (T5), text clip (T6), bleed (T7). All §3–§8 spec items map to a task; acceptance criteria 1–7 are each covered by a test.
- **Placeholder scan:** none — every code/test step contains full content.
- **Type/name consistency:** `PathSegment(type, pts)`, `Region.shape/segments/bleed`, `validate_segments`, `segments_bbox`, `region_to_painter_path`, `_RegionPathItem` are used identically across tasks.
