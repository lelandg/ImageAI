# Curved Text Overlays Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overlay text (caption/sfx) can follow an editable quadratic-Bézier curve, rendered identically in GUI canvas, PNG, and PDF, with drag-handle editing and AI-designer authoring.

**Architecture:** A new optional `Overlay.text_path` (one `move` + one `quad` PathSegment) is serialized as an SVG d-string. `qt_renderer._add_overlay` grows a branch that lays glyph outlines along the arc-length-parameterized curve into a single `QGraphicsPathItem` (fill = text color, pen = new `TextStyle.outline_px/outline_color`). `OverlayEditor` gains three drag handles; `OverlayInspector` gains a curve toggle + outline/point controls; the designer prompt learns the optional `text_path` key.

**Tech Stack:** Python 3.12, PySide6 (QPainterPath / QGraphicsPathItem), dataclasses, pytest with the existing `qapp` fixture (`tests/conftest.py:8`).

**Spec:** `Plans/2026-07-29-layout-curved-text-design.md` (approved 2026-07-29).

## Global Constraints

- Repo root: `/mnt/d/Documents/Code/GitHub/ImageAI` — all commands run with absolute paths, never `cd`.
- Test command prefix (WSL): `PYTHONPATH=/mnt/d/Documents/Code/GitHub/ImageAI QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python3 -m pytest`
- Branch: `feat/layout-curved-text` (already created from origin/main). Commit after every task; never commit on red tests.
- `text_path` is honored **only** for overlay kinds `caption` and `sfx`; exactly `[move, quad]`; coordinates are page pixels.
- Malformed `text_path` NEVER raises — log a warning and treat as None (project must still open).
- Old project files must round-trip unchanged: when `text_path` is None the key is omitted; `TextStyle` outline fields default to `0.0` / `"#000000"`.
- `TextStyle` has NO default for `family` — construct with `TextStyle(family=["DejaVu Sans"])` in any new code.
- Do not modify `main_original.py`, `core/layout/engine.py`, or `core/layout/text_renderer.py` (legacy, not in the render path).

---

### Task 1: Pure curve/layout helpers (`core/layout/text_path.py`)

**Files:**
- Create: `core/layout/text_path.py`
- Test: `tests/layout/test_text_path.py`

**Interfaces:**
- Consumes: `core.layout.models.PathSegment`, `core.layout.geometry.validate_segments`.
- Produces (used by Tasks 2–6):
  - `validate_text_path(segments: List[PathSegment]) -> List[str]`
  - `default_text_path(anchor: Tuple[float, float], chord_w: float, peak_px: Optional[float] = None) -> List[PathSegment]`
  - `glyph_offsets(advances: List[float], path_len: float, align: str, letter_spacing: float = 0.0) -> List[float]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/layout/test_text_path.py
from core.layout.models import PathSegment
from core.layout.text_path import validate_text_path, default_text_path, glyph_offsets


def _mq(x0=0.0, y0=0.0, cx=50.0, cy=-20.0, x1=100.0, y1=0.0):
    return [PathSegment(type="move", pts=[(x0, y0)]),
            PathSegment(type="quad", pts=[(cx, cy), (x1, y1)])]


def test_validate_accepts_move_quad():
    assert validate_text_path(_mq()) == []


def test_validate_rejects_wrong_shapes():
    assert validate_text_path([]) != []
    assert validate_text_path(_mq() + [PathSegment(type="close", pts=[])]) != []
    assert validate_text_path([PathSegment(type="move", pts=[(0, 0)]),
                               PathSegment(type="line", pts=[(10, 0)])]) != []
    assert validate_text_path([PathSegment(type="quad", pts=[(1, 1), (2, 2)])]) != []


def test_validate_rejects_non_finite():
    bad = _mq(cx=float("nan"))
    assert validate_text_path(bad) != []


def test_default_text_path_geometry():
    segs = default_text_path((500.0, 300.0), 400.0)
    assert validate_text_path(segs) == []
    (sx, sy) = segs[0].pts[0]
    (cx, cy), (ex, ey) = segs[1].pts
    assert (sx, sy) == (300.0, 300.0)
    assert (ex, ey) == (700.0, 300.0)
    assert cx == 500.0
    # peak defaults to 12% of chord; control sits at 2x the peak above the chord
    assert abs(cy - (300.0 - 2 * 0.12 * 400.0)) < 1e-9


def test_default_text_path_explicit_peak():
    segs = default_text_path((0.0, 0.0), 200.0, peak_px=10.0)
    assert segs[1].pts[0][1] == -20.0


def test_glyph_offsets_center_symmetric():
    # Three glyphs of width 10 on a path of length 100, centered:
    # total 30, start 35 -> midpoints at 40, 50, 60.
    offs = glyph_offsets([10.0, 10.0, 10.0], 100.0, "center")
    assert offs == [40.0, 50.0, 60.0]


def test_glyph_offsets_left_right():
    assert glyph_offsets([10.0, 10.0], 100.0, "left") == [5.0, 15.0]
    assert glyph_offsets([10.0, 10.0], 100.0, "right") == [85.0, 95.0]


def test_glyph_offsets_letter_spacing_monotonic():
    offs = glyph_offsets([10.0, 10.0, 10.0], 100.0, "left", letter_spacing=4.0)
    assert offs == [5.0, 19.0, 33.0]
    assert all(b > a for a, b in zip(offs, offs[1:]))


def test_glyph_offsets_overflow_not_truncated():
    # Text longer than the path: offsets run past the ends instead of clamping.
    offs = glyph_offsets([60.0, 60.0], 100.0, "center")
    assert offs[0] < 30.0 + 1e-9
    assert offs[-1] > 100.0 - 30.0 - 1e-9
    assert len(offs) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=/mnt/d/Documents/Code/GitHub/ImageAI QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python3 -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_text_path.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.layout.text_path'`

- [ ] **Step 3: Write the implementation**

```python
# core/layout/text_path.py
"""Pure helpers for text-on-a-curve overlays (no Qt).

The curve is a single open quadratic Bézier: segments == [move, quad].
Glyph layout math lives here so it is unit-testable without a QApplication;
the Qt renderer maps the resulting arc-length offsets onto the painter path.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from core.layout.geometry import validate_segments
from core.layout.models import PathSegment


def validate_text_path(segments: List[PathSegment]) -> List[str]:
    """Problems for an overlay text path; [] means valid.

    v1 contract: exactly one 'move' followed by one 'quad' (open path).
    """
    issues = validate_segments(segments or [])
    if issues:
        return issues
    if (len(segments) != 2 or segments[0].type != "move"
            or segments[1].type != "quad"):
        return ["text path must be exactly M + Q (one open quadratic Bézier)"]
    return []


def default_text_path(anchor: Tuple[float, float], chord_w: float,
                      peak_px: Optional[float] = None) -> List[PathSegment]:
    """Seed a gentle upward arch centred on ``anchor``.

    ``peak_px`` is the visual rise of the curve's midpoint above the chord
    (defaults to 12% of the chord). The quad control point sits at twice the
    peak because a quadratic Bézier's midpoint lies halfway to the control.
    """
    ax, ay = anchor
    w = max(40.0, float(chord_w))
    peak = w * 0.12 if peak_px is None else float(peak_px)
    return [
        PathSegment(type="move", pts=[(ax - w / 2.0, ay)]),
        PathSegment(type="quad", pts=[(ax, ay - 2.0 * peak), (ax + w / 2.0, ay)]),
    ]


def glyph_offsets(advances: List[float], path_len: float, align: str,
                  letter_spacing: float = 0.0) -> List[float]:
    """Arc-length distance of each glyph's advance midpoint along the path.

    ``advances`` are per-glyph advance widths (spaces included). Offsets may
    run past [0, path_len] when the text is longer than the curve; the caller
    extrapolates along the end tangents rather than truncating.
    """
    total = sum(advances) + letter_spacing * max(0, len(advances) - 1)
    if align == "left":
        start = 0.0
    elif align == "right":
        start = path_len - total
    else:  # center: default for curved text (incl. "justify", meaningless here)
        start = (path_len - total) / 2.0
    out: List[float] = []
    d = start
    for adv in advances:
        out.append(d + adv / 2.0)
        d += adv + letter_spacing
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Same command as Step 2. Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/layout/text_path.py tests/layout/test_text_path.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(layout): pure text-path helpers for curved overlay text"
```

---

### Task 2: Model fields + schema round-trip

**Files:**
- Modify: `core/layout/models.py:40-52` (TextStyle), `core/layout/models.py:141-160` (Overlay)
- Modify: `core/layout/schema.py:1-9` (imports), `:49-67` (OVERLAY_JSON_SCHEMA), `:118-145` (overlay to/from dict)
- Test: `tests/layout/test_overlay_text_path_schema.py`

**Interfaces:**
- Consumes: Task 1's `validate_text_path`; existing `svg_path.svg_to_segments` / `segments_to_svg`.
- Produces: `Overlay.text_path: Optional[List[PathSegment]] = None`; `TextStyle.outline_px: float = 0.0`; `TextStyle.outline_color: str = "#000000"`; JSON key `"text_path": "M x y Q cx cy x y"` (omitted when None).

- [ ] **Step 1: Write the failing tests**

```python
# tests/layout/test_overlay_text_path_schema.py
from core.layout.models import Overlay, PathSegment, TextStyle
from core.layout.schema import overlay_to_dict, overlay_from_dict


def _tp():
    return [PathSegment(type="move", pts=[(100.0, 200.0)]),
            PathSegment(type="quad", pts=[(300.0, 120.0), (500.0, 200.0)])]


def test_round_trip_text_path():
    ov = Overlay(id="t", kind="caption", text="TITLE", anchor=(300.0, 200.0),
                 text_path=_tp())
    d = overlay_to_dict(ov)
    assert d["text_path"] == "M 100 200 Q 300 120 500 200"
    back = overlay_from_dict(d)
    assert back.text_path is not None
    assert back.text_path[0].type == "move"
    assert back.text_path[1].pts == [(300.0, 120.0), (500.0, 200.0)]


def test_none_text_path_key_omitted():
    ov = Overlay(id="t", kind="caption", text="x", anchor=(0.0, 0.0))
    d = overlay_to_dict(ov)
    assert "text_path" not in d
    assert overlay_from_dict(d).text_path is None


def test_malformed_text_path_dropped_with_warning(caplog):
    d = overlay_to_dict(Overlay(id="t", kind="sfx", text="x", anchor=(0.0, 0.0)))
    d["text_path"] = "M 0 0 L 10 10"  # line, not quad -> invalid contract
    with caplog.at_level("WARNING"):
        back = overlay_from_dict(d)
    assert back.text_path is None
    assert any("text_path" in r.message for r in caplog.records)


def test_garbage_text_path_dropped():
    d = overlay_to_dict(Overlay(id="t", kind="sfx", text="x", anchor=(0.0, 0.0)))
    d["text_path"] = "not a path"
    assert overlay_from_dict(d).text_path is None


def test_text_style_outline_round_trip():
    ts = TextStyle(family=["DejaVu Sans"], outline_px=3.0, outline_color="#442200")
    ov = Overlay(id="t", kind="caption", text="x", anchor=(0.0, 0.0), text_style=ts)
    back = overlay_from_dict(overlay_to_dict(ov))
    assert back.text_style.outline_px == 3.0
    assert back.text_style.outline_color == "#442200"


def test_old_file_without_outline_fields_loads():
    ov = Overlay(id="t", kind="caption", text="x", anchor=(0.0, 0.0),
                 text_style=TextStyle(family=["DejaVu Sans"]))
    d = overlay_to_dict(ov)
    del d["text_style"]["outline_px"]
    del d["text_style"]["outline_color"]
    back = overlay_from_dict(d)
    assert back.text_style.outline_px == 0.0
    assert back.text_style.outline_color == "#000000"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=/mnt/d/Documents/Code/GitHub/ImageAI QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python3 -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_overlay_text_path_schema.py -v`
Expected: FAIL — `TypeError: Overlay.__init__() got an unexpected keyword argument 'text_path'`

- [ ] **Step 3: Add the model fields**

In `core/layout/models.py`, `TextStyle` — append after `letter_spacing: float = 0.0`:

```python
    # Glyph outline, applied by the curved-text renderer (0 = no outline).
    outline_px: float = 0.0
    outline_color: str = "#000000"
```

In `Overlay` — append after `rotation: float = 0.0  # degrees ...`:

```python
    # Optional text-on-a-curve baseline: exactly [move, quad] in page pixels.
    # Honored for caption/sfx kinds; None = normal straight block at `anchor`.
    text_path: Optional[List["PathSegment"]] = None
```

- [ ] **Step 4: Wire the schema**

In `core/layout/schema.py` add at the top (after the existing imports):

```python
import logging

from core.layout.svg_path import segments_to_svg, svg_to_segments
from core.layout.text_path import validate_text_path

logger = logging.getLogger(__name__)
```

In `OVERLAY_JSON_SCHEMA["properties"]` add (also fixing the pre-existing `rotation` drift):

```python
        "rotation": {"type": "number"},
        "text_path": {"type": "string"},
```

In `overlay_to_dict`, after building `d` and before `return d`:

```python
    if ov.text_path:
        d["text_path"] = segments_to_svg(ov.text_path)
```

In `overlay_from_dict`, before the `return Overlay(...)` add:

```python
    text_path = None
    tp_raw = d.get("text_path")
    if tp_raw:
        segs = svg_to_segments(str(tp_raw))
        problems = validate_text_path(segs)
        if problems:
            logger.warning("Overlay %r: invalid text_path %r dropped: %s",
                           d.get("id"), tp_raw, "; ".join(problems))
        else:
            text_path = segs
```

and pass `text_path=text_path,` in the `Overlay(...)` constructor call.

- [ ] **Step 5: Run tests to verify they pass**

Same command as Step 2. Expected: 6 passed. Also run the neighbors to catch regressions:
`... -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_overlay_schema.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_overlay_model.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/layout/models.py core/layout/schema.py tests/layout/test_overlay_text_path_schema.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(layout): Overlay.text_path + TextStyle outline fields with SVG d-string serialization"
```

---

### Task 3: Curved-text rendering in `qt_renderer`

**Files:**
- Modify: `core/layout/qt_renderer.py` — imports (`:1-18`), `_add_overlay` (`:286-388`), new helpers before `_add_overlay`
- Test: `tests/layout/test_overlay_text_path_render.py`

**Interfaces:**
- Consumes: Task 1 (`glyph_offsets`, `validate_text_path`), Task 2 fields, existing `segments_to_painter_path`.
- Produces:
  - `_overlay_font(ts) -> QFont` (module-private; also used by Task 5's seed sizing)
  - `_point_angle_at(path: QPainterPath, dist: float) -> tuple[QPointF, float]`
  - `_curved_text_glyphs(text: str, font: QFont, ts, curve: QPainterPath) -> QPainterPath`
  - Scene contract: a curved overlay contributes exactly one `QGraphicsPathItem` with `item.data(0) == overlay.id`, brush = text color, pen = outline (NoPen when 0), and NO balloon body.

- [ ] **Step 1: Write the failing tests**

```python
# tests/layout/test_overlay_text_path_render.py
from PySide6.QtWidgets import QGraphicsPathItem

from core.layout.models import Overlay, PageSpec, PathSegment, TextStyle
from core.layout import qt_renderer


def _tp(y=200.0, peak=40.0):
    return [PathSegment(type="move", pts=[(50.0, y)]),
            PathSegment(type="quad", pts=[(200.0, y - 2 * peak), (350.0, y)])]


def _curved(text="CURVED TITLE", **kw):
    ts = kw.pop("text_style", TextStyle(family=["DejaVu Sans"], size_px=32,
                                        color="#000000", align="center"))
    return Overlay(id="c1", kind="caption", text=text, anchor=(200.0, 200.0),
                   text_path=_tp(), text_style=ts, **kw)


def _page(overlays):
    return PageSpec(page_size_px=(400, 400), regions=[], overlays=overlays)


def _path_items(scene):
    return [it for it in scene.items()
            if isinstance(it, QGraphicsPathItem) and it.data(0) == "c1"]


def test_curved_overlay_adds_single_path_item_no_body(qapp):
    scene = qt_renderer.build_scene(_page([_curved()]))
    items = _path_items(scene)
    assert len(items) == 1
    # No balloon body: the only other items would be body/_OverlayPathItem or text
    assert not any(isinstance(it, qt_renderer._OverlayPathItem) for it in scene.items())


def test_glyphs_follow_curve_above_chord(qapp):
    scene = qt_renderer.build_scene(_page([_curved()]))
    item = _path_items(scene)[0]
    r = item.path().boundingRect()
    # Peak is 40px above the chord at y=200; glyph tops must reach well above
    # the chord, and the path must span most of the curve horizontally.
    assert r.top() < 175.0
    assert r.width() > 150.0


def test_curved_text_renders_pixels_along_arc(qapp):
    img = qt_renderer.render_page_to_image(_page([_curved()]))
    # Sample mid-glyph above the arc baseline (baseline dips to y=160 at the
    # midpoint; a 32px font's glyph bodies sit roughly y 135-160) — must be inked.
    found_dark = False
    for dx in range(-30, 31, 5):
        c = img.pixelColor(200 + dx, 150)
        if c.lightness() < 200:
            found_dark = True
            break
    assert found_dark


def test_outline_pen_applied(qapp):
    ts = TextStyle(family=["DejaVu Sans"], size_px=32, color="#FFD700",
                   align="center", outline_px=3.0, outline_color="#331100")
    scene = qt_renderer.build_scene(_page([_curved(text_style=ts)]))
    item = _path_items(scene)[0]
    assert abs(item.pen().widthF() - 3.0) < 1e-6
    assert item.brush().color().name().lower() == "#ffd700"


def test_no_outline_means_no_pen(qapp):
    from PySide6.QtCore import Qt
    scene = qt_renderer.build_scene(_page([_curved()]))
    assert _path_items(scene)[0].pen().style() == Qt.NoPen


def test_rotation_applied_about_anchor(qapp):
    scene = qt_renderer.build_scene(_page([_curved(rotation=25.0)]))
    item = _path_items(scene)[0]
    assert abs(item.rotation() - 25.0) < 1e-6


def test_invalid_text_path_falls_back_to_straight_block(qapp, caplog):
    ov = _curved()
    ov.text_path = [PathSegment(type="move", pts=[(0.0, 0.0)])]  # invalid: no quad
    with caplog.at_level("WARNING"):
        scene = qt_renderer.build_scene(_page([ov]))
    # Falls through to the normal caption path -> a balloon body exists.
    assert any(isinstance(it, qt_renderer._OverlayPathItem) for it in scene.items())


def test_speech_kind_ignores_text_path(qapp):
    ov = Overlay(id="c1", kind="speech", text="hi", anchor=(200.0, 200.0),
                 text_path=_tp())
    scene = qt_renderer.build_scene(_page([ov]))
    assert any(isinstance(it, qt_renderer._OverlayPathItem) for it in scene.items())


def test_empty_text_adds_nothing_and_does_not_crash(qapp):
    scene = qt_renderer.build_scene(_page([_curved(text="")]))
    assert _path_items(scene) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=/mnt/d/Documents/Code/GitHub/ImageAI QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python3 -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_overlay_text_path_render.py -v`
Expected: FAIL (curved overlays currently render as normal captions; `_path_items` finds nothing).

- [ ] **Step 3: Implement rendering**

In `core/layout/qt_renderer.py` add to the top-level imports: `import math`, and extend the `core.layout` imports:

```python
from core.layout.text_path import glyph_offsets, validate_text_path
```

Insert the three helpers just above `_add_overlay` (after `_overlay_as_styleable`):

```python
def _overlay_font(ts) -> QFont:
    """Font for overlay text; first family present in Qt's font DB wins.

    Falls back to the first listed family (Qt substitutes) when none match,
    and to DejaVu Sans when no style/family is given.
    """
    from PySide6.QtGui import QFontDatabase
    font = QFont()
    fams = list(ts.family) if ts and ts.family else ["DejaVu Sans"]
    available = set(QFontDatabase.families())
    font.setFamily(next((f for f in fams if f in available), fams[0]))
    font.setPixelSize(ts.size_px if ts and ts.size_px else 16)
    if ts and ts.italic:
        font.setItalic(True)
    if ts and ts.weight in ("bold", "black", "semibold"):
        font.setBold(True)
    return font


def _point_angle_at(path: QPainterPath, dist: float):
    """(point, tangent angle°) at arc length ``dist``, extrapolating past the ends.

    Qt angles are CCW-positive in a y-down space, so the tangent direction is
    (cos a, -sin a); overflowing glyphs continue straight along the exit tangent
    instead of piling up on the endpoint.
    """
    length = path.length()
    if 0.0 <= dist <= length:
        t = path.percentAtLength(dist)
        return path.pointAtPercent(t), path.angleAtPercent(t)
    edge = 0.0 if dist < 0.0 else 1.0
    p = path.pointAtPercent(edge)
    ang = path.angleAtPercent(edge)
    over = dist if dist < 0.0 else dist - length
    rad = math.radians(ang)
    return QPointF(p.x() + over * math.cos(rad), p.y() - over * math.sin(rad)), ang


def _curved_text_glyphs(text: str, font: QFont, ts, curve: QPainterPath) -> QPainterPath:
    """One combined outline path: each glyph's advance midpoint sits on the curve,
    rotated to the local tangent. Spaces consume arc length but add no outline."""
    from PySide6.QtGui import QFontMetricsF, QTransform
    fm = QFontMetricsF(font)
    spacing = float(getattr(ts, "letter_spacing", 0.0) or 0.0) if ts else 0.0
    advances = [fm.horizontalAdvance(ch) for ch in text]
    align = ts.align if ts and ts.align else "center"
    offsets = glyph_offsets(advances, curve.length(), align, spacing)
    out = QPainterPath()
    for ch, adv, dist in zip(text, advances, offsets):
        if ch.isspace():
            continue
        pos, ang = _point_angle_at(curve, dist)
        tr = QTransform()
        tr.translate(pos.x(), pos.y())
        tr.rotate(-ang)
        glyph = QPainterPath()
        glyph.addText(-adv / 2.0, 0.0, font, ch)
        out.addPath(tr.map(glyph))
    return out


def _add_curved_text_overlay(scene: QGraphicsScene, ov, ts, base_z: float) -> None:
    """Render a caption/sfx overlay whose text follows ov.text_path.

    One QGraphicsPathItem: brush = text color, pen = TextStyle outline. No
    balloon body. Same item serves canvas, PNG, and PDF.
    """
    font = _overlay_font(ts)
    curve = segments_to_painter_path(ov.text_path)
    glyphs = _curved_text_glyphs(ov.text or "", font, ts, curve)
    if glyphs.isEmpty():
        return
    item = QGraphicsPathItem(glyphs)
    item.setBrush(QBrush(QColor(ts.color if ts and ts.color else "#111111")))
    outline_px = float(getattr(ts, "outline_px", 0.0) or 0.0) if ts else 0.0
    if outline_px > 0:
        outline_color = (getattr(ts, "outline_color", "#000000") or "#000000")
        pen = QPen(QColor(outline_color), outline_px)
        pen.setJoinStyle(Qt.RoundJoin)  # avoid miter spikes on glyph corners
        item.setPen(pen)
    else:
        item.setPen(QPen(Qt.NoPen))
    item.setZValue(base_z + ov.z + 0.1)
    rot = getattr(ov, "rotation", 0.0) or 0.0
    if rot:
        item.setTransformOriginPoint(QPointF(ov.anchor[0], ov.anchor[1]))
        item.setRotation(rot)
    item.setData(0, ov.id)
    scene.addItem(item)
```

In `_add_overlay`, right after `ts = effective_text_style(...)` (line ~303), insert the branch:

```python
    # Text-on-a-curve: caption/sfx with a valid text_path bypass the balloon
    # body entirely; invalid paths log and fall through to the straight block.
    tp = getattr(ov, "text_path", None)
    if tp and ov.kind in ("caption", "sfx"):
        issues = validate_text_path(tp)
        if not issues:
            _add_curved_text_overlay(scene, ov, ts, base_z)
            return
        logger.warning("Overlay %s: invalid text_path ignored: %s",
                       ov.id, "; ".join(issues))
```

Then replace the inline font-building block in `_add_overlay` (lines ~305-313, from `font = QFont()` through `font.setBold(True)`) with:

```python
    font = _overlay_font(ts)
```

- [ ] **Step 4: Run tests to verify they pass**

Same command as Step 2. Expected: 9 passed. Regression check:
`... -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_overlay_render.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_overlay_render_rotation.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/layout/qt_renderer.py tests/layout/test_overlay_text_path_render.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(layout): render caption/sfx text along a quadratic Bézier with optional glyph outline"
```

---

### Task 4: Curve drag handles in `OverlayEditor`

**Files:**
- Modify: `gui/layout/overlay_editor.py`
- Test: `tests/layout/test_overlay_editor_text_path.py`

**Interfaces:**
- Consumes: `Overlay.text_path` (Task 2), `validate_text_path` (Task 1); existing `_OvHandle`, `begin_edit`/`move_handle`/`commit` protocol and `LayoutTab.set_refresh_suspended`/`snapshot_and_refresh`.
- Produces: handle kinds `"tp0"` (start, green), `"tpc"` (bow control, amber), `"tp1"` (end, green) alongside the existing `"body"`/`"tail"`; drags write back into `ov.text_path` segments; invalid geometry restores the pre-drag snapshot on commit.

- [ ] **Step 1: Write the failing tests**

Mirror `tests/layout/test_overlay_editor.py`'s fake-tab pattern — read that file first and reuse its stubs if they exist; otherwise:

```python
# tests/layout/test_overlay_editor_text_path.py
from core.layout.models import Overlay, PageSpec, PathSegment
from gui.layout.overlay_editor import OverlayEditor


class _FakeCanvas:
    def __init__(self, scene):
        self._scene = scene

    def scene(self):
        return self._scene


class _FakeTab:
    def __init__(self, page):
        self._page = page
        self.suspended = None
        self.refreshed = []

    def _current_page(self):
        return self._page

    def set_refresh_suspended(self, on):
        self.suspended = on

    def snapshot_and_refresh(self, prompt):
        self.refreshed.append(prompt)


def _tp():
    return [PathSegment(type="move", pts=[(100.0, 200.0)]),
            PathSegment(type="quad", pts=[(200.0, 120.0), (300.0, 200.0)])]


def _setup(qapp, overlay):
    from PySide6.QtWidgets import QGraphicsScene
    page = PageSpec(page_size_px=(400, 400), regions=[], overlays=[overlay])
    scene = QGraphicsScene(0, 0, 400, 400)
    tab = _FakeTab(page)
    ed = OverlayEditor(_FakeCanvas(scene), tab)
    ed.set_edit_overlay(overlay.id)
    return ed, tab


def test_curved_overlay_gets_five_handle_kinds_worth(qapp):
    ov = Overlay(id="c", kind="caption", text="T", anchor=(200.0, 200.0),
                 text_path=_tp())
    ed, _tab = _setup(qapp, ov)
    kinds = sorted(h._kind for h in ed._handles)
    assert kinds == ["body", "tp0", "tp1", "tpc"]


def test_straight_overlay_unchanged(qapp):
    ov = Overlay(id="c", kind="caption", text="T", anchor=(200.0, 200.0))
    ed, _tab = _setup(qapp, ov)
    assert sorted(h._kind for h in ed._handles) == ["body"]


def test_drag_control_writes_back(qapp):
    ov = Overlay(id="c", kind="caption", text="T", anchor=(200.0, 200.0),
                 text_path=_tp())
    ed, tab = _setup(qapp, ov)
    ed.begin_edit()
    ed.move_handle("tpc", 210.0, 90.0)
    assert ov.text_path[1].pts[0] == (210.0, 90.0)
    ed.move_handle("tp0", 90.0, 210.0)
    assert ov.text_path[0].pts[0] == (90.0, 210.0)
    ed.move_handle("tp1", 310.0, 190.0)
    assert ov.text_path[1].pts[1] == (310.0, 190.0)
    ed.commit()
    assert tab.refreshed  # snapshot taken


def test_commit_restores_on_invalid_geometry(qapp):
    ov = Overlay(id="c", kind="caption", text="T", anchor=(200.0, 200.0),
                 text_path=_tp())
    ed, _tab = _setup(qapp, ov)
    ed.begin_edit()
    ov.text_path[1].pts[0] = (float("nan"), 90.0)  # corrupt mid-drag
    ed.commit()
    assert ov.text_path[1].pts[0] == (200.0, 120.0)  # pre-drag restored
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=/mnt/d/Documents/Code/GitHub/ImageAI QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python3 -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_overlay_editor_text_path.py -v`
Expected: FAIL — handle kinds `tp0/tpc/tp1` don't exist.

- [ ] **Step 3: Implement**

In `gui/layout/overlay_editor.py`:

Add a module-level color map under `_SNAP_RADIUS`:

```python
_HANDLE_COLORS = {
    "body": "#2D7DD2", "tail": "#E84A5F",
    "tp0": "#39A96B", "tp1": "#39A96B", "tpc": "#F6B93B",
}
```

In `rebuild_handles`, after the existing `tail` handle block:

```python
        if getattr(ov, "text_path", None):
            self._add_handle("tp0", ov.text_path[0].pts[0])
            self._add_handle("tpc", ov.text_path[1].pts[0])
            self._add_handle("tp1", ov.text_path[1].pts[1])
```

In `_add_handle`, replace the brush line with:

```python
        h.setBrush(QBrush(QColor(_HANDLE_COLORS.get(kind, "#2D7DD2"))))
```

In `begin_edit`, replace `self._pre = (ov.anchor, ov.tail_target)` with a snapshot that deep-copies the path:

Add `from core.layout.models import PathSegment` to the module's imports, then:

```python
        tp = getattr(ov, "text_path", None)
        tp_copy = ([PathSegment(type=s.type, pts=[tuple(p) for p in s.pts]) for s in tp]
                   if tp else None)
        self._pre = (ov.anchor, ov.tail_target, tp_copy)
```

In `move_handle`, after the `tail` branch:

```python
        elif kind in ("tp0", "tpc", "tp1") and getattr(ov, "text_path", None):
            if kind == "tp0":
                ov.text_path[0].pts[0] = (x, y)
            elif kind == "tpc":
                ov.text_path[1].pts[0] = (x, y)
            else:
                ov.text_path[1].pts[1] = (x, y)
```

In `commit`, after the tail-snap block and before `self._pre = None`:

```python
        if getattr(ov, "text_path", None):
            from core.layout.text_path import validate_text_path
            if validate_text_path(ov.text_path):
                # Invalid mid-drag geometry: restore the pre-drag snapshot.
                if self._pre is not None and len(self._pre) == 3 and self._pre[2]:
                    ov.text_path = self._pre[2]
```

- [ ] **Step 4: Run tests to verify they pass**

Same command as Step 2, plus regression:
`... -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_overlay_editor.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/layout/overlay_editor.py tests/layout/test_overlay_editor_text_path.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(layout): drag handles for overlay text-path curve (start/bow/end)"
```

---

### Task 5: Inspector toggle + LayoutTab wiring

**Files:**
- Modify: `gui/layout/overlay_inspector.py`
- Modify: `gui/layout/layout_tab.py` (signal hookup at `:131-138`; handlers near `:566-630`)
- Test: `tests/layout/test_overlay_inspector_curve.py`

**Interfaces:**
- Consumes: Tasks 1–3 (`default_text_path`, `_overlay_font`, model fields); existing intent-signal pattern (inspector emits, LayoutTab mutates).
- Produces:
  - `OverlayInspector.curveToggled = Signal(str, bool)` — (overlay_id, on)
  - `OverlayInspector.outlineChanged = Signal(str, float, str)` — (overlay_id, px, hex)
  - `OverlayInspector.set_page(...)` stores `_kind`/`_has_curve` per list item; `set_selected` enables the curve checkbox only for caption/sfx and reflects `_has_curve`; outline row enabled only while the curve box is checked.
  - `LayoutTab._set_overlay_curve(overlay_id: str, on: bool) -> bool` and `LayoutTab._set_overlay_outline(overlay_id: str, px: float, color: str) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
# tests/layout/test_overlay_inspector_curve.py
from core.layout.models import Overlay, PageSpec, PathSegment
from gui.layout.overlay_inspector import OverlayInspector


def _page():
    tp = [PathSegment(type="move", pts=[(0.0, 0.0)]),
          PathSegment(type="quad", pts=[(10.0, -5.0), (20.0, 0.0)])]
    return PageSpec(page_size_px=(400, 400), regions=[], overlays=[
        Overlay(id="cap", kind="caption", text="curved", anchor=(10.0, 10.0),
                text_path=tp),
        Overlay(id="sp", kind="speech", text="talk", anchor=(20.0, 20.0)),
        Overlay(id="fx", kind="sfx", text="POW", anchor=(30.0, 30.0)),
    ])


def test_curve_checkbox_enabled_only_for_caption_sfx(qapp):
    insp = OverlayInspector()
    insp.set_page(_page())
    insp.set_selected("sp")
    assert not insp.curve_chk.isEnabled()
    insp.set_selected("fx")
    assert insp.curve_chk.isEnabled()
    assert not insp.curve_chk.isChecked()
    insp.set_selected("cap")
    assert insp.curve_chk.isEnabled()
    assert insp.curve_chk.isChecked()  # reflects existing text_path


def test_curve_toggle_emits(qapp):
    insp = OverlayInspector()
    insp.set_page(_page())
    insp.set_selected("fx")
    got = []
    insp.curveToggled.connect(lambda oid, on: got.append((oid, on)))
    insp.curve_chk.setChecked(True)
    assert got == [("fx", True)]


def test_outline_change_emits(qapp):
    insp = OverlayInspector()
    insp.set_page(_page())
    insp.set_selected("cap")
    got = []
    insp.outlineChanged.connect(lambda oid, px, col: got.append((oid, px, col)))
    insp.outline_spin.setValue(3.5)
    assert got and got[-1][0] == "cap" and abs(got[-1][1] - 3.5) < 1e-9


def test_layout_tab_curve_handlers():
    # Pure-logic test of the LayoutTab handler functions via a minimal stub;
    # mirrors how tests/layout/test_overlay_wiring.py exercises handlers.
    from gui.layout.layout_tab import LayoutTab
    page = _page()

    class _Stub:
        document = type("D", (), {"style": None})()
        def _current_page(self):
            return page
        def _find_overlay(self, oid):
            return next((o for o in page.overlays if o.id == oid), None)
        def snapshot_and_refresh(self, prompt):
            self.last = prompt

    stub = _Stub()
    assert LayoutTab._set_overlay_curve(stub, "fx", True) is True
    fx = stub._find_overlay("fx")
    assert fx.text_path is not None and len(fx.text_path) == 2
    assert LayoutTab._set_overlay_curve(stub, "fx", False) is True
    assert fx.text_path is None
    assert LayoutTab._set_overlay_curve(stub, "sp", True) is False  # speech: refused
    assert LayoutTab._set_overlay_outline(stub, "cap", 3.0, "#442200") is True
    cap = stub._find_overlay("cap")
    assert cap.text_style is not None
    assert cap.text_style.outline_px == 3.0
    assert cap.text_style.outline_color == "#442200"
```

Note: `test_layout_tab_curve_handlers` needs a `qapp` only if `_set_overlay_curve` touches Qt font metrics — it does (seed sizing). Give the test the `qapp` fixture argument.

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=/mnt/d/Documents/Code/GitHub/ImageAI QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python3 -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_overlay_inspector_curve.py -v`
Expected: FAIL — `AttributeError: ... no attribute 'curve_chk'`.

- [ ] **Step 3: Implement the inspector**

In `gui/layout/overlay_inspector.py`:

Add signals after `editToggled`:

```python
    curveToggled = Signal(str, bool)        # (overlay_id, on)
    outlineChanged = Signal(str, float, str)  # (overlay_id, px, hex color)
```

Extend imports: `QDoubleSpinBox`, `QLineEdit` from `PySide6.QtWidgets`.

In `_build`, after the rotation row:

```python
        curve_row = QHBoxLayout()
        self.curve_chk = QCheckBox("Curve text")
        self.curve_chk.setToolTip("Caption/SFX only: text follows an editable arc "
                                  "(drag its handles with 'Edit on canvas')")
        self.curve_chk.toggled.connect(self._on_curve)
        curve_row.addWidget(self.curve_chk)
        curve_row.addStretch(1)
        root.addLayout(curve_row)

        outline_row = QHBoxLayout()
        outline_row.addWidget(QLabel("Outline:"))
        self.outline_spin = QDoubleSpinBox()
        self.outline_spin.setRange(0.0, 50.0)
        self.outline_spin.setSingleStep(0.5)
        self.outline_spin.setSuffix(" px")
        self.outline_spin.valueChanged.connect(self._on_outline)
        outline_row.addWidget(self.outline_spin)
        self.outline_color = QLineEdit("#000000")
        self.outline_color.setMaximumWidth(80)
        self.outline_color.editingFinished.connect(self._on_outline)
        outline_row.addWidget(self.outline_color)
        outline_row.addStretch(1)
        root.addLayout(outline_row)
```

In `set_page`, inside the overlay loop, after `item._rotation = ...`:

```python
                item._kind = ov.kind
                item._has_curve = bool(getattr(ov, "text_path", None))
                ts = ov.text_style
                item._outline_px = float(getattr(ts, "outline_px", 0.0) or 0.0) if ts else 0.0
                item._outline_color = (getattr(ts, "outline_color", "#000000")
                                       if ts else "#000000")
```

In `set_selected`, extend the item-lookup loop to also capture `kind = getattr(it, "_kind", "")`, `has_curve = getattr(it, "_has_curve", False)`, `opx = getattr(it, "_outline_px", 0.0)`, `ocol = getattr(it, "_outline_color", "#000000")` (initialize all before the loop), then after the rotation_spin block:

```python
        curve_ok = enabled and kind in ("caption", "sfx")
        self.curve_chk.blockSignals(True)
        self.curve_chk.setEnabled(curve_ok)
        self.curve_chk.setChecked(curve_ok and has_curve)
        self.curve_chk.blockSignals(False)
        for w in (self.outline_spin, self.outline_color):
            w.setEnabled(curve_ok and has_curve)
        self.outline_spin.blockSignals(True)
        self.outline_spin.setValue(float(opx))
        self.outline_spin.blockSignals(False)
        self.outline_color.blockSignals(True)
        self.outline_color.setText(str(ocol))
        self.outline_color.blockSignals(False)
```

Also update the `for w in (...)` enable loop at the top of `set_selected` to leave the new widgets out (they're governed by the block above).

Add the handlers at the bottom:

```python
    def _on_curve(self, checked: bool):
        if self._selected_id is not None:
            self.curveToggled.emit(self._selected_id, bool(checked))

    def _on_outline(self, _value=None):
        if self._selected_id is not None:
            self.outlineChanged.emit(self._selected_id,
                                     float(self.outline_spin.value()),
                                     self.outline_color.text().strip() or "#000000")
```

- [ ] **Step 4: Implement the LayoutTab handlers**

In `gui/layout/layout_tab.py`, connect in `__init__` next to the other overlay_inspector connects (`:133-137`):

```python
        self.overlay_inspector.curveToggled.connect(self._set_overlay_curve)
        self.overlay_inspector.outlineChanged.connect(self._set_overlay_outline)
```

Add handlers near `_set_overlay_rotation` (`:617`):

```python
    def _set_overlay_curve(self, overlay_id: str, on: bool) -> bool:
        ov = self._find_overlay(overlay_id)
        if ov is None or ov.kind not in ("caption", "sfx"):
            return False
        if on and not getattr(ov, "text_path", None):
            from PySide6.QtGui import QFontMetricsF
            from core.layout.qt_renderer import _overlay_as_styleable, _overlay_font
            from core.layout.styles import effective_text_style
            from core.layout.text_path import default_text_path
            role = ov.role or ("caption" if ov.kind == "caption" else "sfx")
            style = self.document.style if self.document else None
            ts = effective_text_style(_overlay_as_styleable(ov, role), style)
            fm = QFontMetricsF(_overlay_font(ts))
            chord = max(120.0, fm.horizontalAdvance(ov.text or "Text") * 1.15)
            ov.text_path = default_text_path(ov.anchor, chord)
            self.snapshot_and_refresh(f"curve overlay text: {overlay_id}")
        elif not on and getattr(ov, "text_path", None):
            ov.text_path = None
            self.snapshot_and_refresh(f"uncurve overlay text: {overlay_id}")
        return True

    def _set_overlay_outline(self, overlay_id: str, px: float, color: str) -> bool:
        ov = self._find_overlay(overlay_id)
        if ov is None:
            return False
        if ov.text_style is None:
            from dataclasses import replace
            from core.layout.qt_renderer import _overlay_as_styleable
            from core.layout.styles import effective_text_style
            role = ov.role or ("caption" if ov.kind == "caption" else "sfx")
            style = self.document.style if self.document else None
            eff = effective_text_style(_overlay_as_styleable(ov, role), style)
            if eff is not None:
                ov.text_style = replace(eff)
            else:
                from core.layout.models import TextStyle
                ov.text_style = TextStyle(family=["DejaVu Sans"])
        ov.text_style.outline_px = float(px)
        ov.text_style.outline_color = color or "#000000"
        self.snapshot_and_refresh(f"overlay outline: {overlay_id}")
        return True
```

NOTE for the implementer: check `core/layout/styles.py:65 effective_text_style` — if it can return None (it can, per its docstring), the fallback above covers it. `replace(eff)` copies the role style into an explicit per-overlay style so the outline edit doesn't mutate the shared ProjectStyle object.

- [ ] **Step 5: Run tests to verify they pass**

Same command as Step 2, plus regressions:
`... -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_overlay_inspector.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_overlay_wiring.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/layout/overlay_inspector.py gui/layout/layout_tab.py tests/layout/test_overlay_inspector_curve.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(layout): curve-text toggle + outline controls in overlay inspector"
```

---

### Task 6: AI designer support

**Files:**
- Modify: `core/layout/designer.py` (prompt `:57-62`, `_build_overlay` `:165-183`)
- Test: `tests/layout/test_designer_text_path.py`

**Interfaces:**
- Consumes: `svg_to_segments`, `validate_text_path`, Task 2's `Overlay.text_path`.
- Produces: designer overlay dicts may carry `"text_path": "M x y Q cx cy x y"` and `"rotation": number`; `_build_overlay` validates and passes both through (text_path only for caption/sfx).

- [ ] **Step 1: Write the failing tests**

```python
# tests/layout/test_designer_text_path.py
from core.layout.designer import _build_overlay


def _base(**kw):
    d = {"id": "o1", "kind": "caption", "text": "TITLE", "anchor": [100, 100]}
    d.update(kw)
    return d


def test_valid_text_path_parsed():
    ov = _build_overlay(_base(text_path="M 50 100 Q 100 60 150 100"),
                        {}, (400, 400), 0)
    assert ov is not None and ov.text_path is not None
    assert ov.text_path[1].pts == [(100.0, 60.0), (150.0, 100.0)]


def test_invalid_text_path_dropped_overlay_kept():
    ov = _build_overlay(_base(text_path="M 0 0 L 10 10"), {}, (400, 400), 0)
    assert ov is not None and ov.text_path is None


def test_text_path_ignored_for_speech():
    d = _base(kind="speech", text_path="M 50 100 Q 100 60 150 100",
              tail_target=[10, 10])
    ov = _build_overlay(d, {}, (400, 400), 0)
    assert ov is not None and ov.text_path is None


def test_rotation_passthrough():
    ov = _build_overlay(_base(rotation=15), {}, (400, 400), 0)
    assert ov is not None and abs(ov.rotation - 15.0) < 1e-9


def test_bad_rotation_defaults_zero():
    ov = _build_overlay(_base(rotation="sideways"), {}, (400, 400), 0)
    assert ov is not None and ov.rotation == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=/mnt/d/Documents/Code/GitHub/ImageAI QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python3 -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_designer_text_path.py -v`
Expected: FAIL — `Overlay` built without `text_path`/`rotation` kwargs (rotation currently dropped, attribute is 0.0 — the rotation test may pass by accident for `rotation=15`? No: `_build_overlay` never reads `od["rotation"]`, so `ov.rotation == 0.0` and the test fails).

- [ ] **Step 3: Implement**

In `core/layout/designer.py`, prompt block — replace the overlays contract lines (`:57-62`) with:

```python
        f'    "overlays": [ {{ "id": string,\n'
        f'        "kind": "speech"|"thought"|"caption"|"sfx", "text": string,\n'
        f'        "anchor_region": string, "anchor_offset": [fx,fy] (0..1 within region),\n'
        f'        "tail_to_region": string,            // tail points at that region center\n'
        f'        "anchor": [x,y], "tail_target": [x,y], // raw-pixel alternative\n'
        f'        "rotation": number (degrees clockwise),\n'
        f'        "text_path": "M x y Q cx cy x y",     // caption/sfx only: text follows\n'
        f"        //   this single quadratic Bézier (page pixels) — arched titles/SFX\n"
        f'        "role": string }} ]\n'
```

In `_build_overlay`, add imports at the top of `designer.py` if missing: `from core.layout.svg_path import svg_to_segments` and `from core.layout.text_path import validate_text_path`. Then before the `return Overlay(...)`:

```python
    text_path = None
    tp_raw = od.get("text_path")
    if isinstance(tp_raw, str) and tp_raw.strip():
        if kind in ("caption", "sfx"):
            segs = svg_to_segments(tp_raw)
            problems = validate_text_path(segs)
            if problems:
                logger.warning("Designer overlay %r: invalid text_path %r dropped: %s",
                               od.get("id"), tp_raw, "; ".join(problems))
            else:
                text_path = segs
        else:
            logger.warning("Designer overlay %r: text_path only applies to caption/sfx; ignored",
                           od.get("id"))
    try:
        rotation = float(od.get("rotation", 0.0) or 0.0)
    except (TypeError, ValueError):
        rotation = 0.0
```

and extend the constructor call:

```python
    return Overlay(
        id=od.get("id", f"ov{idx + 1}"), kind=kind, text=str(od.get("text", "")),
        anchor=anchor, anchor_mode=anchor_mode, tail_target=tail,
        z=z, role=od.get("role", ""), rotation=rotation, text_path=text_path,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Same command as Step 2, plus regression:
`... -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_layout_tab_designer_overlays.py -v` (and any `test_designer*.py` in tests/layout/).
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/layout/designer.py tests/layout/test_designer_text_path.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(layout): designer LLM can author text_path + rotation on overlays"
```

---

### Task 7: Full suite, docs, and design-doc truth-up

**Files:**
- Modify: `Docs/ImageAI-CLI-Guide.md` (layout section), `Plans/2026-07-29-layout-curved-text-design.md`

**Interfaces:** none new.

- [ ] **Step 1: Run the whole layout suite**

Run: `PYTHONPATH=/mnt/d/Documents/Code/GitHub/ImageAI QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python3 -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/ -v`
Expected: all pass (fix anything red before proceeding).

- [ ] **Step 2: Visual smoke test (headless)**

Write a throwaway project JSON to the scratchpad with one curved caption over a colored page, render with the same code path the CLI uses:

```python
# scratch: render_curved_smoke.py
from core.layout.models import DocumentSpec, Overlay, PageSpec, PathSegment, TextStyle
from core.layout import qt_renderer
from PySide6.QtWidgets import QApplication
app = QApplication([])
ov = Overlay(id="t", kind="caption", text="NOBODY IS", anchor=(500.0, 300.0),
             text_style=TextStyle(family=["DejaVu Serif"], size_px=96,
                                  color="#F2D48A", align="center",
                                  outline_px=3.0, outline_color="#3A2410"),
             text_path=[PathSegment(type="move", pts=[(150.0, 320.0)]),
                        PathSegment(type="quad", pts=[(500.0, 220.0), (850.0, 320.0)])])
page = PageSpec(page_size_px=(1000, 600), background="#4A3520", regions=[], overlays=[ov])
qt_renderer.save_page_png(page, "/tmp/claude-1000/-mnt-d-Documents-Code-GitHub-NISF/0fb99701-a960-4c1c-8b76-4e2ac38b4bb8/scratchpad/curved_smoke.png")
print("ok")
```

Run it with `QT_QPA_PLATFORM=offscreen`, then LOOK at the PNG (Read tool). Gold arched text with a dark outline, evenly spaced, no glyph pile-ups. (Check `save_page_png`'s exact signature at `core/layout/qt_renderer.py:448` first and adapt.)

- [ ] **Step 3: Update docs**

In `Docs/ImageAI-CLI-Guide.md`, find the layout project-JSON section and add a short "Curved text (text_path)" subsection: the JSON key with the `"M x y Q cx cy x y"` example from the smoke test, the caption/sfx restriction, outline fields, and the GUI toggle ("Curve text" + Edit on canvas handles).

In `Plans/2026-07-29-layout-curved-text-design.md`, amend the GUI editing paragraph: drags update handle positions live but the rendered text updates on release (matches the existing overlay/geometry editor UX — scene refresh is suspended during drags); numeric X/Y spinboxes were dropped in favor of drag handles + JSON. Mark status "Implemented".

- [ ] **Step 4: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add Docs/ImageAI-CLI-Guide.md Plans/2026-07-29-layout-curved-text-design.md
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "docs: curved-text overlay usage (text_path) in CLI guide; truth-up design doc"
```

---

## Post-plan (not tasks in this repo)

- **NISF cover project** (`/mnt/d/Documents/Code/GitHub/NISF/Layouts/cover-layout.json`): built by the main session after Task 7, per the design doc's "Consumer deliverable" section; verified by exporting a PNG and visually inspecting.
- **Version bump + changelog** via `version-manager` happens when a PR is opened (only on request).
