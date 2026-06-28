# Comic Layout — Region Operations (#5b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add panel-level split (two-click free-line knife), merge, and delete to the Layout-tab manual editor, on top of the #5a `GeometryEditor` foundation and the #2 pure polygon primitives.

**Architecture:** A new pure, Qt-free `core/layout/region_ops.py` reduces a region to a polygon (`region_to_polygon`), then uses `polygon.clip_halfplane` (split) and `polygon.union_polygons` (merge) to produce new **polygon** regions. `CanvasWidget` gains a small tool-mode state machine that emits `knifeLine`/`mergeTarget`; `GeometryInspector` gains Delete/Knife/Merge controls (emit-signals-only); `LayoutTab` owns all model mutation via directly-callable `_apply_delete/_apply_knife/_apply_merge` methods (tested without Qt events).

**Tech Stack:** Python 3.12, PySide6 (GUI), pytest. Reuses `core/layout/polygon.py` (`clip_halfplane`, `union_polygons`, `ensure_orientation`, `signed_area`), `core/layout/models.py` (`Region`, `PathSegment`), `core/layout/history.py` (`History`), and #5a's `LayoutTab.snapshot_and_refresh`/`_find_region`/`geometry_editor`.

## Global Constraints

- Test interpreter: `.venv_linux/bin/python`, ALWAYS prefixed with `QT_QPA_PLATFORM=offscreen`.
- Full layout suite must stay green: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` (currently **293 passed** on branch `feat/comic-layout-geometry-core`).
- **No new third-party dependency.**
- `core/layout/region_ops.py` and `core/layout/polygon.py` stay **Qt-free** (importable headless). Qt code lives only in `gui/layout/`.
- **All errors logged** (`logging.getLogger(__name__)`): an unsupported/failed op is a **no-op + log + status message**, never a crash, never a corrupt model.
- **Scope:** split / merge / delete only. Operates on rect, polygon, and **straight-edged** `path` (move/line/close); curved paths (quad/cubic) are rejected (region_to_polygon → None). **No** vertex insert/delete, **no** line↔curve, **no** rect-corner resize, **no** overlay/export work (those are #5c).
- **Inspector/controller split:** UI widgets emit intent signals; `LayoutTab` owns all model mutation (same pattern as #5a).
- **Results are `polygon` regions** copying the source's `kind/z/bleed/image_style/role/name`.
- **Coordinates:** scene == page pixels.
- Conventional Commits (`feat(layout): …`). Commit after each task.
- **Branch:** continue on `feat/comic-layout-geometry-core`. **Do NOT open a pull request** — the single PR comes only after the whole comic-layout feature (#5c) is done.

### Names used across tasks (keep identical)
- `region_ops.region_to_polygon(region) -> Optional[Poly]` (Task 1); `_poly_bbox(poly) -> Rect`, `_region_from_polygon(template, poly, *, id) -> Region` (Task 1).
- `region_ops.split_region(region, a, b) -> Optional[Tuple[Region, Region]]` (Task 2).
- `region_ops.merge_regions(base, other) -> Optional[Region]` (Task 3).
- `LayoutTab._apply_delete(region_id) -> bool`, `_apply_knife(region_id, a, b) -> bool`, `_apply_merge(base_id, other_id) -> bool`, `_current_page()`, `_region_index(region_id) -> Optional[int]` (Task 4).
- `CanvasWidget.set_tool_mode(mode)`, `tool_mode() -> str`, `_register_knife_point(x, y) -> Optional[tuple]`, signals `knifeLine(float,float,float,float)` + `mergeTarget(str)` (Task 5).
- `GeometryInspector` signals `deleteRequested(str)`, `knifeToggled(str,bool)`, `mergeToggled(str,bool)` + widgets `delete_btn`/`knife_btn`/`merge_btn` (Task 6); `LayoutTab._on_region_delete_requested/_on_region_knife_toggled/_on_canvas_knife_line/_on_region_merge_toggled/_on_canvas_merge_target` (Task 6).

---

### Task 1: `region_to_polygon` + region/polygon helpers (pure)

**Files:**
- Create: `core/layout/region_ops.py`
- Test: `tests/layout/test_region_ops.py` (create)

**Interfaces:**
- Consumes: `Region`, `PathSegment` (`core.layout.models`); `Poly`, `Point` (`core.layout.polygon`).
- Produces: `region_to_polygon(region) -> Optional[Poly]`; `_poly_bbox(poly) -> Rect`; `_region_from_polygon(template, poly, *, id) -> Region`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_region_ops.py`:

```python
from core.layout.models import Region, PathSegment
from core.layout.region_ops import region_to_polygon


def test_region_to_polygon_rect():
    r = Region(id="r", kind="image", shape="rect", bbox=(10, 20, 100, 40))
    assert region_to_polygon(r) == [
        (10.0, 20.0), (110.0, 20.0), (110.0, 60.0), (10.0, 60.0)]


def test_region_to_polygon_polygon():
    r = Region(id="p", kind="image", shape="polygon",
               points=[(0, 0), (40, 0), (40, 30)], bbox=(0, 0, 40, 30))
    assert region_to_polygon(r) == [(0.0, 0.0), (40.0, 0.0), (40.0, 30.0)]


def test_region_to_polygon_straight_path():
    r = Region(id="q", kind="image", shape="path", bbox=(0, 0, 50, 50), segments=[
        PathSegment(type="move", pts=[(0.0, 0.0)]),
        PathSegment(type="line", pts=[(50.0, 0.0)]),
        PathSegment(type="line", pts=[(50.0, 50.0)]),
        PathSegment(type="close", pts=[]),
    ])
    assert region_to_polygon(r) == [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0)]


def test_region_to_polygon_curved_path_none():
    r = Region(id="c", kind="image", shape="path", bbox=(0, 0, 50, 50), segments=[
        PathSegment(type="move", pts=[(0.0, 0.0)]),
        PathSegment(type="cubic", pts=[(10.0, 10.0), (20.0, 20.0), (50.0, 50.0)]),
        PathSegment(type="close", pts=[]),
    ])
    assert region_to_polygon(r) is None


def test_region_to_polygon_degenerate_polygon_none():
    r = Region(id="d", kind="image", shape="polygon", points=[(0, 0), (1, 1)], bbox=(0, 0, 1, 1))
    assert region_to_polygon(r) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_ops.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.layout.region_ops'`.

- [ ] **Step 3: Implement the module foundation**

Create `core/layout/region_ops.py`:

```python
"""Pure (Qt-free) panel operations for the manual editor: split / merge / delete.

A region is reduced to an open-ring polygon, transformed with
``polygon.clip_halfplane`` / ``polygon.union_polygons``, and rebuilt as a
``polygon`` Region. Curved path regions (quad/cubic) are unsupported and yield
None so callers degrade gracefully — never crash, never corrupt the model.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from core.layout.models import Region
from core.layout.polygon import (
    Poly, Point, clip_halfplane, union_polygons, ensure_orientation, signed_area,
)

logger = logging.getLogger(__name__)

Rect = Tuple[int, int, int, int]
_AREA_EPS = 1.0  # sq-px tolerance for the merge area-conservation check


def region_to_polygon(region: Region) -> Optional[Poly]:
    """Open-ring polygon for a region, or None if unsupported/degenerate.

    rect -> 4 bbox corners; polygon -> its points; path with only move/line/close
    -> ordered anchor points; path with any quad/cubic -> None (curved).
    """
    if region.shape == "rect":
        x, y, w, h = region.bbox
        return [(float(x), float(y)), (float(x + w), float(y)),
                (float(x + w), float(y + h)), (float(x), float(y + h))]
    if region.shape == "polygon":
        if len(region.points) < 3:
            return None
        return [(float(px), float(py)) for px, py in region.points]
    if region.shape == "path":
        poly: Poly = []
        for seg in region.segments:
            if seg.type in ("quad", "cubic"):
                return None
            if seg.type in ("move", "line"):
                px, py = seg.pts[0]
                poly.append((float(px), float(py)))
            # close -> contributes no point
        return poly if len(poly) >= 3 else None
    return None


def _poly_bbox(poly: Poly) -> Rect:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x0, y0 = min(xs), min(ys)
    return (round(x0), round(y0), round(max(xs) - x0), round(max(ys) - y0))


def _region_from_polygon(template: Region, poly: Poly, *, id: str) -> Region:
    """Build a polygon Region from ``poly``, copying identity/style from template."""
    return Region(
        id=id,
        kind=template.kind,
        shape="polygon",
        bbox=_poly_bbox(poly),
        points=[(round(px), round(py)) for px, py in poly],
        bleed=template.bleed,
        z=template.z,
        name=template.name,
        role=template.role,
        text_style=template.text_style,
        image_style=template.image_style,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_ops.py -q`
Expected: PASS (5 passed). Then full suite green: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` (expect ~298).

- [ ] **Step 5: Commit**

```bash
git add core/layout/region_ops.py tests/layout/test_region_ops.py
git commit -m "feat(layout): region_to_polygon + polygon-region helpers (pure)"
```

---

### Task 2: `split_region` — two-click free-line knife (pure)

**Files:**
- Modify: `core/layout/region_ops.py`
- Test: `tests/layout/test_region_ops.py` (append)

**Interfaces:**
- Consumes: `region_to_polygon`, `_region_from_polygon` (Task 1); `clip_halfplane`, `ensure_orientation` (`core.layout.polygon`).
- Produces: `split_region(region, a, b) -> Optional[Tuple[Region, Region]]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/layout/test_region_ops.py`:

```python
from core.layout.region_ops import split_region


def _square(id="s"):
    return Region(id=id, kind="image", shape="rect", bbox=(0, 0, 100, 100),
                  bleed=True, z=5)


def test_split_square_vertical_midline():
    out = split_region(_square(), (50.0, 0.0), (50.0, 100.0))
    assert out is not None
    a, b = out
    assert a.shape == "polygon" and b.shape == "polygon"
    assert a.id == "s_a" and b.id == "s_b"
    assert a.bleed is True and a.z == 5  # identity/style copied
    xranges = sorted([
        (min(p[0] for p in a.points), max(p[0] for p in a.points)),
        (min(p[0] for p in b.points), max(p[0] for p in b.points)),
    ])
    assert xranges == [(0, 50), (50, 100)]


def test_split_miss_returns_none():
    # vertical line entirely to the right of the square -> one side empty
    assert split_region(_square(), (200.0, 0.0), (200.0, 100.0)) is None


def test_split_curved_path_none():
    r = Region(id="c", kind="image", shape="path", bbox=(0, 0, 50, 50), segments=[
        PathSegment(type="move", pts=[(0.0, 0.0)]),
        PathSegment(type="quad", pts=[(25.0, 25.0), (50.0, 0.0)]),
        PathSegment(type="close", pts=[]),
    ])
    assert split_region(r, (10.0, 0.0), (10.0, 50.0)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_ops.py -k split -q`
Expected: FAIL — `ImportError: cannot import name 'split_region'`.

- [ ] **Step 3: Implement `split_region`**

Append to `core/layout/region_ops.py`:

```python
def split_region(region: Region, a: Point, b: Point) -> Optional[Tuple[Region, Region]]:
    """Cut ``region`` by the line through a->b into two polygon regions.

    Returns ``(left, right)`` — ``left`` is the half on the LEFT of a->b, ``right``
    the other half (clip with the cut reversed). Returns None if the region is
    curved/unsupported or the cut misses (either side has < 3 vertices). The input
    region is never mutated. New ids are ``f"{region.id}_a"`` / ``f"{region.id}_b"``.
    """
    poly = region_to_polygon(region)
    if poly is None:
        return None
    poly = ensure_orientation(poly)
    left = clip_halfplane(poly, a, b)
    right = clip_halfplane(poly, b, a)
    if len(left) < 3 or len(right) < 3:
        return None
    return (
        _region_from_polygon(region, left, id=f"{region.id}_a"),
        _region_from_polygon(region, right, id=f"{region.id}_b"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_ops.py -q`
Expected: PASS. Then full suite green (expect ~301).

- [ ] **Step 5: Commit**

```bash
git add core/layout/region_ops.py tests/layout/test_region_ops.py
git commit -m "feat(layout): split_region two-click free-line knife (pure)"
```

---

### Task 3: `merge_regions` — adjacency union (pure)

**Files:**
- Modify: `core/layout/region_ops.py`
- Test: `tests/layout/test_region_ops.py` (append)

**Interfaces:**
- Consumes: `region_to_polygon`, `_region_from_polygon`, `_AREA_EPS` (Task 1); `union_polygons`, `ensure_orientation`, `signed_area` (`core.layout.polygon`).
- Produces: `merge_regions(base, other) -> Optional[Region]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/layout/test_region_ops.py`:

```python
from core.layout.region_ops import merge_regions


def test_merge_adjacent_squares():
    left = Region(id="L", kind="image", shape="rect", bbox=(0, 0, 50, 100), z=3)
    right = Region(id="R", kind="image", shape="rect", bbox=(50, 0, 50, 100))
    m = merge_regions(left, right)
    assert m is not None
    assert m.id == "L" and m.shape == "polygon" and m.z == 3
    assert m.bbox == (0, 0, 100, 100)


def test_merge_disjoint_returns_none():
    left = Region(id="L", kind="image", shape="rect", bbox=(0, 0, 50, 100))
    far = Region(id="R", kind="image", shape="rect", bbox=(60, 0, 50, 100))
    assert merge_regions(left, far) is None


def test_merge_curved_returns_none():
    left = Region(id="L", kind="image", shape="rect", bbox=(0, 0, 50, 100))
    curved = Region(id="C", kind="image", shape="path", bbox=(0, 0, 3, 3), segments=[
        PathSegment(type="move", pts=[(0.0, 0.0)]),
        PathSegment(type="cubic", pts=[(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]),
    ])
    assert merge_regions(left, curved) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_ops.py -k merge -q`
Expected: FAIL — `ImportError: cannot import name 'merge_regions'`.

- [ ] **Step 3: Implement `merge_regions`**

Append to `core/layout/region_ops.py`:

```python
def merge_regions(base: Region, other: Region) -> Optional[Region]:
    """Union two adjacent regions into one polygon region (keeps base's identity).

    Returns None if either region is curved/unsupported, or the two are not a clean
    edge-merge: the union must yield exactly one ring whose area equals the sum of
    the inputs' areas (no gap, no overlap). This makes the result independent of
    ``union_polygons`` behavior on disjoint input. Inputs are never mutated.
    """
    p1 = region_to_polygon(base)
    p2 = region_to_polygon(other)
    if p1 is None or p2 is None:
        return None
    p1 = ensure_orientation(p1)
    p2 = ensure_orientation(p2)
    rings = union_polygons([p1, p2])
    if len(rings) != 1 or len(rings[0]) < 3:
        return None
    merged = ensure_orientation(rings[0])
    if abs(signed_area(merged) - (signed_area(p1) + signed_area(p2))) > _AREA_EPS:
        return None  # gap or overlap -> not a clean adjacency merge
    return _region_from_polygon(base, merged, id=base.id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_ops.py -q`
Expected: PASS (all region_ops tests). Then full suite green (expect ~304). If `test_merge_adjacent_squares` fails on `bbox`, print `union_polygons([p1,p2])` to confirm the ring; the area guard already rejects bad unions, so a failure here means the two rects don't share their full edge in the fixture (they do: both span y 0..100 at x=50).

- [ ] **Step 5: Commit**

```bash
git add core/layout/region_ops.py tests/layout/test_region_ops.py
git commit -m "feat(layout): merge_regions adjacency union with area-conservation guard (pure)"
```

---

### Task 4: `LayoutTab` mutation methods — delete / knife / merge

**Files:**
- Modify: `gui/layout/layout_tab.py` (add `_current_page`, `_region_index`, `_apply_delete`, `_apply_knife`, `_apply_merge`; place after `_find_region` ~214)
- Test: `tests/layout/test_region_ops_gui.py` (create)

**Interfaces:**
- Consumes: `region_ops.split_region`, `region_ops.merge_regions` (Tasks 2-3); `LayoutTab.snapshot_and_refresh`, `geometry_editor.active_region_id/set_edit_region`, `self.document`, `self.status` (#5a).
- Produces: `_current_page() -> Optional[PageSpec]`; `_region_index(region_id) -> Optional[int]`; `_apply_delete(region_id) -> bool`; `_apply_knife(region_id, a, b) -> bool`; `_apply_merge(base_id, other_id) -> bool`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_region_ops_gui.py`:

```python
from gui.layout.layout_tab import LayoutTab
from core.layout.models import Region


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tab_with(regions):
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = regions
    tab._refresh()
    return tab


def test_apply_delete_removes_and_snapshots(qapp):
    tab = _tab_with([
        Region(id="a", kind="image", shape="rect", bbox=(0, 0, 50, 50)),
        Region(id="b", kind="image", shape="rect", bbox=(50, 0, 50, 50)),
    ])
    before = len(tab.history.snapshots())
    assert tab._apply_delete("a") is True
    assert [r.id for r in tab.document.pages[0].regions] == ["b"]
    assert len(tab.history.snapshots()) == before + 1


def test_apply_knife_splits_in_place(qapp):
    tab = _tab_with([Region(id="x", kind="image", shape="rect", bbox=(0, 0, 100, 100))])
    before = len(tab.history.snapshots())
    assert tab._apply_knife("x", (50.0, 0.0), (50.0, 100.0)) is True
    assert [r.id for r in tab.document.pages[0].regions] == ["x_a", "x_b"]
    assert len(tab.history.snapshots()) == before + 1


def test_apply_knife_miss_no_change(qapp):
    tab = _tab_with([Region(id="x", kind="image", shape="rect", bbox=(0, 0, 100, 100))])
    before = len(tab.history.snapshots())
    assert tab._apply_knife("x", (200.0, 0.0), (200.0, 100.0)) is False
    assert [r.id for r in tab.document.pages[0].regions] == ["x"]
    assert len(tab.history.snapshots()) == before


def test_apply_merge_combines(qapp):
    tab = _tab_with([
        Region(id="L", kind="image", shape="rect", bbox=(0, 0, 50, 100)),
        Region(id="R", kind="image", shape="rect", bbox=(50, 0, 50, 100)),
    ])
    before = len(tab.history.snapshots())
    assert tab._apply_merge("L", "R") is True
    assert [r.id for r in tab.document.pages[0].regions] == ["L"]
    assert tab.document.pages[0].regions[0].bbox == (0, 0, 100, 100)
    assert len(tab.history.snapshots()) == before + 1


def test_apply_merge_disjoint_no_change(qapp):
    tab = _tab_with([
        Region(id="L", kind="image", shape="rect", bbox=(0, 0, 50, 100)),
        Region(id="R", kind="image", shape="rect", bbox=(60, 0, 50, 100)),
    ])
    before = len(tab.history.snapshots())
    assert tab._apply_merge("L", "R") is False
    assert len(tab.document.pages[0].regions) == 2
    assert len(tab.history.snapshots()) == before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_ops_gui.py -q`
Expected: FAIL — `AttributeError: 'LayoutTab' object has no attribute '_apply_delete'`.

- [ ] **Step 3: Implement the mutation methods**

In `gui/layout/layout_tab.py`, add after `_find_region` (~214):

```python
    def _current_page(self):
        if not self.document or not self.document.pages:
            return None
        return self.document.pages[0]

    def _region_index(self, region_id: str):
        page = self._current_page()
        if page is None:
            return None
        for i, r in enumerate(page.regions):
            if r.id == region_id:
                return i
        return None

    def _apply_delete(self, region_id: str) -> bool:
        page = self._current_page()
        idx = self._region_index(region_id)
        if page is None or idx is None:
            return False
        if self.geometry_editor.active_region_id() == region_id:
            self.geometry_editor.set_edit_region(None)
        region = page.regions[idx]
        del page.regions[idx]
        self.snapshot_and_refresh(f"delete panel: {region.name or region.id}")
        return True

    def _apply_knife(self, region_id: str, a, b) -> bool:
        import logging
        page = self._current_page()
        idx = self._region_index(region_id)
        if page is None or idx is None:
            return False
        from core.layout.region_ops import split_region
        out = split_region(page.regions[idx], a, b)
        if out is None:
            logging.getLogger(__name__).warning(
                "knife: cut missed or unsupported shape for region %s", region_id)
            self.status.setText("Cannot split — the cut line missed the panel")
            return False
        page.regions[idx:idx + 1] = list(out)
        self.snapshot_and_refresh(f"split panel: {region_id}")
        return True

    def _apply_merge(self, base_id: str, other_id: str) -> bool:
        import logging
        page = self._current_page()
        if page is None or base_id == other_id:
            return False
        bi = self._region_index(base_id)
        oi = self._region_index(other_id)
        if bi is None or oi is None:
            return False
        from core.layout.region_ops import merge_regions
        merged = merge_regions(page.regions[bi], page.regions[oi])
        if merged is None:
            logging.getLogger(__name__).warning(
                "merge: regions %s + %s are not adjacent", base_id, other_id)
            self.status.setText("Cannot merge — panels are not adjacent")
            return False
        page.regions[bi] = merged
        del page.regions[oi]  # replacing base did not change length, so oi is valid
        self.snapshot_and_refresh(f"merge panels: {base_id} + {other_id}")
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_ops_gui.py -q`
Expected: PASS (5 passed). Then full suite green (expect ~309).

- [ ] **Step 5: Commit**

```bash
git add gui/layout/layout_tab.py tests/layout/test_region_ops_gui.py
git commit -m "feat(layout): LayoutTab delete/knife/merge mutation methods"
```

---

### Task 5: `CanvasWidget` tool modes — knife / merge click capture

**Files:**
- Modify: `gui/layout/canvas_widget.py`
- Test: `tests/layout/test_canvas_tool_mode.py` (create)

**Interfaces:**
- Consumes: nothing new (uses `QGraphicsView.mapToScene`, `scene().items`).
- Produces: `CanvasWidget.set_tool_mode(mode)`, `tool_mode() -> str`, `_register_knife_point(x, y) -> Optional[tuple]`, `_region_id_at(scene_pt) -> Optional[str]`; signals `knifeLine(float,float,float,float)`, `mergeTarget(str)`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_canvas_tool_mode.py`:

```python
from gui.layout.canvas_widget import CanvasWidget


def test_knife_two_click_state(qapp):
    c = CanvasWidget()
    c.set_tool_mode("knife")
    assert c.tool_mode() == "knife"
    assert c._register_knife_point(10.0, 20.0) is None       # first click stored
    assert c._register_knife_point(30.0, 40.0) == (10.0, 20.0, 30.0, 40.0)


def test_set_tool_mode_resets_and_validates(qapp):
    c = CanvasWidget()
    c.set_tool_mode("knife")
    c._register_knife_point(1.0, 1.0)        # half-entered knife
    c.set_tool_mode("bogus")                 # invalid -> "none" + reset
    assert c.tool_mode() == "none"
    assert c._knife_first is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_canvas_tool_mode.py -q`
Expected: FAIL — `AttributeError: 'CanvasWidget' object has no attribute 'set_tool_mode'`.

- [ ] **Step 3: Implement tool modes**

In `gui/layout/canvas_widget.py`:

(a) Add the two signals next to `regionSelected`:

```python
    regionSelected = Signal(str)
    knifeLine = Signal(float, float, float, float)  # p1x, p1y, p2x, p2y (scene px)
    mergeTarget = Signal(str)                        # clicked region id
```

(b) In `__init__`, after `self.setScene(QGraphicsScene(self))`, add:

```python
        self._tool_mode = "none"
        self._knife_first = None
```

(c) Add the tool-mode methods (after `selected_region_id`):

```python
    def set_tool_mode(self, mode: str) -> None:
        """Switch the canvas tool: "none" (normal select), "knife", or "merge"."""
        if mode not in ("none", "knife", "merge"):
            mode = "none"
        self._tool_mode = mode
        self._knife_first = None

    def tool_mode(self) -> str:
        return self._tool_mode

    def _register_knife_point(self, x: float, y: float):
        """Collect a knife click; return (x1,y1,x2,y2) on the second, else None."""
        if self._knife_first is None:
            self._knife_first = (x, y)
            return None
        x1, y1 = self._knife_first
        self._knife_first = None
        return (x1, y1, x, y)

    def _region_id_at(self, scene_pt):
        for it in self.scene().items(scene_pt):
            rid = it.data(0)
            if rid:
                return rid
        return None

    def mousePressEvent(self, event):
        if self._tool_mode == "knife":
            sp = self.mapToScene(event.position().toPoint())
            line = self._register_knife_point(sp.x(), sp.y())
            if line is not None:
                self._tool_mode = "none"
                self.knifeLine.emit(*line)
            event.accept()
            return
        if self._tool_mode == "merge":
            sp = self.mapToScene(event.position().toPoint())
            rid = self._region_id_at(sp)
            self._tool_mode = "none"
            if rid:
                self.mergeTarget.emit(rid)
            event.accept()
            return
        super().mousePressEvent(event)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_canvas_tool_mode.py -q`
Expected: PASS (2 passed). Then full suite green (expect ~311). Confirm existing `test_geometry_editor*.py` still pass (normal mode `"none"` falls through to `super().mousePressEvent`, so selection/handle-drag behavior is unchanged).

- [ ] **Step 5: Commit**

```bash
git add gui/layout/canvas_widget.py tests/layout/test_canvas_tool_mode.py
git commit -m "feat(layout): canvas knife/merge tool modes with click capture"
```

---

### Task 6: Inspector buttons + controller wiring (integration)

**Files:**
- Modify: `gui/layout/geometry_inspector.py` (add Delete/Knife/Merge controls + signals; reset toggles in `set_region`)
- Modify: `gui/layout/layout_tab.py` (`_build`: connect inspector + canvas signals; add toggle handlers + `_knife_region_id`/`_merge_base_id`)
- Test: `tests/layout/test_region_ops_wiring.py` (create)

**Interfaces:**
- Consumes: `_apply_delete/_apply_knife/_apply_merge` (Task 4); `CanvasWidget.set_tool_mode`, `knifeLine`, `mergeTarget` (Task 5).
- Produces: `GeometryInspector.deleteRequested(str)/knifeToggled(str,bool)/mergeToggled(str,bool)` + `delete_btn`/`knife_btn`/`merge_btn`; `LayoutTab._on_region_delete_requested/_on_region_knife_toggled/_on_canvas_knife_line/_on_region_merge_toggled/_on_canvas_merge_target`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_region_ops_wiring.py`:

```python
from gui.layout.layout_tab import LayoutTab
from gui.layout.geometry_inspector import GeometryInspector
from core.layout.models import Region


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tab_with(regions):
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = regions
    tab._refresh()
    return tab


def test_inspector_emits_delete_and_toggles(qapp):
    insp = GeometryInspector()
    r = Region(id="p", kind="image", shape="polygon",
               points=[(0, 0), (10, 0), (10, 10)], bbox=(0, 0, 10, 10))
    insp.set_region(r)
    seen = []
    insp.deleteRequested.connect(lambda rid: seen.append(("del", rid)))
    insp.knifeToggled.connect(lambda rid, on: seen.append(("knife", rid, on)))
    insp.delete_btn.click()
    insp.knife_btn.setChecked(True)
    assert ("del", "p") in seen
    assert ("knife", "p", True) in seen


def test_knife_wiring_end_to_end(qapp):
    tab = _tab_with([Region(id="x", kind="image", shape="rect", bbox=(0, 0, 100, 100))])
    tab._on_region_knife_toggled("x", True)
    assert tab.canvas.tool_mode() == "knife"
    tab.canvas.knifeLine.emit(50.0, 0.0, 50.0, 100.0)
    assert [r.id for r in tab.document.pages[0].regions] == ["x_a", "x_b"]


def test_merge_wiring_end_to_end(qapp):
    tab = _tab_with([
        Region(id="L", kind="image", shape="rect", bbox=(0, 0, 50, 100)),
        Region(id="R", kind="image", shape="rect", bbox=(50, 0, 50, 100)),
    ])
    tab._on_region_merge_toggled("L", True)
    assert tab.canvas.tool_mode() == "merge"
    tab.canvas.mergeTarget.emit("R")
    assert [r.id for r in tab.document.pages[0].regions] == ["L"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_ops_wiring.py -q`
Expected: FAIL — `AttributeError: 'GeometryInspector' object has no attribute 'delete_btn'`.

- [ ] **Step 3: Add the inspector controls**

In `gui/layout/geometry_inspector.py`:

(a) Add `QPushButton` to the imports:

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QSpinBox, QPushButton,
)
```

(b) Add the signals next to the existing ones:

```python
    deleteRequested = Signal(str)        # (region_id)
    knifeToggled = Signal(str, bool)     # (region_id, on)
    mergeToggled = Signal(str, bool)     # (region_id, on)
```

(c) In `_build`, after the `edit_shape_chk` line (`root.addWidget(self.edit_shape_chk)`), add a button row:

```python
        ops_row = QHBoxLayout()
        self.delete_btn = QPushButton("Delete panel")
        self.delete_btn.clicked.connect(self._on_delete)
        ops_row.addWidget(self.delete_btn)
        self.knife_btn = QPushButton("Knife (split)")
        self.knife_btn.setCheckable(True)
        self.knife_btn.toggled.connect(self._on_knife)
        ops_row.addWidget(self.knife_btn)
        self.merge_btn = QPushButton("Merge…")
        self.merge_btn.setCheckable(True)
        self.merge_btn.toggled.connect(self._on_merge)
        ops_row.addWidget(self.merge_btn)
        root.addLayout(ops_row)
```

(d) In `set_region`, reset/enable the new controls. Find the block that resets `edit_shape_chk` (it does `blockSignals(True)`, `setChecked(False)`, `setEnabled(...)`, `blockSignals(False)`) and add, immediately after it:

```python
        for btn in (self.knife_btn, self.merge_btn):
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.setEnabled(region is not None)
            btn.blockSignals(False)
        self.delete_btn.setEnabled(region is not None)
```

(e) Add the handlers (after `_on_edit_shape`):

```python
    def _on_delete(self):
        if self._region is not None:
            self.deleteRequested.emit(self._region.id)

    def _on_knife(self, checked: bool):
        if self._region is not None:
            self.knifeToggled.emit(self._region.id, bool(checked))

    def _on_merge(self, checked: bool):
        if self._region is not None:
            self.mergeToggled.emit(self._region.id, bool(checked))
```

- [ ] **Step 4: Wire `LayoutTab`**

In `gui/layout/layout_tab.py`:

(a) In `__init__`, after `self._locked = self._load_locked()` (before `self._build()`), add:

```python
        self._knife_region_id = None
        self._merge_base_id = None
```

(b) In `_build`, in the geometry-inspector wiring block (where `editShapeToggled` is connected), add:

```python
        self.geometry_inspector.deleteRequested.connect(self._on_region_delete_requested)
        self.geometry_inspector.knifeToggled.connect(self._on_region_knife_toggled)
        self.geometry_inspector.mergeToggled.connect(self._on_region_merge_toggled)
```

(c) In `_build`, immediately after `self.canvas.regionSelected.connect(self._on_region_selected)` (~line 97), connect the canvas tool signals:

```python
        self.canvas.knifeLine.connect(self._on_canvas_knife_line)
        self.canvas.mergeTarget.connect(self._on_canvas_merge_target)
```

(d) Add the handlers (after the `_apply_*` methods from Task 4):

```python
    def _on_region_delete_requested(self, region_id: str):
        self._apply_delete(region_id)

    def _on_region_knife_toggled(self, region_id: str, on: bool):
        if on:
            self._knife_region_id = region_id
            self.canvas.set_tool_mode("knife")
            self.status.setText("Knife: click two points to cut the panel")
        else:
            self._knife_region_id = None
            self.canvas.set_tool_mode("none")

    def _on_canvas_knife_line(self, x1: float, y1: float, x2: float, y2: float):
        rid = self._knife_region_id
        self._knife_region_id = None
        if rid:
            self._apply_knife(rid, (x1, y1), (x2, y2))

    def _on_region_merge_toggled(self, region_id: str, on: bool):
        if on:
            self._merge_base_id = region_id
            self.canvas.set_tool_mode("merge")
            self.status.setText("Merge: click an adjacent panel")
        else:
            self._merge_base_id = None
            self.canvas.set_tool_mode("none")

    def _on_canvas_merge_target(self, other_id: str):
        base = self._merge_base_id
        self._merge_base_id = None
        if base:
            self._apply_merge(base, other_id)
```

- [ ] **Step 5: Run tests + commit**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_region_ops_wiring.py -q` → PASS (3 passed). Then the FULL suite: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` → all green (expect ~314), confirming `test_geometry_inspector.py` still constructs `GeometryInspector` cleanly with the new buttons.

```bash
git add gui/layout/geometry_inspector.py gui/layout/layout_tab.py tests/layout/test_region_ops_wiring.py
git commit -m "feat(layout): wire delete/knife/merge inspector controls to canvas + controller"
```

---

## Notes / deliberately deferred (not gaps)
- **Vertex insert/delete, line↔curve conversion, rect-corner resize** — possible later additions; not #5b.
- **Splitting/merging curved path regions** — would need curve subdivision; rejected fail-safe for now.
- **Overlay editing + SFX rotation + stranded-overlay reposition + PIL→Qt export unification** → **#5c**.
- **Merge UX is single-step** (toggle Merge, click the other panel). Multi-select merge is not in scope.

## Self-Review (completed by plan author)
- **Spec coverage:** split (Task 2, two-click free line via clip_halfplane both sides) + merge (Task 3, union_polygons + area-conservation guard) + delete (Task 4) + canvas knife/merge capture (Task 5) + inspector controls & wiring (Task 6). region_to_polygon (Task 1) underpins all three ops; curved-path rejection is in Task 1 and exercised by Tasks 2-3. Error paths (cut miss / not adjacent / curved) → no-op + log + status (Task 4), tested in Task 4. Inspector/controller split honored (widgets emit; LayoutTab mutates).
- **Placeholder scan:** no TBD/TODO; every code step shows complete code; degrade paths are concrete (`split_region`/`merge_regions` return None → status + warning).
- **Type/name consistency:** `region_to_polygon`/`_region_from_polygon` (T1) consumed by `split_region`/`merge_regions` (T2/T3); those consumed by `_apply_knife`/`_apply_merge` (T4); `set_tool_mode`/`knifeLine`/`mergeTarget` (T5) consumed by the wiring (T6); inspector signal names (`deleteRequested`/`knifeToggled`/`mergeToggled`) match between `GeometryInspector` and the `LayoutTab` connects. `clip_halfplane`/`union_polygons`/`ensure_orientation`/`signed_area`, `Region` fields, `snapshot_and_refresh`, `geometry_editor.active_region_id/set_edit_region` all match real signatures.
- **Test interpreter/baseline:** all tasks use `.venv_linux/bin/python` under `QT_QPA_PLATFORM=offscreen`; suite 293 → ~314 (5+3+3+5+2+3 = 21 new tests; counts approximate — binding check is "all new tests pass and the full suite stays green").
