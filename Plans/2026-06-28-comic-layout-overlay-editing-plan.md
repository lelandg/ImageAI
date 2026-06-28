# Comic Layout — Overlay Editing + Export (#5c) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the comic-layout manual editor with full overlay authoring (place/move/tail-snap/delete + SFX rotation + stranded-overlay reposition) and make exports render the comic layout (PIL→Qt fold-in). This is the FINAL sub-project of the comic-layout feature.

**Architecture:** A new `rotation` field on `Overlay` (rendered via Qt `setRotation` about the anchor). A pure `core/layout/overlay_ops.py` for stranded detection/reposition. An `OverlayInspector` (emit-signals-only list + authoring controls) and an `OverlayEditor` controller (drag handles regenerated after each scene rebuild, mirroring #5a's `GeometryEditor`). `LayoutTab` owns all mutation. Exports route through the existing Qt renderer.

**Tech Stack:** Python 3.12, PySide6 (GUI), pytest. Reuses `core/layout/qt_renderer.py` (`_add_overlay`, `save_page_png`, `render_page_to_image`, `export_document_pdf`, `build_scene`), `core/layout/balloons.py` (`overlay_to_segments`), `core/layout/schema.py` (`overlay_to_dict`/`overlay_from_dict`), `core/layout/models.py` (`Overlay`, `OverlayStyle`, `Region`), `core/layout/history.py`, and #5a/#5b `LayoutTab` plumbing (`snapshot_and_refresh`, `set_refresh_suspended`, `_current_page`, `_refresh`).

## Global Constraints

- Test interpreter: `.venv_linux/bin/python`, ALWAYS prefixed with `QT_QPA_PLATFORM=offscreen`.
- Full layout suite must stay green: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` (currently **316 passed** on branch `feat/comic-layout-geometry-core`).
- **No new third-party dependency.**
- `core/layout/overlay_ops.py` stays **Qt-free** (importable headless). Qt code lives only in `gui/layout/` and `core/layout/qt_renderer.py`.
- **All errors logged** (`logging.getLogger(__name__)`): a failed/degenerate op is a **no-op + log**, never a crash, never a corrupt model.
- **Backward compatibility:** existing pages (no `rotation` key) load with `rotation == 0.0`; serialization round-trips byte-stable for existing fields.
- **Inspector/controller split:** UI widgets emit intent signals; `LayoutTab` owns all model mutation (same pattern as #5a/#5b).
- **Coordinates:** scene == page pixels. Rotation is **degrees clockwise about the overlay anchor**.
- **Scope:** place/move/tail-snap/delete, SFX rotation (via inspector spin), stranded reposition, export fold-in. **No** contour-aware text wrapping, **no** rotation drag handle, **no** multi-overlay select.
- Conventional Commits (`feat(layout): …`). Commit after each task.
- **Branch:** continue on `feat/comic-layout-geometry-core`. **Do NOT open a pull request** as part of these tasks — the single comic-layout PR is a separate step after #5c is complete.

### Names used across tasks (keep identical)
- `Overlay.rotation: float = 0.0` (Task 1).
- `overlay_ops.overlay_anchor_stranded(ov, regions) -> bool`, `nearest_region_center(point, regions) -> Optional[Tuple[float,float]]`, `reposition_stranded_overlays(page) -> int` (Task 3).
- `OverlayInspector` signals `addRequested(str)`, `deleteRequested(str)`, `rotationChanged(str,int)`, `overlaySelected(str)`, `editToggled(str,bool)`; methods `set_page(page)`, `set_selected(overlay_id)`; widgets `overlay_list`/`rotation_spin`/`edit_chk` (Task 4).
- `OverlayEditor(canvas, layout_tab)` with `set_edit_overlay(id|None)`, `rebuild_handles()`, `begin_edit()`, `move_handle(kind, x, y)`, `commit()`, `_find_overlay(id)` (Task 5).
- `LayoutTab._add_overlay(kind)`, `_delete_overlay(id)`, `_set_overlay_rotation(id, deg)`, `_on_overlay_selected(id)`, `_on_overlay_edit_toggled(id, on)`, `export_png_to(path)` (Tasks 6-7).

---

### Task 1: `Overlay.rotation` field + serialization round-trip (pure)

**Files:**
- Modify: `core/layout/models.py` (`Overlay` ~159)
- Modify: `core/layout/schema.py` (`overlay_to_dict` ~118, `overlay_from_dict` ~132)
- Test: `tests/layout/test_overlay_rotation.py` (create)

**Interfaces:**
- Consumes: `Overlay` (`core.layout.models`).
- Produces: `Overlay.rotation: float = 0.0`; `overlay_to_dict` emits `"rotation"`; `overlay_from_dict` reads it degrade-safe.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_overlay_rotation.py`:

```python
from core.layout.models import Overlay
from core.layout.schema import overlay_to_dict, overlay_from_dict


def _ov(**kw):
    base = dict(id="o1", kind="sfx", text="BOOM", anchor=(100.0, 100.0))
    base.update(kw)
    return Overlay(**base)


def test_rotation_defaults_to_zero():
    assert _ov().rotation == 0.0


def test_rotation_round_trips():
    d = overlay_to_dict(_ov(rotation=37.5))
    assert d["rotation"] == 37.5
    assert overlay_from_dict(d).rotation == 37.5


def test_rotation_missing_key_loads_zero():
    d = overlay_to_dict(_ov())
    del d["rotation"]
    assert overlay_from_dict(d).rotation == 0.0


def test_rotation_non_numeric_degrades_to_zero():
    d = overlay_to_dict(_ov())
    d["rotation"] = None
    assert overlay_from_dict(d).rotation == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_rotation.py -q`
Expected: FAIL — `TypeError: Overlay.__init__() got an unexpected keyword argument 'rotation'`.

- [ ] **Step 3: Add the field + serialization**

In `core/layout/models.py`, in the `Overlay` dataclass, add after the `style` field (~159):

```python
    rotation: float = 0.0  # degrees clockwise about the anchor (SFX & balloons)
```

In `core/layout/schema.py` `overlay_to_dict`, add `"rotation": ov.rotation,` to the dict (e.g. after the `"z": ov.z, "role": ov.role,` line):

```python
        "z": ov.z, "role": ov.role, "rotation": ov.rotation,
```

In `overlay_from_dict`, add the `rotation` kwarg to the `Overlay(...)` call (degrade-safe):

```python
        rotation=float(d.get("rotation", 0.0) or 0.0),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_rotation.py -q`
Expected: PASS (4 passed). Then full suite green: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` (expect ~320). Confirm existing overlay serialization tests still pass.

- [ ] **Step 5: Commit**

```bash
git add core/layout/models.py core/layout/schema.py tests/layout/test_overlay_rotation.py
git commit -m "feat(layout): Overlay.rotation field with serialization round-trip"
```

---

### Task 2: render overlay rotation (`_add_overlay`)

**Files:**
- Modify: `core/layout/qt_renderer.py` (`_add_overlay` ~286, near the end after `text_item` is built)
- Test: `tests/layout/test_overlay_render_rotation.py` (create)

**Interfaces:**
- Consumes: `Overlay.rotation` (Task 1); `build_scene` (`core.layout.qt_renderer`).
- Produces: `_add_overlay` rotates the body (or, for SFX, the text item) about the anchor.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_overlay_render_rotation.py`:

```python
from core.layout.models import PageSpec, Overlay
from core.layout import qt_renderer


def _page(overlays):
    return PageSpec(page_size_px=(400, 400), regions=[], overlays=overlays)


def test_sfx_overlay_rotation_applied(qapp):
    ov = Overlay(id="s", kind="sfx", text="POW", anchor=(200.0, 200.0), rotation=30.0)
    scene = qt_renderer.build_scene(_page([ov]))
    rots = [it.rotation() for it in scene.items() if hasattr(it, "rotation")]
    assert any(abs(r - 30.0) < 1e-6 for r in rots)


def test_speech_overlay_rotation_applied(qapp):
    ov = Overlay(id="b", kind="speech", text="hi", anchor=(200.0, 200.0), rotation=45.0)
    scene = qt_renderer.build_scene(_page([ov]))
    rots = [it.rotation() for it in scene.items() if hasattr(it, "rotation")]
    assert any(abs(r - 45.0) < 1e-6 for r in rots)


def test_zero_rotation_no_transform(qapp):
    ov = Overlay(id="b", kind="speech", text="hi", anchor=(200.0, 200.0))
    scene = qt_renderer.build_scene(_page([ov]))
    rots = [it.rotation() for it in scene.items() if hasattr(it, "rotation")]
    assert all(abs(r) < 1e-6 for r in rots)
```

(If `PageSpec`'s constructor kwargs differ, read `core/layout/models.py` `PageSpec` and adjust the `_page` helper — the test only needs a page with `page_size_px`, empty `regions`, and the given `overlays`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_render_rotation.py -q`
Expected: FAIL — `test_sfx_overlay_rotation_applied`/`test_speech_overlay_rotation_applied` fail (no item has rotation 30/45).

- [ ] **Step 3: Apply rotation in `_add_overlay`**

In `core/layout/qt_renderer.py`, at the END of `_add_overlay` (after the `if body_item is None: scene.addItem(text_item)` block), add:

```python
    # Rotation: spin the body (text rides along as its child) or, for SFX with no
    # body, the text item — both about the overlay anchor (scene coords).
    rot = getattr(ov, "rotation", 0.0) or 0.0
    if rot:
        from PySide6.QtCore import QPointF
        if body_item is not None:
            body_item.setTransformOriginPoint(QPointF(ax, ay))  # body sits at scene origin
            body_item.setRotation(rot)
        else:
            text_item.setTransformOriginPoint(
                QPointF(ax - text_item.x(), ay - text_item.y()))
            text_item.setRotation(rot)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_render_rotation.py -q`
Expected: PASS (3 passed). Then full suite green (expect ~323).

- [ ] **Step 5: Commit**

```bash
git add core/layout/qt_renderer.py tests/layout/test_overlay_render_rotation.py
git commit -m "feat(layout): render overlay rotation about the anchor"
```

---

### Task 3: `overlay_ops` — stranded detection + reposition (pure)

**Files:**
- Create: `core/layout/overlay_ops.py`
- Test: `tests/layout/test_overlay_ops.py` (create)

**Interfaces:**
- Consumes: `Overlay`, `Region`, `PageSpec` (`core.layout.models`).
- Produces: `overlay_anchor_stranded(ov, regions) -> bool`; `nearest_region_center(point, regions) -> Optional[Tuple[float,float]]`; `reposition_stranded_overlays(page) -> int`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_overlay_ops.py`:

```python
from core.layout.models import PageSpec, Region, Overlay
from core.layout.overlay_ops import (
    overlay_anchor_stranded, nearest_region_center, reposition_stranded_overlays,
)


def _regions():
    return [
        Region(id="a", kind="image", shape="rect", bbox=(0, 0, 100, 100)),
        Region(id="b", kind="image", shape="rect", bbox=(200, 0, 100, 100)),
    ]


def test_stranded_true_when_outside_all_bboxes():
    ov = Overlay(id="o", kind="sfx", text="x", anchor=(150.0, 50.0))  # in the gap
    assert overlay_anchor_stranded(ov, _regions()) is True


def test_stranded_false_when_inside_a_bbox():
    ov = Overlay(id="o", kind="sfx", text="x", anchor=(50.0, 50.0))  # inside region a
    assert overlay_anchor_stranded(ov, _regions()) is False


def test_nearest_region_center_picks_closest():
    assert nearest_region_center((150.0, 50.0), _regions()) == (250.0, 50.0)
    assert nearest_region_center((140.0, 50.0), _regions()) == (50.0, 50.0)


def test_nearest_region_center_none_when_no_regions():
    assert nearest_region_center((10.0, 10.0), []) is None


def test_reposition_moves_only_stranded():
    page = PageSpec(page_size_px=(400, 400), regions=_regions(), overlays=[
        Overlay(id="in", kind="sfx", text="x", anchor=(50.0, 50.0)),    # inside a
        Overlay(id="out", kind="sfx", text="y", anchor=(150.0, 50.0)),  # stranded -> nearest b
    ])
    moved = reposition_stranded_overlays(page)
    assert moved == 1
    by_id = {o.id: o.anchor for o in page.overlays}
    assert by_id["in"] == (50.0, 50.0)        # untouched
    assert by_id["out"] == (250.0, 50.0)      # moved to region b center


def test_reposition_noop_without_regions():
    page = PageSpec(page_size_px=(400, 400), regions=[], overlays=[
        Overlay(id="o", kind="sfx", text="x", anchor=(10.0, 10.0))])
    assert reposition_stranded_overlays(page) == 0
```

(If `PageSpec`/`Region` kwargs differ, read `core/layout/models.py` and adjust the fixtures — the logic only needs region `bbox` and overlay `anchor`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_ops.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.layout.overlay_ops'`.

- [ ] **Step 3: Implement `overlay_ops`**

Create `core/layout/overlay_ops.py`:

```python
"""Pure (Qt-free) overlay operations: stranded-anchor detection + reposition.

When a regions-only redesign replaces the panels, pixel-anchored overlays can be
left floating over empty space. These helpers detect that (anchor outside every
region's bbox) and move the anchor onto the nearest region's bbox center.
Deterministic; never mutates input regions.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from core.layout.models import Overlay, Region, PageSpec

logger = logging.getLogger(__name__)

Point = Tuple[float, float]


def _bbox_contains(bbox, x: float, y: float) -> bool:
    bx, by, bw, bh = bbox
    return bx <= x <= bx + bw and by <= y <= by + bh


def _bbox_center(bbox) -> Point:
    bx, by, bw, bh = bbox
    return (bx + bw / 2.0, by + bh / 2.0)


def overlay_anchor_stranded(ov: Overlay, regions: List[Region]) -> bool:
    """True if the overlay's anchor lies outside every region's bbox."""
    ax, ay = ov.anchor
    return not any(_bbox_contains(r.bbox, ax, ay) for r in regions)


def nearest_region_center(point: Point, regions: List[Region]) -> Optional[Point]:
    """bbox center of the region whose center is nearest ``point`` (None if empty)."""
    if not regions:
        return None
    px, py = point
    best = None
    best_d2 = None
    for r in regions:
        cx, cy = _bbox_center(r.bbox)
        d2 = (cx - px) ** 2 + (cy - py) ** 2
        if best_d2 is None or d2 < best_d2:
            best_d2 = d2
            best = (cx, cy)
    return best


def reposition_stranded_overlays(page: PageSpec) -> int:
    """Move every stranded overlay's anchor to the nearest region center.

    Returns the number of overlays moved. No-op (0) when the page has no regions
    or no overlays. Logs a summary when it moves any.
    """
    regions = list(page.regions)
    if not regions or not page.overlays:
        return 0
    moved = 0
    for ov in page.overlays:
        if overlay_anchor_stranded(ov, regions):
            target = nearest_region_center(ov.anchor, regions)
            if target is not None:
                ov.anchor = target
                moved += 1
    if moved:
        logger.info("repositioned %d stranded overlay(s) onto nearest panels", moved)
    return moved
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_ops.py -q`
Expected: PASS (6 passed). Then full suite green (expect ~329).

- [ ] **Step 5: Commit**

```bash
git add core/layout/overlay_ops.py tests/layout/test_overlay_ops.py
git commit -m "feat(layout): overlay_ops stranded-anchor detection + reposition (pure)"
```

---

### Task 4: `OverlayInspector` widget (emit-signals-only)

**Files:**
- Create: `gui/layout/overlay_inspector.py`
- Test: `tests/layout/test_overlay_inspector.py` (create)

**Interfaces:**
- Consumes: `PageSpec`, `Overlay` (`core.layout.models`).
- Produces: `OverlayInspector` with signals `addRequested(str)`, `deleteRequested(str)`, `rotationChanged(str,int)`, `overlaySelected(str)`, `editToggled(str,bool)`; methods `set_page(page)`, `set_selected(overlay_id)`; widgets `overlay_list`, `rotation_spin`, `edit_chk`, `add_speech_btn`/`add_thought_btn`/`add_caption_btn`/`add_sfx_btn`, `delete_btn`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_overlay_inspector.py`:

```python
from PySide6.QtCore import Qt
from gui.layout.overlay_inspector import OverlayInspector
from core.layout.models import PageSpec, Overlay


def _page(overlays):
    return PageSpec(page_size_px=(400, 400), regions=[], overlays=overlays)


def test_set_page_lists_overlays(qapp):
    insp = OverlayInspector()
    insp.set_page(_page([
        Overlay(id="o1", kind="speech", text="hi", anchor=(10.0, 10.0)),
        Overlay(id="o2", kind="sfx", text="POW", anchor=(20.0, 20.0)),
    ]))
    assert insp.overlay_list.count() == 2


def test_add_buttons_emit_kind(qapp):
    insp = OverlayInspector()
    seen = []
    insp.addRequested.connect(lambda k: seen.append(k))
    insp.add_speech_btn.click()
    insp.add_sfx_btn.click()
    assert seen == ["speech", "sfx"]


def test_rotation_and_delete_emit_for_selected(qapp):
    insp = OverlayInspector()
    insp.set_page(_page([Overlay(id="o1", kind="sfx", text="x", anchor=(0.0, 0.0), rotation=10.0)]))
    insp.set_selected("o1")
    assert insp.rotation_spin.value() == 10
    rot, dele = [], []
    insp.rotationChanged.connect(lambda i, d: rot.append((i, d)))
    insp.deleteRequested.connect(lambda i: dele.append(i))
    insp.rotation_spin.setValue(90)
    insp.delete_btn.click()
    assert rot == [("o1", 90)]
    assert dele == ["o1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_inspector.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gui.layout.overlay_inspector'`.

- [ ] **Step 3: Create `OverlayInspector`**

Create `gui/layout/overlay_inspector.py`:

```python
"""Overlay inspector: list + author comic text overlays.

Emits intent signals only; ``LayoutTab`` owns all model mutation (same split as
Geometry/Content inspectors).
"""
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSpinBox, QCheckBox,
)
from PySide6.QtCore import Signal, Qt

from core.layout.models import PageSpec, Overlay


class OverlayInspector(QWidget):
    addRequested = Signal(str)        # (kind)
    deleteRequested = Signal(str)     # (overlay_id)
    rotationChanged = Signal(str, int)  # (overlay_id, degrees)
    overlaySelected = Signal(str)     # (overlay_id)
    editToggled = Signal(str, bool)   # (overlay_id, on)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_id: Optional[str] = None
        self._build()
        self.set_selected(None)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(QLabel("Overlays"))

        self.overlay_list = QListWidget()
        self.overlay_list.itemSelectionChanged.connect(self._on_row_changed)
        root.addWidget(self.overlay_list)

        add_row = QHBoxLayout()
        self.add_speech_btn = QPushButton("+Speech")
        self.add_thought_btn = QPushButton("+Thought")
        self.add_caption_btn = QPushButton("+Caption")
        self.add_sfx_btn = QPushButton("+SFX")
        for btn, kind in ((self.add_speech_btn, "speech"),
                          (self.add_thought_btn, "thought"),
                          (self.add_caption_btn, "caption"),
                          (self.add_sfx_btn, "sfx")):
            btn.clicked.connect(lambda _checked=False, k=kind: self.addRequested.emit(k))
            add_row.addWidget(btn)
        root.addLayout(add_row)

        edit_row = QHBoxLayout()
        self.delete_btn = QPushButton("Delete overlay")
        self.delete_btn.clicked.connect(self._on_delete)
        edit_row.addWidget(self.delete_btn)
        self.edit_chk = QCheckBox("Edit on canvas")
        self.edit_chk.toggled.connect(self._on_edit)
        edit_row.addWidget(self.edit_chk)
        edit_row.addStretch(1)
        root.addLayout(edit_row)

        rot_row = QHBoxLayout()
        rot_row.addWidget(QLabel("Rotation:"))
        self.rotation_spin = QSpinBox()
        self.rotation_spin.setRange(0, 359)
        self.rotation_spin.setSuffix("°")
        self.rotation_spin.valueChanged.connect(self._on_rotation)
        rot_row.addWidget(self.rotation_spin)
        rot_row.addStretch(1)
        root.addLayout(rot_row)

    def set_page(self, page: Optional[PageSpec]):
        self.overlay_list.blockSignals(True)
        self.overlay_list.clear()
        if page is not None:
            for ov in page.overlays:
                item = QListWidgetItem(f"{ov.kind}: {ov.text[:20]}")
                item.setData(Qt.UserRole, ov.id)
                self.overlay_list.addItem(item)
        self.overlay_list.blockSignals(False)
        self.set_selected(self._selected_id)

    def set_selected(self, overlay_id: Optional[str]):
        self._selected_id = overlay_id
        enabled = overlay_id is not None
        for w in (self.delete_btn, self.rotation_spin, self.edit_chk):
            w.setEnabled(enabled)
        # reflect rotation + edit toggle from the listed item, if present
        rot = 0
        for i in range(self.overlay_list.count()):
            it = self.overlay_list.item(i)
            if it.data(Qt.UserRole) == overlay_id:
                self.overlay_list.blockSignals(True)
                self.overlay_list.setCurrentRow(i)
                self.overlay_list.blockSignals(False)
                rot = getattr(it, "_rotation", 0)
                break
        self.edit_chk.blockSignals(True)
        self.edit_chk.setChecked(False)
        self.edit_chk.blockSignals(False)
        self.rotation_spin.blockSignals(True)
        self.rotation_spin.setValue(int(rot))
        self.rotation_spin.blockSignals(False)

    def _selected_overlay_id(self) -> Optional[str]:
        it = self.overlay_list.currentItem()
        return it.data(Qt.UserRole) if it is not None else None

    def _on_row_changed(self):
        oid = self._selected_overlay_id()
        if oid is not None:
            self._selected_id = oid
            self.overlaySelected.emit(oid)

    def _on_delete(self):
        if self._selected_id is not None:
            self.deleteRequested.emit(self._selected_id)

    def _on_rotation(self, value: int):
        if self._selected_id is not None:
            self.rotationChanged.emit(self._selected_id, int(value))

    def _on_edit(self, checked: bool):
        if self._selected_id is not None:
            self.editToggled.emit(self._selected_id, bool(checked))
```

For the rotation reflection in `set_selected`, store the rotation on the list item when building. Update `set_page` to stash it: after `item.setData(Qt.UserRole, ov.id)`, add `item._rotation = int(getattr(ov, "rotation", 0) or 0)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_inspector.py -q`
Expected: PASS (3 passed). Then full suite green (expect ~332).

- [ ] **Step 5: Commit**

```bash
git add gui/layout/overlay_inspector.py tests/layout/test_overlay_inspector.py
git commit -m "feat(layout): overlay inspector (list/add/delete/rotation/edit signals)"
```

---

### Task 5: `OverlayEditor` controller — body + tail handles

**Files:**
- Create: `gui/layout/overlay_editor.py`
- Test: `tests/layout/test_overlay_editor.py` (create)

**Interfaces:**
- Consumes: `overlay_ops.nearest_region_center` (Task 3); `LayoutTab.set_refresh_suspended`/`snapshot_and_refresh`/`_current_page`/`canvas` (#5a); `History`.
- Produces: `OverlayEditor(canvas, layout_tab)` with `set_edit_overlay(id|None)`, `rebuild_handles()`, `begin_edit()`, `move_handle(kind, x, y)`, `commit()`, `_find_overlay(id)`; `_OvHandle` (draggable handle, `kind ∈ {"body","tail"}`).

This mirrors #5a `GeometryEditor`: handles are regenerated from the model after every
scene rebuild (`LayoutTab._refresh` calls `rebuild_handles`). The test drives the
controller methods directly (no synthetic Qt mouse events).

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_overlay_editor.py`:

```python
from gui.layout.layout_tab import LayoutTab
from core.layout.models import Region, Overlay


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tab(overlays, regions=None):
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = regions or []
    tab.document.pages[0].overlays = overlays
    tab._refresh()
    return tab


def test_body_handle_only_when_no_tail(qapp):
    tab = _tab([Overlay(id="o", kind="caption", text="x", anchor=(50.0, 50.0))])
    tab.overlay_editor.set_edit_overlay("o")
    kinds = sorted(h._kind for h in tab.overlay_editor._handles)
    assert kinds == ["body"]


def test_body_and_tail_handles_when_tail(qapp):
    tab = _tab([Overlay(id="o", kind="speech", text="x", anchor=(50.0, 50.0),
                        tail_target=(80.0, 90.0))])
    tab.overlay_editor.set_edit_overlay("o")
    kinds = sorted(h._kind for h in tab.overlay_editor._handles)
    assert kinds == ["body", "tail"]


def test_move_body_commits_anchor(qapp):
    tab = _tab([Overlay(id="o", kind="caption", text="x", anchor=(50.0, 50.0))])
    tab.overlay_editor.set_edit_overlay("o")
    before = len(tab.history.snapshots())
    tab.overlay_editor.begin_edit()
    tab.overlay_editor.move_handle("body", 120.0, 130.0)
    tab.overlay_editor.commit()
    assert tab.document.pages[0].overlays[0].anchor == (120.0, 130.0)
    assert len(tab.history.snapshots()) == before + 1


def test_tail_commit_snaps_to_region_center(qapp):
    tab = _tab(
        [Overlay(id="o", kind="speech", text="x", anchor=(50.0, 50.0), tail_target=(60.0, 60.0))],
        regions=[Region(id="r", kind="image", shape="rect", bbox=(200, 200, 100, 100))],
    )
    tab.overlay_editor.set_edit_overlay("o")
    tab.overlay_editor.begin_edit()
    tab.overlay_editor.move_handle("tail", 248.0, 248.0)  # near region center (250,250)
    tab.overlay_editor.commit()
    assert tab.document.pages[0].overlays[0].tail_target == (250.0, 250.0)


def test_edit_off_clears_handles(qapp):
    tab = _tab([Overlay(id="o", kind="caption", text="x", anchor=(50.0, 50.0))])
    tab.overlay_editor.set_edit_overlay("o")
    tab.overlay_editor.set_edit_overlay(None)
    assert tab.overlay_editor._handles == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_editor.py -q`
Expected: FAIL — `AttributeError: 'LayoutTab' object has no attribute 'overlay_editor'` (the editor is wired in Task 6; this task creates the class and a temporary direct instantiation in the test will fail until Task 6 — so this task ALSO adds a minimal `self.overlay_editor = OverlayEditor(self.canvas, self)` in `LayoutTab._build` and a `rebuild_handles()` call in `_refresh`. See Step 3(b).)

- [ ] **Step 3: Create `OverlayEditor` and wire the minimal hooks**

(a) Create `gui/layout/overlay_editor.py`:

```python
"""Manual overlay editor: body/tail drag handles layered on the canvas.

Mirrors GeometryEditor: handles are regenerated from the model after each scene
rebuild (LayoutTab._refresh), not preserved. Move-only. Tail drags snap to the
nearest region center on commit.
"""
from typing import List, Optional

from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem
from PySide6.QtGui import QBrush, QPen, QColor
from PySide6.QtCore import QRectF

_HANDLE_R = 6.0
_SNAP_RADIUS = 40.0  # px: tail snaps to a region center within this distance


class _OvHandle(QGraphicsEllipseItem):
    """A draggable overlay handle. ``kind`` is "body" or "tail"."""

    def __init__(self, editor: "OverlayEditor", kind: str):
        super().__init__()
        self._editor = editor
        self._kind = kind
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

    def mousePressEvent(self, event):
        self._editor.begin_edit()
        super().mousePressEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self._editor.move_handle(self._kind, self.x(), self.y())
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._editor.commit()


class OverlayEditor:
    """Owns body/tail drag handles for one selected overlay on a canvas."""

    def __init__(self, canvas, layout_tab):
        self._canvas = canvas
        self._tab = layout_tab
        self._edit_id: Optional[str] = None
        self._handles: List[_OvHandle] = []
        self._pre = None

    def active_overlay_id(self) -> Optional[str]:
        return self._edit_id

    def set_edit_overlay(self, overlay_id: Optional[str]) -> None:
        self._edit_id = overlay_id or None
        self.rebuild_handles()

    def _find_overlay(self, overlay_id):
        page = self._tab._current_page()
        if page is None or not overlay_id:
            return None
        for ov in page.overlays:
            if ov.id == overlay_id:
                return ov
        return None

    def _clear(self):
        for h in self._handles:
            s = h.scene()
            if s is not None:
                s.removeItem(h)
        self._handles = []

    def rebuild_handles(self) -> None:
        self._clear()
        ov = self._find_overlay(self._edit_id)
        if ov is None:
            self._edit_id = None
            return
        scene = self._canvas.scene()
        if scene is None:
            return
        self._add_handle("body", ov.anchor)
        if ov.tail_target is not None:
            self._add_handle("tail", ov.tail_target)

    def _add_handle(self, kind: str, pos):
        scene = self._canvas.scene()
        h = _OvHandle(self, kind)
        h.setRect(QRectF(-_HANDLE_R, -_HANDLE_R, 2 * _HANDLE_R, 2 * _HANDLE_R))
        h.setPos(pos[0], pos[1])
        h.setZValue(1_000_000)
        h.setBrush(QBrush(QColor("#E84A5F") if kind == "tail" else QColor("#2D7DD2")))
        h.setPen(QPen(QColor("#FFFFFF"), 1.5))
        scene.addItem(h)
        self._handles.append(h)

    def begin_edit(self) -> None:
        ov = self._find_overlay(self._edit_id)
        if ov is None:
            self._pre = None
            return
        self._pre = (ov.anchor, ov.tail_target)
        self._tab.set_refresh_suspended(True)

    def move_handle(self, kind: str, x: float, y: float) -> None:
        ov = self._find_overlay(self._edit_id)
        if ov is None:
            return
        if kind == "body":
            ov.anchor = (x, y)
        elif kind == "tail":
            ov.tail_target = (x, y)

    def commit(self) -> None:
        self._tab.set_refresh_suspended(False)
        ov = self._find_overlay(self._edit_id)
        if ov is None:
            self._pre = None
            return
        # Tail snaps to the nearest region center within the snap radius.
        if ov.tail_target is not None:
            from core.layout.overlay_ops import nearest_region_center
            page = self._tab._current_page()
            regions = list(page.regions) if page is not None else []
            center = nearest_region_center(ov.tail_target, regions)
            if center is not None:
                dx = center[0] - ov.tail_target[0]
                dy = center[1] - ov.tail_target[1]
                if (dx * dx + dy * dy) ** 0.5 <= _SNAP_RADIUS:
                    ov.tail_target = center
        self._pre = None
        self._tab.snapshot_and_refresh(f"edit overlay: {ov.id}")
```

(b) In `gui/layout/layout_tab.py`:
- In `_build`, immediately after the `GeometryEditor` is created (`self.geometry_editor = GeometryEditor(self.canvas, self)`), add:

```python
        from gui.layout.overlay_editor import OverlayEditor
        self.overlay_editor = OverlayEditor(self.canvas, self)
```

- In `_refresh`, in the same guarded block that calls `ge.rebuild_handles()`, also rebuild overlay handles:

```python
            oe = getattr(self, "overlay_editor", None)
            if oe is not None:
                oe.rebuild_handles()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_editor.py -q`
Expected: PASS (5 passed). Then full suite green (expect ~337).

- [ ] **Step 5: Commit**

```bash
git add gui/layout/overlay_editor.py gui/layout/layout_tab.py tests/layout/test_overlay_editor.py
git commit -m "feat(layout): overlay editor body/tail handles with tail-snap commit"
```

---

### Task 6: LayoutTab overlay wiring (add/delete/rotation/select + stranded reposition)

**Files:**
- Modify: `gui/layout/layout_tab.py` (`_build`: create + wire `OverlayInspector`; handlers; `_refresh`: `overlay_inspector.set_page`; `apply_designer_result`: reposition on regions-only)
- Test: `tests/layout/test_overlay_wiring.py` (create)

**Interfaces:**
- Consumes: `OverlayInspector` (Task 4); `OverlayEditor` (Task 5); `overlay_ops.reposition_stranded_overlays` (Task 3); `Overlay`, `OverlayStyle` (`core.layout.models`).
- Produces: `LayoutTab._add_overlay(kind)`, `_delete_overlay(id)`, `_set_overlay_rotation(id, deg)`, `_on_overlay_selected(id)`, `_on_overlay_edit_toggled(id, on)`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_overlay_wiring.py`:

```python
from gui.layout.layout_tab import LayoutTab
from core.layout.models import Region, Overlay


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tab():
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = []
    tab.document.pages[0].overlays = []
    tab._refresh()
    return tab


def test_add_overlay_appends_and_snapshots(qapp):
    tab = _tab()
    before = len(tab.history.snapshots())
    tab._add_overlay("speech")
    ovs = tab.document.pages[0].overlays
    assert len(ovs) == 1 and ovs[0].kind == "speech"
    assert len(tab.history.snapshots()) == before + 1


def test_delete_overlay_removes_and_snapshots(qapp):
    tab = _tab()
    tab._add_overlay("sfx")
    oid = tab.document.pages[0].overlays[0].id
    before = len(tab.history.snapshots())
    tab._delete_overlay(oid)
    assert tab.document.pages[0].overlays == []
    assert len(tab.history.snapshots()) == before + 1


def test_set_overlay_rotation_writes_model(qapp):
    tab = _tab()
    tab._add_overlay("sfx")
    oid = tab.document.pages[0].overlays[0].id
    tab._set_overlay_rotation(oid, 75)
    assert tab.document.pages[0].overlays[0].rotation == 75


def test_apply_designer_regions_only_repositions_overlays(qapp):
    tab = _tab()
    tab.document.pages[0].overlays = [
        Overlay(id="o", kind="sfx", text="x", anchor=(5.0, 5.0))]  # will be stranded

    class R:  # minimal designer result: regions only, no overlays
        regions = [Region(id="r", kind="image", shape="rect", bbox=(200, 200, 100, 100))]
        overlays = []
    tab.apply_designer_result(R())
    assert tab.document.pages[0].overlays[0].anchor == (250.0, 250.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_wiring.py -q`
Expected: FAIL — `AttributeError: 'LayoutTab' object has no attribute '_add_overlay'`.

- [ ] **Step 3: Add handlers + wire the inspector**

In `gui/layout/layout_tab.py`:

(a) In `_build`, after the `OverlayEditor` creation (Task 5), create + wire the inspector (place it near the geometry inspector's `root.addWidget`):

```python
        from gui.layout.overlay_inspector import OverlayInspector
        self.overlay_inspector = OverlayInspector()
        self.overlay_inspector.addRequested.connect(self._add_overlay)
        self.overlay_inspector.deleteRequested.connect(self._delete_overlay)
        self.overlay_inspector.rotationChanged.connect(self._set_overlay_rotation)
        self.overlay_inspector.overlaySelected.connect(self._on_overlay_selected)
        self.overlay_inspector.editToggled.connect(self._on_overlay_edit_toggled)
        root.addWidget(self.overlay_inspector)
```

(b) In `_refresh`, in the guarded editor block, refresh the overlay list:

```python
            oi = getattr(self, "overlay_inspector", None)
            if oi is not None and self.document and self.document.pages:
                oi.set_page(self.document.pages[0])
```

(c) Add the handlers (after the region-op handlers):

```python
    _OVERLAY_DEFAULT_TEXT = {
        "speech": "Dialogue", "thought": "Thinking…",
        "caption": "Caption", "sfx": "POW!",
    }

    def _new_overlay_id(self, page) -> str:
        n = 1
        existing = {o.id for o in page.overlays}
        while f"ov{n}" in existing:
            n += 1
        return f"ov{n}"

    def _add_overlay(self, kind: str) -> bool:
        from core.layout.models import Overlay
        page = self._current_page()
        if page is None or kind not in ("speech", "thought", "caption", "sfx"):
            return False
        pw, ph = page.page_size_px
        cx, cy = pw / 2.0, ph / 2.0
        tail = (cx, cy + 80.0) if kind in ("speech", "thought") else None
        ov = Overlay(id=self._new_overlay_id(page), kind=kind,
                     text=self._OVERLAY_DEFAULT_TEXT.get(kind, ""),
                     anchor=(cx, cy), tail_target=tail)
        page.overlays.append(ov)
        self.snapshot_and_refresh(f"add {kind} overlay")
        self.overlay_inspector.set_selected(ov.id)
        return True

    def _find_overlay(self, overlay_id):
        page = self._current_page()
        if page is None:
            return None
        for ov in page.overlays:
            if ov.id == overlay_id:
                return ov
        return None

    def _delete_overlay(self, overlay_id: str) -> bool:
        page = self._current_page()
        if page is None:
            return False
        for i, ov in enumerate(page.overlays):
            if ov.id == overlay_id:
                if self.overlay_editor.active_overlay_id() == overlay_id:
                    self.overlay_editor.set_edit_overlay(None)
                del page.overlays[i]
                self.snapshot_and_refresh(f"delete overlay: {overlay_id}")
                return True
        return False

    def _set_overlay_rotation(self, overlay_id: str, deg: int) -> bool:
        ov = self._find_overlay(overlay_id)
        if ov is None:
            return False
        ov.rotation = float(deg)
        self.snapshot_and_refresh(f"rotate overlay: {overlay_id}")
        return True

    def _on_overlay_selected(self, overlay_id: str):
        self.overlay_inspector.set_selected(overlay_id)
        self.overlay_editor.set_edit_overlay(None)

    def _on_overlay_edit_toggled(self, overlay_id: str, on: bool):
        self.overlay_editor.set_edit_overlay(overlay_id if on else None)
```

(d) In `apply_designer_result` (~584), the existing structure is:

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
```

Add a `regions-only` reposition: convert the second `if` into an `if/elif` so that when regions were redesigned but overlays were NOT replaced, stranded overlays are tidied. Replace the `if getattr(result, "overlays", None):` block with:

```python
        if getattr(result, "overlays", None):
            self.document.pages[0].overlays = list(result.overlays)
            applied = True
        elif result.regions:
            # Regions-only redesign: tidy overlays stranded over the new panels.
            from core.layout.overlay_ops import reposition_stranded_overlays
            reposition_stranded_overlays(self.document.pages[0])
```

Leave the `if applied: history.append + _refresh` block unchanged (the regions branch already set `applied = True`, so the refresh still runs).

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_wiring.py -q`
Expected: PASS (4 passed). Then full suite green (expect ~341). Confirm `test_layout_tab_designer_overlays.py` still passes (the overlays-replaced path is unchanged).

- [ ] **Step 5: Commit**

```bash
git add gui/layout/layout_tab.py tests/layout/test_overlay_wiring.py
git commit -m "feat(layout): wire overlay inspector + add/delete/rotate + stranded reposition"
```

---

### Task 7: Export fold-in — Qt-path PNG export + retire the PIL bypass

**Files:**
- Modify: `gui/layout/layout_tab.py` (toolbar "Export PNG…" + `export_png_to`)
- Modify: `gui/layout/export_dialog.py` (`LayoutExportWorker._export_png`/`_export_pdf` → Qt renderer)
- Test: `tests/layout/test_export_qt.py` (create)

**Interfaces:**
- Consumes: `qt_renderer.save_page_png`, `qt_renderer.render_page_to_image`, `qt_renderer.export_document_pdf` (`core.layout.qt_renderer`); `dataclasses.replace`.
- Produces: `LayoutTab.export_png_to(path)`; `LayoutExportWorker` renders via the Qt renderer (no `LayoutEngine` for image rendering).

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_export_qt.py`:

```python
import os
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def test_export_png_to_writes_file(qapp, tmp_path):
    tab = LayoutTab(config=FakeConfig())
    out = tmp_path / "page.png"
    tab.export_png_to(str(out))
    assert out.exists() and out.stat().st_size > 0


def test_export_worker_uses_qt_renderer(qapp):
    # The PIL LayoutEngine must no longer be used for image rendering in the worker.
    import inspect
    from gui.layout import export_dialog
    src = inspect.getsource(export_dialog.LayoutExportWorker)
    assert "qt_renderer" in src
    assert "engine.render_page" not in src  # PIL render path removed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_export_qt.py -q`
Expected: FAIL — `AttributeError: 'LayoutTab' object has no attribute 'export_png_to'` and the worker still references `engine.render_page`.

- [ ] **Step 3: Add the Layout-tab PNG export**

In `gui/layout/layout_tab.py`:

(a) Add `export_png_to` (next to `export_pdf_to` ~442):

```python
    def export_png_to(self, path: str):
        if self.document is None or not self.document.pages:
            return
        from core.layout import qt_renderer
        style = self.document.style if self.document else None
        qt_renderer.save_page_png(self.document.pages[0], path, style=style)
        self.status.setText(f"Exported {path}")
```

(b) Add a toolbar button + dialog. In `_build`'s toolbar list, add `("Export PNG…", self._export_png_dialog)` next to the existing `("Export PDF…", self._export_dialog)` entry. Add the dialog method (next to `_export_dialog`):

```python
    def _export_png_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "", "PNG Images (*.png)")
        if path:
            try:
                self.export_png_to(path)
            except Exception as e:  # noqa: BLE001
                self._report_error("export png", e)
```

- [ ] **Step 4: Redirect the PIL worker to the Qt renderer**

In `gui/layout/export_dialog.py`, replace the body of `_export_png` and `_export_pdf` so they render via the Qt renderer instead of `LayoutEngine`.

Replace `_export_png` with:

```python
    def _export_png(self, output_path: Path, pages_to_export: List[int], num_pages: int):
        """Export to PNG sequence via the Qt renderer (comic geometry + overlays)."""
        from core.layout import qt_renderer
        for idx, page_num in enumerate(pages_to_export):
            page = self.document.pages[page_num]
            progress_pct = int((idx / num_pages) * 100)
            self.progress.emit(progress_pct, f"Rendering page {page_num + 1}...")
            image = qt_renderer.render_page_to_image(page, style=self.document.style)
            if num_pages > 1:
                page_output = output_path.parent / f"{output_path.stem}_page{page_num + 1:03d}.png"
            else:
                page_output = output_path
            image.save(str(page_output), "PNG")
            logger.info(f"Exported page {page_num + 1} to {page_output}")
        self.progress.emit(100, "Complete!")
```

Replace `_export_pdf` with (renders the selected pages via the Qt PDF path):

```python
    def _export_pdf(self, output_path: Path, pages_to_export: List[int], num_pages: int):
        """Export to PDF via the Qt renderer (comic geometry + overlays)."""
        from dataclasses import replace
        from core.layout import qt_renderer
        self.progress.emit(0, "Rendering PDF...")
        sub = replace(self.document,
                      pages=[self.document.pages[i] for i in pages_to_export])
        qt_renderer.export_document_pdf(sub, str(output_path), dpi=self.dpi)
        self.progress.emit(100, "Complete!")
```

If `LayoutEngine` is now unused in the file, remove the `from core.layout import LayoutEngine` import (line ~18) to keep the module clean. Leave `_export_json` unchanged.

- [ ] **Step 5: Run tests + commit**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_export_qt.py -q` → PASS (2 passed). Then the FULL suite: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` → all green (expect ~343).

```bash
git add gui/layout/layout_tab.py gui/layout/export_dialog.py tests/layout/test_export_qt.py
git commit -m "feat(layout): Qt-path PNG export + route export dialog through Qt renderer"
```

---

## Notes / deliberately deferred (not gaps)
- **Contour-aware text wrapping** (text follows a non-rect balloon interior) — future polish.
- **Rotation drag handle** — rotation is via the inspector spin in #5c.
- **Multi-overlay select / z-reorder UI** — not in #5c.
- **#5b cleanup Minors** (split id-uniqueness, mid-file test imports, missing annotations) — fold opportunistically if a task touches that code.
- After #5c, the whole comic-layout feature is complete → the single PR is the next step (separate from these tasks).

## Self-Review (completed by plan author)
- **Spec coverage:** rotation field+serialization (Task 1) + render (Task 2); stranded reposition pure (Task 3) + wired into designer-apply (Task 6); overlay inspector place/delete/rotation/select/edit (Task 4) + controller mutation (Task 6); overlay move/tail-snap handles (Task 5); export fold-in PNG + PIL→Qt redirect (Task 7). Every design §4 item maps to a task. Error paths (no regions, missing overlay, malformed rotation) covered in Tasks 3/5/1.
- **Placeholder scan:** no TBD/TODO; every code step shows complete code. Two steps say "read the file first to confirm anchors" (PageSpec kwargs in tests; the apply_designer_result else-branch) — these are verification notes, not placeholders; the code to add is given.
- **Type/name consistency:** `Overlay.rotation` (T1) read by renderer (T2), inspector (T4), wiring (T6); `overlay_ops.*` (T3) consumed by `OverlayEditor.commit` (T5) + `apply_designer_result` (T6); `OverlayInspector` signals (T4) connected in `_build` (T6); `OverlayEditor(canvas, layout_tab)` + `rebuild_handles` (T5) called from `_refresh` (T5 wires the hook); `save_page_png`/`render_page_to_image`/`export_document_pdf` (T7) match real signatures (verified). `_current_page`/`snapshot_and_refresh`/`set_refresh_suspended` reused from #5a.
- **Test interpreter/baseline:** all tasks use `.venv_linux/bin/python` under `QT_QPA_PLATFORM=offscreen`; suite 316 → ~343 (4+3+6+3+5+4+2 = 27 new tests; counts approximate — binding check is "all new tests pass and the full suite stays green").
