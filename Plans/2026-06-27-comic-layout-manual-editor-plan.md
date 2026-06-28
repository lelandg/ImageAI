# Comic Layout — Manual Editor: Region Geometry (#5a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual region-geometry editor to the Layout tab — move-only vertex/curve-handle drag on existing `path`/`polygon` panels, per-panel bleed/borderless toggles — on top of an editing foundation (handles that survive the full-scene rebuild, segment write-back, a geometry inspector, undo via `History`).

**Architecture:** A new `GeometryEditor` controller (`gui/layout/geometry_editor.py`) layered on `CanvasWidget`. The pure renderer stays display-only. Because `LayoutTab._refresh` rebuilds the whole scene on every change, the controller **regenerates edit handles from the model after each rebuild** — so handles survive refreshes by reconstruction, not preservation. A handle drag mutates the bound `region.segments[i].pts[j]`/`region.points[i]`, updates the panel's path item in place (no full refresh mid-drag), and the commit recomputes `bbox`, validates, snapshots undo, and refreshes.

**Tech Stack:** Python 3.12, PySide6 (GUI), pytest. Reuses `core/layout/geometry.py` (`validate_segments`, `segments_bbox`), `core/layout/qt_renderer.py` (`region_to_painter_path`, `_RegionPathItem`, `_writeback_move`, `build_scene`), `core/layout/history.py` (`History.append`), and `core/layout/models.py` (`Region`, `PathSegment`, `ImageStyle`).

## Global Constraints

- Test interpreter: `.venv_linux/bin/python`. Run with `QT_QPA_PLATFORM=offscreen` prefixed (required for the GUI tests; harmless for the pure tests).
- Full layout suite must stay green: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` (currently **276 passed** on branch `feat/comic-layout-geometry-core`).
- **No new third-party dependency.**
- `core/layout/geometry.py` stays **Qt-free** (importable headless). Qt code lives only in `gui/layout/` and `core/layout/qt_renderer.py`.
- **All errors logged** (`logging.getLogger(__name__)`): an edit that fails `validate_segments` is reverted + logged, never persisted, never crashes.
- **Scope:** move-only vertex/curve editing on `path`+`polygon` regions; rect regions keep their existing translate-drag. **No** vertex insert/delete, **no** line↔curve conversion, **no** split/knife/merge/delete (those are #5b), **no** overlay editing (#5c).
- **Inspector/controller split:** UI widgets emit intent signals; `LayoutTab` owns all model mutation (same pattern as `ContentInspector`).
- **Coordinates:** scene == page pixels. Handles carry their model point as `item.pos()`.
- Conventional Commits (`feat(layout): …`). Commit after each task.
- **Branch:** continue on `feat/comic-layout-geometry-core`. **Do NOT open a pull request** — the single PR comes only after the whole comic-layout feature is done.

### Names used across tasks (keep identical)
- `geometry.translate_segments(segments, dx, dy) -> List[PathSegment]` (Task 1).
- `GeometryInspector` with signals `bleedToggled(str,bool)`, `borderlessToggled(str,bool)`, `zChanged(str,int)` (Task 3), plus `editShapeToggled(str,bool)` (Task 4); method `set_region(region)`. Module const `gui/layout/layout_tab.py:_DEFAULT_STROKE_PX = 4`.
- `GeometryEditor(canvas, layout_tab)` with `set_edit_region(region_id|None)`, `rebuild_handles()`, `edit_points()`, `active_region_id()` (Task 4); `begin_edit()`, `move_handle(index, x, y)`, `commit()` (Task 5). Module fn `edit_points_for_region(region) -> List[_EditPoint]` (Task 4).
- `LayoutTab.set_refresh_suspended(bool)` and `LayoutTab.snapshot_and_refresh(prompt)` (Task 5); `LayoutTab._find_region(region_id)` (exists).

---

### Task 1: `geometry.translate_segments` — pure segment-offset helper

**Files:**
- Modify: `core/layout/geometry.py`
- Test: `tests/layout/test_geometry.py` (append; create if missing)

**Interfaces:**
- Consumes: `PathSegment` (`core.layout.models`).
- Produces: `translate_segments(segments: List[PathSegment], dx: float, dy: float) -> List[PathSegment]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/layout/test_geometry.py` (create the file with this content if it does not exist — start it with `from core.layout.models import PathSegment` and `from core.layout.geometry import translate_segments`):

```python
from core.layout.models import PathSegment
from core.layout.geometry import translate_segments


def test_translate_segments_offsets_all_point_types():
    segs = [
        PathSegment(type="move", pts=[(10.0, 10.0)]),
        PathSegment(type="line", pts=[(90.0, 10.0)]),
        PathSegment(type="cubic", pts=[(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]),
        PathSegment(type="close", pts=[]),
    ]
    out = translate_segments(segs, 5.0, -2.0)
    assert out[0].pts == [(15.0, 8.0)]
    assert out[1].pts == [(95.0, 8.0)]
    assert out[2].pts == [(6.0, 0.0), (8.0, 2.0), (10.0, 4.0)]
    assert out[3].pts == []
    assert [s.type for s in out] == ["move", "line", "cubic", "close"]


def test_translate_segments_does_not_mutate_input():
    segs = [PathSegment(type="move", pts=[(0.0, 0.0)])]
    out = translate_segments(segs, 1.0, 1.0)
    assert out[0] is not segs[0]
    assert segs[0].pts == [(0.0, 0.0)]


def test_translate_segments_zero_delta_keeps_values():
    segs = [PathSegment(type="line", pts=[(3.0, 4.0)])]
    assert translate_segments(segs, 0.0, 0.0)[0].pts == [(3.0, 4.0)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_geometry.py -k translate -q`
Expected: FAIL — `ImportError: cannot import name 'translate_segments'`.

- [ ] **Step 3: Implement `translate_segments`**

Append to `core/layout/geometry.py` (after `segments_bbox`):

```python
def translate_segments(segments: List[PathSegment], dx: float, dy: float) -> List[PathSegment]:
    """Return NEW PathSegments with every point offset by (dx, dy).

    Pure/Qt-free. The manual editor uses this to persist a whole-panel translate
    drag into a path region's ``segments`` (the write-back gap deferred from #5)
    and as the offset primitive for geometry edits. The input is never mutated.
    """
    return [
        PathSegment(type=seg.type, pts=[(px + dx, py + dy) for (px, py) in seg.pts])
        for seg in segments
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_geometry.py -q`
Expected: PASS. Then full suite green: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` (expect ~279).

- [ ] **Step 5: Commit**

```bash
git add core/layout/geometry.py tests/layout/test_geometry.py
git commit -m "feat(layout): translate_segments pure offset helper"
```

---

### Task 2: segment write-back on a path-region translate drag

**Files:**
- Modify: `core/layout/qt_renderer.py` (`_RegionMoveMixin._bind_region` ~136, `_writeback_move` ~107)
- Test: `tests/layout/test_writeback_move.py` (create)

**Interfaces:**
- Consumes: `geometry.translate_segments` (Task 1); `_RegionPathItem`, `region_to_painter_path` (`core.layout.qt_renderer`).
- Produces: `_writeback_move` now persists a path region's `segments` (and `bbox`) on a translate; `_bind_region` captures `_base_segments`.

Closes the gap flagged in `_writeback_move`'s NOTE: a `path` region drag currently writes only `bbox`, so it visually reverts on the next refresh (`region_to_painter_path` re-reads `segments`).

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_writeback_move.py`:

```python
from PySide6.QtWidgets import QGraphicsItem

from core.layout.models import Region, PathSegment
from core.layout import qt_renderer


def _triangle():
    return [
        PathSegment(type="move", pts=[(10.0, 10.0)]),
        PathSegment(type="line", pts=[(50.0, 10.0)]),
        PathSegment(type="line", pts=[(50.0, 50.0)]),
        PathSegment(type="close", pts=[]),
    ]


def test_writeback_translates_path_segments(qapp):
    r = Region(id="p1", kind="image", shape="path", segments=_triangle(), bbox=(10, 10, 40, 40))
    item = qt_renderer._RegionPathItem(qt_renderer.region_to_painter_path(r), r)
    item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
    item.setPos(5.0, -3.0)  # fires itemChange -> _writeback_move

    assert r.segments[0].pts == [(15.0, 7.0)]
    assert r.segments[1].pts == [(55.0, 7.0)]
    assert r.segments[2].pts == [(55.0, 47.0)]
    assert r.bbox == (15, 7, 40, 40)


def test_writeback_rect_region_unchanged_behavior(qapp):
    r = Region(id="t1", kind="text", shape="rect", bbox=(0, 0, 100, 40))
    from PySide6.QtCore import QRectF
    item = qt_renderer._RegionRectItem(QRectF(0, 0, 100, 40), r)
    item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
    item.setPos(7.0, 9.0)
    assert r.bbox == (7, 9, 100, 40)  # translate-only, size unchanged
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_writeback_move.py -q`
Expected: FAIL — `test_writeback_translates_path_segments` fails because `r.segments` is unchanged (only `bbox` is written today).

- [ ] **Step 3: Capture `_base_segments` and write segments back for path regions**

In `core/layout/qt_renderer.py`, extend `_bind_region` (currently ~136):

```python
    def _bind_region(self, region: Region) -> None:
        self._region = region
        self._base_bbox = tuple(region.bbox)
        self._base_points = list(region.points)
        self._base_segments = list(region.segments)
```

Replace `_writeback_move` (currently ~107) with (note the NOTE about the deferred gap is removed because it is now handled):

```python
def _writeback_move(item) -> None:
    """Persist a drag into the bound region's geometry.

    Handles carry their geometry in item-local coords with the item at scene
    (0,0), so a drag shows up purely as ``item.pos()`` — the delta to apply to
    the region's original geometry. For ``shape="path"`` regions the delta is
    applied to ``segments`` (the geometry the renderer reads); rect/polygon
    regions translate ``bbox`` and ``points``.
    """
    region = getattr(item, "_region", None)
    if region is None:
        return
    dx, dy = item.x(), item.y()
    bx, by, bw, bh = item._base_bbox
    if region.shape == "path" and getattr(item, "_base_segments", None):
        from core.layout.geometry import translate_segments
        region.segments = translate_segments(item._base_segments, dx, dy)
        region.bbox = (round(bx + dx), round(by + dy), bw, bh)
        return
    region.bbox = (round(bx + dx), round(by + dy), bw, bh)
    if item._base_points:
        region.points = [(round(px + dx), round(py + dy)) for px, py in item._base_points]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_writeback_move.py -q`
Expected: PASS (2 passed). Full suite green: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` (expect ~281). Confirm the existing region/drag tests still pass (rect/polygon behavior unchanged).

- [ ] **Step 5: Commit**

```bash
git add core/layout/qt_renderer.py tests/layout/test_writeback_move.py
git commit -m "feat(layout): writeback translates path-region segments on drag"
```

---

### Task 3: `GeometryInspector` — bleed / borderless / z toggles

**Files:**
- Create: `gui/layout/geometry_inspector.py`
- Modify: `gui/layout/layout_tab.py` (`_build` ~46, `_on_region_selected` ~224; add handlers + `_DEFAULT_STROKE_PX`)
- Test: `tests/layout/test_geometry_inspector.py` (create)

**Interfaces:**
- Consumes: `Region`, `ImageStyle` (`core.layout.models`); `LayoutTab._find_region`, `LayoutTab.history`.
- Produces: `GeometryInspector` with `set_region(region)` and signals `bleedToggled(str,bool)`, `borderlessToggled(str,bool)`, `zChanged(str,int)`; `LayoutTab._on_region_bleed_toggled/_on_region_borderless_toggled/_on_region_z_changed`; module const `_DEFAULT_STROKE_PX = 4`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_geometry_inspector.py`:

```python
from gui.layout.geometry_inspector import GeometryInspector
from gui.layout.layout_tab import LayoutTab
from core.layout.models import Region, ImageStyle


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def test_inspector_reflects_region_and_emits(qapp):
    insp = GeometryInspector()
    r = Region(id="p1", kind="image", shape="path", bbox=(0, 0, 100, 100),
               bleed=True, z=3, image_style=ImageStyle(stroke_px=6))
    insp.set_region(r)
    assert insp.bleed_chk.isChecked() is True
    assert insp.borderless_chk.isChecked() is False  # stroke 6 -> not borderless
    assert insp.z_spin.value() == 3

    seen = []
    insp.bleedToggled.connect(lambda rid, b: seen.append(("bleed", rid, b)))
    insp.bleed_chk.setChecked(False)
    assert seen == [("bleed", "p1", False)]


def test_layout_tab_geometry_handlers_write_model(qapp):
    tab = LayoutTab(config=FakeConfig())
    page = tab.document.pages[0]
    page.regions = [Region(id="p1", kind="image", shape="path", bbox=(0, 0, 100, 100),
                           image_style=ImageStyle(stroke_px=6))]

    tab._on_region_bleed_toggled("p1", True)
    assert page.regions[0].bleed is True

    tab._on_region_borderless_toggled("p1", True)
    assert page.regions[0].image_style.stroke_px == 0
    tab._on_region_borderless_toggled("p1", False)
    assert page.regions[0].image_style.stroke_px == 4

    tab._on_region_z_changed("p1", 12)
    assert page.regions[0].z == 12


def test_borderless_creates_image_style_when_absent(qapp):
    tab = LayoutTab(config=FakeConfig())
    page = tab.document.pages[0]
    page.regions = [Region(id="p1", kind="image", shape="path", bbox=(0, 0, 100, 100))]
    tab._on_region_borderless_toggled("p1", False)
    assert page.regions[0].image_style is not None
    assert page.regions[0].image_style.stroke_px == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_geometry_inspector.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gui.layout.geometry_inspector'`.

- [ ] **Step 3: Create `GeometryInspector`**

Create `gui/layout/geometry_inspector.py`:

```python
"""Geometry inspector: per-region bleed / borderless / z toggles.

Emits intent signals; ``LayoutTab`` owns the model mutation (same split as
ContentInspector). The "Edit shape" toggle is added in #5a Task 4.
"""
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QSpinBox,
)
from PySide6.QtCore import Signal

from core.layout.models import Region


class GeometryInspector(QWidget):
    bleedToggled = Signal(str, bool)        # (region_id, bleed)
    borderlessToggled = Signal(str, bool)   # (region_id, borderless)
    zChanged = Signal(str, int)             # (region_id, z)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._region: Optional[Region] = None
        self._build()
        self.set_region(None)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.header = QLabel("No region selected")
        self.header.setStyleSheet("font-weight: bold;")
        root.addWidget(self.header)

        self.shape_label = QLabel("")
        self.shape_label.setStyleSheet("color: #666; font-size: 11px;")
        root.addWidget(self.shape_label)

        self.bleed_chk = QCheckBox("Bleed (extend to page edge)")
        self.bleed_chk.toggled.connect(self._on_bleed)
        root.addWidget(self.bleed_chk)

        self.borderless_chk = QCheckBox("Borderless (no panel stroke)")
        self.borderless_chk.toggled.connect(self._on_borderless)
        root.addWidget(self.borderless_chk)

        z_row = QHBoxLayout()
        z_row.addWidget(QLabel("Z-order:"))
        self.z_spin = QSpinBox()
        self.z_spin.setRange(-1000, 1000)
        self.z_spin.valueChanged.connect(self._on_z)
        z_row.addWidget(self.z_spin)
        z_row.addStretch(1)
        root.addLayout(z_row)

    def set_region(self, region: Optional[Region]):
        self._region = region
        enabled = region is not None
        for w in (self.bleed_chk, self.borderless_chk, self.z_spin):
            w.setEnabled(enabled)
        if region is None:
            self.header.setText("No region selected")
            self.shape_label.setText("")
            return
        self.header.setText(f"Geometry: {region.name or region.id}")
        self.shape_label.setText(f"shape: {region.shape}")
        stroke = region.image_style.stroke_px if region.image_style else 0
        self.bleed_chk.blockSignals(True)
        self.bleed_chk.setChecked(bool(region.bleed))
        self.bleed_chk.blockSignals(False)
        self.borderless_chk.blockSignals(True)
        self.borderless_chk.setChecked(stroke == 0)
        self.borderless_chk.blockSignals(False)
        self.z_spin.blockSignals(True)
        self.z_spin.setValue(int(region.z))
        self.z_spin.blockSignals(False)

    def _on_bleed(self, checked: bool):
        if self._region is not None:
            self.bleedToggled.emit(self._region.id, bool(checked))

    def _on_borderless(self, checked: bool):
        if self._region is not None:
            self.borderlessToggled.emit(self._region.id, bool(checked))

    def _on_z(self, value: int):
        if self._region is not None:
            self.zChanged.emit(self._region.id, int(value))
```

- [ ] **Step 4: Wire it into `LayoutTab`**

In `gui/layout/layout_tab.py`:

(a) Add a module-level constant near the top (after the imports block):

```python
_DEFAULT_STROKE_PX = 4  # panel stroke applied when "borderless" is unchecked
```

(b) In `_build`, after the `self.inspector = ContentInspector(...)` block and its `root.addWidget(self.inspector)` line, add:

```python
        from gui.layout.geometry_inspector import GeometryInspector
        self.geometry_inspector = GeometryInspector()
        self.geometry_inspector.bleedToggled.connect(self._on_region_bleed_toggled)
        self.geometry_inspector.borderlessToggled.connect(self._on_region_borderless_toggled)
        self.geometry_inspector.zChanged.connect(self._on_region_z_changed)
        root.addWidget(self.geometry_inspector)
```

(c) In `_on_region_selected`, after the existing `self.inspector.set_region(region, text_style=ts)` line, add:

```python
        self.geometry_inspector.set_region(region)
```

(d) Add the three handlers (place them after `_on_region_text_style_changed`):

```python
    def _on_region_bleed_toggled(self, region_id: str, bleed: bool):
        region = self._find_region(region_id)
        if region is None:
            return
        region.bleed = bool(bleed)
        if self.history is not None:
            self.history.append(f"bleed: {region.name or region.id}")
        self._refresh()

    def _on_region_borderless_toggled(self, region_id: str, borderless: bool):
        region = self._find_region(region_id)
        if region is None:
            return
        from core.layout.models import ImageStyle
        if region.image_style is None:
            region.image_style = ImageStyle()
        region.image_style.stroke_px = 0 if borderless else _DEFAULT_STROKE_PX
        if self.history is not None:
            self.history.append(f"borderless: {region.name or region.id}")
        self._refresh()

    def _on_region_z_changed(self, region_id: str, z: int):
        region = self._find_region(region_id)
        if region is None:
            return
        region.z = int(z)
        if self.history is not None:
            self.history.append(f"z: {region.name or region.id}")
        self._refresh()
```

- [ ] **Step 5: Run tests + commit**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_geometry_inspector.py -q` → PASS (3 passed). Then full suite: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` → green (expect ~284), confirming the existing `test_layout_tab_designer_overlays.py` still constructs `LayoutTab` cleanly.

```bash
git add gui/layout/geometry_inspector.py gui/layout/layout_tab.py tests/layout/test_geometry_inspector.py
git commit -m "feat(layout): geometry inspector with bleed/borderless/z toggles"
```

---

### Task 4: `GeometryEditor` controller — edit handles that survive the rebuild

**Files:**
- Create: `gui/layout/geometry_editor.py`
- Modify: `gui/layout/geometry_inspector.py` (add the "Edit shape" toggle + signal)
- Modify: `gui/layout/layout_tab.py` (`_build`: create the editor + connect toggle; `_refresh`: call `rebuild_handles`; `_on_region_selected`: exit edit mode on selection change)
- Test: `tests/layout/test_geometry_editor.py` (create)

**Interfaces:**
- Consumes: `region_to_painter_path` (`core.layout.qt_renderer`); `LayoutTab._find_region`, `LayoutTab.canvas`, `CanvasWidget.scene()`.
- Produces: `edit_points_for_region(region) -> List[_EditPoint]` (each `_EditPoint` has `.x`, `.y`, `.is_control`, `.apply(x,y)`); `GeometryEditor(canvas, layout_tab)` with `set_edit_region(region_id|None)`, `rebuild_handles()`, `edit_points()`, `active_region_id()`; `_HandleItem` (visual handle; made draggable in Task 5). `GeometryInspector.editShapeToggled(str,bool)` signal + `edit_shape_chk`.

This task makes handles **appear** at the right positions for the selected `path`/`polygon` region and survive a scene rebuild. Dragging is Task 5.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_geometry_editor.py`:

```python
from gui.layout.layout_tab import LayoutTab
from gui.layout.geometry_editor import edit_points_for_region
from core.layout.models import Region, PathSegment


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _diamond_path():
    return Region(id="p1", kind="image", shape="path", bbox=(0, 0, 100, 100), segments=[
        PathSegment(type="move", pts=[(50.0, 0.0)]),
        PathSegment(type="line", pts=[(100.0, 50.0)]),
        PathSegment(type="cubic", pts=[(80.0, 80.0), (60.0, 100.0), (50.0, 100.0)]),
        PathSegment(type="close", pts=[]),
    ])


def test_edit_points_for_path_region():
    pts = edit_points_for_region(_diamond_path())
    # move(1 anchor) + line(1 anchor) + cubic(2 controls + 1 anchor) + close(0) = 5
    assert len(pts) == 5
    assert (pts[0].x, pts[0].y) == (50.0, 0.0)
    assert pts[2].is_control is True and pts[3].is_control is True
    assert pts[4].is_control is False and (pts[4].x, pts[4].y) == (50.0, 100.0)


def test_edit_points_for_polygon_region():
    r = Region(id="q1", kind="image", shape="polygon", points=[(0, 0), (40, 0), (40, 30)],
               bbox=(0, 0, 40, 30))
    pts = edit_points_for_region(r)
    assert len(pts) == 3
    assert all(not p.is_control for p in pts)
    assert (pts[1].x, pts[1].y) == (40.0, 0.0)


def test_edit_points_rect_region_empty():
    r = Region(id="t1", kind="text", shape="rect", bbox=(0, 0, 50, 20))
    assert edit_points_for_region(r) == []


def test_handles_appear_and_survive_refresh(qapp):
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = [_diamond_path()]
    tab._refresh()
    tab.geometry_editor.set_edit_region("p1")
    assert len(tab.geometry_editor._handles) == 5
    tab._refresh()  # full scene rebuild
    assert len(tab.geometry_editor._handles) == 5  # regenerated, not lost


def test_edit_mode_off_clears_handles(qapp):
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = [_diamond_path()]
    tab._refresh()
    tab.geometry_editor.set_edit_region("p1")
    tab.geometry_editor.set_edit_region(None)
    assert tab.geometry_editor._handles == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_geometry_editor.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gui.layout.geometry_editor'`.

- [ ] **Step 3: Create `GeometryEditor`**

Create `gui/layout/geometry_editor.py`:

```python
"""Manual region-geometry editor: vertex/curve handles layered on the canvas.

The renderer rebuilds the whole scene on every refresh, so handles are
regenerated from the model after each rebuild (see LayoutTab._refresh) rather
than preserved. Move-only: handle generation here; dragging/commit is #5a Task 5.
"""
from typing import Callable, List, Optional

from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem
from PySide6.QtGui import QBrush, QPen, QColor
from PySide6.QtCore import QRectF

from core.layout.qt_renderer import region_to_painter_path

_HANDLE_R = 6.0  # handle radius in scene (page-pixel) units


class _EditPoint:
    """One draggable model point: its current position + how to write a new one."""
    __slots__ = ("x", "y", "is_control", "apply")

    def __init__(self, x: float, y: float, is_control: bool,
                 apply: Callable[[float, float], None]):
        self.x = x
        self.y = y
        self.is_control = is_control
        self.apply = apply


def edit_points_for_region(region) -> List["_EditPoint"]:
    """Ordered editable points for a path|polygon region (rect -> [])."""
    pts: List[_EditPoint] = []
    if region.shape == "polygon":
        for i in range(len(region.points)):
            pts.append(_polygon_point(region, i))
    elif region.shape == "path":
        for seg in region.segments:
            if seg.type in ("move", "line"):
                pts.append(_seg_point(seg, 0, is_control=False))
            elif seg.type == "quad":
                pts.append(_seg_point(seg, 0, is_control=True))
                pts.append(_seg_point(seg, 1, is_control=False))
            elif seg.type == "cubic":
                pts.append(_seg_point(seg, 0, is_control=True))
                pts.append(_seg_point(seg, 1, is_control=True))
                pts.append(_seg_point(seg, 2, is_control=False))
            # close -> no handle
    return pts


def _polygon_point(region, i: int) -> "_EditPoint":
    px, py = region.points[i]

    def apply(x: float, y: float):
        region.points[i] = (round(x), round(y))

    return _EditPoint(float(px), float(py), False, apply)


def _seg_point(seg, j: int, *, is_control: bool) -> "_EditPoint":
    px, py = seg.pts[j]

    def apply(x: float, y: float):
        seg.pts[j] = (x, y)

    return _EditPoint(float(px), float(py), is_control, apply)


class _HandleItem(QGraphicsEllipseItem):
    """A vertex/control handle. Visual in Task 4; made draggable in Task 5."""

    def __init__(self, editor: "GeometryEditor", index: int):
        super().__init__()
        self._editor = editor
        self._index = index


class GeometryEditor:
    """Owns the edit handles for one selected path/polygon region on a canvas."""

    def __init__(self, canvas, layout_tab):
        self._canvas = canvas
        self._tab = layout_tab
        self._edit_region_id: Optional[str] = None
        self._points: List[_EditPoint] = []
        self._handles: List[_HandleItem] = []
        self._shape_item = None

    def active_region_id(self) -> Optional[str]:
        return self._edit_region_id

    def edit_points(self) -> List[_EditPoint]:
        return self._points

    def set_edit_region(self, region_id: Optional[str]) -> None:
        self._edit_region_id = region_id or None
        self.rebuild_handles()

    def rebuild_handles(self) -> None:
        """Re-create handles from the model for the active region.

        Call after every scene rebuild — handles are not preserved across the
        renderer's full-scene rebuild, they are reconstructed here.
        """
        self._clear()
        if not self._edit_region_id:
            return
        region = self._tab._find_region(self._edit_region_id)
        if region is None or region.shape not in ("path", "polygon"):
            self._edit_region_id = None
            return
        scene = self._canvas.scene()
        if scene is None:
            return
        self._shape_item = self._find_shape_item(scene, region)
        self._points = edit_points_for_region(region)
        for idx, ep in enumerate(self._points):
            h = _HandleItem(self, idx)
            h.setRect(QRectF(-_HANDLE_R, -_HANDLE_R, 2 * _HANDLE_R, 2 * _HANDLE_R))
            h.setPos(ep.x, ep.y)
            h.setZValue(1_000_000)
            h.setBrush(QBrush(QColor("#FFFFFF") if ep.is_control else QColor("#2D7DD2")))
            h.setPen(QPen(QColor("#2D7DD2"), 1.5))
            scene.addItem(h)
            self._handles.append(h)

    def _find_shape_item(self, scene, region):
        for it in scene.items():
            if getattr(it, "_region", None) is region and hasattr(it, "setPath"):
                return it
        return None

    def _clear(self) -> None:
        scene = self._canvas.scene()
        if scene is not None:
            for h in self._handles:
                scene.removeItem(h)
        self._handles = []
        self._points = []
        self._shape_item = None
```

- [ ] **Step 4: Add the "Edit shape" toggle to `GeometryInspector` and wire the editor in `LayoutTab`**

(a) In `gui/layout/geometry_inspector.py`, add the signal (next to the other signals):

```python
    editShapeToggled = Signal(str, bool)    # (region_id, on)
```

In `_build`, after the z-order row, add an edit-shape checkbox:

```python
        self.edit_shape_chk = QCheckBox("Edit shape (drag vertices)")
        self.edit_shape_chk.toggled.connect(self._on_edit_shape)
        root.addWidget(self.edit_shape_chk)
```

Replace the **entire** `set_region` method (from Task 3) with the version below — it resets/enables the edit-shape toggle on every selection change (enabled only for path/polygon) and otherwise behaves identically to Task 3:

```python
    def set_region(self, region: Optional[Region]):
        self._region = region
        enabled = region is not None
        for w in (self.bleed_chk, self.borderless_chk, self.z_spin):
            w.setEnabled(enabled)
        # Edit-shape applies only to vertex-bearing shapes; reset on every change.
        self.edit_shape_chk.blockSignals(True)
        self.edit_shape_chk.setChecked(False)
        self.edit_shape_chk.setEnabled(bool(region and region.shape in ("path", "polygon")))
        self.edit_shape_chk.blockSignals(False)
        if region is None:
            self.header.setText("No region selected")
            self.shape_label.setText("")
            return
        self.header.setText(f"Geometry: {region.name or region.id}")
        self.shape_label.setText(f"shape: {region.shape}")
        stroke = region.image_style.stroke_px if region.image_style else 0
        self.bleed_chk.blockSignals(True)
        self.bleed_chk.setChecked(bool(region.bleed))
        self.bleed_chk.blockSignals(False)
        self.borderless_chk.blockSignals(True)
        self.borderless_chk.setChecked(stroke == 0)
        self.borderless_chk.blockSignals(False)
        self.z_spin.blockSignals(True)
        self.z_spin.setValue(int(region.z))
        self.z_spin.blockSignals(False)
```

Add the handler:

```python
    def _on_edit_shape(self, checked: bool):
        if self._region is not None:
            self.editShapeToggled.emit(self._region.id, bool(checked))
```

(b) In `gui/layout/layout_tab.py` `_build`, immediately after the `self.canvas = CanvasWidget()` / `root.addWidget(self.canvas, 1)` lines, create the editor (it needs the canvas):

```python
        from gui.layout.geometry_editor import GeometryEditor
        self.geometry_editor = GeometryEditor(self.canvas, self)
```

In the geometry-inspector wiring block (Task 3), add:

```python
        self.geometry_inspector.editShapeToggled.connect(self._on_region_edit_shape_toggled)
```

Add the handler (after the other geometry handlers):

```python
    def _on_region_edit_shape_toggled(self, region_id: str, on: bool):
        self.geometry_editor.set_edit_region(region_id if on else None)
```

(c) In `_refresh`, after `self.canvas.load_page(...)`, regenerate handles (guarded so it is safe before the editor exists):

```python
    def _refresh(self):
        if self.document and self.document.pages:
            self.canvas.load_page(self.document.pages[0], self.document.style,
                                  locked=self._locked)
            self.status.setText(f"{self.document.title} — {self.document.pages[0].page_size_px}")
            ge = getattr(self, "geometry_editor", None)
            if ge is not None:
                ge.rebuild_handles()
        self.documentChanged.emit()
```

(d) In `_on_region_selected`, exit edit mode on any selection change (the inspector also unchecks its toggle in `set_region`). After `self.geometry_inspector.set_region(region)`:

```python
        self.geometry_editor.set_edit_region(None)
```

- [ ] **Step 5: Run tests + commit**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_geometry_editor.py -q` → PASS (5 passed). Full suite: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` → green (expect ~289).

```bash
git add gui/layout/geometry_editor.py gui/layout/geometry_inspector.py gui/layout/layout_tab.py tests/layout/test_geometry_editor.py
git commit -m "feat(layout): geometry editor handles (regenerated across scene rebuild)"
```

---

### Task 5: handle drag → live edit + commit (bbox, validate, undo, refresh)

**Files:**
- Modify: `gui/layout/geometry_editor.py` (`_HandleItem` drag events; `GeometryEditor.begin_edit/move_handle/commit`)
- Modify: `gui/layout/layout_tab.py` (`set_refresh_suspended`, `snapshot_and_refresh`, `_refresh` suspend guard)
- Modify: `gui/layout/canvas_widget.py` (`resizeEvent` re-fit)
- Test: `tests/layout/test_geometry_editor_drag.py` (create)

**Interfaces:**
- Consumes: `geometry.validate_segments`, `geometry.segments_bbox`; `region_to_painter_path`; `LayoutTab._find_region`, `LayoutTab._refresh`, `LayoutTab.history`.
- Produces: `GeometryEditor.begin_edit()`, `GeometryEditor.move_handle(index, x, y)`, `GeometryEditor.commit()`; `LayoutTab.set_refresh_suspended(bool)`, `LayoutTab.snapshot_and_refresh(prompt)`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_geometry_editor_drag.py`:

```python
from gui.layout.layout_tab import LayoutTab
from core.layout.models import Region, PathSegment


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tri():
    return Region(id="p1", kind="image", shape="path", bbox=(10, 10, 40, 40), segments=[
        PathSegment(type="move", pts=[(10.0, 10.0)]),
        PathSegment(type="line", pts=[(50.0, 10.0)]),
        PathSegment(type="line", pts=[(50.0, 50.0)]),
        PathSegment(type="close", pts=[]),
    ])


def _editing_tab():
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = [_tri()]
    tab._refresh()
    tab.geometry_editor.set_edit_region("p1")
    return tab


def test_move_handle_mutates_segment_point(qapp):
    tab = _editing_tab()
    tab.geometry_editor.begin_edit()
    tab.geometry_editor.move_handle(0, 20.0, 5.0)  # drag the 'move' anchor
    seg0 = tab.document.pages[0].regions[0].segments[0]
    assert seg0.pts == [(20.0, 5.0)]


def test_commit_recomputes_bbox_and_snapshots(qapp):
    tab = _editing_tab()
    before = len(tab.history.snapshots())
    tab.geometry_editor.begin_edit()
    tab.geometry_editor.move_handle(2, 90.0, 90.0)  # move the 2nd line endpoint out
    tab.geometry_editor.commit()
    r = tab.document.pages[0].regions[0]
    assert r.segments[2].pts == [(90.0, 90.0)]
    assert r.bbox == (10, 10, 80, 80)  # segments_bbox over (10,10),(50,10),(90,90)
    assert len(tab.history.snapshots()) == before + 1


def test_begin_edit_suspends_refresh_commit_resumes(qapp):
    tab = _editing_tab()
    tab.geometry_editor.begin_edit()
    assert tab._suspend_refresh is True
    tab.geometry_editor.commit()
    assert tab._suspend_refresh is False


def test_polygon_vertex_edit_commits(qapp):
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = [Region(id="q1", kind="image", shape="polygon",
                                            points=[(0, 0), (40, 0), (40, 30)], bbox=(0, 0, 40, 30))]
    tab._refresh()
    tab.geometry_editor.set_edit_region("q1")
    tab.geometry_editor.begin_edit()
    tab.geometry_editor.move_handle(2, 60.0, 50.0)
    tab.geometry_editor.commit()
    r = tab.document.pages[0].regions[0]
    assert r.points[2] == (60, 50)
    assert r.bbox == (0, 0, 60, 50)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_geometry_editor_drag.py -q`
Expected: FAIL — `AttributeError: 'GeometryEditor' object has no attribute 'begin_edit'`.

- [ ] **Step 3: Add the `LayoutTab` refresh plumbing**

In `gui/layout/layout_tab.py`:

(a) At the top of `_refresh`, honor a suspend flag:

```python
    def _refresh(self):
        if getattr(self, "_suspend_refresh", False):
            return
        if self.document and self.document.pages:
            self.canvas.load_page(self.document.pages[0], self.document.style,
                                  locked=self._locked)
            self.status.setText(f"{self.document.title} — {self.document.pages[0].page_size_px}")
            ge = getattr(self, "geometry_editor", None)
            if ge is not None:
                ge.rebuild_handles()
        self.documentChanged.emit()
```

(b) Add the two helpers (after `_refresh`):

```python
    def set_refresh_suspended(self, on: bool):
        """Block scene rebuilds during an active handle drag (else handles vanish)."""
        self._suspend_refresh = bool(on)

    def snapshot_and_refresh(self, prompt: str):
        if self.history is not None:
            self.history.append(prompt)
        self._refresh()
```

- [ ] **Step 4: Add drag + commit to `GeometryEditor` and make `_HandleItem` interactive**

In `gui/layout/geometry_editor.py`:

(a) Make `_HandleItem` draggable and route its events to the editor:

```python
class _HandleItem(QGraphicsEllipseItem):
    """A vertex/control handle. Dragging mutates the bound model point."""

    def __init__(self, editor: "GeometryEditor", index: int):
        super().__init__()
        self._editor = editor
        self._index = index
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

    def mousePressEvent(self, event):
        self._editor.begin_edit()
        super().mousePressEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self._editor.move_handle(self._index, self.x(), self.y())
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._editor.commit()
```

(b) Add `begin_edit`, `move_handle`, and `commit` to `GeometryEditor` (and an `_pre` field — initialize `self._pre = None` in `__init__`):

```python
    def begin_edit(self) -> None:
        """Snapshot pre-edit geometry (for validation revert) and freeze refreshes."""
        region = self._tab._find_region(self._edit_region_id) if self._edit_region_id else None
        if region is None:
            self._pre = None
            return
        self._pre = (
            [type(s)(type=s.type, pts=list(s.pts)) for s in region.segments],
            list(region.points),
            tuple(region.bbox),
        )
        self._tab.set_refresh_suspended(True)

    def move_handle(self, index: int, x: float, y: float) -> None:
        """Apply a handle's new scene position to the model + live-update the path."""
        if not (0 <= index < len(self._points)):
            return
        self._points[index].apply(x, y)
        region = self._tab._find_region(self._edit_region_id) if self._edit_region_id else None
        if region is not None and self._shape_item is not None:
            self._shape_item.setPath(region_to_painter_path(region))

    def commit(self) -> None:
        """Persist the edit: validate, recompute bbox, snapshot, refresh."""
        self._tab.set_refresh_suspended(False)
        region = self._tab._find_region(self._edit_region_id) if self._edit_region_id else None
        if region is None:
            self._pre = None
            return
        from core.layout.geometry import validate_segments, segments_bbox
        if region.shape == "path":
            issues = validate_segments(region.segments)
            if issues:
                import logging
                logging.getLogger(__name__).warning(
                    "Geometry edit on %s produced invalid segments; reverting: %s",
                    region.id, "; ".join(issues))
                if self._pre is not None:
                    region.segments, region.points, region.bbox = self._pre
                self._pre = None
                self._tab._refresh()
                return
            bx, by, bw, bh = segments_bbox(region.segments)
            region.bbox = (round(bx), round(by), round(bw), round(bh))
        elif region.shape == "polygon" and region.points:
            xs = [p[0] for p in region.points]
            ys = [p[1] for p in region.points]
            region.bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        self._pre = None
        self._tab.snapshot_and_refresh(f"edit shape: {region.name or region.id}")
```

Also add `self._pre = None` to `GeometryEditor.__init__` (next to the other instance attrs).

- [ ] **Step 5: Add `resizeEvent` re-fit to `CanvasWidget`**

In `gui/layout/canvas_widget.py`, add (so handles stay aligned when the widget resizes):

```python
    def resizeEvent(self, event):
        super().resizeEvent(event)
        scene = self.scene()
        if scene is not None:
            self.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)
```

- [ ] **Step 6: Run tests + commit**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_geometry_editor_drag.py -q` → PASS (4 passed). Then the FULL suite: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` → all green (expect ~293).

```bash
git add gui/layout/geometry_editor.py gui/layout/layout_tab.py gui/layout/canvas_widget.py tests/layout/test_geometry_editor_drag.py
git commit -m "feat(layout): vertex/curve handle drag with commit (bbox, validate, undo)"
```

---

## Notes / deliberately deferred (not gaps)
- **Split/knife, merge, delete** → **#5b** (reuse `polygon.clip_halfplane` / `union_polygons`; this task's editor foundation carries over).
- **Overlay editing** — balloon placement/drag, tail→region snapping, SFX rotation (new `Overlay.rotation` field), contour-aware wrapping → **#5c**. The #4 carry-forward (stranded pixel-anchored overlays on a regions-only redesign) lands with #5c.
- **PIL export still bypasses the Qt renderer/overlays** (carried from #1–#3) — biggest cross-cutting follow-up, after the editor phases.
- **Vertex insert/delete, line↔curve conversion, rect-corner resize** — possible #5b additions; not #5a.
- **Content/text-style edits still don't snapshot undo** (pre-existing). #5a adds snapshots for geometry edits only; harmonizing content-edit undo is out of scope.

## Self-Review (completed by plan author)
- **Spec coverage:** editing foundation = handle regeneration across rebuild (Task 4 `rebuild_handles` + `_refresh` hook) + segment write-back (Task 2) + undo (Task 5 `snapshot_and_refresh`) + geometry inspector (Task 3); move-only vertex/curve drag (Tasks 4–5, `edit_points_for_region` covers move/line/quad/cubic anchors + controls, polygon vertices); bleed/borderless toggles (Task 3). Every design §4–§9 item maps to a task; error path (invalid segments → revert + log) is Task 5 `commit`.
- **Placeholder scan:** no TBD/TODO; every code step shows complete code; the degrade path is concrete (`validate_segments` → restore `self._pre` + `logger.warning`).
- **Type/name consistency:** `translate_segments` (T1) consumed by `_writeback_move` (T2); `edit_points_for_region`/`_EditPoint.apply` (T4) consumed by `move_handle` (T5); `GeometryEditor.set_edit_region/rebuild_handles` (T4) called from `LayoutTab._refresh`/`_on_region_edit_shape_toggled`; `set_refresh_suspended`/`snapshot_and_refresh` (T5) called from `GeometryEditor.begin_edit`/`commit`; signal names (`bleedToggled`/`borderlessToggled`/`zChanged`/`editShapeToggled`) match between `GeometryInspector` and `LayoutTab` connects. `region_to_painter_path`, `_RegionPathItem`, `_writeback_move`, `segments_bbox`, `validate_segments`, `History.append`, `ImageStyle.stroke_px`, `Region.points/segments/bbox/bleed/z` all match the real signatures.
- **Test interpreter/baseline:** all tasks use `.venv_linux/bin/python` under `QT_QPA_PLATFORM=offscreen`; suite 276 → ~293 (3+2+3+5+4 = 17 new tests; counts approximate — the binding check is "all new tests pass and the full suite stays green").
