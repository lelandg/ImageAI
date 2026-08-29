# Sprite GUI (B): Frames, Preview, Processing, Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Date:** 2026-08-29
**Spec:** `Plans/2026-08-29-sprite-tab-design.md` — §1.4 (undo), §1.5 (shortcuts),
§1.6 (storage + purge), §2 (data model), §4.5 (GUI module table).
**Sub-project:** 5b of 8 — depends on 1 (core spine), 3 (keying), 4 (pixel art),
5a (tab skeleton, workers, prefs); extended by 6 (image route, retouch, engine exports).
**Branch:** `feat/sprite-tab` (already checked out). Commit per task. No version bump.

## Goal

Give the Sprite tab its right-hand working area: a frame strip that edits the
frame list with undo, a preview player with a loop-seam meter, a nearest-neighbor
pixel view with a key-color picker, a processing panel that runs the pipeline
in a worker thread, an export dialog with pluggable formats, and the §1.5
keyboard shortcuts. Every piece is a tested widget that sub-project 6 extends
through two hooks: `FrameStrip.retouchRequested(int)` and
`ExportDialog.register_format(id, label, fn)`.

## Architecture

```
gui/sprite/
  undo_controller.py   UndoController — one SnapshotStack per action id (§1.4)
  pixel_view.py        PixelView(QGraphicsView) — integer zoom, grid, checkerboard, color pick
  preview_player.py    PreviewPlayer(QWidget) — QTimer + QPixmap; modes; tags; seam meter
  frame_strip.py       FrameStrip(QWidget) + FrameOverridesDialog — list edits push snapshots
  ml_install_dialog.py SpriteMLInstallDialog — PackageInstaller for mediapipe / rembg
  processing_panel.py  ProcessingPanel(QWidget) — settings groups, Run pipeline, chroma preview
  export_dialog.py     ExportDialog(DialogCleanupMixin, QDialog) — profiles × formats, purge
  shortcuts.py         install_shortcuts(tab) — §1.5 table
  frames_workspace.py  FramesWorkspace(QObject) — builds the widgets, wires them into SpriteTab
```

Data flow:

```
SpriteTab.projectChanged / actionSelected(id)
   └─ FramesWorkspace._set_action(action)
        ├─ FrameStrip.set_frames(action.frames)      edits → action.frames, snapshot first
        ├─ PreviewPlayer.set_frames(...)             source combo: cells | hd | pixel
        ├─ ProcessingPanel.set_action(action)        Run pipeline → SpriteWorker(run_pipeline)
        └─ UndoController.set_active(action.id)      Ctrl+Z / Ctrl+Y → FramesWorkspace.undo/redo
ProcessingPanel.pipelineFinished(id) → strip + player reload from action.frames
ProcessingPanel.exportRequested → ExportDialog(project) → SpriteWorker(run_export) → purge (opt-in)
```

Threading: every pipeline run, chroma preview, palette rebuild, ffprobe, and export
runs inside a `SpriteWorker` (sub-project 5a). The UI thread decodes at most one
frame per paint and never imports PIL or calls ffmpeg.

## Tech Stack

- PySide6 6.11 (QGraphicsView, QListWidget IconMode, QTimer, QShortcut, QSettings)
- numpy (seam meter on QImage buffers)
- `core.sprite.*` from sub-projects 1, 3, 4 (pure Python)
- `gui.common.dialog_conventions` (`bind_primary_action`, `DialogCleanupMixin`,
  `set_default_button`, `standard_splitter`, `persist_splitter`, `restore_splitter`)
- `gui.llm_utils.DialogStatusConsole`
- `core.package_installer.PackageInstaller`

## Global Constraints

- Repo root: `/mnt/d/Documents/Code/GitHub/ImageAI`. Never `cd`; use absolute paths and
  `git -C /mnt/d/Documents/Code/GitHub/ImageAI …`.
- `PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python`.
- GUI tests: `QT_QPA_PLATFORM=offscreen $PY -m pytest <path> -v` (session `qapp` fixture from
  `tests/conftest.py`; QSettings and data paths are sandboxed there).
- Primary action = Ctrl+Enter via `bind_primary_action`. Embedded panels bind with
  `context=Qt.WidgetWithChildrenShortcut` so two panels in one window never make the
  shortcut ambiguous. Dialogs use `DialogCleanupMixin` (Escape = reject).
- No `QMovie`. Playback = `QTimer` + `QPixmap`.
- Every zoomed render uses `Qt.FastTransformation`; never `SmoothPixmapTransform`.
- Images scale proportionally (`Qt.KeepAspectRatio`); never cropped or distorted.
- No hand-built data paths. Project-relative paths derive from `project.project_dir`
  or `get_data_paths()`; `tests/test_no_hardcoded_paths.py` must stay green.
- QSettings: one store, `prefs.sprite_settings()` (= `QSettings("ImageAI", "Sprite")`); read and
  write keys through `prefs.get_pref` / `prefs.set_pref` under `sprite/…`; splitters persist
  with `persist_splitter(prefs.sprite_settings(), key, splitter)`.
- Every user-facing error is logged (`logger.error`) AND shown (`QMessageBox` or console).
- Conventional Commits; one commit per task; no version bump (docs/plans rule applies
  to the PR gate in sub-project 7).
- Prose and docstrings: Simplified Technical English style.

## Cross-plan contract (assumed from sub-projects 1, 3, 4, 5a)

| Symbol | Module | Signature used here |
|---|---|---|
| `FrameMeta`, `TagMeta`, `SheetMeta` | `core/sprite/models.py` | design §2 |
| `SpriteProject`, `ActionCard`, `OutputProfile`, `KeySettings`, `StabilizeSettings`, `ExtractionSettings` | `core/sprite/project.py` | design §2; `SpriteProject(name, project_dir, character_source, plate_path)` constructs with defaults for the rest |
| `FrameListSnapshot`, `SnapshotStack` | `core/sprite/undo.py` | design §1.4; `SnapshotStack(depth=50)` with `push`, `undo(current)`, `redo()`, `can_undo`, `can_redo`, `clear()` (confirmed in the core plan) |
| `CancelToken`, `ProgressFn`, `no_progress`, `run_pipeline`, `stage_dir` | `core/sprite/pipeline.py` | design §1.1, §4.1 |
| `probe_video`, `estimate_frame_count` | `core/sprite/extract.py` | design §4.1; probe keys `fps`, `nb_frames`, `duration`, `width`, `height`, `source` (confirmed) |
| `CELL_PRESETS: Tuple[Tuple[str, Size], ...]`, `CUSTOM_CELL_LABEL = "Custom…"` | `core/sprite/presets.py` | `(label, (w, h))` in display order (confirmed in the core plan) |
| `OutputProfile.upscale_small: bool`, `stages/<id>/pixel/pixel.json` (`warnings` key) | `core/sprite/project.py`, pixel stage | sub-project 4 (orchestrator decision 2026-08-29); the panel reads the field with `getattr(..., False)` until it lands |
| `GridOptions`, `export_grid` | `core/sprite/exporters/grid.py` | design §4.1 |
| `export_aseprite_json`, `export_texturepacker_json`, `export_png_sequence`, `export_single_frame`, `export_gif` | `core/sprite/exporters/*` | design §4.1 |
| `ffmpeg_chromakey_preview`, `pick_key_color` | `core/sprite/keying.py` | design §4.3 |
| `available_backends`, `REMBG_MODELS` | `core/sprite/matting.py` | design §4.3 |
| `sprite_ml_packages() -> Tuple[List[str], str]` (`(packages, index_url)`), `python_supports_rembg() -> bool` | `core/sprite/ml_install.py` | sub-project 3 (confirmed in the keying plan, Task 10) |
| `FLOYD_WARNING: str`, `rebuild_palette(project, profile, frames: Sequence[PIL.Image.Image]) -> List[str]` | `core/sprite/pixelart.py` | sub-project 4 (confirmed in the pixel-art plan, Task 6) |
| `SpriteTab(config, parent=None)` | `gui/sprite/sprite_tab.py` | confirmed in the 5a plan, Task 8: hooks `set_frame_widget(w)`, `set_preview_widget(w)`, `set_processing_widget(w)`; `current_project` (property), `current_action()`, signals `projectChanged()` and `actionSelected(str)` (`""` when nothing is selected); `add_toolbar_action(text, slot) -> QPushButton`; `log(message, level="INFO")`; `console`, `action_cards_panel`, `queue_panel` (`statusChanged()`), `shutdown()` |
| `WorkerHost` mixin | `gui/sprite/workers.py` | `start_job(job, *, label, on_finished, on_failed, on_cancelled=None, on_progress=None) -> Optional[SpriteWorker]` (None while busy), `is_busy()`, `cancel_running()`, `shutdown(timeout_ms=5000)`; used by `ProcessingPanel` and `ExportDialog` |
| `SpriteWorker(job, *, label="job", parent=None)` | `gui/sprite/workers.py` | `job(progress, token)`; signals `progress(str,int,int,str)`, `finished(object)`, `failed(str)`, `cancelled()`; `cancel()` (confirmed in the 5a plan, Task 1) |
| `sprite_settings() -> QSettings("ImageAI", "Sprite")`, `get_pref(key, default=None)`, `set_pref(key, value)`, `purge_after_export_enabled`, `set_purge_after_export`, `confirm_purge` | `gui/sprite/prefs.py` | sub-project 5a (confirmed, Task 3); every 5b QSettings key goes through `get_pref`/`set_pref` under `sprite/…` |
| **Consumed by sub-project 6** | this plan | `ExportDialog.{register_format(id, label, fn(meta, out_dir)), format_checks, set_grid_options, pivot_x_spin, pivot_y_spin, name_template_edit, options_layout, current_meta()}`; `FrameStrip.retouchRequested(int)`; `PixelView.selection_rect()`; `SpriteTab.{undo_stack, frame_strip, pixel_view, refresh_frames()}`; format ids `grid`, `aseprite_json`, `texturepacker_json`, `png_sequence`, `gif` (its `FORMAT_IDS`) |

If a name differs when this plan runs, change the import line and record the
change under "Deviations from the design" at the end of this file.

## File Structure

| Path | Kind | Responsibility |
|---|---|---|
| `gui/sprite/undo_controller.py` | new | `UndoController` — per-action `SnapshotStack`, `stateChanged(bool, bool)` |
| `gui/sprite/pixel_view.py` | new | `PixelView`, `checkerboard_brush`, `qimage_to_rgba` |
| `gui/sprite/preview_player.py` | new | `PreviewPlayer`, `next_index`, `loop_seam_score`, `seam_level` |
| `gui/sprite/frame_strip.py` | new | `FrameStrip`, `FrameOverridesDialog`, `sanitize_frame_name`, `unique_name` |
| `gui/sprite/ml_install_dialog.py` | new | `SpriteMLInstallDialog` |
| `gui/sprite/processing_panel.py` | new | `ProcessingPanel`, `ProfileEditor` |
| `gui/sprite/export_dialog.py` | new | `ExportDialog`, `ExportRequest`, `ExportFormat`, `FormatFn`, `run_export`, `BUILTIN_FORMATS`, `sheet_png_path`, `parse_scales`, `default_export_dir` |
| `gui/sprite/shortcuts.py` | new | `SHORTCUT_TABLE`, `install_shortcuts`, `resolve_target` |
| `gui/sprite/frames_workspace.py` | new | `FramesWorkspace` |
| `gui/sprite/sprite_tab.py` | modified | two lines: construct `FramesWorkspace(self)` at the end of `__init__` |
| `tests/sprite/gui/gui_synthetic.py` | new | synthetic frames / project helpers (no binary fixtures) |
| `tests/sprite/gui/test_undo_controller.py` | new | Task 1 |
| `tests/sprite/gui/test_pixel_view.py` | new | Task 2 |
| `tests/sprite/gui/test_preview_player.py` | new | Task 3 |
| `tests/sprite/gui/test_frame_strip.py` | new | Task 4 |
| `tests/sprite/gui/test_ml_install_dialog.py` | new | Task 5 |
| `tests/sprite/gui/test_processing_panel.py` | new | Task 6 |
| `tests/sprite/gui/test_export_dialog.py` | new | Task 7 |
| `tests/sprite/gui/test_shortcuts.py` | new | Task 8 |
| `tests/sprite/gui/test_sprite_tab_integration.py` | new | Task 9 |

---

### Task 1: Test helpers + `UndoController`

**Files:**
- Create: `tests/sprite/gui/gui_synthetic.py`
- Create: `tests/sprite/gui/test_undo_controller.py`
- Create: `gui/sprite/undo_controller.py`

**Interfaces:**
- Consumes: `core.sprite.models.FrameMeta`, `core.sprite.undo.FrameListSnapshot`,
  `core.sprite.undo.SnapshotStack`.
- Produces: `UndoController(QObject)`:
  - `stateChanged = Signal(bool, bool)` — `(can_undo, can_redo)` for the action just touched
  - `__init__(self, depth: int = 50, parent=None)`
  - `stack(self, action_id: str) -> SnapshotStack`
  - `set_active(self, action_id: Optional[str]) -> None`; property `active_action`
  - `can_undo(self, action_id: Optional[str] = None) -> bool`; `can_redo(...)`
  - `snapshot(self, action_id: str, frames: Sequence[FrameMeta], label: str) -> FrameListSnapshot`
  - `undo(self, action_id: str, current: Sequence[FrameMeta]) -> Optional[List[FrameMeta]]`
  - `redo(self, action_id: str) -> Optional[List[FrameMeta]]`
  - `clear(self, action_id: str) -> None`

**Steps:**

- [ ] Write the shared synthetic helper `tests/sprite/gui/gui_synthetic.py`:

```python
"""Synthetic frames and projects for the sprite GUI tests (no binary fixtures)."""
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtGui import QColor, QImage

from core.sprite.models import FrameMeta, SheetMeta, TagMeta
from core.sprite.project import ActionCard, SpriteProject


def write_frame_png(path: Path, size: Tuple[int, int] = (8, 8),
                    color: Tuple[int, int, int, int] = (255, 0, 0, 255),
                    dot: Optional[Tuple[int, int]] = None) -> Path:
    """Write a flat RGBA PNG; `dot` marks one blue pixel so frames differ."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(size[0], size[1], QImage.Format_RGBA8888)
    image.fill(QColor(*color))
    if dot is not None:
        image.setPixelColor(dot[0], dot[1], QColor(0, 0, 255, 255))
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"cannot write {path}")
    return path


def make_frames(root: Path, n: int = 4, size: Tuple[int, int] = (8, 8),
                duration_ms: int = 100) -> List[FrameMeta]:
    frames: List[FrameMeta] = []
    for i in range(n):
        path = write_frame_png(root / f"{i:04d}.png", size=size, dot=(i % size[0], 0))
        frames.append(FrameMeta(
            name=f"frame_{i:02d}",
            source_path=path,
            frame=(0, 0, size[0], size[1]),
            source_size=size,
            sprite_source_size=(0, 0, size[0], size[1]),
            duration_ms=duration_ms,
        ))
    return frames


def make_project(root: Path, n_frames: int = 4) -> Tuple[SpriteProject, ActionCard]:
    project = SpriteProject(name="test_sprite", project_dir=root,
                            character_source=None, plate_path=None)
    action = ActionCard(id="act1", name="walk", prompt="walk cycle")
    action.frames = make_frames(root / "stages" / action.id / "stabilize", n_frames)
    project.actions.append(action)
    return project, action


def sheet_from_action(action: ActionCard, profile: str = "hd") -> SheetMeta:
    n = len(action.frames)
    return SheetMeta(
        title=action.name,
        frames=list(action.frames),
        tags=[TagMeta(name=action.name, from_index=0, to_index=max(0, n - 1))],
        cell_size=(8, 8),
        profile=profile,
    )
```

- [ ] Write the failing test `tests/sprite/gui/test_undo_controller.py`:

```python
from pathlib import Path

from gui.sprite.undo_controller import UndoController
from gui_synthetic import make_frames


def test_snapshot_then_undo_returns_previous_list(qapp, tmp_path):
    frames = make_frames(tmp_path, 3)
    ctl = UndoController()
    states = []
    ctl.stateChanged.connect(lambda u, r: states.append((u, r)))

    ctl.snapshot("a", frames, "delete frame 2")
    assert ctl.can_undo("a") and not ctl.can_redo("a")
    assert states[-1] == (True, False)

    edited = frames[:2]
    restored = ctl.undo("a", edited)
    assert restored is not None
    assert [f.name for f in restored] == [f.name for f in frames]
    assert ctl.can_redo("a")


def test_undo_returns_deep_copies(qapp, tmp_path):
    frames = make_frames(tmp_path, 2)
    ctl = UndoController()
    ctl.snapshot("a", frames, "x")
    restored = ctl.undo("a", frames)
    restored[0].duration_ms = 999
    assert frames[0].duration_ms == 100  # the original list is untouched


def test_redo_restores_edited_list(qapp, tmp_path):
    frames = make_frames(tmp_path, 3)
    ctl = UndoController()
    ctl.snapshot("a", frames, "delete")
    edited = frames[:2]
    ctl.undo("a", edited)
    again = ctl.redo("a")
    assert again is not None
    assert [f.name for f in again] == [f.name for f in edited]


def test_stacks_are_per_action(qapp, tmp_path):
    frames = make_frames(tmp_path, 2)
    ctl = UndoController()
    ctl.snapshot("a", frames, "x")
    assert ctl.can_undo("a")
    assert not ctl.can_undo("b")
    assert ctl.undo("b", frames) is None


def test_set_active_emits_state_for_that_action(qapp, tmp_path):
    frames = make_frames(tmp_path, 2)
    ctl = UndoController()
    ctl.snapshot("a", frames, "x")
    states = []
    ctl.stateChanged.connect(lambda u, r: states.append((u, r)))
    ctl.set_active("b")
    assert states[-1] == (False, False)
    ctl.set_active("a")
    assert states[-1] == (True, False)
    assert ctl.active_action == "a"


def test_clear_drops_history(qapp, tmp_path):
    frames = make_frames(tmp_path, 2)
    ctl = UndoController()
    ctl.snapshot("a", frames, "x")
    ctl.clear("a")
    assert not ctl.can_undo("a") and not ctl.can_redo("a")
```

- [ ] Run: `QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_undo_controller.py -v` → fails with `ModuleNotFoundError: gui.sprite.undo_controller`.

- [ ] Implement `gui/sprite/undo_controller.py`:

```python
"""Per-action undo/redo for the sprite frame list (design §1.4).

The pipeline is non-destructive, so only list edits enter the stack: delete,
reorder, duplicate, insert, duration edit, override edit, retouch. Each edit
pushes a deep copy of the list *before* the change.
"""
from __future__ import annotations

import copy
import logging
from typing import Dict, List, Optional, Sequence

from PySide6.QtCore import QObject, Signal

from core.sprite.models import FrameMeta
from core.sprite.undo import FrameListSnapshot, SnapshotStack

logger = logging.getLogger(__name__)


class UndoController(QObject):
    """One `SnapshotStack` per action id; emits `stateChanged(can_undo, can_redo)`."""

    stateChanged = Signal(bool, bool)

    def __init__(self, depth: int = 50, parent=None):
        super().__init__(parent)
        self._depth = depth
        self._stacks: Dict[str, SnapshotStack] = {}
        self._active: Optional[str] = None

    # ----- stacks -----------------------------------------------------
    def stack(self, action_id: str) -> SnapshotStack:
        stack = self._stacks.get(action_id)
        if stack is None:
            stack = SnapshotStack(depth=self._depth)
            self._stacks[action_id] = stack
        return stack

    @property
    def active_action(self) -> Optional[str]:
        return self._active

    def set_active(self, action_id: Optional[str]) -> None:
        self._active = action_id
        self._emit_state(action_id)

    def can_undo(self, action_id: Optional[str] = None) -> bool:
        action_id = action_id or self._active
        return bool(action_id) and self.stack(action_id).can_undo

    def can_redo(self, action_id: Optional[str] = None) -> bool:
        action_id = action_id or self._active
        return bool(action_id) and self.stack(action_id).can_redo

    def clear(self, action_id: str) -> None:
        self._stacks[action_id] = SnapshotStack(depth=self._depth)
        self._emit_state(action_id)

    # ----- operations -------------------------------------------------
    def snapshot(self, action_id: str, frames: Sequence[FrameMeta], label: str) -> FrameListSnapshot:
        snap = FrameListSnapshot(action_id=action_id, frames=self._copy(frames), label=label)
        self.stack(action_id).push(snap)
        logger.debug("Sprite undo: snapshot '%s' for action %s (%d frames)",
                     label, action_id, len(snap.frames))
        self._emit_state(action_id)
        return snap

    def undo(self, action_id: str, current: Sequence[FrameMeta]) -> Optional[List[FrameMeta]]:
        stack = self.stack(action_id)
        if not stack.can_undo:
            return None
        now = FrameListSnapshot(action_id=action_id, frames=self._copy(current), label="current")
        snap = stack.undo(now)
        self._emit_state(action_id)
        if snap is None:
            return None
        logger.info("Sprite undo: '%s' (action %s)", snap.label, action_id)
        return list(self._copy(snap.frames))

    def redo(self, action_id: str) -> Optional[List[FrameMeta]]:
        stack = self.stack(action_id)
        if not stack.can_redo:
            return None
        snap = stack.redo()
        self._emit_state(action_id)
        if snap is None:
            return None
        logger.info("Sprite redo: '%s' (action %s)", snap.label, action_id)
        return list(self._copy(snap.frames))

    # ----- internals --------------------------------------------------
    @staticmethod
    def _copy(frames: Sequence[FrameMeta]):
        return tuple(copy.deepcopy(list(frames)))

    def _emit_state(self, action_id: Optional[str]) -> None:
        if not action_id:
            self.stateChanged.emit(False, False)
            return
        stack = self.stack(action_id)
        self.stateChanged.emit(stack.can_undo, stack.can_redo)
```

- [ ] Run the test file again → 6 passed.
- [ ] Commit:

```
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/undo_controller.py tests/sprite/gui/gui_synthetic.py tests/sprite/gui/test_undo_controller.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): UndoController with per-action snapshot stacks"
```

---

### Task 2: `PixelView`

**Files:**
- Create: `tests/sprite/gui/test_pixel_view.py`
- Create: `gui/sprite/pixel_view.py`

**Interfaces:**
- Consumes: PySide6 only.
- Produces:
  - `checkerboard_brush(size: int = 8, light: str = "#c8c8c8", dark: str = "#8c8c8c") -> QBrush`
  - `qimage_to_rgba(image: QImage) -> np.ndarray` (h, w, 4) uint8
  - `PixelView(QGraphicsView)`:
    - `colorPicked = Signal(str)` (`"#RRGGBB"`), `zoomChanged = Signal(int)`, `gridToggled = Signal(bool)`
    - `set_image(self, source: Union[Path, str, QImage, QPixmap, None]) -> bool`; `image() -> Optional[QImage]`
    - `zoom() -> int`; `set_zoom(int)`; `zoom_in()`; `zoom_out()`; `zoom_reset()`; `fit_zoom() -> int`
    - `grid_visible() -> bool`; `set_grid_visible(bool)`; `toggle_grid() -> bool`
    - `pick_mode() -> bool`; `set_pick_mode(bool)`; `color_at(x: int, y: int) -> Optional[str]`
    - `select_mode() -> bool`; `set_select_mode(bool)`; `selection_rect() -> Optional[Rect]` (image
      pixels `(x, y, w, h)`; sub-project 6 reads it for region retouch); `set_selection_rect(Optional[Rect])`;
      `clear_selection()`; `selectionChanged = Signal(object)`
  - Constants: `MIN_ZOOM = 1`, `MAX_ZOOM = 16`, `GRID_MIN_ZOOM = 4`, `ZOOM_STEPS = (1, 2, 3, 4, 6, 8, 12, 16)`,
    `Rect = Tuple[int, int, int, int]`

**Steps:**

- [ ] Write the failing test `tests/sprite/gui/test_pixel_view.py`:

```python
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest

from gui.sprite.pixel_view import (MAX_ZOOM, MIN_ZOOM, PixelView, checkerboard_brush,
                                   qimage_to_rgba)
from gui_synthetic import write_frame_png


def _image():
    image = QImage(4, 4, QImage.Format_RGBA8888)
    image.fill(QColor(0, 255, 0, 255))
    image.setPixelColor(1, 1, QColor(255, 0, 0, 255))
    return image


def test_set_image_from_path_and_qimage(qapp, tmp_path):
    view = PixelView()
    assert view.set_image(_image())
    assert view.image().width() == 4
    path = write_frame_png(tmp_path / "f.png", size=(6, 3))
    assert view.set_image(path)
    assert (view.image().width(), view.image().height()) == (6, 3)
    assert view.set_image(tmp_path / "missing.png") is False  # logged, previous image kept
    assert view.image().width() == 6


def test_zoom_is_integer_and_clamped(qapp):
    view = PixelView()
    view.set_image(_image())
    seen = []
    view.zoomChanged.connect(seen.append)
    view.set_zoom(4)
    assert view.zoom() == 4
    assert view.transform().m11() == 4 and view.transform().m22() == 4
    view.set_zoom(99)
    assert view.zoom() == MAX_ZOOM
    view.set_zoom(0)
    assert view.zoom() == MIN_ZOOM
    assert seen == [4, MAX_ZOOM, MIN_ZOOM]


def test_zoom_in_out_follow_steps(qapp):
    view = PixelView()
    view.set_image(_image())
    view.zoom_in()
    view.zoom_in()
    assert view.zoom() == 3
    view.zoom_out()
    assert view.zoom() == 2
    view.zoom_reset()
    assert view.zoom() == 1
    view.set_zoom(5)          # between steps
    view.zoom_in()
    assert view.zoom() == 6   # next step up
    view.zoom_out()
    assert view.zoom() == 4   # next step down


def test_pixmap_item_uses_nearest_neighbor(qapp):
    from PySide6.QtGui import QPainter
    view = PixelView()
    view.set_image(_image())
    assert view._item.transformationMode() == Qt.FastTransformation
    assert not (view.renderHints() & QPainter.SmoothPixmapTransform)


def test_grid_toggle(qapp):
    view = PixelView()
    got = []
    view.gridToggled.connect(got.append)
    assert view.grid_visible() is True
    assert view.toggle_grid() is False
    assert view.grid_visible() is False
    assert got == [False]


def test_color_at_returns_hex_or_none(qapp):
    view = PixelView()
    view.set_image(_image())
    assert view.color_at(1, 1) == "#FF0000"
    assert view.color_at(0, 0) == "#00FF00"
    assert view.color_at(4, 0) is None
    assert view.color_at(-1, 0) is None


def test_click_in_pick_mode_emits_color_and_leaves_pick_mode(qapp):
    view = PixelView()
    view.resize(160, 160)
    view.show()
    view.set_image(_image())
    view.set_zoom(8)
    qapp.processEvents()
    view.set_pick_mode(True)
    got = []
    view.colorPicked.connect(got.append)
    pos = view.mapFromScene(QPointF(1.5, 1.5))
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier, pos)
    assert got == ["#FF0000"]
    assert view.pick_mode() is False


def test_drag_in_select_mode_sets_selection_rect(qapp):
    view = PixelView()
    view.resize(160, 160)
    view.show()
    view.set_image(_image())
    view.set_zoom(8)
    qapp.processEvents()
    view.set_select_mode(True)
    got = []
    view.selectionChanged.connect(got.append)
    start = view.mapFromScene(QPointF(0.5, 0.5))
    end = view.mapFromScene(QPointF(2.5, 3.5))
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier, end)
    assert view.selection_rect() == (0, 0, 3, 4)
    assert got[-1] == (0, 0, 3, 4)
    assert view.select_mode() is False
    view.clear_selection()
    assert view.selection_rect() is None
    assert got[-1] is None
    view.set_selection_rect((1, 1, 9, 9))  # clamped to the 4×4 image
    assert view.selection_rect() == (1, 1, 3, 3)
    view.set_selection_rect((7, 7, 2, 2))  # fully outside → cleared
    assert view.selection_rect() is None


def test_qimage_to_rgba_shape_and_values(qapp):
    arr = qimage_to_rgba(_image())
    assert arr.shape == (4, 4, 4)
    assert tuple(arr[1, 1]) == (255, 0, 0, 255)
    assert tuple(arr[0, 0]) == (0, 255, 0, 255)


def test_checkerboard_brush_is_textured(qapp):
    brush = checkerboard_brush(4)
    assert brush.style() == Qt.TexturePattern
    assert brush.texture().width() == 8
```

- [ ] Run → fails on import.

- [ ] Implement `gui/sprite/pixel_view.py`:

```python
"""Nearest-neighbor zoom view for one sprite frame (design §4.5).

Integer zoom 1–16×, a pixel grid at zoom ≥ 4, a fixed-size checkerboard behind
the transparent areas, and a click-to-pick mode for the key color.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

logger = logging.getLogger(__name__)

MIN_ZOOM = 1
MAX_ZOOM = 16
GRID_MIN_ZOOM = 4
ZOOM_STEPS = (1, 2, 3, 4, 6, 8, 12, 16)
CHECKER_SIZE = 8
Rect = Tuple[int, int, int, int]   # x, y, w, h in image pixels (same shape as core.sprite.models.Rect)


def checkerboard_brush(size: int = CHECKER_SIZE, light: str = "#c8c8c8",
                       dark: str = "#8c8c8c") -> QBrush:
    """A 2×2 checker tile brush; drawn in device pixels so it never zooms."""
    tile = QPixmap(size * 2, size * 2)
    tile.fill(QColor(light))
    painter = QPainter(tile)
    painter.fillRect(0, 0, size, size, QColor(dark))
    painter.fillRect(size, size, size, size, QColor(dark))
    painter.end()
    return QBrush(tile)


def qimage_to_rgba(image: QImage) -> np.ndarray:
    """Copy a QImage into an (h, w, 4) uint8 RGBA array."""
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    width, height = converted.width(), converted.height()
    stride = converted.bytesPerLine()
    buffer = bytes(converted.constBits())
    rows = np.frombuffer(buffer, dtype=np.uint8)[: stride * height].reshape(height, stride)
    return rows[:, : width * 4].reshape(height, width, 4).copy()


class PixelView(QGraphicsView):
    """QGraphicsView that shows one image with integer nearest-neighbor zoom."""

    colorPicked = Signal(str)
    zoomChanged = Signal(int)
    gridToggled = Signal(bool)
    selectionChanged = Signal(object)   # Optional[Rect]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._item = QGraphicsPixmapItem()
        self._item.setTransformationMode(Qt.FastTransformation)
        self._scene.addItem(self._item)
        self._image: Optional[QImage] = None
        self._zoom = 1
        self._grid = True
        self._pick_mode = False
        self._select_mode = False
        self._selection: Optional[Rect] = None
        self._drag_start: Optional[Tuple[int, int]] = None
        self._checker = checkerboard_brush()

        self.setRenderHint(QPainter.Antialiasing, False)
        self.setRenderHint(QPainter.SmoothPixmapTransform, False)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setAlignment(Qt.AlignCenter)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)

    # ----- image ------------------------------------------------------
    def set_image(self, source: Union[Path, str, QImage, QPixmap, None]) -> bool:
        """Show `source`. Returns False (and keeps the old image) when a file fails to decode."""
        if source is None:
            image = None
        elif isinstance(source, QImage):
            image = source
        elif isinstance(source, QPixmap):
            image = source.toImage()
        else:
            image = QImage(str(source))
            if image.isNull():
                logger.error("PixelView: cannot decode image %s", source)
                return False
        self._image = image
        if image is None:
            self._item.setPixmap(QPixmap())
            self._scene.setSceneRect(QRectF())
        else:
            self._item.setPixmap(QPixmap.fromImage(image))
            self._scene.setSceneRect(QRectF(0, 0, image.width(), image.height()))
        self.viewport().update()
        return True

    def image(self) -> Optional[QImage]:
        return self._image

    # ----- zoom -------------------------------------------------------
    def zoom(self) -> int:
        return self._zoom

    def set_zoom(self, zoom: int) -> None:
        zoom = max(MIN_ZOOM, min(MAX_ZOOM, int(zoom)))
        self._zoom = zoom
        self.resetTransform()
        self.scale(zoom, zoom)
        self.zoomChanged.emit(zoom)
        self.viewport().update()

    def zoom_in(self) -> None:
        self.set_zoom(next((z for z in ZOOM_STEPS if z > self._zoom), MAX_ZOOM))

    def zoom_out(self) -> None:
        self.set_zoom(next((z for z in reversed(ZOOM_STEPS) if z < self._zoom), MIN_ZOOM))

    def zoom_reset(self) -> None:
        self.set_zoom(MIN_ZOOM)

    def fit_zoom(self) -> int:
        """Largest integer zoom that keeps the whole image inside the viewport."""
        if self._image is None or self._image.width() == 0 or self._image.height() == 0:
            return self._zoom
        vw, vh = self.viewport().width(), self.viewport().height()
        zoom = min(vw // self._image.width(), vh // self._image.height())
        self.set_zoom(max(MIN_ZOOM, min(MAX_ZOOM, zoom)))
        return self._zoom

    # ----- grid -------------------------------------------------------
    def grid_visible(self) -> bool:
        return self._grid

    def set_grid_visible(self, visible: bool) -> None:
        self._grid = bool(visible)
        self.gridToggled.emit(self._grid)
        self.viewport().update()

    def toggle_grid(self) -> bool:
        self.set_grid_visible(not self._grid)
        return self._grid

    # ----- picking ----------------------------------------------------
    def pick_mode(self) -> bool:
        return self._pick_mode

    def set_pick_mode(self, enabled: bool) -> None:
        self._pick_mode = bool(enabled)
        if self._pick_mode:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.viewport().unsetCursor()

    def color_at(self, x: int, y: int) -> Optional[str]:
        """Hex color of the image pixel at (x, y), or None outside the image."""
        if self._image is None:
            return None
        if not (0 <= x < self._image.width() and 0 <= y < self._image.height()):
            return None
        return self._image.pixelColor(x, y).name(QColor.HexRgb).upper()

    # ----- region selection (sub-project 6 retouch reads it) ----------
    def select_mode(self) -> bool:
        return self._select_mode

    def set_select_mode(self, enabled: bool) -> None:
        self._select_mode = bool(enabled)
        self._drag_start = None
        if self._select_mode:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)
        elif not self._pick_mode:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.viewport().unsetCursor()

    def selection_rect(self) -> Optional[Rect]:
        return self._selection

    def set_selection_rect(self, rect: Optional[Rect]) -> None:
        """Store `rect` clamped to the image; an empty or outside rect clears the selection."""
        clamped: Optional[Rect] = None
        if rect is not None and self._image is not None:
            x, y, w, h = (int(v) for v in rect)
            x0, y0 = max(0, x), max(0, y)
            x1 = min(self._image.width(), x + w)
            y1 = min(self._image.height(), y + h)
            if x1 > x0 and y1 > y0:
                clamped = (x0, y0, x1 - x0, y1 - y0)
        self._selection = clamped
        self.selectionChanged.emit(clamped)
        self.viewport().update()

    def clear_selection(self) -> None:
        self.set_selection_rect(None)

    def _scene_pixel(self, event) -> Tuple[int, int]:
        point = self.mapToScene(event.position().toPoint())
        return int(point.x()) if point.x() >= 0 else -1, int(point.y()) if point.y() >= 0 else -1

    # ----- events -----------------------------------------------------
    def mousePressEvent(self, event):
        if self._pick_mode and event.button() == Qt.LeftButton:
            x, y = self._scene_pixel(event)
            color = self.color_at(x, y)
            self.set_pick_mode(False)
            if color is not None:
                logger.info("PixelView: picked color %s at (%d, %d)", color, x, y)
                self.colorPicked.emit(color)
            event.accept()
            return
        if self._select_mode and event.button() == Qt.LeftButton:
            self._drag_start = self._scene_pixel(event)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._select_mode and self._drag_start is not None:
            self._selection = self._rect_between(self._drag_start, self._scene_pixel(event))
            self.viewport().update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._select_mode and self._drag_start is not None and event.button() == Qt.LeftButton:
            rect = self._rect_between(self._drag_start, self._scene_pixel(event))
            self._drag_start = None
            self.set_select_mode(False)
            self.set_selection_rect(rect)
            logger.info("PixelView: selected region %s", rect)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _rect_between(self, a: Tuple[int, int], b: Tuple[int, int]) -> Optional[Rect]:
        if self._image is None:
            return None
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.save()
        painter.resetTransform()
        painter.fillRect(self.viewport().rect(), self._checker)
        painter.restore()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        self._draw_selection(painter)
        if not self._grid or self._zoom < GRID_MIN_ZOOM or self._image is None:
            return
        width, height = self._image.width(), self._image.height()
        area = rect.intersected(QRectF(0, 0, width, height))
        if area.isEmpty():
            return
        pen = QPen(QColor(0, 0, 0, 90))
        pen.setCosmetic(True)
        pen.setWidth(1)
        painter.setPen(pen)
        for x in range(int(area.left()), min(int(area.right()) + 1, width) + 1):
            painter.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
        for y in range(int(area.top()), min(int(area.bottom()) + 1, height) + 1):
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))

    def _draw_selection(self, painter: QPainter) -> None:
        if self._selection is None:
            return
        x, y, w, h = self._selection
        pen = QPen(QColor(255, 255, 0, 220))
        pen.setCosmetic(True)
        pen.setWidth(1)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 255, 0, 40))
        painter.drawRect(QRectF(x, y, w, h))
```

- [ ] Run → 10 passed.
- [ ] Commit:

```
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/pixel_view.py tests/sprite/gui/test_pixel_view.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): PixelView with integer zoom, grid, checkerboard, color pick"
```

---

### Task 3: `PreviewPlayer`

**Files:**
- Create: `tests/sprite/gui/test_preview_player.py`
- Create: `gui/sprite/preview_player.py`

**Interfaces:**
- Consumes: `FrameMeta`, `TagMeta`, `PixelView`, `qimage_to_rgba`.
- Produces:
  - `MODES = ("forward", "reverse", "pingpong")`, `SEAM_GOOD = 0.02`, `SEAM_WARN = 0.08`
  - `next_index(index: int, lo: int, hi: int, mode: str, direction: int) -> Tuple[int, int]`
  - `loop_seam_score(first: QImage, last: QImage) -> float` (mean abs RGBA diff, 0..1)
  - `seam_level(score: float) -> str` (`"good" | "warn" | "bad"`)
  - `PreviewPlayer(QWidget)`:
    - `frameChanged = Signal(int)`, `playingChanged = Signal(bool)`, `modeChanged = Signal(str)`, `sourceChanged = Signal(str)`
    - `view: PixelView`
    - `set_frames(frames: Sequence[FrameMeta])`; `frames() -> List[FrameMeta]`
    - `set_tags(tags: Sequence[TagMeta])`; `active_range() -> Tuple[int, int]`
    - `set_sources(names: Sequence[str])`; `source() -> str`
    - `current_index() -> int`; `set_current_index(int)`
    - `play()`, `pause()`, `toggle_play()`, `is_playing() -> bool`
    - `step(delta: int)`, `step_back()`, `step_forward()`, `first()`, `last()`
    - `mode() -> str`, `set_mode(str)`, `cycle_mode() -> str`
    - `seam_score() -> float`, `fps_readout() -> str`

**Steps:**

- [ ] Write the failing test `tests/sprite/gui/test_preview_player.py`:

```python
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest

from core.sprite.models import TagMeta
from gui.sprite.preview_player import (MODES, PreviewPlayer, loop_seam_score, next_index,
                                       seam_level)
from gui_synthetic import make_frames


def test_next_index_modes():
    assert next_index(2, 0, 3, "forward", 1) == (3, 1)
    assert next_index(3, 0, 3, "forward", 1) == (0, 1)
    assert next_index(0, 0, 3, "reverse", -1) == (3, -1)
    assert next_index(2, 0, 3, "pingpong", 1) == (3, 1)
    assert next_index(3, 0, 3, "pingpong", 1) == (2, -1)
    assert next_index(0, 0, 3, "pingpong", -1) == (1, 1)
    assert next_index(0, 0, 0, "forward", 1) == (0, 1)


def test_loop_seam_score_zero_for_identical_and_positive_for_different(qapp):
    a = QImage(4, 4, QImage.Format_RGBA8888)
    a.fill(QColor(255, 0, 0, 255))
    b = QImage(a)
    assert loop_seam_score(a, b) == 0.0
    b.setPixelColor(0, 0, QColor(0, 0, 255, 255))
    score = loop_seam_score(a, b)
    assert 0.0 < score < 0.1
    assert seam_level(0.0) == "good"
    assert seam_level(0.05) == "warn"
    assert seam_level(0.5) == "bad"


def test_set_frames_shows_first_and_reports_seam(qapp, tmp_path):
    player = PreviewPlayer()
    frames = make_frames(tmp_path, 4)
    player.set_frames(frames)
    assert player.current_index() == 0
    assert player.view.image() is not None
    assert 0.0 < player.seam_score() < 0.1
    assert "12" in player.fps_readout() or "10" in player.fps_readout()  # 100 ms → 10.0 fps
    assert player.slider.maximum() == 3


def test_step_and_bounds(qapp, tmp_path):
    player = PreviewPlayer()
    player.set_frames(make_frames(tmp_path, 3))
    seen = []
    player.frameChanged.connect(seen.append)
    player.step_forward()
    player.step_forward()
    player.step_forward()  # wraps
    assert seen == [1, 2, 0]
    player.last()
    assert player.current_index() == 2
    player.first()
    assert player.current_index() == 0
    player.step_back()
    assert player.current_index() == 2


def test_tags_restrict_range_and_set_mode(qapp, tmp_path):
    player = PreviewPlayer()
    player.set_frames(make_frames(tmp_path, 6))
    player.set_tags([TagMeta(name="idle", from_index=0, to_index=1),
                     TagMeta(name="walk", from_index=2, to_index=5, direction="pingpong")])
    player.tag_combo.setCurrentIndex(2)  # 0 = All frames
    assert player.active_range() == (2, 5)
    assert player.current_index() == 2
    assert player.mode() == "pingpong"
    player.step_back()
    assert player.current_index() == 5  # wraps inside the tag range


def test_cycle_mode_order(qapp):
    player = PreviewPlayer()
    got = []
    player.modeChanged.connect(got.append)
    assert player.mode() == MODES[0]
    assert player.cycle_mode() == "reverse"
    assert player.cycle_mode() == "pingpong"
    assert player.cycle_mode() == "forward"
    assert got == ["reverse", "pingpong", "forward"]


def test_timer_playback_honors_duration(qapp, tmp_path):
    player = PreviewPlayer()
    player.set_frames(make_frames(tmp_path, 4, duration_ms=5))
    seen = []
    player.frameChanged.connect(seen.append)
    states = []
    player.playingChanged.connect(states.append)
    player.play()
    assert player.is_playing()
    QTest.qWait(150)
    player.pause()
    assert not player.is_playing()
    assert len(seen) >= 3
    assert states == [True, False]
    count_before = len(seen)
    QTest.qWait(40)
    assert len(seen) == count_before  # timer stopped


def test_sources_combo_emits(qapp):
    player = PreviewPlayer()
    got = []
    player.sourceChanged.connect(got.append)
    player.set_sources(["cells", "hd", "pixel"])
    assert player.source() == "cells"
    player.source_combo.setCurrentIndex(1)
    assert got == ["hd"]
    assert player.source() == "hd"


def test_empty_frames_are_safe(qapp):
    player = PreviewPlayer()
    player.set_frames([])
    player.play()
    player.step_forward()
    player.last()
    assert player.current_index() == 0
    assert player.seam_score() == 0.0
    assert not player.is_playing()
```

- [ ] Run → fails on import.

- [ ] Implement `gui/sprite/preview_player.py`:

```python
"""Animation preview: QTimer + QPixmap, per-frame duration, loop modes, seam meter.

No QMovie (Qt cannot decode APNG; WebP stutters). Frames decode lazily on
first use and stay cached until `set_frames` replaces the list.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider,
                               QVBoxLayout, QWidget)

from core.sprite.models import FrameMeta, TagMeta

from .pixel_view import PixelView, qimage_to_rgba

logger = logging.getLogger(__name__)

MODES = ("forward", "reverse", "pingpong")
SEAM_GOOD = 0.02
SEAM_WARN = 0.08
MIN_TIMER_MS = 1
SEAM_STYLES = {
    "good": "color: #73c991; font-weight: bold;",
    "warn": "color: #cca700; font-weight: bold;",
    "bad": "color: #f14c4c; font-weight: bold;",
}
SEAM_TEXT = {"good": "seamless", "warn": "small jump", "bad": "visible seam"}


def next_index(index: int, lo: int, hi: int, mode: str, direction: int) -> Tuple[int, int]:
    """Next frame index inside [lo, hi] for `mode`; returns (index, direction)."""
    if hi <= lo:
        return lo, direction
    if mode == "forward":
        return (lo if index >= hi else index + 1), 1
    if mode == "reverse":
        return (hi if index <= lo else index - 1), -1
    candidate = index + direction
    if candidate > hi:
        return hi - 1, -1
    if candidate < lo:
        return lo + 1, 1
    return candidate, direction


def loop_seam_score(first: QImage, last: QImage) -> float:
    """Mean absolute RGBA difference between the loop's last and first frame (0..1)."""
    a = qimage_to_rgba(first).astype(np.float32) / 255.0
    b = qimage_to_rgba(last).astype(np.float32) / 255.0
    if a.shape != b.shape:
        height = max(a.shape[0], b.shape[0])
        width = max(a.shape[1], b.shape[1])
        padded_a = np.zeros((height, width, 4), np.float32)
        padded_b = np.zeros((height, width, 4), np.float32)
        padded_a[: a.shape[0], : a.shape[1]] = a
        padded_b[: b.shape[0], : b.shape[1]] = b
        a, b = padded_a, padded_b
    return float(np.abs(a - b).mean())


def seam_level(score: float) -> str:
    if score < SEAM_GOOD:
        return "good"
    if score < SEAM_WARN:
        return "warn"
    return "bad"


class PreviewPlayer(QWidget):
    """Plays a frame list with per-frame durations; shows fps and loop-seam readouts."""

    frameChanged = Signal(int)
    playingChanged = Signal(bool)
    modeChanged = Signal(str)
    sourceChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frames: List[FrameMeta] = []
        self._tags: List[TagMeta] = []
        self._cache: Dict[int, QPixmap] = {}
        self._range: Tuple[int, int] = (0, -1)
        self._index = 0
        self._direction = 1
        self._mode = MODES[0]
        self._playing = False
        self._seam = 0.0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)
        self._build()

    # ----- UI ---------------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        self.source_combo = QComboBox()
        self.source_combo.setToolTip("Which frames to preview: pipeline cells or a profile output")
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.source_combo.setVisible(False)
        top.addWidget(QLabel("Source:"))
        top.addWidget(self.source_combo)
        self.tag_combo = QComboBox()
        self.tag_combo.addItem("All frames")
        self.tag_combo.currentIndexChanged.connect(self._on_tag_changed)
        top.addWidget(QLabel("Tag:"))
        top.addWidget(self.tag_combo)
        top.addStretch()
        self.fps_label = QLabel("")
        top.addWidget(self.fps_label)
        self.seam_label = QLabel("")
        self.seam_label.setToolTip("Loop seam: mean RGBA difference between the last and first frame (0 = perfect loop)")
        top.addWidget(self.seam_label)
        layout.addLayout(top)

        self.view = PixelView()
        layout.addWidget(self.view, 1)

        controls = QHBoxLayout()
        self.first_btn = QPushButton("|<")
        self.first_btn.setToolTip("First frame (Home)")
        self.first_btn.clicked.connect(self.first)
        self.prev_btn = QPushButton("<")
        self.prev_btn.setToolTip("Previous frame (,)")
        self.prev_btn.clicked.connect(self.step_back)
        self.play_btn = QPushButton("Play")
        self.play_btn.setToolTip("Play / pause (Space)")
        self.play_btn.clicked.connect(self.toggle_play)
        self.next_btn = QPushButton(">")
        self.next_btn.setToolTip("Next frame (.)")
        self.next_btn.clicked.connect(self.step_forward)
        self.last_btn = QPushButton(">|")
        self.last_btn.setToolTip("Last frame (End)")
        self.last_btn.clicked.connect(self.last)
        self.mode_btn = QPushButton(self._mode)
        self.mode_btn.setToolTip("Loop mode: forward → reverse → ping-pong (L)")
        self.mode_btn.clicked.connect(self.cycle_mode)
        for button in (self.first_btn, self.prev_btn, self.play_btn, self.next_btn,
                       self.last_btn, self.mode_btn):
            button.setAutoDefault(False)
            controls.addWidget(button)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self._on_slider)
        controls.addWidget(self.slider, 1)
        self.index_label = QLabel("0 / 0")
        controls.addWidget(self.index_label)
        layout.addLayout(controls)

    # ----- data -------------------------------------------------------
    def set_frames(self, frames: Sequence[FrameMeta]) -> None:
        self.pause()
        self._frames = list(frames)
        self._cache = {}
        self._range = (0, len(self._frames) - 1)
        self._direction = 1
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(0, len(self._frames) - 1))
        self.slider.blockSignals(False)
        self._index = 0
        self._show(0, emit=False)
        self._update_readouts()

    def frames(self) -> List[FrameMeta]:
        return list(self._frames)

    def set_tags(self, tags: Sequence[TagMeta]) -> None:
        self._tags = list(tags)
        self.tag_combo.blockSignals(True)
        self.tag_combo.clear()
        self.tag_combo.addItem("All frames")
        for tag in self._tags:
            self.tag_combo.addItem(tag.name)
        self.tag_combo.blockSignals(False)
        self._apply_tag(0)

    def active_range(self) -> Tuple[int, int]:
        return self._range

    def set_sources(self, names: Sequence[str]) -> None:
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for name in names:
            self.source_combo.addItem(name)
        self.source_combo.blockSignals(False)
        self.source_combo.setVisible(bool(names))

    def source(self) -> str:
        return self.source_combo.currentText()

    # ----- position ---------------------------------------------------
    def current_index(self) -> int:
        return self._index

    def set_current_index(self, index: int) -> None:
        if not self._frames:
            return
        self._show(max(0, min(len(self._frames) - 1, int(index))))

    def step(self, delta: int) -> None:
        if not self._frames:
            return
        lo, hi = self._range
        span = hi - lo + 1
        if span <= 0:
            return
        offset = (self._index - lo + delta) % span
        self._show(lo + offset)

    def step_back(self) -> None:
        self.step(-1)

    def step_forward(self) -> None:
        self.step(1)

    def first(self) -> None:
        if self._frames:
            self._show(self._range[0])

    def last(self) -> None:
        if self._frames:
            self._show(self._range[1])

    # ----- playback ---------------------------------------------------
    def play(self) -> None:
        if self._playing or not self._frames:
            return
        self._playing = True
        self.play_btn.setText("Pause")
        self.playingChanged.emit(True)
        self._schedule()

    def pause(self) -> None:
        if not self._playing:
            return
        self._playing = False
        self._timer.stop()
        self.play_btn.setText("Play")
        self.playingChanged.emit(False)

    def toggle_play(self) -> None:
        if self._playing:
            self.pause()
        else:
            self.play()

    def is_playing(self) -> bool:
        return self._playing

    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            mode = MODES[0]
        self._mode = mode
        self._direction = -1 if mode == "reverse" else 1
        self.mode_btn.setText(mode)
        self.modeChanged.emit(mode)

    def cycle_mode(self) -> str:
        self.set_mode(MODES[(MODES.index(self._mode) + 1) % len(MODES)])
        return self._mode

    # ----- readouts ---------------------------------------------------
    def seam_score(self) -> float:
        return self._seam

    def fps_readout(self) -> str:
        lo, hi = self._range
        if not self._frames or hi < lo:
            return ""
        durations = [max(1, f.duration_ms) for f in self._frames[lo:hi + 1]]
        mean = sum(durations) / len(durations)
        text = f"{1000.0 / mean:.1f} fps"
        if len(set(durations)) > 1:
            text += " (variable)"
        return text

    # ----- internals --------------------------------------------------
    def _pixmap(self, index: int) -> QPixmap:
        pixmap = self._cache.get(index)
        if pixmap is None:
            frame = self._frames[index]
            pixmap = QPixmap(str(frame.source_path)) if frame.source_path else QPixmap()
            if pixmap.isNull():
                logger.error("PreviewPlayer: cannot decode frame %s (%s)", index, frame.source_path)
            self._cache[index] = pixmap
        return pixmap

    def _show(self, index: int, emit: bool = True) -> None:
        if not self._frames:
            self._index = 0
            self.view.set_image(None)
            self.index_label.setText("0 / 0")
            return
        self._index = index
        self.view.set_image(self._pixmap(index))
        self.slider.blockSignals(True)
        self.slider.setValue(index)
        self.slider.blockSignals(False)
        self.index_label.setText(f"{index + 1} / {len(self._frames)}")
        if emit:
            self.frameChanged.emit(index)

    def _schedule(self) -> None:
        if not self._playing or not self._frames:
            return
        frame = self._frames[self._index]
        self._timer.start(max(MIN_TIMER_MS, int(frame.duration_ms)))

    def _advance(self) -> None:
        if not self._playing or not self._frames:
            return
        lo, hi = self._range
        self._index, self._direction = next_index(self._index, lo, hi, self._mode, self._direction)
        self._show(self._index)
        self._schedule()

    def _on_slider(self, value: int) -> None:
        self._show(value)

    def _on_tag_changed(self, combo_index: int) -> None:
        self._apply_tag(combo_index)

    def _apply_tag(self, combo_index: int) -> None:
        count = len(self._frames)
        if combo_index <= 0 or combo_index > len(self._tags) or count == 0:
            self._range = (0, count - 1)
        else:
            tag = self._tags[combo_index - 1]
            lo = max(0, min(count - 1, tag.from_index))
            hi = max(lo, min(count - 1, tag.to_index))
            self._range = (lo, hi)
            if tag.direction.startswith("pingpong"):
                self.set_mode("pingpong")
                if tag.direction == "pingpong_reverse":
                    self._direction = -1
            elif tag.direction == "reverse":
                self.set_mode("reverse")
            else:
                self.set_mode("forward")
        if count:
            self._show(self._range[0])
        self._update_readouts()

    def _on_source_changed(self, _index: int) -> None:
        self.sourceChanged.emit(self.source())

    def _update_readouts(self) -> None:
        self.fps_label.setText(self.fps_readout())
        lo, hi = self._range
        if not self._frames or hi <= lo:
            self._seam = 0.0
            self.seam_label.setText("")
            return
        first = self._pixmap(lo).toImage()
        last = self._pixmap(hi).toImage()
        if first.isNull() or last.isNull():
            self._seam = 0.0
            self.seam_label.setText("Loop seam: n/a")
            return
        self._seam = loop_seam_score(first, last)
        level = seam_level(self._seam)
        self.seam_label.setText(f"Loop seam: {self._seam:.3f} ({SEAM_TEXT[level]})")
        self.seam_label.setStyleSheet(SEAM_STYLES[level])
```

- [ ] Run → 9 passed.
- [ ] Commit:

```
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/preview_player.py tests/sprite/gui/test_preview_player.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): PreviewPlayer with QTimer playback, loop modes, seam meter"
```

---

### Task 4: `FrameStrip` + `FrameOverridesDialog`

**Files:**
- Create: `tests/sprite/gui/test_frame_strip.py`
- Create: `gui/sprite/frame_strip.py`

**Interfaces:**
- Consumes: `FrameMeta`, `export_single_frame` (`core/sprite/exporters/png_sequence.py`),
  `UndoController`, `DialogCleanupMixin`, `bind_primary_action`, `set_default_button`.
- Produces:
  - `sanitize_frame_name(text: str) -> str`; `unique_name(base: str, taken: Sequence[str]) -> str`
  - `FrameOverridesDialog(DialogCleanupMixin, QDialog)`: `__init__(overrides: Dict[str, Any], parent=None)`,
    `set_values(Dict[str, Any])`, `values() -> Dict[str, Any]` (keys ⊆ `key_color`, `tolerance`, `softness`)
  - `FrameStrip(QWidget)`:
    - Signals: `framesChanged()`, `frameSelected(int)`, `retouchRequested(int)` (sub-project 6 wires
      this), `frameExported(object)` (`Path`), `logMessage(str, str)`
    - `__init__(undo: UndoController, parent=None)`
    - `set_action_id(str)`, `action_id() -> str`
    - `set_frames(Sequence[FrameMeta])`, `frames() -> List[FrameMeta]`, `count() -> int`
    - `selected_indices() -> List[int]`, `current_index() -> int`, `select_index(int)`
    - `duplicate_selected() -> int`, `delete_selected() -> int`,
      `insert_from_file(paths: Optional[Sequence[Path]] = None) -> int`, `move_frame(src: int, dst: int)`,
      `apply_duration(duration_ms: Optional[int] = None)`, `apply_overrides(indices, overrides)`,
      `edit_overrides_for_selected()`, `export_selected_frame(out_png: Optional[Path] = None) -> Optional[Path]`,
      `request_retouch()`, `refresh()` (re-reads thumbnails from the current `FrameMeta` objects;
      sub-project 6 calls it after a retouch repoints `source_path`)
    - Every destructive op calls `UndoController.snapshot(action_id, frames, label)` **before** the change.

**Steps:**

- [ ] Write the failing test `tests/sprite/gui/test_frame_strip.py`:

```python
from pathlib import Path

from PySide6.QtWidgets import QDialog

import gui.sprite.frame_strip as fs
from gui.sprite.frame_strip import FrameOverridesDialog, FrameStrip, sanitize_frame_name, unique_name
from gui.sprite.undo_controller import UndoController
from gui_synthetic import make_frames, write_frame_png


def _strip(tmp_path, n=4):
    undo = UndoController()
    strip = FrameStrip(undo)
    strip.set_action_id("act1")
    strip.set_frames(make_frames(tmp_path, n))
    return strip, undo


def test_helpers():
    assert sanitize_frame_name("Hero Walk 03.png") == "Hero_Walk_03_png"
    assert sanitize_frame_name("***") == "frame"
    assert unique_name("a", ["a", "a_2"]) == "a_3"
    assert unique_name("b", ["a"]) == "b"


def test_set_frames_builds_items_without_snapshot(qapp, tmp_path):
    strip, undo = _strip(tmp_path)
    assert strip.count() == 4
    assert strip.list.count() == 4
    assert [f.name for f in strip.frames()] == [f"frame_{i:02d}" for i in range(4)]
    assert not undo.can_undo("act1")


def test_delete_pushes_snapshot_and_undo_restores(qapp, tmp_path):
    strip, undo = _strip(tmp_path)
    changed = []
    strip.framesChanged.connect(lambda: changed.append(1))
    strip.select_index(1)
    assert strip.delete_selected() == 1
    assert [f.name for f in strip.frames()] == ["frame_00", "frame_02", "frame_03"]
    assert changed == [1]
    assert undo.can_undo("act1")
    restored = undo.undo("act1", strip.frames())
    strip.set_frames(restored)
    assert strip.count() == 4


def test_duplicate_inserts_unique_name_after_source(qapp, tmp_path):
    strip, undo = _strip(tmp_path)
    strip.select_index(0)
    assert strip.duplicate_selected() == 1
    names = [f.name for f in strip.frames()]
    assert names[:2] == ["frame_00", "frame_00_copy"]
    assert strip.frames()[1].source_path == strip.frames()[0].source_path
    assert undo.can_undo("act1")
    strip.select_index(0)
    strip.duplicate_selected()
    assert [f.name for f in strip.frames()][1] == "frame_00_copy_2"


def test_move_frame_reorders(qapp, tmp_path):
    strip, undo = _strip(tmp_path)
    strip.move_frame(3, 0)
    assert [f.name for f in strip.frames()] == ["frame_03", "frame_00", "frame_01", "frame_02"]
    assert strip.list.item(0).data(fs.Qt.UserRole) == 0
    assert undo.can_undo("act1")


def test_insert_from_file_reads_size(qapp, tmp_path):
    strip, undo = _strip(tmp_path, 2)
    extra = write_frame_png(tmp_path / "extra" / "Wide Frame.png", size=(12, 6))
    strip.select_index(0)
    assert strip.insert_from_file([extra]) == 1
    inserted = strip.frames()[1]
    assert inserted.name == "Wide_Frame"
    assert inserted.source_size == (12, 6)
    assert inserted.frame == (0, 0, 12, 6)
    assert inserted.duration_ms == 100
    assert undo.can_undo("act1")


def test_insert_from_file_reports_bad_image(qapp, tmp_path, monkeypatch):
    strip, undo = _strip(tmp_path, 1)
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a png")
    shown = []
    monkeypatch.setattr(fs.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    assert strip.insert_from_file([bad]) == 0
    assert shown and strip.count() == 1
    assert not undo.can_undo("act1")


def test_apply_duration_to_selection(qapp, tmp_path):
    strip, undo = _strip(tmp_path)
    strip.select_index(2)
    strip.duration_spin.setValue(250)
    strip.apply_duration()
    assert strip.frames()[2].duration_ms == 250
    assert strip.frames()[0].duration_ms == 100
    assert undo.can_undo("act1")


def test_apply_overrides(qapp, tmp_path):
    strip, undo = _strip(tmp_path)
    strip.apply_overrides([1, 2], {"tolerance": 0.3})
    assert strip.frames()[1].overrides == {"tolerance": 0.3}
    assert strip.frames()[2].overrides == {"tolerance": 0.3}
    assert strip.frames()[0].overrides == {}
    assert undo.can_undo("act1")


def test_overrides_dialog_values_only_enabled_fields(qapp):
    dialog = FrameOverridesDialog({"tolerance": 0.25})
    assert dialog.tolerance_on.isChecked()
    assert abs(dialog.tolerance.value() - 0.25) < 1e-9
    dialog.key_color_on.setChecked(True)
    dialog.key_color.setText("#00ff00")
    dialog.softness_on.setChecked(False)
    assert dialog.values() == {"tolerance": 0.25, "key_color": "#00FF00"}
    dialog.key_color.setText("garbage")
    assert "key_color" not in dialog.values()
    dialog.done(QDialog.Rejected)


def test_selection_emits_frame_selected_and_updates_spin(qapp, tmp_path):
    strip, _ = _strip(tmp_path)
    strip.frames()[3].duration_ms = 400
    strip.set_frames(strip.frames())
    got = []
    strip.frameSelected.connect(got.append)
    strip.select_index(3)
    assert got == [3]
    assert strip.duration_spin.value() == 400


def test_export_selected_frame_writes_png(qapp, tmp_path):
    strip, _ = _strip(tmp_path)
    strip.select_index(1)
    exported = []
    strip.frameExported.connect(exported.append)
    out = tmp_path / "out" / "single.png"
    assert strip.export_selected_frame(out) == out
    assert out.exists() and out.stat().st_size > 0
    assert exported == [out]


def test_request_retouch_emits_current_index(qapp, tmp_path):
    strip, _ = _strip(tmp_path)
    got = []
    strip.retouchRequested.connect(got.append)
    strip.select_index(2)
    strip.request_retouch()
    assert got == [2]


def test_refresh_rereads_thumbnails_after_source_repoint(qapp, tmp_path):
    strip, _ = _strip(tmp_path, 2)
    frame = strip.frames()[0]  # same FrameMeta object the strip holds
    before = strip.list.item(0).icon().pixmap(8, 8).toImage()
    frame.source_path = write_frame_png(tmp_path / "r" / "0000.r1.png", color=(0, 0, 255, 255))
    strip.select_index(1)
    strip.refresh()
    after = strip.list.item(0).icon().pixmap(8, 8).toImage()
    assert after != before
    assert strip.count() == 2
    assert strip.current_index() == 1  # selection survives a refresh
```

- [ ] Run → fails on import.

- [ ] Implement `gui/sprite/frame_strip.py`:

```python
"""Frame strip: order, duplicate, delete, insert, duration, per-frame overrides.

Design §4.5 / §1.4: every destructive list edit pushes a `FrameListSnapshot`
through the `UndoController` before the change. Files on disk are never
deleted here; the list only points at them.
"""
from __future__ import annotations

import copy
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem,
                               QMenu, QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
                               QWidget)

from core.sprite.exporters.png_sequence import export_single_frame
from core.sprite.models import FrameMeta
from gui.common.dialog_conventions import DialogCleanupMixin, bind_primary_action, set_default_button

from .undo_controller import UndoController

logger = logging.getLogger(__name__)

THUMB_PX = 64
MIN_DURATION_MS = 20
MAX_DURATION_MS = 10000
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def sanitize_frame_name(text: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_")
    return name or "frame"


def unique_name(base: str, taken: Sequence[str]) -> str:
    if base not in taken:
        return base
    k = 2
    while f"{base}_{k}" in taken:
        k += 1
    return f"{base}_{k}"


class FrameOverridesDialog(DialogCleanupMixin, QDialog):
    """Edit per-frame processing overrides: key_color, tolerance, softness."""

    def __init__(self, overrides: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Frame overrides")
        self.setModal(True)
        form = QFormLayout(self)

        self.key_color_on = QCheckBox("Key color")
        self.key_color = QLineEdit()
        self.key_color.setPlaceholderText("#RRGGBB")
        self.key_color_btn = QPushButton("…")
        self.key_color_btn.setToolTip("Choose a color")
        self.key_color_btn.setAutoDefault(False)
        self.key_color_btn.clicked.connect(self._pick_color)
        row = QHBoxLayout()
        row.addWidget(self.key_color, 1)
        row.addWidget(self.key_color_btn)
        form.addRow(self.key_color_on, row)

        self.tolerance_on = QCheckBox("Tolerance")
        self.tolerance = QDoubleSpinBox()
        self.tolerance.setRange(0.0, 1.0)
        self.tolerance.setSingleStep(0.01)
        self.tolerance.setDecimals(2)
        form.addRow(self.tolerance_on, self.tolerance)

        self.softness_on = QCheckBox("Softness")
        self.softness = QDoubleSpinBox()
        self.softness.setRange(0.0, 1.0)
        self.softness.setSingleStep(0.01)
        self.softness.setDecimals(2)
        form.addRow(self.softness_on, self.softness)

        hint = QLabel("Only checked fields override the action's key settings.")
        hint.setWordWrap(True)
        form.addRow(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        set_default_button(self, buttons.button(QDialogButtonBox.Ok))
        self._primary = bind_primary_action(self, self.accept)
        self.set_values(overrides)

    def set_values(self, overrides: Dict[str, Any]) -> None:
        self.key_color_on.setChecked("key_color" in overrides)
        self.key_color.setText(str(overrides.get("key_color", "") or ""))
        self.tolerance_on.setChecked("tolerance" in overrides)
        self.tolerance.setValue(float(overrides.get("tolerance", 0.2)))
        self.softness_on.setChecked("softness" in overrides)
        self.softness.setValue(float(overrides.get("softness", 0.1)))

    def values(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        if self.key_color_on.isChecked():
            text = self.key_color.text().strip()
            if HEX_RE.match(text):
                result["key_color"] = text.upper()
            else:
                logger.warning("Frame overrides: ignored invalid key color %r", text)
        if self.tolerance_on.isChecked():
            result["tolerance"] = round(self.tolerance.value(), 4)
        if self.softness_on.isChecked():
            result["softness"] = round(self.softness.value(), 4)
        return result

    def _pick_color(self) -> None:
        start = QColor(self.key_color.text()) if HEX_RE.match(self.key_color.text()) else QColor("#00FF00")
        color = QColorDialog.getColor(start, self, "Key color")
        if color.isValid():
            self.key_color.setText(color.name().upper())
            self.key_color_on.setChecked(True)


class _FrameList(QListWidget):
    """IconMode list whose internal drag-drop reorders the model (Static movement)."""

    aboutToReorder = Signal()
    reordered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(False)
        # Static movement: Qt reorders the rows on an internal drop instead of
        # free-placing the icon. Free/Snap movement would only move the icon.
        self.setMovement(QListView.Static)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setIconSize(QSize(THUMB_PX, THUMB_PX))
        self.setResizeMode(QListView.Adjust)
        self.setSpacing(4)
        self.setUniformItemSizes(True)
        self.setHorizontalScrollMode(QListWidget.ScrollPerPixel)
        self.setMinimumHeight(THUMB_PX + 44)

    def dropEvent(self, event):
        internal = event.source() is self
        if internal:
            self.aboutToReorder.emit()
        super().dropEvent(event)
        if internal:
            self.reordered.emit()


class FrameStrip(QWidget):
    """Thumbnail strip of an action's frames with list-edit tools and undo snapshots."""

    framesChanged = Signal()
    frameSelected = Signal(int)
    retouchRequested = Signal(int)
    frameExported = Signal(object)
    logMessage = Signal(str, str)

    def __init__(self, undo: UndoController, parent=None):
        super().__init__(parent)
        self._undo = undo
        self._action_id = ""
        self._frames: List[FrameMeta] = []
        self._syncing = False
        self._build()

    # ----- UI ---------------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tools = QHBoxLayout()
        self.duplicate_btn = QPushButton("Duplicate")
        self.duplicate_btn.setToolTip("Duplicate the selected frame(s) (Ctrl+D)")
        self.duplicate_btn.clicked.connect(self.duplicate_selected)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setToolTip("Remove the selected frame(s) from the list (Delete). Files stay on disk.")
        self.delete_btn.clicked.connect(self.delete_selected)
        self.insert_btn = QPushButton("Insert…")
        self.insert_btn.setToolTip("Insert PNG files after the current frame")
        self.insert_btn.clicked.connect(lambda: self.insert_from_file())
        self.overrides_btn = QPushButton("Overrides…")
        self.overrides_btn.setToolTip("Per-frame key color / tolerance / softness")
        self.overrides_btn.clicked.connect(self.edit_overrides_for_selected)
        self.export_btn = QPushButton("Export frame…")
        self.export_btn.setToolTip("Write the current frame as a single PNG")
        self.export_btn.clicked.connect(lambda: self.export_selected_frame())
        for button in (self.duplicate_btn, self.delete_btn, self.insert_btn,
                       self.overrides_btn, self.export_btn):
            button.setAutoDefault(False)
            tools.addWidget(button)
        tools.addStretch()
        tools.addWidget(QLabel("Duration:"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(MIN_DURATION_MS, MAX_DURATION_MS)
        self.duration_spin.setSuffix(" ms")
        self.duration_spin.setValue(100)
        self.duration_spin.setToolTip("Duration of the selected frame(s); Enter applies")
        self.duration_spin.editingFinished.connect(lambda: self.apply_duration())
        tools.addWidget(self.duration_spin)
        layout.addLayout(tools)

        self.list = _FrameList()
        self.list.currentRowChanged.connect(self._on_current_changed)
        self.list.aboutToReorder.connect(lambda: self._snapshot("reorder"))
        self.list.reordered.connect(self._finish_reorder)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.list)

    # ----- data -------------------------------------------------------
    def set_action_id(self, action_id: str) -> None:
        self._action_id = action_id or ""

    def action_id(self) -> str:
        return self._action_id

    def set_frames(self, frames: Sequence[FrameMeta]) -> None:
        self._frames = list(frames)
        self._rebuild()

    def frames(self) -> List[FrameMeta]:
        return list(self._frames)

    def count(self) -> int:
        return len(self._frames)

    def selected_indices(self) -> List[int]:
        return sorted(self.list.row(item) for item in self.list.selectedItems())

    def current_index(self) -> int:
        return self.list.currentRow()

    def select_index(self, index: int) -> None:
        if 0 <= index < self.list.count():
            self.list.setCurrentRow(index)

    def refresh(self) -> None:
        """Rebuild the thumbnails from the current FrameMeta objects.

        A retouch (sub-project 6) repoints `FrameMeta.source_path` in place and then
        calls this; the list order and the selection stay as they are.
        """
        self._rebuild()

    # ----- destructive operations (snapshot first) --------------------
    def duplicate_selected(self) -> int:
        indices = self._target_indices()
        if not indices:
            return 0
        self._snapshot(f"duplicate {len(indices)}")
        names = [f.name for f in self._frames]
        last = -1
        for index in reversed(indices):
            clone = copy.deepcopy(self._frames[index])
            clone.name = unique_name(f"{clone.name}_copy", names)
            names.append(clone.name)
            self._frames.insert(index + 1, clone)
            last = index + 1
        self._emit_changed()
        self.select_index(last)
        return len(indices)

    def delete_selected(self) -> int:
        indices = self._target_indices()
        if not indices:
            return 0
        self._snapshot(f"delete {len(indices)}")
        drop = set(indices)
        self._frames = [f for i, f in enumerate(self._frames) if i not in drop]
        self._emit_changed()
        self.select_index(min(indices[0], len(self._frames) - 1))
        return len(indices)

    def insert_from_file(self, paths: Optional[Sequence[Path]] = None) -> int:
        if paths is None:
            chosen, _ = QFileDialog.getOpenFileNames(self, "Insert frames", "", "PNG images (*.png)")
            paths = [Path(p) for p in chosen]
        paths = [Path(p) for p in paths]
        if not paths:
            return 0
        at = self.current_index()
        reference = self._frames[at] if 0 <= at < len(self._frames) else None
        duration = reference.duration_ms if reference is not None else 100
        names = [f.name for f in self._frames]
        new_frames: List[FrameMeta] = []
        for path in paths:
            image = QImage(str(path))
            if image.isNull():
                self._warn("Insert frame", f"Cannot read image: {path}")
                continue
            width, height = image.width(), image.height()
            name = unique_name(sanitize_frame_name(path.stem), names)
            names.append(name)
            new_frames.append(FrameMeta(
                name=name, source_path=path, frame=(0, 0, width, height),
                source_size=(width, height), sprite_source_size=(0, 0, width, height),
                duration_ms=duration,
            ))
        if not new_frames:
            return 0
        self._snapshot(f"insert {len(new_frames)}")
        insert_at = at + 1 if at >= 0 else len(self._frames)
        self._frames[insert_at:insert_at] = new_frames
        self._emit_changed()
        self.select_index(insert_at)
        logger.info("Frame strip: inserted %d frame(s) at %d", len(new_frames), insert_at)
        return len(new_frames)

    def move_frame(self, src: int, dst: int) -> None:
        if not (0 <= src < len(self._frames)) or not (0 <= dst < len(self._frames)) or src == dst:
            return
        self._snapshot("reorder")
        frame = self._frames.pop(src)
        self._frames.insert(dst, frame)
        self._emit_changed()
        self.select_index(dst)

    def apply_duration(self, duration_ms: Optional[int] = None) -> None:
        indices = self._target_indices()
        if not indices:
            return
        value = int(duration_ms if duration_ms is not None else self.duration_spin.value())
        value = max(MIN_DURATION_MS, min(MAX_DURATION_MS, value))
        if all(self._frames[i].duration_ms == value for i in indices):
            return
        self._snapshot("duration")
        for index in indices:
            self._frames[index].duration_ms = value
        self._emit_changed()

    def apply_overrides(self, indices: Sequence[int], overrides: Dict[str, Any]) -> None:
        indices = [i for i in indices if 0 <= i < len(self._frames)]
        if not indices:
            return
        self._snapshot("overrides")
        for index in indices:
            self._frames[index].overrides = dict(overrides)
        self._emit_changed()

    def edit_overrides_for_selected(self) -> None:
        indices = self._target_indices()
        if not indices:
            return
        dialog = FrameOverridesDialog(self._frames[indices[0]].overrides, self)
        if dialog.exec() == QDialog.Accepted:
            self.apply_overrides(indices, dialog.values())

    def export_selected_frame(self, out_png: Optional[Path] = None) -> Optional[Path]:
        index = self.current_index()
        if not (0 <= index < len(self._frames)):
            self._warn("Export frame", "Select a frame first.")
            return None
        frame = self._frames[index]
        if out_png is None:
            chosen, _ = QFileDialog.getSaveFileName(self, "Export frame", f"{frame.name}.png",
                                                    "PNG image (*.png)")
            if not chosen:
                return None
            out_png = Path(chosen)
        try:
            out_png.parent.mkdir(parents=True, exist_ok=True)
            written = Path(export_single_frame(frame, out_png))
        except Exception as exc:
            logger.error("Export frame failed: %s", exc, exc_info=True)
            self.logMessage.emit(f"Export frame failed: {exc}", "ERROR")
            QMessageBox.critical(self, "Export frame", f"Export failed:\n{exc}")
            return None
        logger.info("Exported frame %s → %s", frame.name, written)
        self.logMessage.emit(f"Exported frame {frame.name} → {written}", "SUCCESS")
        self.frameExported.emit(written)
        return written

    def request_retouch(self) -> None:
        index = self.current_index()
        if index >= 0:
            self.retouchRequested.emit(index)

    # ----- internals --------------------------------------------------
    def _target_indices(self) -> List[int]:
        indices = self.selected_indices()
        if indices:
            return indices
        current = self.current_index()
        return [current] if current >= 0 else []

    def _snapshot(self, label: str) -> None:
        self._undo.snapshot(self._action_id, self._frames, label)

    def _rebuild(self) -> None:
        current = self.current_index()
        self.list.blockSignals(True)
        self.list.clear()
        for index, frame in enumerate(self._frames):
            self.list.addItem(self._make_item(index, frame))
        self.list.blockSignals(False)
        if 0 <= current < self.list.count():
            self.list.setCurrentRow(current)

    def _make_item(self, index: int, frame: FrameMeta) -> QListWidgetItem:
        item = QListWidgetItem(self._thumbnail(frame), str(index))
        item.setData(Qt.UserRole, index)
        overrides = ", ".join(f"{k}={v}" for k, v in frame.overrides.items()) or "none"
        item.setToolTip(f"{frame.name}\n{frame.duration_ms} ms\noverrides: {overrides}")
        item.setFlags(item.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
        return item

    @staticmethod
    def _thumbnail(frame: FrameMeta) -> QIcon:
        pixmap = QPixmap(str(frame.source_path)) if frame.source_path else QPixmap()
        if pixmap.isNull():
            pixmap = QPixmap(THUMB_PX, THUMB_PX)
            pixmap.fill(QColor("#444444"))
        else:
            pixmap = pixmap.scaled(THUMB_PX, THUMB_PX, Qt.KeepAspectRatio, Qt.FastTransformation)
        return QIcon(pixmap)

    def _on_current_changed(self, row: int) -> None:
        if 0 <= row < len(self._frames):
            self.duration_spin.blockSignals(True)
            self.duration_spin.setValue(self._frames[row].duration_ms)
            self.duration_spin.blockSignals(False)
            self.frameSelected.emit(row)

    def _finish_reorder(self) -> None:
        order = [self.list.item(row).data(Qt.UserRole) for row in range(self.list.count())]
        if sorted(order) != list(range(len(self._frames))):
            logger.error("Frame strip: reorder produced an inconsistent order %s", order)
            self._rebuild()
            return
        self._frames = [self._frames[i] for i in order]
        self._emit_changed()

    def _emit_changed(self) -> None:
        self._rebuild()
        self.framesChanged.emit()

    def _context_menu(self, pos) -> None:
        menu = QMenu(self)
        for text, slot in (("Duplicate", self.duplicate_selected),
                           ("Delete", self.delete_selected),
                           ("Insert from file…", lambda: self.insert_from_file()),
                           ("Edit overrides…", self.edit_overrides_for_selected),
                           ("Export selected frame…", lambda: self.export_selected_frame()),
                           ("Retouch…", self.request_retouch)):
            action = QAction(text, menu)
            action.triggered.connect(slot)
            menu.addAction(action)
        menu.exec(self.list.mapToGlobal(pos))

    def _warn(self, title: str, message: str) -> None:
        logger.error("%s: %s", title, message)
        self.logMessage.emit(f"{title}: {message}", "ERROR")
        QMessageBox.warning(self, title, message)
```

- [ ] Run → 14 passed.
- [ ] Commit:

```
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/frame_strip.py tests/sprite/gui/test_frame_strip.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): FrameStrip with reorder, duplicate, delete, insert, overrides, undo snapshots"
```

---

### Task 5: `SpriteMLInstallDialog` (ML backend install)

**Files:**
- Create: `tests/sprite/gui/test_ml_install_dialog.py`
- Create: `gui/sprite/ml_install_dialog.py`

**Interfaces:**
- Consumes: `core.package_installer.PackageInstaller(packages, update_requirements, index_url)`
  with signals `progress(str)`, `percentage(int)`, `finished(bool, str)`;
  `core.sprite.ml_install.sprite_ml_packages()`, `core.sprite.ml_install.python_supports_rembg()`;
  `DialogStatusConsole`, `standard_splitter`, `persist_splitter`, `restore_splitter`,
  `DialogCleanupMixin`, `bind_primary_action`, `set_default_button`.
- Produces: `SpriteMLInstallDialog(DialogCleanupMixin, QDialog)`:
  - `installFinished = Signal(bool)`
  - `packages() -> List[str]` (rembg specs removed when `python_supports_rembg()` is False;
    `sprite_ml_packages()` returns `(packages, index_url)` and already omits rembg on an unsupported
    Python — the dialog filters again so the gate label is always right), `index_url() -> str`
  - `rembg_gated() -> bool`
  - `start_install() -> None`; `is_running() -> bool`
  - widgets: `install_btn`, `close_btn`, `gate_label`, `progress_bar`, `console: DialogStatusConsole`

**Steps:**

- [ ] Write the failing test `tests/sprite/gui/test_ml_install_dialog.py`:

```python
from PySide6.QtCore import QThread, Signal
from PySide6.QtTest import QTest

import gui.sprite.ml_install_dialog as mid
from gui.sprite.ml_install_dialog import SpriteMLInstallDialog

SPECS = ["mediapipe>=0.10", "rembg[cpu]>=2.0"]


def test_packages_exclude_rembg_when_python_is_gated(qapp, monkeypatch):
    monkeypatch.setattr(mid, "sprite_ml_packages", lambda: (list(SPECS), ""))
    monkeypatch.setattr(mid, "python_supports_rembg", lambda: False)
    dialog = SpriteMLInstallDialog()
    assert dialog.packages() == ["mediapipe>=0.10"]
    assert dialog.rembg_gated()
    assert not dialog.gate_label.isHidden()
    dialog.done(0)


def test_packages_include_rembg_when_supported(qapp, monkeypatch):
    monkeypatch.setattr(mid, "sprite_ml_packages", lambda: (list(SPECS), ""))
    monkeypatch.setattr(mid, "python_supports_rembg", lambda: True)
    dialog = SpriteMLInstallDialog()
    assert dialog.packages() == SPECS
    assert not dialog.rembg_gated()
    assert dialog.gate_label.isHidden()
    dialog.done(0)


class _FakeInstaller(QThread):
    progress = Signal(str)
    finished = Signal(bool, str)
    percentage = Signal(int)

    def __init__(self, packages, update_requirements=True, index_url=None):
        super().__init__()
        self.packages = list(packages)
        self.update_requirements = update_requirements
        self.index_url = index_url

    def run(self):
        self.progress.emit("fake install line")
        self.percentage.emit(100)
        self.finished.emit(True, "fake ok")


def test_start_install_runs_installer_and_emits(qapp, monkeypatch):
    monkeypatch.setattr(mid, "sprite_ml_packages", lambda: (list(SPECS), ""))
    monkeypatch.setattr(mid, "python_supports_rembg", lambda: True)
    monkeypatch.setattr(mid, "PackageInstaller", _FakeInstaller)
    dialog = SpriteMLInstallDialog()
    got = []
    dialog.installFinished.connect(got.append)
    dialog.start_install()
    assert dialog.is_running() or got == [True]
    for _ in range(200):
        if got:
            break
        QTest.qWait(20)
    assert got == [True]
    assert "fake install line" in dialog.console.console.toPlainText()
    assert dialog._installer.update_requirements is False
    assert dialog._installer.index_url is None  # "" from sprite_ml_packages → PyPI default
    assert dialog.close_btn.isEnabled()
    dialog.done(0)


def test_reject_is_blocked_while_running(qapp, monkeypatch):
    monkeypatch.setattr(mid, "sprite_ml_packages", lambda: (list(SPECS), ""))
    monkeypatch.setattr(mid, "python_supports_rembg", lambda: True)

    class _Slow(_FakeInstaller):
        def run(self):
            QThread.msleep(150)
            self.finished.emit(True, "slow ok")

    monkeypatch.setattr(mid, "PackageInstaller", _Slow)
    shown = []
    monkeypatch.setattr(mid.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    dialog = SpriteMLInstallDialog()
    dialog.show()
    dialog.start_install()
    dialog.reject()
    assert shown and dialog.isVisible()
    dialog._installer.wait(5000)
    QTest.qWait(20)
    dialog.reject()
    assert not dialog.isVisible()
```

- [ ] Run → fails on import.

- [ ] Implement `gui/sprite/ml_install_dialog.py`:

```python
"""Runtime install dialog for the sprite ML matting backends (mediapipe, rembg).

Mirrors gui/install_dialog.py (Real-ESRGAN): PackageInstaller thread, status
console in a persisted splitter, close blocked while pip runs. rembg needs
Python 3.11–3.13 (design decision 4); the dialog drops it on other versions
and says so.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
                               QPushButton, QVBoxLayout, QWidget)

from core.package_installer import PackageInstaller
from core.sprite.ml_install import python_supports_rembg, sprite_ml_packages
from gui.common.dialog_conventions import (DialogCleanupMixin, bind_primary_action,
                                           persist_splitter, restore_splitter,
                                           set_default_button, standard_splitter)
from gui.llm_utils import DialogStatusConsole

from . import prefs

logger = logging.getLogger(__name__)

SPLITTER_KEY = "sprite/ml_install/splitter"


class SpriteMLInstallDialog(DialogCleanupMixin, QDialog):
    """Install the optional ML background-removal packages into the running venv."""

    installFinished = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install sprite ML backends")
        self.setModal(True)
        self.setMinimumSize(560, 440)
        self.settings = prefs.sprite_settings()
        self._installer: Optional[PackageInstaller] = None
        self._packages, self._index_url = self._select_packages()
        self._build()

    # ----- package selection ----------------------------------------
    @staticmethod
    def _select_packages() -> Tuple[List[str], str]:
        packages, index_url = sprite_ml_packages()
        specs = [str(s) for s in packages]
        if not python_supports_rembg():
            specs = [s for s in specs if not s.lower().startswith("rembg")]
        return specs, str(index_url or "")

    def packages(self) -> List[str]:
        return list(self._packages)

    def index_url(self) -> str:
        return self._index_url

    def rembg_gated(self) -> bool:
        return not python_supports_rembg()

    # ----- UI ---------------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Install optional ML background removal")
        title.setStyleSheet("font-weight: bold; font-size: 12pt;")
        top_layout.addWidget(title)

        info = QLabel("These packages install into the running Python environment:\n"
                      + "\n".join(f"  • {spec}" for spec in self._packages)
                      + "\n\nmediapipe removes backgrounds with no model download. "
                        "rembg downloads its model (isnet-anime, 168 MB, MIT) on first use.")
        info.setWordWrap(True)
        top_layout.addWidget(info)

        self.gate_label = QLabel("rembg needs Python 3.11–3.13. This Python is outside that "
                                 "range, so only mediapipe will be installed.")
        self.gate_label.setWordWrap(True)
        self.gate_label.setStyleSheet("color: #cca700;")
        self.gate_label.setVisible(self.rembg_gated())
        top_layout.addWidget(self.gate_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        top_layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Ready.")
        top_layout.addWidget(self.status_label)

        self.console = DialogStatusConsole("Installation output")
        self.splitter = standard_splitter(Qt.Vertical, self)
        self.splitter.addWidget(top)
        self.splitter.addWidget(self.console)
        self.splitter.setStretchFactor(1, 1)
        if not restore_splitter(self.settings, SPLITTER_KEY, self.splitter):
            self.splitter.setSizes([220, 240])
        layout.addWidget(self.splitter, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.close_btn)
        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(self.start_install)
        self.install_btn.setEnabled(bool(self._packages))
        buttons.addWidget(self.install_btn)
        layout.addLayout(buttons)

        set_default_button(self, self.install_btn, focus=bool(self._packages))
        self._primary = bind_primary_action(self, self.install_btn.click)

    # ----- install ----------------------------------------------------
    def is_running(self) -> bool:
        return self._installer is not None and self._installer.isRunning()

    def start_install(self) -> None:
        if self.is_running():
            return
        if not self._packages:
            self._warn("Nothing to install", "No packages are selected for this Python version.")
            return
        logger.info("Sprite ML install: %s", self._packages)
        self.console.log(f"Installing: {', '.join(self._packages)}")
        self.status_label.setText("Installing…")
        self.install_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self._primary.set_enabled(False)
        # update_requirements=False: the sprite extras live in requirements-sprite-ml.txt
        self._installer = PackageInstaller(self._packages, update_requirements=False,
                                           index_url=self._index_url or None)
        self._installer.progress.connect(self._on_progress)
        self._installer.percentage.connect(self.progress_bar.setValue)
        self._installer.finished.connect(self._on_finished)
        self._installer.start()

    def _on_progress(self, message: str) -> None:
        self.status_label.setText(message)
        self.console.log(message)

    def _on_finished(self, ok: bool, message: str) -> None:
        self.close_btn.setEnabled(True)
        self.install_btn.setEnabled(not ok)
        self._primary.set_enabled(not ok)
        if ok:
            logger.info("Sprite ML install finished: %s", message)
            self.status_label.setText("Installed. Restart ImageAI to load the new backends.")
            self.console.log(message, "SUCCESS")
        else:
            logger.error("Sprite ML install failed: %s", message)
            self.status_label.setText("Install failed.")
            self.console.log(message, "ERROR")
            QMessageBox.warning(self, "Install failed", message)
        self.installFinished.emit(ok)

    # ----- exit paths -------------------------------------------------
    def reject(self) -> None:
        if self.is_running():
            self._warn("Installation in progress",
                       "Wait for pip to finish. Closing now may leave packages half installed.")
            return
        super().reject()

    def on_dialog_close(self) -> None:
        persist_splitter(self.settings, SPLITTER_KEY, self.splitter)

    def _warn(self, title: str, message: str) -> None:
        logger.warning("%s: %s", title, message)
        self.console.log(f"{title}: {message}", "WARNING")
        QMessageBox.warning(self, title, message)
```

- [ ] Run → 4 passed.
- [ ] Commit:

```
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/ml_install_dialog.py tests/sprite/gui/test_ml_install_dialog.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): ML backend install dialog with Python version gate"
```

---

### Task 6: `ProcessingPanel` + `ProfileEditor`

**Files:**
- Create: `tests/sprite/gui/test_processing_panel.py`
- Create: `gui/sprite/processing_panel.py`

**Interfaces:**
- Consumes: `estimate_frame_count`, `probe_video` (`core/sprite/extract.py`);
  `ffmpeg_chromakey_preview` (`core/sprite/keying.py`); `available_backends`, `REMBG_MODELS`
  (`core/sprite/matting.py`); `run_pipeline`, `stage_dir` (`core/sprite/pipeline.py`);
  `FLOYD_WARNING` (`core/sprite/pixelart.py`; the "Rebuild palette" button clears
  `OutputProfile.locked_palette` and re-runs the pipeline — sub-project 4's `ensure_palette`
  rebuilds from the fitted frames because `locked_palette` is in the pixel-stage fingerprint);
  `CELL_PRESETS`, `CUSTOM_CELL_LABEL` (`core/sprite/presets.py`); `SpriteProject`, `ActionCard`,
  `OutputProfile` (+ `upscale_small`, read with `getattr` until sub-project 4 lands the field);
  `stages/<id>/pixel/pixel.json` `warnings` (sub-project 4); `SpriteWorker`, `WorkerHost` (5a);
  `SpriteMLInstallDialog` (Task 5); `PixelView` (Task 2); `bind_primary_action`.
- Produces:
  - `ProfileEditor(QGroupBox)`: `changed = Signal()`, `rebuildRequested = Signal(str)`;
    `__init__(profile_name: str, parent=None)`; `load(profile: OutputProfile)`;
    `store(profile: OutputProfile)`; widgets `enabled`, `preset`, `width`, `height`,
    `binary_alpha`, `threshold`, `defringe`, `palette_size`, `dither`, `dither_warning`,
    `palette_lock`, `rebuild_btn`, `upscale_small`.
  - `ProcessingPanel(WorkerHost, QWidget)` (one `SpriteWorker` at a time via `start_job`; a
    separate short-lived probe worker runs ffprobe when the action changes):
    - Signals: `pipelineFinished(str)` (action id), `settingsChanged()`, `logMessage(str, str)`,
      `exportRequested()`
    - `set_project(Optional[SpriteProject])`, `project()`, `set_action(Optional[ActionCard])`, `action()`
    - `attach_pixel_view(view: PixelView)`, `pick_key_color()`
    - `set_probe(Optional[Dict[str, Any]])`, `estimate_text() -> str`
    - `refresh_backends()`, `open_install_dialog()`
    - `run_pipeline()` (Ctrl+Enter, `WidgetWithChildrenShortcut`), `cancel()`, `preview_key_on_clip()`,
      `rebuild_palette_for(profile_name: str)` (clears the lock, re-runs the pipeline, emits
      `pipelineFinished`), `is_busy() -> bool` (from `WorkerHost`), `shutdown(timeout_ms=5000)`
    - `profile_editors: Dict[str, ProfileEditor]`
    - widgets: `extract_mode`, `every_n`, `target_fps`, `exact_n`, `trim_start`, `trim_end`,
      `cull`, `cull_threshold`, `estimate_label`, `key_method`, `key_color_edit`, `pick_btn`,
      `tolerance`, `softness`, `despill`, `decontaminate`, `choke`, `feather`, `despeckle`,
      `ml_backend`, `ml_model`, `ml_refine`, `ml_status`, `install_btn`, `anchor`, `dejitter`,
      `dejitter_method`, `pad`, `force_check`, `run_btn`, `cancel_btn`, `preview_btn`,
      `export_btn`, `progress_bar`, `progress_label`
  - Constants: `EXTRACT_MODES`, `KEY_METHODS`, `DESPILL_MODES`, `ML_BACKENDS`, `DITHER_MODES`,
    `ANCHORS`, `DEJITTER_METHODS`, `CUSTOM_PRESET` (= `presets.CUSTOM_CELL_LABEL`, "Custom…")

**Steps:**

- [ ] Write the failing test `tests/sprite/gui/test_processing_panel.py`:

```python
import time

import pytest
from PySide6.QtTest import QTest

import gui.sprite.processing_panel as pp
from gui.sprite.pixel_view import PixelView
from gui.sprite.processing_panel import CUSTOM_PRESET, ProcessingPanel
from gui_synthetic import make_project


def _wait_idle(panel, timeout_s=10.0):
    deadline = time.monotonic() + timeout_s
    while panel.is_busy() and time.monotonic() < deadline:
        QTest.qWait(20)
    QTest.qWait(20)
    assert not panel.is_busy(), "worker did not finish"


@pytest.fixture
def panel(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    project, action = make_project(tmp_path)
    widget = ProcessingPanel()
    widget.set_project(project)
    widget.set_action(action)
    yield widget, project, action
    widget.shutdown()


def test_loads_project_settings(panel):
    widget, project, action = panel
    assert widget.key_method.currentData() == project.key.method
    assert widget.extract_mode.currentData() == project.extraction.mode
    assert set(widget.profile_editors) == {p.name for p in project.profiles}
    assert widget.run_btn.isEnabled()


def test_tolerance_slider_writes_back(panel):
    widget, project, _ = panel
    changed = []
    widget.settingsChanged.connect(lambda: changed.append(1))
    widget.tolerance.setValue(35)
    assert abs(project.key.tolerance - 0.35) < 1e-9
    assert changed


def test_extract_mode_and_stabilize_write_back(panel):
    widget, project, _ = panel
    widget.extract_mode.setCurrentIndex(widget.extract_mode.findData("target_fps"))
    assert project.extraction.mode == "target_fps"
    widget.target_fps.setValue(15)
    assert project.extraction.target_fps == 15
    widget.dejitter.setChecked(False)
    assert project.stabilize.dejitter is False
    widget.anchor.setCurrentIndex(widget.anchor.findData("center"))
    assert project.stabilize.anchor == "center"


def test_key_color_edit_writes_back_and_validates(panel):
    widget, project, _ = panel
    widget.key_color_edit.setText("#12ab34")
    assert project.key.key_color == "#12AB34"
    widget.key_color_edit.setText("nope")
    assert project.key.key_color is None


def test_estimate_readout_uses_probe(panel):
    widget, project, _ = panel
    assert "?" in widget.estimate_text()
    widget.set_probe({"fps": 24.0, "nb_frames": 48, "duration": 2.0, "width": 64, "height": 64})
    text = widget.estimate_text()
    assert "?" not in text and any(ch.isdigit() for ch in text)
    assert widget.estimate_label.text() == text


def test_profile_editor_floyd_warning_and_custom_size(panel):
    widget, project, _ = panel
    editor = widget.profile_editors["pixel"]
    profile = next(p for p in project.profiles if p.name == "pixel")
    assert editor.dither_warning.isHidden()
    editor.dither.setCurrentIndex(editor.dither.findData("floyd"))
    assert not editor.dither_warning.isHidden()
    assert profile.dither == "floyd"
    editor.preset.setCurrentText(CUSTOM_PRESET)
    editor.width.setValue(72)
    editor.height.setValue(80)
    assert profile.cell_size == (72, 80)
    editor.palette_size.setValue(0)
    assert profile.palette_size is None
    editor.palette_size.setValue(16)
    assert profile.palette_size == 16
    editor.upscale_small.setChecked(True)
    assert getattr(profile, "upscale_small", None) is True


def test_run_pipeline_uses_worker_and_emits(panel, monkeypatch):
    widget, project, action = panel
    calls = []

    def fake_run(proj, act, *, upto, progress, token, force):
        calls.append((proj, act, upto, force))
        progress("key", 1, 2, "keying")
        return {"key": [], "stabilize": []}

    monkeypatch.setattr(pp, "run_pipeline", fake_run)
    done = []
    widget.pipelineFinished.connect(done.append)
    logs = []
    widget.logMessage.connect(lambda m, l: logs.append((m, l)))
    widget.force_check.setChecked(True)
    widget.run_pipeline()
    assert widget.is_busy()
    _wait_idle(widget)
    assert calls == [(project, action, "pixel", True)]
    assert done == [action.id]
    assert any(l == "SUCCESS" for _, l in logs)


def test_failed_pipeline_is_logged_and_shown(panel, monkeypatch):
    widget, _, _ = panel

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(pp, "run_pipeline", boom)
    shown = []
    monkeypatch.setattr(pp.QMessageBox, "critical", staticmethod(lambda *a, **k: shown.append(a)))
    logs = []
    widget.logMessage.connect(lambda m, l: logs.append((m, l)))
    widget.run_pipeline()
    _wait_idle(widget)
    assert shown
    assert any(l == "ERROR" and "boom" in m for m, l in logs)


def test_preview_key_requires_clip(panel, monkeypatch):
    widget, _, action = panel
    action.clip = None
    shown = []
    monkeypatch.setattr(pp.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    widget.preview_key_on_clip()
    assert shown and not widget.is_busy()


def test_preview_key_runs_ffmpeg_helper(panel, monkeypatch, tmp_path):
    widget, project, action = panel
    clip = tmp_path / "clips" / "act1.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"\x00")
    action.clip = type("Clip", (), {"path": clip})()
    calls = []

    def fake_preview(video, out_mp4, key_color, similarity, blend):
        calls.append((video, out_mp4, key_color, similarity, blend))
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_mp4.write_bytes(b"\x00")
        return out_mp4

    monkeypatch.setattr(pp, "ffmpeg_chromakey_preview", fake_preview)
    opened = []
    monkeypatch.setattr(pp.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url) or True))
    widget.preview_key_on_clip()
    _wait_idle(widget)
    assert len(calls) == 1 and calls[0][0] == clip
    assert calls[0][2] == (project.key.key_color or project.plate_color)
    assert opened


def test_key_color_pick_roundtrip(panel):
    widget, project, _ = panel
    view = PixelView()
    widget.attach_pixel_view(view)
    widget.pick_key_color()
    assert view.pick_mode()
    view.colorPicked.emit("#00FF00")
    assert widget.key_color_edit.text() == "#00FF00"
    assert project.key.key_color == "#00FF00"


def test_install_button_hidden_when_backends_present(panel, monkeypatch):
    widget, _, _ = panel
    assert not widget.install_btn.isHidden()
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": True, "rembg": True})
    widget.refresh_backends()
    assert widget.install_btn.isHidden()
    assert "installed" in widget.ml_status.text()


def test_rebuild_palette_clears_lock_and_reruns_pipeline(panel, monkeypatch):
    widget, project, action = panel
    profile = next(p for p in project.profiles if p.name == "pixel")
    profile.locked_palette = ["#000000", "#FFFFFF"]
    calls = []

    def fake_run(proj, act, *, upto, progress, token, force):
        calls.append((upto, force, profile.locked_palette))
        profile.locked_palette = ["#101010", "#808080", "#F0F0F0"]  # what ensure_palette would store
        return {"pixel": []}

    monkeypatch.setattr(pp, "run_pipeline", fake_run)
    logs = []
    widget.logMessage.connect(lambda m, l: logs.append(m))
    done = []
    widget.pipelineFinished.connect(done.append)
    widget.rebuild_palette_for("pixel")
    _wait_idle(widget)
    assert calls == [("pixel", False, None)]  # the lock was cleared before the run
    assert any("3 colors" in m for m in logs)
    assert done == [action.id]


def test_pixel_warnings_are_logged_after_run(panel, monkeypatch, tmp_path):
    widget, project, action = panel
    monkeypatch.setattr(pp, "stage_dir", lambda proj, act, stage: tmp_path / "stages" / stage)
    report = tmp_path / "stages" / "pixel" / "pixel.json"
    report.parent.mkdir(parents=True)
    report.write_text('{"warnings": ["source 40x40 is smaller than cell 64x64"]}', encoding="utf-8")
    monkeypatch.setattr(pp, "run_pipeline", lambda *a, **k: {"pixel": []})
    logs = []
    widget.logMessage.connect(lambda m, l: logs.append((m, l)))
    widget.run_pipeline()
    _wait_idle(widget)
    assert any(l == "WARNING" and "smaller than cell" in m for m, l in logs)


def test_export_button_emits(panel):
    widget, _, _ = panel
    got = []
    widget.exportRequested.connect(lambda: got.append(1))
    widget.export_btn.click()
    assert got == [1]


def test_no_project_disables_run(qapp, monkeypatch):
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    widget = ProcessingPanel()
    widget.set_project(None)
    assert not widget.run_btn.isEnabled()
    widget.set_probe({"fps": 24.0, "nb_frames": 48, "duration": 2.0})
    assert "?" in widget.estimate_text()
```

- [ ] Run → fails on import.

- [ ] Implement `gui/sprite/processing_panel.py`:

```python
"""Processing panel: extraction, key, profiles, stabilize; runs the pipeline (design §4.5).

Every long job (pipeline, ffprobe, chroma preview, palette rebuild) runs in a
SpriteWorker. Editors write straight into the SpriteProject dataclasses; the
pipeline's stage cache (§1.2) decides what re-runs.
"""
from __future__ import annotations

import contextlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
                               QPushButton, QScrollArea, QSlider, QSpinBox, QVBoxLayout,
                               QWidget)

from core.sprite.extract import estimate_frame_count, probe_video
from core.sprite.keying import ffmpeg_chromakey_preview
from core.sprite.matting import REMBG_MODELS, available_backends
from core.sprite.pipeline import run_pipeline, stage_dir
from core.sprite.pixelart import FLOYD_WARNING
from core.sprite.presets import CELL_PRESETS, CUSTOM_CELL_LABEL
from core.sprite.project import ActionCard, OutputProfile, SpriteProject
from gui.common.dialog_conventions import bind_primary_action

from .ml_install_dialog import SpriteMLInstallDialog
from .pixel_view import PixelView
from .workers import SpriteWorker, WorkerHost

logger = logging.getLogger(__name__)

EXTRACT_MODES = ("every_n", "target_fps", "exact_n")
KEY_METHODS = ("chroma", "ml", "none")
DESPILL_MODES = ("none", "average", "double", "limit")
ML_BACKENDS = ("mediapipe", "rembg")
DITHER_MODES = ("none", "bayer2", "bayer4", "bayer8", "floyd")
ANCHORS = ("bottom_center", "center", "top_left", "top_center", "bottom_left")
DEJITTER_METHODS = ("phase", "centroid")
CUSTOM_PRESET = CUSTOM_CELL_LABEL   # "Custom…" — one label, owned by core.sprite.presets
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@contextlib.contextmanager
def _blocked(*widgets: QWidget):
    for widget in widgets:
        widget.blockSignals(True)
    try:
        yield
    finally:
        for widget in widgets:
            widget.blockSignals(False)


def _combo(values, labels: Optional[Dict[str, str]] = None) -> QComboBox:
    combo = QComboBox()
    for value in values:
        combo.addItem((labels or {}).get(value, value), value)
    return combo


class ProfileEditor(QGroupBox):
    """Editor for one OutputProfile (hd or pixel)."""

    changed = Signal()
    rebuildRequested = Signal(str)

    def __init__(self, profile_name: str, parent=None):
        super().__init__(f"Profile: {profile_name}", parent)
        self.profile_name = profile_name
        form = QFormLayout(self)

        self.enabled = QCheckBox("Enabled")
        form.addRow(self.enabled)

        self.preset = QComboBox()
        for label, _size in CELL_PRESETS:
            self.preset.addItem(label)
        self.preset.addItem(CUSTOM_PRESET)
        self.width = QSpinBox()
        self.width.setRange(1, 4096)
        self.height = QSpinBox()
        self.height.setRange(1, 4096)
        size_row = QHBoxLayout()
        size_row.addWidget(self.preset, 1)
        size_row.addWidget(self.width)
        size_row.addWidget(QLabel("×"))
        size_row.addWidget(self.height)
        form.addRow("Cell size:", size_row)

        self.binary_alpha = QCheckBox("Binary alpha")
        self.threshold = QSpinBox()
        self.threshold.setRange(0, 255)
        self.defringe = QSpinBox()
        self.defringe.setRange(0, 16)
        alpha_row = QHBoxLayout()
        alpha_row.addWidget(self.binary_alpha)
        alpha_row.addWidget(QLabel("threshold"))
        alpha_row.addWidget(self.threshold)
        alpha_row.addWidget(QLabel("defringe px"))
        alpha_row.addWidget(self.defringe)
        form.addRow("Alpha:", alpha_row)

        self.palette_size = QSpinBox()
        self.palette_size.setRange(0, 256)
        self.palette_size.setSpecialValueText("no quantize")
        self.palette_size.setToolTip("Shared palette size; 0 = keep true color")
        form.addRow("Palette size:", self.palette_size)

        self.dither = _combo(DITHER_MODES)
        form.addRow("Dither:", self.dither)
        self.dither_warning = QLabel(FLOYD_WARNING)
        self.dither_warning.setWordWrap(True)
        self.dither_warning.setStyleSheet("color: #cca700;")
        self.dither_warning.setVisible(False)
        form.addRow(self.dither_warning)

        self.palette_lock = QCheckBox("Lock palette (remap new frames)")
        self.rebuild_btn = QPushButton("Rebuild palette")
        self.rebuild_btn.setAutoDefault(False)
        self.rebuild_btn.clicked.connect(lambda: self.rebuildRequested.emit(self.profile_name))
        lock_row = QHBoxLayout()
        lock_row.addWidget(self.palette_lock, 1)
        lock_row.addWidget(self.rebuild_btn)
        form.addRow("Palette lock:", lock_row)

        self.upscale_small = QCheckBox("Upscale sources smaller than the cell")
        self.upscale_small.setToolTip("Sub-project 4: upscale a small source before the integer fit "
                                      "instead of padding it; the pixel stage reports the case in pixel.json")
        form.addRow("Small sources:", self.upscale_small)

        self.preset.currentIndexChanged.connect(self._on_preset)
        self.dither.currentIndexChanged.connect(self._on_dither)
        for spin in (self.width, self.height, self.threshold, self.defringe, self.palette_size):
            spin.valueChanged.connect(lambda _v: self.changed.emit())
        for box in (self.enabled, self.binary_alpha, self.palette_lock, self.upscale_small):
            box.toggled.connect(lambda _v: self.changed.emit())

    def _on_preset(self, index: int) -> None:
        custom = self.preset.currentText() == CUSTOM_PRESET
        self.width.setEnabled(custom)
        self.height.setEnabled(custom)
        if not custom and 0 <= index < len(CELL_PRESETS):
            width, height = CELL_PRESETS[index][1]
            with _blocked(self.width, self.height):
                self.width.setValue(width)
                self.height.setValue(height)
        self.changed.emit()

    def _on_dither(self, _index: int) -> None:
        self.dither_warning.setVisible(self.dither.currentData() == "floyd")
        self.changed.emit()

    def load(self, profile: OutputProfile) -> None:
        with _blocked(self.enabled, self.preset, self.width, self.height, self.binary_alpha,
                      self.threshold, self.defringe, self.palette_size, self.dither,
                      self.palette_lock, self.upscale_small):
            self.enabled.setChecked(profile.enabled)
            match = next((i for i, (_l, size) in enumerate(CELL_PRESETS)
                          if tuple(size) == tuple(profile.cell_size)), None)
            self.preset.setCurrentIndex(match if match is not None else self.preset.count() - 1)
            self.width.setValue(int(profile.cell_size[0]))
            self.height.setValue(int(profile.cell_size[1]))
            self.width.setEnabled(match is None)
            self.height.setEnabled(match is None)
            self.binary_alpha.setChecked(profile.binary_alpha)
            self.threshold.setValue(int(profile.alpha_threshold))
            self.defringe.setValue(int(profile.defringe_px))
            self.palette_size.setValue(int(profile.palette_size or 0))
            self.dither.setCurrentIndex(max(0, self.dither.findData(profile.dither)))
            self.dither_warning.setVisible(profile.dither == "floyd")
            self.palette_lock.setChecked(profile.palette_lock)
            self.upscale_small.setChecked(bool(getattr(profile, "upscale_small", False)))

    def store(self, profile: OutputProfile) -> None:
        profile.enabled = self.enabled.isChecked()
        profile.cell_size = (self.width.value(), self.height.value())
        profile.binary_alpha = self.binary_alpha.isChecked()
        profile.alpha_threshold = self.threshold.value()
        profile.defringe_px = self.defringe.value()
        profile.palette_size = self.palette_size.value() or None
        profile.dither = self.dither.currentData()
        profile.palette_lock = self.palette_lock.isChecked()
        profile.upscale_small = self.upscale_small.isChecked()


class ProcessingPanel(WorkerHost, QWidget):
    """Settings groups + Run pipeline / Preview key / Export buttons.

    `WorkerHost` (5a) owns the one long-running SpriteWorker; `start_job` refuses a
    second job while one runs, and `shutdown()` cancels and joins it.
    """

    pipelineFinished = Signal(str)
    settingsChanged = Signal()
    logMessage = Signal(str, str)
    exportRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project: Optional[SpriteProject] = None
        self._action: Optional[ActionCard] = None
        self._probe: Optional[Dict[str, Any]] = None
        self._probe_path: Optional[Path] = None
        self._worker: Optional[SpriteWorker] = None
        self._probe_worker: Optional[SpriteWorker] = None
        self._view: Optional[PixelView] = None
        self._loading = False
        self.profile_editors: Dict[str, ProfileEditor] = {}
        self._build()
        self._primary = bind_primary_action(self, self.run_pipeline,
                                            context=Qt.WidgetWithChildrenShortcut)
        self.refresh_backends()
        self._sync_enabled()

    # ----- UI ---------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        self._body_layout = QVBoxLayout(body)
        self._body_layout.addWidget(self._build_extraction())
        self._body_layout.addWidget(self._build_key())
        self.profiles_box = QGroupBox("Output profiles")
        self.profiles_layout = QVBoxLayout(self.profiles_box)
        self._body_layout.addWidget(self.profiles_box)
        self._body_layout.addWidget(self._build_stabilize())
        self._body_layout.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        outer.addWidget(self._build_actions())

    def _build_extraction(self) -> QGroupBox:
        box = QGroupBox("Extraction")
        form = QFormLayout(box)
        self.extract_mode = _combo(EXTRACT_MODES, {"every_n": "every N frames",
                                                   "target_fps": "target fps",
                                                   "exact_n": "exactly N frames"})
        form.addRow("Mode:", self.extract_mode)
        self.every_n = QSpinBox()
        self.every_n.setRange(1, 120)
        form.addRow("Every N:", self.every_n)
        self.target_fps = QSpinBox()
        self.target_fps.setRange(1, 60)
        form.addRow("Target fps:", self.target_fps)
        self.exact_n = QSpinBox()
        self.exact_n.setRange(1, 512)
        form.addRow("Exact N:", self.exact_n)
        self.trim_start = QDoubleSpinBox()
        self.trim_start.setRange(0.0, 600.0)
        self.trim_start.setSuffix(" s")
        self.trim_end = QDoubleSpinBox()
        self.trim_end.setRange(0.0, 600.0)
        self.trim_end.setSuffix(" s")
        trim_row = QHBoxLayout()
        trim_row.addWidget(self.trim_start)
        trim_row.addWidget(QLabel("to"))
        trim_row.addWidget(self.trim_end)
        form.addRow("Trim:", trim_row)
        self.cull = QCheckBox("Cull duplicate frames")
        self.cull_threshold = QDoubleSpinBox()
        self.cull_threshold.setRange(0.0, 1.0)
        self.cull_threshold.setSingleStep(0.01)
        self.cull_threshold.setDecimals(3)
        cull_row = QHBoxLayout()
        cull_row.addWidget(self.cull)
        cull_row.addWidget(self.cull_threshold)
        form.addRow("Duplicates:", cull_row)
        self.estimate_label = QLabel("yields ~? frames")
        self.estimate_label.setStyleSheet("font-weight: bold;")
        form.addRow("Estimate:", self.estimate_label)

        self.extract_mode.currentIndexChanged.connect(self._on_changed)
        for spin in (self.every_n, self.target_fps, self.exact_n, self.trim_start,
                     self.trim_end, self.cull_threshold):
            spin.valueChanged.connect(self._on_changed)
        self.cull.toggled.connect(self._on_changed)
        return box

    def _build_key(self) -> QGroupBox:
        box = QGroupBox("Key / matte")
        form = QFormLayout(box)
        self.key_method = _combo(KEY_METHODS, {"chroma": "chroma key", "ml": "ML matte",
                                               "none": "none (source has alpha)"})
        form.addRow("Method:", self.key_method)
        self.key_color_edit = QLineEdit()
        self.key_color_edit.setPlaceholderText("plate color")
        self.key_color_edit.setToolTip("#RRGGBB; empty = the project's plate color")
        self.pick_btn = QPushButton("Pick…")
        self.pick_btn.setAutoDefault(False)
        self.pick_btn.setToolTip("Click a pixel in the preview to pick the key color")
        self.pick_btn.clicked.connect(self.pick_key_color)
        color_row = QHBoxLayout()
        color_row.addWidget(self.key_color_edit, 1)
        color_row.addWidget(self.pick_btn)
        form.addRow("Key color:", color_row)
        self.tolerance = QSlider(Qt.Horizontal)
        self.tolerance.setRange(0, 100)
        self.tolerance_label = QLabel("0.20")
        tol_row = QHBoxLayout()
        tol_row.addWidget(self.tolerance, 1)
        tol_row.addWidget(self.tolerance_label)
        form.addRow("Tolerance:", tol_row)
        self.softness = QSlider(Qt.Horizontal)
        self.softness.setRange(0, 100)
        self.softness_label = QLabel("0.10")
        soft_row = QHBoxLayout()
        soft_row.addWidget(self.softness, 1)
        soft_row.addWidget(self.softness_label)
        form.addRow("Softness:", soft_row)
        self.despill = _combo(DESPILL_MODES)
        form.addRow("Despill:", self.despill)
        self.decontaminate = QCheckBox("Edge decontaminate")
        form.addRow(self.decontaminate)
        self.choke = QSpinBox()
        self.choke.setRange(0, 16)
        self.feather = QSpinBox()
        self.feather.setRange(0, 16)
        self.despeckle = QSpinBox()
        self.despeckle.setRange(0, 16)
        edge_row = QHBoxLayout()
        for label, spin in (("choke", self.choke), ("feather", self.feather), ("despeckle", self.despeckle)):
            edge_row.addWidget(QLabel(label))
            edge_row.addWidget(spin)
        form.addRow("Edges (px):", edge_row)
        self.ml_backend = _combo(ML_BACKENDS)
        self.ml_model = QComboBox()
        for model, info in REMBG_MODELS.items():
            suffix = "" if info.get("default_ok", True) else " (non-commercial)"
            self.ml_model.addItem(f"{model}{suffix}", model)
        self.ml_refine = QCheckBox("Refine edges")
        self.ml_status = QLabel("")
        self.install_btn = QPushButton("Install…")
        self.install_btn.setAutoDefault(False)
        self.install_btn.clicked.connect(self.open_install_dialog)
        ml_row = QHBoxLayout()
        ml_row.addWidget(self.ml_backend)
        ml_row.addWidget(self.ml_model, 1)
        ml_row.addWidget(self.ml_refine)
        ml_row.addWidget(self.install_btn)
        form.addRow("ML backend:", ml_row)
        form.addRow("", self.ml_status)

        self.key_method.currentIndexChanged.connect(self._on_changed)
        self.key_color_edit.textChanged.connect(self._on_changed)
        self.tolerance.valueChanged.connect(lambda v: self.tolerance_label.setText(f"{v / 100:.2f}"))
        self.softness.valueChanged.connect(lambda v: self.softness_label.setText(f"{v / 100:.2f}"))
        self.tolerance.valueChanged.connect(self._on_changed)
        self.softness.valueChanged.connect(self._on_changed)
        self.despill.currentIndexChanged.connect(self._on_changed)
        self.decontaminate.toggled.connect(self._on_changed)
        for spin in (self.choke, self.feather, self.despeckle):
            spin.valueChanged.connect(self._on_changed)
        self.ml_backend.currentIndexChanged.connect(self._on_changed)
        self.ml_model.currentIndexChanged.connect(self._on_changed)
        self.ml_refine.toggled.connect(self._on_changed)
        return box

    def _build_stabilize(self) -> QGroupBox:
        box = QGroupBox("Stabilize")
        form = QFormLayout(box)
        self.anchor = _combo(ANCHORS)
        form.addRow("Anchor:", self.anchor)
        self.dejitter = QCheckBox("De-jitter")
        self.dejitter_method = _combo(DEJITTER_METHODS)
        jitter_row = QHBoxLayout()
        jitter_row.addWidget(self.dejitter)
        jitter_row.addWidget(self.dejitter_method, 1)
        form.addRow("Jitter:", jitter_row)
        self.pad = QSpinBox()
        self.pad.setRange(0, 256)
        form.addRow("Pad (px):", self.pad)
        self.anchor.currentIndexChanged.connect(self._on_changed)
        self.dejitter.toggled.connect(self._on_changed)
        self.dejitter_method.currentIndexChanged.connect(self._on_changed)
        self.pad.valueChanged.connect(self._on_changed)
        return box

    def _build_actions(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.force_check = QCheckBox("Force re-run")
        self.force_check.setToolTip("Ignore the stage cache and re-run every stage")
        row.addWidget(self.force_check)
        row.addStretch()
        self.preview_btn = QPushButton("Preview key on clip")
        self.preview_btn.setToolTip("Write an ffmpeg chromakey preview of the clip and open it")
        self.preview_btn.clicked.connect(self.preview_key_on_clip)
        self.export_btn = QPushButton("Export…")
        self.export_btn.setToolTip("Open the export dialog")
        self.export_btn.clicked.connect(self.exportRequested.emit)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel)
        self.cancel_btn.setEnabled(False)
        self.run_btn = QPushButton("Run pipeline")
        self.run_btn.setToolTip("Run the processing pipeline for the selected action (Ctrl+Enter)")
        self.run_btn.clicked.connect(self.run_pipeline)
        for button in (self.preview_btn, self.export_btn, self.cancel_btn, self.run_btn):
            button.setAutoDefault(False)
            row.addWidget(button)
        layout.addLayout(row)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)
        return panel

    # ----- binding ----------------------------------------------------
    def set_project(self, project: Optional[SpriteProject]) -> None:
        self._project = project
        self._load_from_project()
        self._sync_enabled()

    def project(self) -> Optional[SpriteProject]:
        return self._project

    def set_action(self, action: Optional[ActionCard]) -> None:
        self._action = action
        self._probe = None
        self._probe_path = None
        self._sync_enabled()
        self._update_estimate()
        clip = getattr(action, "clip", None) if action is not None else None
        if clip is not None and getattr(clip, "path", None):
            self._probe_clip(Path(clip.path))

    def action(self) -> Optional[ActionCard]:
        return self._action

    def attach_pixel_view(self, view: PixelView) -> None:
        if self._view is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                self._view.colorPicked.disconnect(self._on_color_picked)
        self._view = view
        view.colorPicked.connect(self._on_color_picked)

    def set_probe(self, probe: Optional[Dict[str, Any]]) -> None:
        self._probe = dict(probe) if probe else None
        self._update_estimate()

    def estimate_text(self) -> str:
        return self.estimate_label.text()

    def _load_from_project(self) -> None:
        project = self._project
        for editor in self.profile_editors.values():
            self.profiles_layout.removeWidget(editor)
            editor.setParent(None)
            editor.deleteLater()
        self.profile_editors = {}
        if project is None:
            self._update_estimate()
            return
        self._loading = True
        try:
            ex = project.extraction
            with _blocked(self.extract_mode, self.every_n, self.target_fps, self.exact_n,
                          self.trim_start, self.trim_end, self.cull, self.cull_threshold):
                self.extract_mode.setCurrentIndex(max(0, self.extract_mode.findData(ex.mode)))
                self.every_n.setValue(int(ex.every_n))
                self.target_fps.setValue(int(ex.target_fps))
                self.exact_n.setValue(int(ex.exact_n))
                self.trim_start.setValue(float(ex.trim_start_s))
                self.trim_end.setValue(float(ex.trim_end_s))
                self.cull.setChecked(bool(ex.cull_duplicates))
                self.cull_threshold.setValue(float(ex.duplicate_threshold))
            key = project.key
            with _blocked(self.key_method, self.key_color_edit, self.tolerance, self.softness,
                          self.despill, self.decontaminate, self.choke, self.feather,
                          self.despeckle, self.ml_backend, self.ml_model, self.ml_refine):
                self.key_method.setCurrentIndex(max(0, self.key_method.findData(key.method)))
                self.key_color_edit.setText(key.key_color or "")
                self.tolerance.setValue(int(round(key.tolerance * 100)))
                self.softness.setValue(int(round(key.softness * 100)))
                self.tolerance_label.setText(f"{key.tolerance:.2f}")
                self.softness_label.setText(f"{key.softness:.2f}")
                self.despill.setCurrentIndex(max(0, self.despill.findData(key.despill)))
                self.decontaminate.setChecked(bool(key.edge_decontaminate))
                self.choke.setValue(int(key.choke_px))
                self.feather.setValue(int(key.feather_px))
                self.despeckle.setValue(int(key.despeckle_px))
                self.ml_backend.setCurrentIndex(max(0, self.ml_backend.findData(key.ml_backend)))
                self.ml_model.setCurrentIndex(max(0, self.ml_model.findData(key.ml_model)))
                self.ml_refine.setChecked(bool(key.ml_refine_edges))
            st = project.stabilize
            with _blocked(self.anchor, self.dejitter, self.dejitter_method, self.pad):
                self.anchor.setCurrentIndex(max(0, self.anchor.findData(st.anchor)))
                self.dejitter.setChecked(bool(st.dejitter))
                self.dejitter_method.setCurrentIndex(max(0, self.dejitter_method.findData(st.dejitter_method)))
                self.pad.setValue(int(st.pad_px))
            for profile in project.profiles:
                editor = ProfileEditor(profile.name)
                editor.load(profile)
                editor.changed.connect(self._on_changed)
                editor.rebuildRequested.connect(self.rebuild_palette_for)
                self.profiles_layout.addWidget(editor)
                self.profile_editors[profile.name] = editor
        finally:
            self._loading = False
        self._update_estimate()

    def _key_color_value(self) -> Optional[str]:
        text = self.key_color_edit.text().strip()
        if not text:
            return None
        if HEX_RE.match(text):
            return text.upper()
        logger.warning("Processing panel: invalid key color %r ignored", text)
        return None

    def _write_back(self) -> None:
        project = self._project
        if project is None:
            return
        ex = project.extraction
        ex.mode = self.extract_mode.currentData()
        ex.every_n = self.every_n.value()
        ex.target_fps = self.target_fps.value()
        ex.exact_n = self.exact_n.value()
        ex.trim_start_s = self.trim_start.value()
        ex.trim_end_s = self.trim_end.value()
        ex.cull_duplicates = self.cull.isChecked()
        ex.duplicate_threshold = self.cull_threshold.value()
        key = project.key
        key.method = self.key_method.currentData()
        key.key_color = self._key_color_value()
        key.tolerance = self.tolerance.value() / 100.0
        key.softness = self.softness.value() / 100.0
        key.despill = self.despill.currentData()
        key.edge_decontaminate = self.decontaminate.isChecked()
        key.choke_px = self.choke.value()
        key.feather_px = self.feather.value()
        key.despeckle_px = self.despeckle.value()
        key.ml_backend = self.ml_backend.currentData()
        key.ml_model = self.ml_model.currentData()
        key.ml_refine_edges = self.ml_refine.isChecked()
        st = project.stabilize
        st.anchor = self.anchor.currentData()
        st.dejitter = self.dejitter.isChecked()
        st.dejitter_method = self.dejitter_method.currentData()
        st.pad_px = self.pad.value()
        for profile in project.profiles:
            editor = self.profile_editors.get(profile.name)
            if editor is not None:
                editor.store(profile)

    def _on_changed(self, *_args) -> None:
        if self._loading or self._project is None:
            return
        self._write_back()
        self.settingsChanged.emit()
        self._update_estimate()

    # ----- readouts ---------------------------------------------------
    def _update_estimate(self) -> None:
        if self._project is None or self._probe is None:
            self.estimate_label.setText("yields ~? frames (no clip probed)")
            return
        try:
            count = estimate_frame_count(self._probe, self._project.extraction)
        except Exception as exc:
            logger.warning("Frame estimate failed: %s", exc)
            self.estimate_label.setText("yields ~? frames")
            return
        self.estimate_label.setText(f"yields ~{count} frames")

    def refresh_backends(self) -> None:
        try:
            available = available_backends()
        except Exception as exc:
            logger.error("available_backends failed: %s", exc, exc_info=True)
            available = {}
        parts = []
        for name in ML_BACKENDS:
            ok = bool(available.get(name, False))
            parts.append(f"{name}: {'installed' if ok else 'not installed'}")
        self.ml_status.setText("; ".join(parts))
        self.install_btn.setVisible(not all(available.get(n, False) for n in ML_BACKENDS))

    def _sync_enabled(self) -> None:
        ready = self._project is not None and self._action is not None and not self.is_busy()
        self.run_btn.setEnabled(ready)
        self.preview_btn.setEnabled(ready)
        self.export_btn.setEnabled(self._project is not None and not self.is_busy())
        self._primary.set_enabled(ready) if hasattr(self, "_primary") else None

    # ----- user actions -----------------------------------------------
    def pick_key_color(self) -> None:
        if self._view is None:
            self._warn("Pick key color", "No preview is attached.")
            return
        self._view.set_pick_mode(True)
        self.logMessage.emit("Click a pixel in the preview to pick the key color.", "INFO")

    def _on_color_picked(self, color: str) -> None:
        self.key_color_edit.setText(color)
        self.logMessage.emit(f"Key color set to {color}", "INFO")

    def open_install_dialog(self) -> None:
        dialog = SpriteMLInstallDialog(self)
        dialog.installFinished.connect(lambda ok: self.refresh_backends())
        dialog.exec()
        self.refresh_backends()

    def run_pipeline(self) -> None:
        project, action = self._project, self._action
        if project is None or action is None:
            self._warn("Run pipeline", "Select an action card first.")
            return
        self._write_back()
        force = self.force_check.isChecked()

        def job(progress, token):
            return run_pipeline(project, action, upto="pixel", progress=progress,
                                token=token, force=force)

        self.logMessage.emit(f"Run pipeline: action '{action.name}' (force={force})", "INFO")
        self._start(job, lambda result: self._pipeline_done(action, result), "Pipeline")

    def _pipeline_done(self, action: ActionCard, result: Any) -> None:
        stages = ", ".join(f"{k}={len(v)}" for k, v in (result or {}).items())
        self.logMessage.emit(f"Pipeline finished for '{action.name}': {stages or 'no output'}", "SUCCESS")
        self._log_pixel_warnings(action)
        self.pipelineFinished.emit(action.id)

    def _log_pixel_warnings(self, action: ActionCard) -> None:
        """Surface the pixel stage's warnings from stages/<id>/pixel/pixel.json (sub-project 4)."""
        project = self._project
        if project is None:
            return
        report = stage_dir(project, action, "pixel") / "pixel.json"
        if not report.exists():
            return
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Cannot read %s: %s", report, exc)
            return
        for warning in data.get("warnings") or []:
            logger.warning("Pixel stage (%s): %s", action.name, warning)
            self.logMessage.emit(f"Pixel profile: {warning}", "WARNING")

    def cancel(self) -> None:
        if self.is_busy():
            self.cancel_running()
            self.logMessage.emit("Cancel requested…", "WARNING")

    def preview_key_on_clip(self) -> None:
        project, action = self._project, self._action
        if project is None or action is None:
            self._warn("Preview key", "Select an action card first.")
            return
        clip = getattr(action, "clip", None)
        if clip is None or not getattr(clip, "path", None):
            self._warn("Preview key", "This action has no clip. Render or import one first.")
            return
        self._write_back()
        key = project.key
        color = key.key_color or project.plate_color
        video = Path(clip.path)
        out_mp4 = stage_dir(project, action, "key") / "preview_chromakey.mp4"

        def job(progress, token):
            progress("key", 0, 0, "ffmpeg chromakey preview")
            out_mp4.parent.mkdir(parents=True, exist_ok=True)
            return ffmpeg_chromakey_preview(video, out_mp4, color, key.tolerance, key.softness)

        self.logMessage.emit(f"Chroma preview: {video.name} key={color}", "INFO")
        self._start(job, self._preview_done, "Chroma preview")

    def _preview_done(self, result: Any) -> None:
        path = Path(result)
        self.logMessage.emit(f"Chroma preview written: {path}", "SUCCESS")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def rebuild_palette_for(self, profile_name: str) -> None:
        project, action = self._project, self._action
        if project is None or action is None:
            self._warn("Rebuild palette", "Select an action card first.")
            return
        profile = next((p for p in project.profiles if p.name == profile_name), None)
        if profile is None:
            self._warn("Rebuild palette", f"Unknown profile '{profile_name}'.")
            return
        self._write_back()

        # Sub-project 4 contract: `locked_palette` is part of the pixel-stage fingerprint.
        # Clearing it and re-running the pipeline makes `ensure_palette` rebuild the palette
        # from the fitted binary-alpha frames — the same frames the quantizer uses.
        profile.locked_palette = None
        self.logMessage.emit(f"Palette lock cleared for '{profile.name}'; re-running the pipeline", "INFO")
        force = self.force_check.isChecked()

        def job(progress, token):
            return run_pipeline(project, action, upto="pixel", progress=progress,
                                token=token, force=force)

        self._start(job, lambda result: self._palette_done(action, profile, result), "Rebuild palette")

    def _palette_done(self, action: ActionCard, profile: OutputProfile, result: Any) -> None:
        colors = list(profile.locked_palette or [])
        self.logMessage.emit(f"Palette rebuilt for '{profile.name}': {len(colors)} colors", "SUCCESS")
        self._log_pixel_warnings(action)
        self.pipelineFinished.emit(action.id)

    # ----- worker plumbing (WorkerHost: one SpriteWorker at a time) ---
    def _start(self, job: Callable, on_done: Callable[[Any], None], label: str) -> bool:
        worker = self.start_job(job, label=label,
                                on_finished=lambda result: self._on_done(on_done, result),
                                on_failed=self._on_failed, on_cancelled=self._on_cancelled,
                                on_progress=self._on_progress)
        if worker is None:
            self._warn(label, "Wait for the current job to finish.")
            return False
        self._set_running(True, label)
        return True

    def _set_running(self, running: bool, label: str = "") -> None:
        self.progress_bar.setVisible(running)
        self.progress_label.setVisible(running)
        self.cancel_btn.setEnabled(running)
        if running:
            self.progress_bar.setRange(0, 0)
            self.progress_label.setText(f"{label}…")
        self._sync_enabled()

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(done)
        else:
            self.progress_bar.setRange(0, 0)
        self.progress_label.setText(f"{stage}: {message}")
        self.logMessage.emit(f"[{stage}] {done}/{total} {message}", "INFO")

    def _on_done(self, on_done: Callable[[Any], None], result: Any) -> None:
        self._worker = None
        self._set_running(False)
        try:
            on_done(result)
        except Exception as exc:
            logger.error("Sprite job completion handler failed: %s", exc, exc_info=True)
            self.logMessage.emit(f"Error: {exc}", "ERROR")
            QMessageBox.critical(self, "Sprite processing", str(exc))

    def _on_failed(self, message: str) -> None:
        self._worker = None
        self._set_running(False)
        logger.error("Sprite job failed: %s", message)
        self.logMessage.emit(f"Failed: {message}", "ERROR")
        QMessageBox.critical(self, "Sprite processing failed", message)

    def _on_cancelled(self) -> None:
        self._worker = None
        self._set_running(False)
        logger.info("Sprite job cancelled")
        self.logMessage.emit("Cancelled.", "WARNING")

    def _probe_clip(self, path: Path) -> None:
        if self._probe_worker is not None and self._probe_worker.isRunning():
            return
        self._probe_path = path
        worker = SpriteWorker(lambda progress, token: probe_video(path), label="probe")
        worker.finished.connect(self._probe_done)
        worker.failed.connect(lambda msg: logger.warning("ffprobe failed for %s: %s", path, msg))
        self._probe_worker = worker
        worker.start()

    def _probe_done(self, result: Any) -> None:
        self._probe_worker = None
        if isinstance(result, dict):
            self.set_probe(result)

    def shutdown(self, timeout_ms: int = 5000) -> None:
        super().shutdown(timeout_ms)          # WorkerHost: cancel + join the main worker
        probe = self._probe_worker
        if probe is not None and probe.isRunning():
            probe.cancel()
            probe.wait(timeout_ms)
        self._probe_worker = None

    def _warn(self, title: str, message: str) -> None:
        logger.warning("%s: %s", title, message)
        self.logMessage.emit(f"{title}: {message}", "WARNING")
        QMessageBox.warning(self, title, message)
```

- [ ] Run → 17 passed.
- [ ] Commit:

```
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/processing_panel.py tests/sprite/gui/test_processing_panel.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): ProcessingPanel with settings groups, worker-run pipeline, chroma preview"
```

---

### Task 7: `ExportDialog` with pluggable formats and purge-after-export

**Files:**
- Create: `tests/sprite/gui/test_export_dialog.py`
- Create: `gui/sprite/export_dialog.py`

**Interfaces:**
- Consumes: `GridOptions`, `export_grid` (`core/sprite/exporters/grid.py`; writes its Aseprite
  sidecar at `<png>.json`); `export_aseprite_json`, `export_texturepacker_json`,
  `export_png_sequence`, `export_gif`; `SheetMeta`; `CancelToken`, `ProgressFn`;
  `SpriteProject.sheet_meta(profile)`, `SpriteProject.purge_intermediates()`;
  `gui.sprite.prefs` (`purge_after_export_enabled`, `set_purge_after_export`, `confirm_purge`);
  `SpriteWorker` (signals `progress`, `finished`, `failed`, `cancelled`); `DialogStatusConsole`;
  `get_data_paths().sprite_projects()`.
- Produces (the surface sub-project 6 consumes is marked ★):
  - `DEFAULT_TEMPLATE = "{title}_{tag}_{frame01}.png"`, `SETTINGS_PREFIX = "sprite/export/"`
  - `FormatFn = Callable[[SheetMeta, Path], List[Path]]` ★ — `fn(meta, out_dir)`; `out_dir` is
    `<out_dir>/<profile>/`. **Contract:** when the format was registered with `needs_sheet=True`
    (or any other selected format was), `run_export` has already called `export_grid`, so `fn`
    receives `meta` with `frame` rects and `sheet_size` filled and the sheet PNG already exists at
    `sheet_png_path(meta, out_dir)` (with its `<png>.json` Aseprite sidecar). A format registered
    without `needs_sheet` may receive unfilled rects when it runs alone.
  - `@dataclass ExportFormat(id, label, fn, needs_sheet: bool = False, takes_template: bool = False)`
  - `BUILTIN_FORMATS` with ids `grid`, `aseprite_json`, `texturepacker_json`, `png_sequence`, `gif`
    (the ids sub-project 6's `FORMAT_IDS` / engine presets select)
  - `@dataclass ExportRequest(project, profiles, formats, out_dir, template, grid, pivot: Optional[Tuple[float, float]], purge)`
  - `sheet_png_path(meta, out_dir) -> Path` = `out_dir / f"{meta.title}_{meta.profile}.png"`
  - `parse_scales(text) -> Tuple[int, ...]`; `default_export_dir(project) -> Path`
  - `run_export(request, formats, *, log, progress, token) -> List[Path]` (no Qt; runs in the worker)
  - `ExportDialog(WorkerHost, DialogCleanupMixin, QDialog)` (export runs through `start_job`;
    QSettings keys go through `prefs.get_pref` / `prefs.set_pref`, splitter state through
    `prefs.sprite_settings()`):
    - `exported = Signal(list)`, `logMessage = Signal(str, str)`
    - `notes_label: QLabel` ★ (word-wrapped, directly under the format list; sub-project 6 writes
      engine-preset notes and fps-reconciliation text there)
    - `__init__(project, parent=None)`
    - `register_format(id, label, fn, *, needs_sheet=False, takes_template=False, checked=False) -> QCheckBox` ★
    - `format_checks: Dict[str, QCheckBox]` ★, `profile_checks: Dict[str, QCheckBox]`
    - `options_layout: QVBoxLayout` ★ (sub-project 6 adds its engine-preset box here)
    - `set_grid_options(opts: GridOptions)` ★, `grid_options() -> GridOptions`
    - `pivot_x_spin`, `pivot_y_spin: QDoubleSpinBox` ★ (0..1; applied to every exported frame)
    - `name_template_edit: QLineEdit` ★
    - `current_meta() -> Optional[SheetMeta]` ★ (first selected profile, unfilled rects)
    - `formats()`, `selected_formats()`, `selected_profiles()`, `request()`, `start_export()`
      (Ctrl+Enter, default button), `is_running()`
    - widgets: `out_dir_edit`, `browse_btn`, `columns`, `border`, `shape`, `inner`, `extrude`,
      `power_of_two`, `scales_edit`, `purge_check`, `progress_bar`, `console`, `export_btn`, `close_btn`

**Steps:**

- [ ] Write the failing test `tests/sprite/gui/test_export_dialog.py`:

```python
import time
from pathlib import Path

import pytest
from PySide6.QtTest import QTest

import gui.sprite.export_dialog as ed
from core.sprite.exporters.grid import GridOptions
from core.sprite.pipeline import CancelToken, no_progress
from core.sprite.project import SpriteProject
from gui.sprite.export_dialog import (BUILTIN_FORMATS, DEFAULT_TEMPLATE, ExportDialog,
                                      ExportRequest, parse_scales, run_export, sheet_png_path)
from gui_synthetic import make_project, sheet_from_action


def _wait_idle(dialog, timeout_s=10.0):
    deadline = time.monotonic() + timeout_s
    while dialog.is_running() and time.monotonic() < deadline:
        QTest.qWait(20)
    QTest.qWait(20)
    assert not dialog.is_running(), "export worker did not finish"


@pytest.fixture
def project(tmp_path, monkeypatch):
    project, _action = make_project(tmp_path)
    monkeypatch.setattr(SpriteProject, "sheet_meta",
                        lambda self, profile: sheet_from_action(self.actions[0], profile))
    monkeypatch.setattr(ed.prefs, "purge_after_export_enabled", lambda: False)
    monkeypatch.setattr(ed.prefs, "set_purge_after_export", lambda value: None)
    monkeypatch.setattr(ed.prefs, "confirm_purge", lambda parent: True)
    return project


def _formats(*ids):
    return [f for f in BUILTIN_FORMATS if f.id in ids]


def _request(project, tmp_path, profiles, formats, **kw):
    base = dict(project=project, profiles=profiles, formats=formats, out_dir=tmp_path / "out",
                template=DEFAULT_TEMPLATE, grid=GridOptions(), pivot=None, purge=False)
    base.update(kw)
    return ExportRequest(**base)


def test_parse_scales():
    assert parse_scales("1,2,4") == (1, 2, 4)
    assert parse_scales(" 2 ") == (2,)
    assert parse_scales("") == (1,)
    assert parse_scales("x,0,-1") == (1,)


def test_builtin_formats_registered_in_order(qapp, project):
    dialog = ExportDialog(project)
    assert dialog.formats() == ["grid", "aseprite_json", "texturepacker_json", "png_sequence", "gif"]
    assert set(dialog.profile_checks) == {p.name for p in project.profiles}
    assert dialog.options_layout is not None
    assert dialog.notes_label.wordWrap() and dialog.notes_label.text() == ""
    dialog.done(0)


def test_register_format_adds_checkbox_and_id(qapp, project):
    dialog = ExportDialog(project)
    box = dialog.register_format("godot_tres", "Godot 4 SpriteFrames (.tres)", lambda meta, out_dir: [])
    assert "godot_tres" in dialog.formats()
    assert box.text() == "Godot 4 SpriteFrames (.tres)"
    assert dialog.format_checks["godot_tres"] is box
    assert "godot_tres" not in dialog.selected_formats()
    box.setChecked(True)
    assert "godot_tres" in dialog.selected_formats()
    with pytest.raises(ValueError):
        dialog.register_format("grid", "dup", lambda meta, out_dir: [])
    dialog.done(0)


def test_run_export_png_sequence_writes_files(project, tmp_path):
    logs = []
    req = _request(project, tmp_path, ["hd"], ["png_sequence"])
    files = run_export(req, _formats("png_sequence"), log=logs.append,
                       progress=no_progress, token=CancelToken())
    assert len(files) == 4
    assert all(Path(p).exists() for p in files)
    assert all(str(p).startswith(str(tmp_path / "out" / "hd")) for p in files)
    assert any("Wrote" in line for line in logs)


def test_run_export_grid_writes_sheet_and_json_sidecar(project, tmp_path):
    req = _request(project, tmp_path, ["hd"], ["grid"], grid=GridOptions(columns=2))
    files = run_export(req, _formats("grid"), log=lambda m: None,
                       progress=no_progress, token=CancelToken())
    names = sorted(Path(p).name for p in files)
    assert names == ["walk_hd.json", "walk_hd.png"]
    assert (tmp_path / "out" / "hd" / "walk_hd.png").stat().st_size > 0


def test_run_export_sheet_written_once_for_sheet_formats(project, tmp_path):
    req = _request(project, tmp_path, ["hd"], ["grid", "aseprite_json", "texturepacker_json"])
    files = run_export(req, _formats("grid", "aseprite_json", "texturepacker_json"),
                       log=lambda m: None, progress=no_progress, token=CancelToken())
    names = sorted(Path(p).name for p in files)
    assert names == ["walk_hd.json", "walk_hd.png", "walk_hd.tp.json"]


def test_run_export_gif_per_tag(project, tmp_path):
    req = _request(project, tmp_path, ["pixel"], ["gif"])
    files = run_export(req, _formats("gif"), log=lambda m: None,
                       progress=no_progress, token=CancelToken())
    assert [Path(p).name for p in files] == ["walk_walk.gif"]


def test_run_export_applies_pivot_and_passes_filled_meta_to_plugins(project, tmp_path):
    seen = []

    def plugin(meta, out_dir):
        seen.append((meta.sheet_size, [f.pivot for f in meta.frames], out_dir))
        return []

    plugin_format = ed.ExportFormat("plugin", "Plugin", plugin, needs_sheet=True)
    req = _request(project, tmp_path, ["hd"], ["plugin"], pivot=(0.25, 0.75))
    run_export(req, [plugin_format], log=lambda m: None, progress=no_progress, token=CancelToken())
    sheet_size, pivots, out_dir = seen[0]
    assert sheet_size != (0, 0)
    assert pivots == [(0.25, 0.75)] * 4
    assert out_dir == tmp_path / "out" / "hd"
    assert sheet_png_path(project.sheet_meta("hd"), out_dir).exists()


def test_run_export_skips_profile_without_frames(project, tmp_path, monkeypatch):
    from core.sprite.models import SheetMeta
    monkeypatch.setattr(SpriteProject, "sheet_meta",
                        lambda self, profile: SheetMeta(title="empty", frames=[], tags=[], profile=profile))
    logs = []
    req = _request(project, tmp_path, ["hd"], ["png_sequence"])
    assert run_export(req, _formats("png_sequence"), log=logs.append,
                      progress=no_progress, token=CancelToken()) == []
    assert any("no frames" in line for line in logs)


def test_dialog_export_runs_worker_and_emits(qapp, project, tmp_path):
    dialog = ExportDialog(project)
    dialog.out_dir_edit.setText(str(tmp_path / "exp"))
    for fmt_id, box in dialog.format_checks.items():
        box.setChecked(fmt_id == "png_sequence")
    for name, box in dialog.profile_checks.items():
        box.setChecked(name == "hd")
    got = []
    dialog.exported.connect(got.append)
    dialog.start_export()
    _wait_idle(dialog)
    assert got and len(got[0]) == 4
    assert all(Path(p).exists() for p in got[0])
    assert "Export complete" in dialog.console.console.toPlainText()
    dialog.done(0)


def test_dialog_validates_selection(qapp, project, monkeypatch):
    dialog = ExportDialog(project)
    for box in dialog.format_checks.values():
        box.setChecked(False)
    shown = []
    monkeypatch.setattr(ed.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    dialog.start_export()
    assert shown and not dialog.is_running()
    dialog.done(0)


def test_set_grid_options_and_current_meta(qapp, project):
    dialog = ExportDialog(project)
    dialog.set_grid_options(GridOptions(columns=4, border_px=2, shape_px=3, inner_px=1,
                                        extrude_px=1, power_of_two=True, scales=(1, 2)))
    opts = dialog.grid_options()
    assert (opts.columns, opts.border_px, opts.shape_px, opts.inner_px, opts.extrude_px) == (4, 2, 3, 1, 1)
    assert opts.power_of_two is True and opts.scales == (1, 2)
    for name, box in dialog.profile_checks.items():
        box.setChecked(name == "pixel")
    meta = dialog.current_meta()
    assert meta is not None and meta.profile == "pixel" and len(meta.frames) == 4
    for box in dialog.profile_checks.values():
        box.setChecked(False)
    assert dialog.current_meta() is None
    dialog.pivot_x_spin.setValue(0.4)
    dialog.pivot_y_spin.setValue(0.9)
    assert dialog.request().pivot == (0.4, 0.9)
    dialog.done(0)


def test_purge_checkbox_requires_confirmation(qapp, project, monkeypatch):
    calls = []
    monkeypatch.setattr(ed.prefs, "set_purge_after_export", calls.append)
    monkeypatch.setattr(ed.prefs, "confirm_purge", lambda parent: False)
    dialog = ExportDialog(project)
    assert not dialog.purge_check.isChecked()
    dialog.purge_check.setChecked(True)
    assert not dialog.purge_check.isChecked()
    assert calls == []
    monkeypatch.setattr(ed.prefs, "confirm_purge", lambda parent: True)
    dialog.purge_check.setChecked(True)
    assert dialog.purge_check.isChecked()
    assert calls == [True]
    dialog.purge_check.setChecked(False)
    assert calls == [True, False]
    dialog.done(0)


def test_purge_runs_after_export_when_enabled(qapp, project, tmp_path, monkeypatch):
    monkeypatch.setattr(ed.prefs, "purge_after_export_enabled", lambda: True)
    purged = []
    monkeypatch.setattr(SpriteProject, "purge_intermediates", lambda self: purged.append(1) or 3)
    dialog = ExportDialog(project)
    assert dialog.purge_check.isChecked()
    dialog.out_dir_edit.setText(str(tmp_path / "exp"))
    for fmt_id, box in dialog.format_checks.items():
        box.setChecked(fmt_id == "png_sequence")
    dialog.start_export()
    _wait_idle(dialog)
    assert purged == [1]
    assert "Purged 3" in dialog.console.console.toPlainText()
    dialog.done(0)


def test_failed_export_is_logged_and_shown(qapp, project, tmp_path, monkeypatch):
    dialog = ExportDialog(project)
    dialog.out_dir_edit.setText(str(tmp_path / "exp"))
    for box in dialog.format_checks.values():
        box.setChecked(False)

    def boom(meta, out_dir):
        raise RuntimeError("disk full")

    dialog.register_format("boom", "Boom", boom, checked=True)
    shown = []
    monkeypatch.setattr(ed.QMessageBox, "critical", staticmethod(lambda *a, **k: shown.append(a)))
    dialog.start_export()
    _wait_idle(dialog)
    assert shown
    assert "disk full" in dialog.console.console.toPlainText()
    dialog.done(0)


def test_settings_round_trip(qapp, project, tmp_path):
    dialog = ExportDialog(project)
    dialog.out_dir_edit.setText(str(tmp_path / "keep"))
    dialog.name_template_edit.setText("{title}-{frame01}.png")
    dialog.columns.setValue(6)
    dialog.scales_edit.setText("1,2")
    dialog.format_checks["gif"].setChecked(True)
    dialog.done(0)  # persists
    again = ExportDialog(project)
    assert again.out_dir_edit.text() == str(tmp_path / "keep")
    assert again.name_template_edit.text() == "{title}-{frame01}.png"
    assert again.columns.value() == 6
    assert again.grid_options().scales == (1, 2)
    assert again.format_checks["gif"].isChecked()
    again.done(0)
```

- [ ] Run → fails on import.

- [ ] Implement `gui/sprite/export_dialog.py`:

```python
"""Sprite export dialog (design §4.5, §1.6).

Formats are plugins: `register_format(id, label, fn)` adds a checkbox and a
callable `fn(meta, out_dir) -> List[Path]`. The built-ins cover the sheet PNG,
Aseprite JSON, TexturePacker JSON, PNG sequence, and GIF; sub-project 6
registers Godot `.tres`, native `.aseprite`, and the engine presets. The
export runs in a SpriteWorker; when the sticky purge preference is on, the
intermediates go to the recycle bin afterwards through
`SpriteProject.purge_intermediates()`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from core.paths import get_data_paths
from core.sprite.exporters.aseprite_json import export_aseprite_json
from core.sprite.exporters.gif import export_gif
from core.sprite.exporters.grid import GridOptions, export_grid
from core.sprite.exporters.png_sequence import export_png_sequence
from core.sprite.exporters.texturepacker_json import export_texturepacker_json
from core.sprite.models import SheetMeta
from core.sprite.pipeline import CancelToken, ProgressFn
from core.sprite.project import SpriteProject
from gui.common.dialog_conventions import (DialogCleanupMixin, bind_primary_action,
                                           persist_splitter, restore_splitter,
                                           set_default_button, standard_splitter)
from gui.llm_utils import DialogStatusConsole

from . import prefs
from .workers import WorkerHost

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = "{title}_{tag}_{frame01}.png"
SETTINGS_PREFIX = "sprite/export/"
SPLITTER_KEY = SETTINGS_PREFIX + "splitter"

FormatFn = Callable[[SheetMeta, Path], List[Path]]


@dataclass
class ExportFormat:
    id: str
    label: str
    fn: FormatFn
    needs_sheet: bool = False        # runner writes the sheet PNG (frame rects filled) first
    takes_template: bool = False     # fn(meta, out_dir, template=...)


@dataclass
class ExportRequest:
    project: SpriteProject
    profiles: List[str]
    formats: List[str]
    out_dir: Path
    template: str
    grid: GridOptions
    pivot: Optional[Tuple[float, float]]
    purge: bool


def sheet_png_path(meta: SheetMeta, out_dir: Path) -> Path:
    return Path(out_dir) / f"{meta.title}_{meta.profile}.png"


def format_grid(meta: SheetMeta, out_dir: Path) -> List[Path]:
    """The sheet PNG; `export_grid` also writes `<png>.json` beside it (design gap 18)."""
    png = sheet_png_path(meta, out_dir)
    if tuple(meta.sheet_size) == (0, 0) or not png.exists():
        export_grid(meta, png, GridOptions())
    files = [png]
    sidecar = png.with_suffix(".json")
    if sidecar.exists():
        files.append(sidecar)
    return files


def format_aseprite_json(meta: SheetMeta, out_dir: Path) -> List[Path]:
    png = sheet_png_path(meta, out_dir)
    out = png.with_suffix(".json")
    export_aseprite_json(meta, out, image_name=png.name)
    return [out]


def format_texturepacker_json(meta: SheetMeta, out_dir: Path) -> List[Path]:
    png = sheet_png_path(meta, out_dir)
    out = Path(out_dir) / f"{meta.title}_{meta.profile}.tp.json"
    export_texturepacker_json(meta, out, image_name=png.name)
    return [out]


def format_png_sequence(meta: SheetMeta, out_dir: Path, template: str = DEFAULT_TEMPLATE) -> List[Path]:
    frames_dir = Path(out_dir) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    return [Path(p) for p in export_png_sequence(meta, frames_dir, template)]


def format_gif(meta: SheetMeta, out_dir: Path) -> List[Path]:
    if not meta.tags:
        logger.warning("GIF export (%s): the sheet has no tags; nothing written", meta.profile)
        return []
    files: List[Path] = []
    for tag in meta.tags:
        out = Path(out_dir) / f"{meta.title}_{tag.name}.gif"
        files.append(Path(export_gif(meta, tag, out, loop=tag.repeat)))
    return files


BUILTIN_FORMATS: Tuple[ExportFormat, ...] = (
    ExportFormat("grid", "Sprite sheet PNG (+ Aseprite JSON sidecar)", format_grid, needs_sheet=True),
    ExportFormat("aseprite_json", "Aseprite JSON", format_aseprite_json, needs_sheet=True),
    ExportFormat("texturepacker_json", "TexturePacker JSON", format_texturepacker_json, needs_sheet=True),
    ExportFormat("png_sequence", "PNG sequence (per tag)", format_png_sequence, takes_template=True),
    ExportFormat("gif", "Animated GIF (per tag)", format_gif),
)


def parse_scales(text: str) -> Tuple[int, ...]:
    values: List[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
        except ValueError:
            logger.warning("Export: ignored scale %r", part)
            return (1,)
        if value <= 0:
            return (1,)
        values.append(value)
    return tuple(values) or (1,)


def default_export_dir(project: SpriteProject) -> Path:
    base = project.project_dir if project.project_dir is not None else get_data_paths().sprite_projects() / project.name
    return Path(base) / "exports"


def run_export(request: ExportRequest, formats: Sequence[ExportFormat], *,
               log: Callable[[str], None], progress: ProgressFn,
               token: CancelToken) -> List[Path]:
    """Export every selected profile with every selected format. No Qt; runs in the worker."""
    written: List[Path] = []
    total = len(request.profiles)
    needs_sheet = any(fmt.needs_sheet for fmt in formats)

    def record(path: Path) -> None:
        path = Path(path)
        if path not in written:
            written.append(path)
            log(f"Wrote {path}")

    for index, profile in enumerate(request.profiles):
        token.raise_if_cancelled()
        meta = request.project.sheet_meta(profile)
        if not meta.frames:
            log(f"Profile '{profile}': no frames; skipped")
            continue
        if request.pivot is not None:
            for frame in meta.frames:
                frame.pivot = (float(request.pivot[0]), float(request.pivot[1]))
        out_dir = request.out_dir / profile
        out_dir.mkdir(parents=True, exist_ok=True)
        if needs_sheet:
            png = sheet_png_path(meta, out_dir)
            progress("export", index, total, f"{profile}: sheet")
            meta = export_grid(meta, png, request.grid)
            record(png)
            sidecar = png.with_suffix(".json")
            if sidecar.exists():
                record(sidecar)
        for fmt in formats:
            token.raise_if_cancelled()
            progress("export", index, total, f"{profile}: {fmt.label}")
            if fmt.takes_template:
                files = fmt.fn(meta, out_dir, template=request.template)
            else:
                files = fmt.fn(meta, out_dir)
            for path in files:
                record(Path(path))
    progress("export", total, total, "done")
    return written


class ExportDialog(WorkerHost, DialogCleanupMixin, QDialog):
    """Profiles × formats export with output dir, template, grid options, pivot, and purge."""

    exported = Signal(list)
    logMessage = Signal(str, str)

    def __init__(self, project: SpriteProject, parent=None):
        super().__init__(parent)
        self.project = project
        self.settings = prefs.sprite_settings()
        self._formats: Dict[str, ExportFormat] = {}
        self.format_checks: Dict[str, QCheckBox] = {}
        self.profile_checks: Dict[str, QCheckBox] = {}
        self._pending_purge = False
        self.setWindowTitle(f"Export sprites — {project.name}")
        self.setModal(True)
        self.setMinimumSize(660, 680)
        self._build()
        for fmt in BUILTIN_FORMATS:
            self.register_format(fmt.id, fmt.label, fmt.fn, needs_sheet=fmt.needs_sheet,
                                 takes_template=fmt.takes_template, checked=fmt.id == "grid")
        self._load_settings()
        self.logMessage.connect(self.console.log)
        self.purge_check.setChecked(prefs.purge_after_export_enabled())
        self.purge_check.toggled.connect(self._on_purge_toggled)
        set_default_button(self, self.export_btn)
        self._primary = bind_primary_action(self, self.start_export)

    # ----- UI ---------------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        top = QWidget()
        self.options_layout = QVBoxLayout(top)
        self.options_layout.setContentsMargins(0, 0, 0, 0)

        profiles_box = QGroupBox("Profiles")
        profiles_row = QHBoxLayout(profiles_box)
        for profile in self.project.profiles:
            box = QCheckBox(profile.name)
            box.setChecked(bool(profile.enabled))
            self.profile_checks[profile.name] = box
            profiles_row.addWidget(box)
        profiles_row.addStretch()
        self.options_layout.addWidget(profiles_box)

        self.formats_box = QGroupBox("Formats")
        self.formats_layout = QVBoxLayout(self.formats_box)
        self.options_layout.addWidget(self.formats_box)
        self.notes_label = QLabel("")            # engine-preset notes (sub-project 6 fills it)
        self.notes_label.setWordWrap(True)
        self.notes_label.setStyleSheet("color: #888;")
        self.options_layout.addWidget(self.notes_label)

        output_box = QGroupBox("Output")
        output_form = QFormLayout(output_box)
        self.out_dir_edit = QLineEdit(str(default_export_dir(self.project)))
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setAutoDefault(False)
        self.browse_btn.clicked.connect(self._browse)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.out_dir_edit, 1)
        dir_row.addWidget(self.browse_btn)
        output_form.addRow("Directory:", dir_row)
        self.name_template_edit = QLineEdit(DEFAULT_TEMPLATE)
        self.name_template_edit.setToolTip("PNG sequence file name: {title} {tag} {frame} {frame01}")
        output_form.addRow("Frame template:", self.name_template_edit)
        self.pivot_x_spin = QDoubleSpinBox()
        self.pivot_x_spin.setRange(0.0, 1.0)
        self.pivot_x_spin.setSingleStep(0.05)
        self.pivot_x_spin.setDecimals(2)
        self.pivot_x_spin.setValue(0.5)
        self.pivot_y_spin = QDoubleSpinBox()
        self.pivot_y_spin.setRange(0.0, 1.0)
        self.pivot_y_spin.setSingleStep(0.05)
        self.pivot_y_spin.setDecimals(2)
        self.pivot_y_spin.setValue(1.0)
        pivot_row = QHBoxLayout()
        pivot_row.addWidget(QLabel("x"))
        pivot_row.addWidget(self.pivot_x_spin)
        pivot_row.addWidget(QLabel("y"))
        pivot_row.addWidget(self.pivot_y_spin)
        pivot_row.addStretch()
        output_form.addRow("Pivot (normalized):", pivot_row)
        self.options_layout.addWidget(output_box)

        grid_box = QGroupBox("Sheet grid")
        grid_form = QFormLayout(grid_box)
        self.columns = QSpinBox()
        self.columns.setRange(0, 256)
        self.columns.setSpecialValueText("one row per tag")
        grid_form.addRow("Columns:", self.columns)
        self.border = QSpinBox()
        self.border.setRange(0, 64)
        self.shape = QSpinBox()
        self.shape.setRange(0, 64)
        self.shape.setValue(1)
        self.inner = QSpinBox()
        self.inner.setRange(0, 64)
        self.extrude = QSpinBox()
        self.extrude.setRange(0, 16)
        pad_row = QHBoxLayout()
        for label, spin in (("border", self.border), ("shape", self.shape),
                            ("inner", self.inner), ("extrude", self.extrude)):
            pad_row.addWidget(QLabel(label))
            pad_row.addWidget(spin)
        grid_form.addRow("Padding (px):", pad_row)
        self.power_of_two = QCheckBox("Power-of-two sheet")
        grid_form.addRow(self.power_of_two)
        self.scales_edit = QLineEdit("1")
        self.scales_edit.setToolTip("Integer nearest-neighbor copies, e.g. 1,2,4 → @2x/@4x")
        grid_form.addRow("Scales:", self.scales_edit)
        self.options_layout.addWidget(grid_box)

        self.purge_check = QCheckBox("Purge intermediates after export (clips/ and stages/ → recycle bin)")
        self.options_layout.addWidget(self.purge_check)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.options_layout.addWidget(self.progress_bar)

        self.console = DialogStatusConsole("Export log")
        self.splitter = standard_splitter(Qt.Vertical, self)
        self.splitter.addWidget(top)
        self.splitter.addWidget(self.console)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        if not restore_splitter(self.settings, SPLITTER_KEY, self.splitter):
            self.splitter.setSizes([500, 180])
        layout.addWidget(self.splitter, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.close_btn)
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self.start_export)
        buttons.addWidget(self.export_btn)
        layout.addLayout(buttons)

    # ----- format registry (sub-project 6 hook) -----------------------
    def register_format(self, id: str, label: str, fn: FormatFn, *, needs_sheet: bool = False,
                        takes_template: bool = False, checked: bool = False) -> QCheckBox:
        """Add an export format checkbox backed by `fn(meta, out_dir) -> List[Path]`.

        With `needs_sheet=True` the runner calls `export_grid` first: `fn` then receives
        `meta` with frame rects and `sheet_size` filled, and the sheet PNG already exists
        at `sheet_png_path(meta, out_dir)`. `takes_template=True` passes the PNG-sequence
        template as `fn(meta, out_dir, template=...)`.
        """
        if id in self._formats:
            raise ValueError(f"export format '{id}' is already registered")
        self._formats[id] = ExportFormat(id=id, label=label, fn=fn, needs_sheet=needs_sheet,
                                         takes_template=takes_template)
        box = QCheckBox(label)
        box.setChecked(checked)
        self.format_checks[id] = box
        self.formats_layout.addWidget(box)
        return box

    def formats(self) -> List[str]:
        return list(self._formats)

    def selected_formats(self) -> List[str]:
        return [fmt_id for fmt_id, box in self.format_checks.items() if box.isChecked()]

    def selected_profiles(self) -> List[str]:
        return [name for name, box in self.profile_checks.items() if box.isChecked()]

    def grid_options(self) -> GridOptions:
        return GridOptions(columns=self.columns.value(), border_px=self.border.value(),
                           shape_px=self.shape.value(), inner_px=self.inner.value(),
                           extrude_px=self.extrude.value(),
                           power_of_two=self.power_of_two.isChecked(),
                           scales=parse_scales(self.scales_edit.text()))

    def set_grid_options(self, opts: GridOptions) -> None:
        self.columns.setValue(int(opts.columns))
        self.border.setValue(int(opts.border_px))
        self.shape.setValue(int(opts.shape_px))
        self.inner.setValue(int(opts.inner_px))
        self.extrude.setValue(int(opts.extrude_px))
        self.power_of_two.setChecked(bool(opts.power_of_two))
        self.scales_edit.setText(",".join(str(s) for s in opts.scales))

    def current_meta(self) -> Optional[SheetMeta]:
        """SheetMeta of the first selected profile (frame rects not yet filled), or None."""
        profiles = self.selected_profiles()
        if not profiles:
            return None
        try:
            return self.project.sheet_meta(profiles[0])
        except Exception as exc:
            logger.error("sheet_meta(%s) failed: %s", profiles[0], exc, exc_info=True)
            self.console.log(f"Cannot build sheet for '{profiles[0]}': {exc}", "ERROR")
            return None

    def request(self) -> ExportRequest:
        return ExportRequest(project=self.project, profiles=self.selected_profiles(),
                             formats=self.selected_formats(),
                             out_dir=Path(self.out_dir_edit.text().strip()),
                             template=self.name_template_edit.text().strip() or DEFAULT_TEMPLATE,
                             grid=self.grid_options(),
                             pivot=(round(self.pivot_x_spin.value(), 4), round(self.pivot_y_spin.value(), 4)),
                             purge=self.purge_check.isChecked())

    # ----- purge preference -------------------------------------------
    def _on_purge_toggled(self, checked: bool) -> None:
        if checked:
            if not prefs.confirm_purge(self):
                self.purge_check.blockSignals(True)
                self.purge_check.setChecked(False)
                self.purge_check.blockSignals(False)
                return
            prefs.set_purge_after_export(True)
            logger.info("Sprite export: purge-after-export enabled")
        else:
            prefs.set_purge_after_export(False)
            logger.info("Sprite export: purge-after-export disabled")

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Export directory", self.out_dir_edit.text())
        if chosen:
            self.out_dir_edit.setText(chosen)

    # ----- export -----------------------------------------------------
    def is_running(self) -> bool:
        return self.is_busy()

    def start_export(self) -> None:
        if self.is_running():
            return
        request = self.request()
        problems = []
        if not request.profiles:
            problems.append("Select at least one profile.")
        if not request.formats:
            problems.append("Select at least one format.")
        if not self.out_dir_edit.text().strip():
            problems.append("Choose an output directory.")
        if problems:
            message = "\n".join(problems)
            logger.warning("Sprite export blocked: %s", message)
            self.console.log(message, "WARNING")
            QMessageBox.warning(self, "Export", message)
            return
        self._save_settings()
        formats = [self._formats[fmt_id] for fmt_id in request.formats]
        self._pending_purge = request.purge
        self.console.log(f"Export: profiles={request.profiles} formats={request.formats} → {request.out_dir}")
        logger.info("Sprite export start: %s", request)

        def log(message: str) -> None:
            self.logMessage.emit(message, "INFO")

        def job(progress, token):
            return run_export(request, formats, log=log, progress=progress, token=token)

        worker = self.start_job(job, label="export", on_finished=self._on_finished,
                                on_failed=self._on_failed, on_cancelled=self._on_cancelled,
                                on_progress=self._on_progress)
        if worker is None:
            return
        self._set_running(True)

    def _set_running(self, running: bool) -> None:
        self.progress_bar.setVisible(running)
        if running:
            self.progress_bar.setRange(0, 0)
        self.export_btn.setEnabled(not running)
        if hasattr(self, "_primary"):
            self._primary.set_enabled(not running)
        self.close_btn.setEnabled(not running)

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(done)
        self.console.log(f"[{stage}] {message}")

    def _on_finished(self, result: Any) -> None:
        self._worker = None
        self._set_running(False)
        files = [Path(p) for p in (result or [])]
        if self._pending_purge:
            try:
                count = self.project.purge_intermediates()
                self.console.log(f"Purged {count} intermediate item(s) to the recycle bin", "WARNING")
                logger.info("Sprite export: purged %s intermediates", count)
            except Exception as exc:
                logger.error("Purge after export failed: %s", exc, exc_info=True)
                self.console.log(f"Purge failed: {exc}", "ERROR")
                QMessageBox.warning(self, "Purge failed", str(exc))
        self.console.log(f"Export complete: {len(files)} file(s)", "SUCCESS")
        logger.info("Sprite export complete: %d files", len(files))
        self.exported.emit(files)

    def _on_failed(self, message: str) -> None:
        self._worker = None
        self._set_running(False)
        logger.error("Sprite export failed: %s", message)
        self.console.log(f"Export failed: {message}", "ERROR")
        QMessageBox.critical(self, "Export failed", message)

    def _on_cancelled(self) -> None:
        self._worker = None
        self._set_running(False)
        logger.info("Sprite export cancelled")
        self.console.log("Export cancelled", "WARNING")

    # ----- settings (prefs.get_pref / set_pref, keys under sprite/export/) ---
    def _load_settings(self) -> None:
        get = prefs.get_pref
        out_dir = get(SETTINGS_PREFIX + "out_dir", "")
        if out_dir:
            self.out_dir_edit.setText(str(out_dir))
        self.name_template_edit.setText(str(get(SETTINGS_PREFIX + "template", DEFAULT_TEMPLATE)))
        self.columns.setValue(int(get(SETTINGS_PREFIX + "grid/columns", 0)))
        self.border.setValue(int(get(SETTINGS_PREFIX + "grid/border", 0)))
        self.shape.setValue(int(get(SETTINGS_PREFIX + "grid/shape", 1)))
        self.inner.setValue(int(get(SETTINGS_PREFIX + "grid/inner", 0)))
        self.extrude.setValue(int(get(SETTINGS_PREFIX + "grid/extrude", 0)))
        self.power_of_two.setChecked(str(get(SETTINGS_PREFIX + "grid/power_of_two", "false")).lower() == "true")
        self.scales_edit.setText(str(get(SETTINGS_PREFIX + "grid/scales", "1")))
        self.pivot_x_spin.setValue(float(get(SETTINGS_PREFIX + "pivot_x", 0.5)))
        self.pivot_y_spin.setValue(float(get(SETTINGS_PREFIX + "pivot_y", 1.0)))
        formats = get(SETTINGS_PREFIX + "formats", None)
        if formats:
            wanted = set(str(formats).split(","))
            for fmt_id, box in self.format_checks.items():
                box.setChecked(fmt_id in wanted)

    def _save_settings(self) -> None:
        put = prefs.set_pref
        put(SETTINGS_PREFIX + "out_dir", self.out_dir_edit.text())
        put(SETTINGS_PREFIX + "template", self.name_template_edit.text())
        put(SETTINGS_PREFIX + "grid/columns", self.columns.value())
        put(SETTINGS_PREFIX + "grid/border", self.border.value())
        put(SETTINGS_PREFIX + "grid/shape", self.shape.value())
        put(SETTINGS_PREFIX + "grid/inner", self.inner.value())
        put(SETTINGS_PREFIX + "grid/extrude", self.extrude.value())
        put(SETTINGS_PREFIX + "grid/power_of_two", "true" if self.power_of_two.isChecked() else "false")
        put(SETTINGS_PREFIX + "grid/scales", self.scales_edit.text())
        put(SETTINGS_PREFIX + "pivot_x", self.pivot_x_spin.value())
        put(SETTINGS_PREFIX + "pivot_y", self.pivot_y_spin.value())
        put(SETTINGS_PREFIX + "formats", ",".join(self.selected_formats()))

    def on_dialog_close(self) -> None:
        self.shutdown()                       # WorkerHost: cancel + join a running export
        self._save_settings()
        persist_splitter(self.settings, SPLITTER_KEY, self.splitter)
```

- [ ] Run → 16 passed.
- [ ] Commit:

```
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/export_dialog.py tests/sprite/gui/test_export_dialog.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): ExportDialog with pluggable formats, grid/pivot options, purge-after-export"
```

---

### Task 8: `install_shortcuts` (§1.5 table)

**Files:**
- Create: `tests/sprite/gui/test_shortcuts.py`
- Create: `gui/sprite/shortcuts.py`

**Interfaces:**
- Consumes: a tab object with attributes `frame_strip` (FrameStrip), `preview_player`
  (PreviewPlayer), `pixel_view` (PixelView), and `frames_workspace` with `undo()` / `redo()`
  (Task 9). Only zero-argument methods are called.
- Produces:
  - `SHORTCUT_TABLE: Tuple[Tuple[str, str, str], ...]` — `(key_sequence, "owner.method", description)`
  - `resolve_target(tab, dotted: str) -> Callable[[], Any]`
  - `install_shortcuts(tab: QWidget) -> Dict[str, QShortcut]` — every shortcut uses
    `Qt.WidgetWithChildrenShortcut` so it fires only while focus is inside the Sprite tab.
    Ctrl+Enter is **not** in this table: each panel/dialog binds its own primary action.

**Steps:**

- [ ] Write the failing test `tests/sprite/gui/test_shortcuts.py`:

```python
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from gui.sprite.shortcuts import SHORTCUT_TABLE, install_shortcuts, resolve_target


class _FakeTab(QWidget):
    def __init__(self):
        super().__init__()
        self.calls = []
        record = lambda name: (lambda: self.calls.append(name))
        self.frame_strip = SimpleNamespace(delete_selected=record("delete"),
                                           duplicate_selected=record("duplicate"))
        self.preview_player = SimpleNamespace(toggle_play=record("play"), step_back=record("prev"),
                                              step_forward=record("next"), first=record("first"),
                                              last=record("last"), cycle_mode=record("mode"))
        self.pixel_view = SimpleNamespace(zoom_in=record("zoom_in"), zoom_out=record("zoom_out"),
                                          zoom_reset=record("zoom_reset"), toggle_grid=record("grid"))
        self.frames_workspace = SimpleNamespace(undo=record("undo"), redo=record("redo"))


EXPECTED_KEYS = {"Space", ",", ".", "Home", "End", "Delete", "Ctrl+D", "Ctrl+Z", "Ctrl+Y",
                 "Ctrl+Shift+Z", "+", "=", "-", "Ctrl+0", "G", "L"}


def test_table_covers_design_1_5():
    assert {row[0] for row in SHORTCUT_TABLE} == EXPECTED_KEYS


def test_install_creates_widget_scoped_shortcuts(qapp):
    tab = _FakeTab()
    shortcuts = install_shortcuts(tab)
    assert set(shortcuts) == EXPECTED_KEYS
    for shortcut in shortcuts.values():
        assert shortcut.context() == Qt.WidgetWithChildrenShortcut
        assert shortcut.parent() is tab
        assert shortcut.isEnabled()


def test_activation_routes_to_targets(qapp):
    tab = _FakeTab()
    shortcuts = install_shortcuts(tab)
    routing = {"Space": "play", ",": "prev", ".": "next", "Home": "first", "End": "last",
               "Delete": "delete", "Ctrl+D": "duplicate", "Ctrl+Z": "undo", "Ctrl+Y": "redo",
               "Ctrl+Shift+Z": "redo", "+": "zoom_in", "=": "zoom_in", "-": "zoom_out",
               "Ctrl+0": "zoom_reset", "G": "grid", "L": "mode"}
    for key, expected in routing.items():
        tab.calls.clear()
        shortcuts[key].activated.emit()
        assert tab.calls == [expected], key


def test_resolve_target_rejects_unknown_owner(qapp):
    tab = _FakeTab()
    assert resolve_target(tab, "view.zoom_in") is tab.pixel_view.zoom_in
    try:
        resolve_target(tab, "nowhere.zoom_in")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown owner must raise KeyError")


def test_reinstall_replaces_previous_shortcuts(qapp):
    tab = _FakeTab()
    first = install_shortcuts(tab)
    second = install_shortcuts(tab)
    assert all(not s.isEnabled() for s in first.values())
    assert all(s.isEnabled() for s in second.values())
```

- [ ] Run → fails on import.

- [ ] Implement `gui/sprite/shortcuts.py`:

```python
"""Keyboard shortcuts for the Sprite tab (design §1.5).

Every shortcut is scoped to the tab (`WidgetWithChildrenShortcut`), so other
tabs keep their own keys and text fields inside the tab still receive plain
characters (Qt gives the focused editor the ShortcutOverride first).
Ctrl+Enter is bound per panel/dialog with `bind_primary_action`, not here.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

OWNER_ATTRS = {
    "strip": "frame_strip",
    "player": "preview_player",
    "view": "pixel_view",
    "workspace": "frames_workspace",
}

SHORTCUT_TABLE: Tuple[Tuple[str, str, str], ...] = (
    ("Space", "player.toggle_play", "Play / pause"),
    (",", "player.step_back", "Previous frame"),
    (".", "player.step_forward", "Next frame"),
    ("Home", "player.first", "First frame"),
    ("End", "player.last", "Last frame"),
    ("Delete", "strip.delete_selected", "Delete selected frame(s)"),
    ("Ctrl+D", "strip.duplicate_selected", "Duplicate frame"),
    ("Ctrl+Z", "workspace.undo", "Undo"),
    ("Ctrl+Y", "workspace.redo", "Redo"),
    ("Ctrl+Shift+Z", "workspace.redo", "Redo"),
    ("+", "view.zoom_in", "Zoom in"),
    ("=", "view.zoom_in", "Zoom in (unshifted +)"),
    ("-", "view.zoom_out", "Zoom out"),
    ("Ctrl+0", "view.zoom_reset", "Zoom 100 %"),
    ("G", "view.toggle_grid", "Toggle pixel grid"),
    ("L", "player.cycle_mode", "Cycle loop mode"),
)


def resolve_target(tab: Any, dotted: str) -> Callable[[], Any]:
    owner, _, method = dotted.partition(".")
    attr = OWNER_ATTRS[owner]           # KeyError on an unknown owner is a programming error
    return getattr(getattr(tab, attr), method)


def install_shortcuts(tab: QWidget) -> Dict[str, QShortcut]:
    """Bind the §1.5 table on `tab`; a second call disables the previous set."""
    previous = getattr(tab, "_sprite_shortcuts", None)
    if previous:
        for shortcut in previous.values():
            shortcut.setEnabled(False)
            shortcut.setParent(None)
            shortcut.deleteLater()
    shortcuts: Dict[str, QShortcut] = {}
    for key, dotted, description in SHORTCUT_TABLE:
        slot = resolve_target(tab, dotted)
        shortcut = QShortcut(QKeySequence(key), tab)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.setWhatsThis(description)
        shortcut.activated.connect(slot)
        shortcuts[key] = shortcut
    tab._sprite_shortcuts = shortcuts
    logger.debug("Sprite shortcuts installed: %s", ", ".join(shortcuts))
    return shortcuts
```

- [ ] Run → 5 passed.
- [ ] Commit:

```
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/shortcuts.py tests/sprite/gui/test_shortcuts.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): tab-scoped keyboard shortcuts per design §1.5"
```

---

### Task 9: `FramesWorkspace` + `SpriteTab` integration

**Files:**
- Create: `tests/sprite/gui/test_sprite_tab_integration.py`
- Create: `gui/sprite/frames_workspace.py`
- Modify: `gui/sprite/sprite_tab.py` (sub-project 5a) — construct the workspace at the end of `SpriteTab.__init__`

**Interfaces:**
- Consumes (5a contract): `SpriteTab.set_frame_widget(w)`, `set_preview_widget(w)`,
  `set_processing_widget(w)`, `current_project` (property), `current_action()`, signals
  `projectChanged()` and `actionSelected(str)`, `console: DialogStatusConsole`.
- Produces: `FramesWorkspace(QObject)`:
  - `__init__(tab)`; attributes `tab`, `undo_controller`, `strip`, `player`, `view`, `panel`, `shortcuts`
  - sets on the tab: `tab.frames_workspace`, `tab.frame_strip`, `tab.preview_player`, `tab.pixel_view`,
    `tab.processing_panel`, `tab.undo_controller`, `tab.undo_stack` (the active action's
    `SnapshotStack`, reassigned on every action change; sub-project 6 pushes retouch snapshots to it),
    `tab.refresh_frames` (bound `FramesWorkspace.refresh_frames`; sub-project 6 calls it after retouch
    and image-route renders)
  - `export_btn: QPushButton` — `tab.add_toolbar_action("Export…", open_export_dialog)` (5a hook);
    the processing panel's own Export… button routes to the same slot
  - `undo() -> bool`, `redo() -> bool`, `refresh_frames()`,
    **`apply_frames(action_id: str, frames: List[FrameMeta], label: str) -> None`** ★ — the public
    edit path for sub-project 6's retouch: snapshots the action's current list via
    `undo_controller.snapshot`, writes `action.frames`, reloads the strip and the player, logs, and
    emits `tab.projectChanged()`. Callers pass a **new** list (deep-copied frames with the new
    `source_path`); they must not push their own snapshot and must not mutate the current
    `FrameMeta` objects in place, or undo would restore the already-changed list.
    `open_export_dialog() -> Optional[ExportDialog]`, `current_action() -> Optional[ActionCard]`,
    `shutdown()`
  - listens to `tab.queue_panel.statusChanged()` and re-reads `action.frames` (the queue's
    `run_pipeline(upto="stabilize")` rebuilds that list when a clip lands)
  - `export_dialog_factory: Callable[[SpriteProject, QWidget], ExportDialog]` (tests replace it)

**Steps:**

- [ ] Write the failing test `tests/sprite/gui/test_sprite_tab_integration.py`:

```python
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from gui.llm_utils import DialogStatusConsole
from gui.sprite.frames_workspace import FramesWorkspace
from gui_synthetic import make_frames, make_project


class _StubQueue(QObject):
    statusChanged = Signal()


class _StubTab(QWidget):
    """Implements the 5a SpriteTab contract that FramesWorkspace consumes."""

    projectChanged = Signal()
    actionSelected = Signal(str)

    def __init__(self, project=None):
        super().__init__()
        self._project = project
        self.console = DialogStatusConsole("Console")
        self.queue_panel = _StubQueue(self)
        self.placed = {}
        self.toolbar_buttons = []
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self.console)

    def add_toolbar_action(self, text, slot):
        button = QPushButton(text, self)
        button.clicked.connect(slot)
        self.toolbar_buttons.append(button)
        return button

    def log(self, message, level="INFO"):
        self.console.log(message, level)

    def set_frame_widget(self, widget):
        self.placed["frame"] = widget
        self._layout.addWidget(widget)

    def set_preview_widget(self, widget):
        self.placed["preview"] = widget
        self._layout.addWidget(widget)

    def set_processing_widget(self, widget):
        self.placed["processing"] = widget
        self._layout.addWidget(widget)

    @property
    def current_project(self):
        return self._project

    def current_action(self):
        if self._project and self._project.actions:
            return self._project.actions[0]
        return None


def _workspace(qapp, tmp_path, monkeypatch):
    import gui.sprite.processing_panel as pp
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    project, action = make_project(tmp_path)
    tab = _StubTab(project)
    workspace = FramesWorkspace(tab)
    tab.projectChanged.emit()
    tab.actionSelected.emit(action.id)
    return tab, workspace, project, action


def test_workspace_places_widgets_and_exposes_attributes(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    assert tab.placed["frame"] is workspace.strip
    assert tab.placed["preview"] is workspace.player
    assert tab.placed["processing"] is workspace.panel
    assert tab.frames_workspace is workspace
    assert tab.frame_strip is workspace.strip
    assert tab.preview_player is workspace.player
    assert tab.pixel_view is workspace.view is workspace.player.view
    assert tab.undo_controller is workspace.undo_controller
    assert tab.undo_stack is workspace.undo_controller.stack(action.id)
    assert tab.refresh_frames == workspace.refresh_frames
    assert [b.text() for b in tab.toolbar_buttons] == ["Export…"]
    assert workspace.export_btn is tab.toolbar_buttons[0]
    assert set(workspace.shortcuts) >= {"Space", "Ctrl+Z"}
    workspace.shutdown()


def test_queue_status_change_rereads_action_frames(qapp, tmp_path, monkeypatch):
    # The queue runs run_pipeline(upto="stabilize") after a clip lands, which rebuilds
    # action.frames; the strip must re-read the list instead of keeping a stale copy.
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    action.frames = make_frames(tmp_path / "rendered", 5)
    tab.queue_panel.statusChanged.emit()
    assert workspace.strip.count() == 5
    assert len(workspace.player.frames()) == 5
    workspace.shutdown()


def test_apply_frames_snapshots_reloads_and_emits_project_changed(qapp, tmp_path, monkeypatch):
    import copy
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    changed = []
    tab.projectChanged.connect(lambda: changed.append(1))
    old_path = action.frames[1].source_path
    # The sub-project 6 retouch pattern: a NEW list, never an in-place edit of the current frames.
    new_frames = copy.deepcopy(action.frames)
    new_frames[1].source_path = tmp_path / "stages" / "act1" / "stabilize" / "0001.r1.png"
    workspace.apply_frames(action.id, new_frames, "retouch 2")
    assert action.frames[1].source_path.name == "0001.r1.png"
    assert workspace.strip.count() == 4
    assert workspace.player.frames()[1].source_path.name == "0001.r1.png"
    assert changed == [1]
    assert "retouch 2" in tab.console.console.toPlainText()
    assert workspace.undo_controller.can_undo(action.id)
    assert workspace.undo() is True                      # the snapshot holds the old path
    assert action.frames[1].source_path == old_path
    workspace.apply_frames("no-such-action", new_frames, "ignored")  # logged, no raise
    workspace.shutdown()


def test_action_selected_loads_strip_player_and_panel(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    assert workspace.strip.count() == 4
    assert len(workspace.player.frames()) == 4
    assert workspace.player.tag_combo.count() == 2  # All frames + walk
    assert workspace.panel.action() is action
    assert workspace.panel.project() is project
    assert workspace.undo_controller.active_action == action.id
    assert workspace.strip.action_id() == action.id
    workspace.shutdown()


def test_strip_edit_updates_action_and_undo_restores(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    workspace.strip.select_index(1)
    workspace.strip.delete_selected()
    assert [f.name for f in action.frames] == ["frame_00", "frame_02", "frame_03"]
    assert len(workspace.player.frames()) == 3
    assert workspace.undo() is True
    assert len(action.frames) == 4
    assert workspace.strip.count() == 4
    assert len(workspace.player.frames()) == 4
    assert workspace.redo() is True
    assert len(action.frames) == 3
    assert workspace.strip.count() == 3
    workspace.shutdown()


def test_selection_sync_between_strip_and_player(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    workspace.strip.select_index(2)
    assert workspace.player.current_index() == 2
    workspace.player.set_current_index(3)
    assert workspace.strip.current_index() == 3
    workspace.shutdown()


def test_pipeline_finished_reloads_from_action(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    action.frames = make_frames(tmp_path / "again", 6)
    workspace.panel.pipelineFinished.emit(action.id)
    assert workspace.strip.count() == 6
    assert len(workspace.player.frames()) == 6
    action.frames = make_frames(tmp_path / "retouched", 2)
    tab.refresh_frames()  # the sub-project 6 entry point
    assert workspace.strip.count() == 2
    assert len(workspace.player.frames()) == 2
    workspace.shutdown()


def test_player_source_switch_uses_sheet_meta(qapp, tmp_path, monkeypatch):
    from core.sprite.project import SpriteProject
    from gui_synthetic import sheet_from_action
    seen = []

    def fake_sheet(self, profile):
        seen.append(profile)
        return sheet_from_action(self.actions[0], profile)

    monkeypatch.setattr(SpriteProject, "sheet_meta", fake_sheet)
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    workspace.player.source_combo.setCurrentIndex(1)  # "hd"
    assert seen == ["hd"]
    assert len(workspace.player.frames()) == 4
    workspace.shutdown()


def test_export_request_opens_dialog_with_project(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    opened = []

    class _FakeDialog(QObject):
        logMessage = Signal(str, str)

        def __init__(self, proj, parent):
            super().__init__(parent)
            opened.append((proj, parent))

        def exec(self):
            return 0

    monkeypatch.setattr(workspace, "export_dialog_factory", lambda proj, parent: _FakeDialog(proj, parent))
    workspace.panel.exportRequested.emit()
    assert opened == [(project, tab)]
    workspace.shutdown()


def test_no_project_clears_everything(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    tab._project = None
    tab.projectChanged.emit()
    assert workspace.strip.count() == 0
    assert workspace.player.frames() == []
    assert workspace.panel.action() is None
    assert workspace.undo() is False
    workspace.shutdown()


class _FakeConfig:
    """The config surface the 5a panels read (mirrors tests in the 5a plan)."""

    def __init__(self):
        self.store = {}

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value):
        self.store[key] = value

    def save(self):
        pass

    def get_api_key(self, provider):
        return "test-key"

    def get_auth_mode(self, provider="google"):
        return "api-key"


def test_real_sprite_tab_constructs_workspace(qapp, monkeypatch):
    import gui.sprite.processing_panel as pp
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    from gui.sprite.sprite_tab import SpriteTab
    tab = SpriteTab(_FakeConfig())
    assert isinstance(tab.frames_workspace, FramesWorkspace)
    assert tab.frame_strip is tab.frames_workspace.strip
    tab.frames_workspace.shutdown()
```

- [ ] Run → fails on import.

- [ ] Implement `gui/sprite/frames_workspace.py`:

```python
"""Builds the 5b widgets and wires them into SpriteTab (design §4.5).

The workspace owns the strip, player (with its PixelView), processing panel,
undo controller, and shortcuts. It listens to the tab's project/action
signals and keeps `ActionCard.frames` as the single source of truth.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, List, Optional

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from core.sprite.models import FrameMeta, TagMeta
from core.sprite.project import ActionCard, SpriteProject
from core.sprite.undo import SnapshotStack

from .export_dialog import ExportDialog
from .frame_strip import FrameStrip
from .preview_player import PreviewPlayer
from .processing_panel import ProcessingPanel
from .shortcuts import install_shortcuts
from .undo_controller import UndoController

if TYPE_CHECKING:  # pragma: no cover
    from .sprite_tab import SpriteTab

logger = logging.getLogger(__name__)

SOURCE_CELLS = "cells"
PROFILE_SOURCES = ("hd", "pixel")


class FramesWorkspace(QObject):
    """Right-hand working area: strip + preview + processing, with undo and shortcuts."""

    export_dialog_factory: Callable[[SpriteProject, QWidget], ExportDialog]

    def __init__(self, tab: "SpriteTab"):
        super().__init__(tab)
        self.tab = tab
        self._action: Optional[ActionCard] = None
        self._syncing = False
        self.export_dialog_factory = ExportDialog

        self.undo_controller = UndoController(parent=self)
        self.strip = FrameStrip(self.undo_controller)
        self.player = PreviewPlayer()
        self.view = self.player.view
        self.panel = ProcessingPanel()
        self.panel.attach_pixel_view(self.view)
        self.player.set_sources([SOURCE_CELLS, *PROFILE_SOURCES])

        tab.set_frame_widget(self.strip)
        tab.set_preview_widget(self.player)
        tab.set_processing_widget(self.panel)
        tab.frames_workspace = self
        tab.frame_strip = self.strip
        tab.preview_player = self.player
        tab.pixel_view = self.view
        tab.processing_panel = self.panel
        tab.undo_controller = self.undo_controller
        tab.undo_stack = SnapshotStack()          # replaced per action in _set_action
        tab.refresh_frames = self.refresh_frames  # sub-project 6 calls tab.refresh_frames()
        self.shortcuts = install_shortcuts(tab)
        self.export_btn = tab.add_toolbar_action("Export…", self.open_export_dialog)

        tab.projectChanged.connect(self._on_project_changed)
        tab.actionSelected.connect(self._on_action_selected)
        tab.queue_panel.statusChanged.connect(self.refresh_frames)
        self.strip.framesChanged.connect(self._on_frames_changed)
        self.strip.frameSelected.connect(self._on_strip_selected)
        self.strip.logMessage.connect(tab.log)
        self.player.frameChanged.connect(self._on_player_frame)
        self.player.sourceChanged.connect(lambda _name: self._reload_player())
        self.panel.pipelineFinished.connect(self._on_pipeline_finished)
        self.panel.logMessage.connect(tab.log)
        self.panel.exportRequested.connect(self.open_export_dialog)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    # ----- tab events -------------------------------------------------
    def current_action(self) -> Optional[ActionCard]:
        return self._action

    def _on_project_changed(self) -> None:
        project = self.tab.current_project
        self.panel.set_project(project)
        self._set_action(self.tab.current_action() if project is not None else None)

    def _on_action_selected(self, action_id: str) -> None:
        project = self.tab.current_project
        action = None
        if project is not None:
            action = next((a for a in project.actions if a.id == action_id), None)
        self._set_action(action)

    def _set_action(self, action: Optional[ActionCard]) -> None:
        self._action = action
        self.panel.set_action(action)
        self.undo_controller.set_active(action.id if action is not None else None)
        self.tab.undo_stack = (self.undo_controller.stack(action.id) if action is not None
                               else SnapshotStack())
        self.strip.set_action_id(action.id if action is not None else "")
        self.strip.set_frames(list(action.frames) if action is not None else [])
        self._reload_player()

    # ----- frame list -------------------------------------------------
    def _on_frames_changed(self) -> None:
        action = self._action
        if action is None:
            return
        action.frames = self.strip.frames()
        self.tab.log(f"Frames updated for '{action.name}': {len(action.frames)}")
        self._reload_player()

    def _reload_player(self) -> None:
        action = self._action
        project = self.tab.current_project
        if action is None:
            self.player.set_frames([])
            self.player.set_tags([])
            return
        source = self.player.source() or SOURCE_CELLS
        frames: List[FrameMeta]
        tags: List[TagMeta]
        if source == SOURCE_CELLS or project is None:
            frames = list(action.frames)
            tags = [TagMeta(name=action.name, from_index=0, to_index=max(0, len(frames) - 1))]
        else:
            try:
                meta = project.sheet_meta(source)
            except Exception as exc:
                logger.error("sheet_meta(%s) failed: %s", source, exc, exc_info=True)
                self.tab.log(f"Cannot load profile '{source}': {exc}", "ERROR")
                frames, tags = [], []
            else:
                frames, tags = list(meta.frames), list(meta.tags)
        self.player.set_frames(frames)
        self.player.set_tags(tags)

    def _on_strip_selected(self, index: int) -> None:
        if self._syncing or self.player.source() != SOURCE_CELLS:
            return
        self._syncing = True
        try:
            self.player.set_current_index(index)
        finally:
            self._syncing = False

    def _on_player_frame(self, index: int) -> None:
        if self._syncing or self.player.source() != SOURCE_CELLS:
            return
        self._syncing = True
        try:
            self.strip.select_index(index)
        finally:
            self._syncing = False

    def _on_pipeline_finished(self, action_id: str) -> None:
        action = self._action
        if action is not None and action.id == action_id:
            self.refresh_frames()

    def refresh_frames(self) -> None:
        """Reload the strip and the player from `ActionCard.frames`.

        Called after a pipeline run here, and by sub-project 6 after a retouch or an
        image-route render replaces frames on the current action.
        """
        action = self._action
        self.strip.set_frames(list(action.frames) if action is not None else [])
        self._reload_player()

    # ----- undo / redo (Ctrl+Z / Ctrl+Y) ------------------------------
    def undo(self) -> bool:
        action = self._action
        if action is None:
            return False
        frames = self.undo_controller.undo(action.id, self.strip.frames())
        if frames is None:
            return False
        self._replace_frames(action, frames, "Undo")
        return True

    def redo(self) -> bool:
        action = self._action
        if action is None:
            return False
        frames = self.undo_controller.redo(action.id)
        if frames is None:
            return False
        self._replace_frames(action, frames, "Redo")
        return True

    def _replace_frames(self, action: ActionCard, frames: List[FrameMeta], label: str) -> None:
        """Write `action.frames` and reload the strip and the player (no snapshot, no signal)."""
        action.frames = list(frames)
        self.strip.set_frames(action.frames)
        self._reload_player()
        self.tab.log(f"{label}: '{action.name}' now has {len(action.frames)} frames")

    def apply_frames(self, action_id: str, frames: List[FrameMeta], label: str) -> None:
        """Public edit path for sub-project 6 (retouch, image route).

        Pushes a snapshot of the action's current list, replaces it with `frames`, reloads
        the strip and the player, and emits `tab.projectChanged()` so the tab marks the
        project modified. Pass a NEW list (deep-copied frames with the new `source_path`);
        do not push a snapshot yourself and do not edit the current FrameMeta objects in
        place — the snapshot must hold the list as it was before the change.
        """
        project = self.tab.current_project
        action = None
        if project is not None:
            action = next((a for a in project.actions if a.id == action_id), None)
        if action is None:
            logger.error("apply_frames: unknown action id %r", action_id)
            self.tab.log(f"{label}: action {action_id!r} not found", "ERROR")
            return
        self.undo_controller.snapshot(action.id, action.frames, label)
        self._replace_frames(action, frames, label)
        self.tab.projectChanged.emit()

    # ----- export -----------------------------------------------------
    def open_export_dialog(self) -> Optional[ExportDialog]:
        project = self.tab.current_project
        if project is None:
            logger.warning("Export requested with no project open")
            self.tab.log("Export: open or create a sprite project first.", "WARNING")
            QMessageBox.warning(self.tab, "Export", "Open or create a sprite project first.")
            return None
        dialog = self.export_dialog_factory(project, self.tab)
        dialog.logMessage.connect(self.tab.log)
        dialog.exec()
        return dialog

    # ----- lifecycle --------------------------------------------------
    def shutdown(self) -> None:
        self.player.pause()
        self.panel.shutdown()
```

- [ ] Edit `gui/sprite/sprite_tab.py` (sub-project 5a's file; its Task 8 reserves the attributes
  the workspace sets). At the **end** of `SpriteTab.__init__`, after `self._sync_title()`, add:

```python
        # Sub-project 5b: strip + preview + processing + export + shortcuts + undo.
        from .frames_workspace import FramesWorkspace
        self.frames_workspace = FramesWorkspace(self)
```

  and as the **first** line of `SpriteTab.shutdown()` (5a's method; `MainWindow.closeEvent`
  calls it) add `self.frames_workspace.shutdown()` so the processing and export workers are
  cancelled and joined before the panels go down. Use a local import: `frames_workspace`
  imports nothing from `sprite_tab` at runtime, and the local import keeps `sprite_tab`
  importable on its own for 5a's tests. The `aboutToQuit` connection in the workspace stays as
  a safety net for exits that skip the main window.

- [ ] Run `test_sprite_tab_integration.py` → 9 passed. Then re-run 5a's tab tests:
  `QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui -v`
  → all green (5a's tests plus Tasks 1–9).
- [ ] Commit:

```
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/frames_workspace.py gui/sprite/sprite_tab.py tests/sprite/gui/test_sprite_tab_integration.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): wire frame strip, preview, processing, export, undo, shortcuts into SpriteTab"
```

---

### Task 10: Full-suite run and guard checks

**Files:** none new.

**Steps:**

- [ ] Run the sprite GUI suite:
  `QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite -v`
  → green.
- [ ] Run the path guard and dialog-convention suites:
  `QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/gui/test_dialog_conventions.py -v`
  → green (no `AppData` / `XDG` / `.imageai` tokens in `gui/sprite/`).
- [ ] Run the whole suite once:
  `QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI -q`
  → green. Paste the final summary line into the commit body of the next step.
- [ ] Grep the new modules for banned patterns; every command must print nothing:

```
grep -n "QMovie" /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/*.py
grep -n "SmoothPixmapTransform, True\|Qt.SmoothTransformation" /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/pixel_view.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/preview_player.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/frame_strip.py
grep -n "from PIL\|import PIL" /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/frame_strip.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/preview_player.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/pixel_view.py
```

- [ ] Update the plan-file checkboxes above and commit the plan state:

```
git -C /mnt/d/Documents/Code/GitHub/ImageAI add Plans/2026-08-29-sprite-gui-b-plan.md
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "docs(plans): sprite GUI (B) plan — tasks complete, suite green"
```

No version bump: the PR gate in sub-project 7 bumps once for the whole feature.

---

## Self-review

**Spec coverage (design §4.5 row by row):**

| Design line | Where |
|---|---|
| `frame_strip.py` — icon mode, drag reorder, duplicate/delete/insert, duration spin, per-frame overrides, snapshot on every destructive op | Task 4: `_FrameList` (IconMode + `Static` movement + `InternalMove`), `duplicate_selected`, `delete_selected`, `insert_from_file`, `move_frame`, `apply_duration`, `apply_overrides`; each calls `_snapshot()` first |
| `preview_player.py` — QTimer + QPixmap, per-frame ms, forward/reverse/pingpong, tag combo, scrub, seam meter | Task 3: `_schedule()` uses `duration_ms`; `next_index`; `tag_combo`; `slider`; `loop_seam_score` |
| `pixel_view.py` — QGraphicsView, FastTransformation, integer zoom 1–16, grid, checkerboard | Task 2 |
| `processing_panel.py` — key / cleanup / alpha / stabilize / profile groups; Run pipeline (Ctrl+Enter); re-run of changed stages | Task 6; the stage cache (§1.2) in `run_pipeline` decides what re-runs; `force_check` bypasses it |
| `export_dialog.py` — profile × formats; output dir; purge-after-export (sticky, confirmed) | Task 7; "Export selected frame" lives on the strip (design decision row "—": per-frame export) |
| `shortcuts.py` — §1.5 table | Task 8; Ctrl+Enter bound per panel; Escape via QDialog/`DialogCleanupMixin` |
| §1.4 undo — `FrameListSnapshot` stack, depth 50, per action; retouch = pointer swap | Task 1 `UndoController(depth=50)`; retouch itself is sub-project 6 (it calls `undo_controller.snapshot(...)` then repoints `source_path`) |
| §1.6 purge — QSettings `sprite/purge_after_export`, confirmation, recycle bin | Task 7 delegates to `prefs` (5a) and `SpriteProject.purge_intermediates()` (1) |

**Hooks for sub-project 6 (names taken from its plan):** `FrameStrip.retouchRequested(int)`
(context menu "Retouch…" + `request_retouch()`); `PixelView.selection_rect()` for region retouch;
`ExportDialog.register_format(id, label, fn)` with `fn(meta, out_dir) -> List[Path]`, plus
`format_checks`, `options_layout`, `set_grid_options`, `pivot_x_spin`/`pivot_y_spin`,
`name_template_edit`, `current_meta()`; `tab.undo_stack`, `tab.refresh_frames()`, and
`tab.frames_workspace.apply_frames(action_id, frames, label)` from `FramesWorkspace`. The runner fills frame rects and writes the sheet PNG before any
`needs_sheet` format runs; a plugin that needs the sheet without declaring `needs_sheet` (6's
`write_godot_tres`) lays the grid out itself, which the runner tolerates.

**Threading:** `ProcessingPanel` and `ExportDialog` are `WorkerHost`s (5a): `start_job` wraps
`run_pipeline`, `ffmpeg_chromakey_preview`, and `run_export`; a separate short probe worker runs
`probe_video`. Worker-side logging goes through the `logMessage` Qt signal (queued to the UI
thread); no widget is touched from the worker. `shutdown()` cancels and joins.

**Frame-list ownership:** `ActionCard.frames` is the single list. `run_pipeline` rebuilds it at the
`stabilize` stage and a deleted frame whose file still exists returns (core plan note), so the
strip re-reads `action.frames` after every pipeline run (`pipelineFinished`) and after every queue
status change; a delete that must stick is a snapshot-backed list edit, never a file operation.

**Error path:** every `_warn`/`_on_failed` logs with `logger` and shows a `QMessageBox` or a
console line; tests patch `QMessageBox.warning/critical` at module scope and assert both.

**Test determinism:** no real key events (matches `tests/gui/test_dialog_conventions.py`, which
calls `_activated()` directly); the single mouse-click test (`PixelView` pick) uses `QTest.mouseClick`
on the viewport, which needs no window focus. Timer test uses 5 ms frames and a 150 ms wait.

**Known limits (not bugs, follow-ups for the PR notes):**
- The strip decodes thumbnails synchronously in `set_frames`; fine for ≤ 200 cells, a lazy
  icon loader is a later optimization.
- `PreviewPlayer` caches decoded frames for the current list only; a 64-frame 1024² hd list
  costs ~256 MB while previewed.
- Drag-drop reorder is exercised through `move_frame()`; a real `QDropEvent` is not simulated.

## Deviations from the design

1. **`UndoController.undo(action_id, current)`** takes the current frame list because
   `SnapshotStack.undo(current)` (design §1.4) needs it to fill the redo stack. `redo(action_id)`
   has no `current` argument, matching `SnapshotStack.redo()`.
2. **The PixelView lives inside the PreviewPlayer.** Design §4.5 lists `pixel_view.py` and
   `preview_player.py` as separate modules (kept) but the tab shows one view: the player renders
   the current frame in its `PixelView`, so zoom, grid, and key-color picking act on the frame
   under playback. `tab.pixel_view is tab.preview_player.view`.
3. **Export… button placement.** Two entry points to one slot: the tab toolbar via 5a's
   `add_toolbar_action("Export…", …)` and the `ProcessingPanel` action row (`export_btn` →
   `exportRequested`), because the processing panel is where the user has just run the pipeline.
4. **`FramesWorkspace` is a new module** (not in §4.5). It keeps the 5a/5b seam to two lines in
   `sprite_tab.py` and lets both plans be written in parallel.
5. **Ctrl+Enter scope.** Panels bind the primary action with `Qt.WidgetWithChildrenShortcut`
   instead of the window-wide default, because the queue panel (5a) and the processing panel share
   one window; two window-scoped bindings would make the shortcut ambiguous and fire neither.
6. **Preview source selector** (`cells | hd | pixel`) is an addition: `ActionCard.frames` holds the
   stabilized cells; the profile outputs come from `SpriteProject.sheet_meta(profile)`. Strip
   selection sync applies only to the `cells` source.
7. **Sibling names checked against the final sibling plans on 2026-08-29:** all confirmed —
   `presets.CELL_PRESETS` / `CUSTOM_CELL_LABEL`, `SnapshotStack` (+ `clear()`), `probe_video` keys,
   `run_pipeline` rebuilding `action.frames` at `stabilize`, `SpriteProject` defaults,
   `SpriteWorker(job, *, label, parent)` + `cancelled()`, `WorkerHost`, `prefs.*`,
   `sprite_ml_packages() -> (packages, index_url)`, `rebuild_palette(project, profile, frames)`,
   and `SpriteTab(config, parent=None)` with the three `set_*_widget` hooks, `current_project`,
   `current_action()`, `projectChanged()`, `actionSelected(str)`, `add_toolbar_action`, `log`,
   `console`, `queue_panel.statusChanged()` (5a Task 8).
10. **`WorkerHost` instead of a private worker slot.** `ProcessingPanel` and `ExportDialog` mix in
    5a's `WorkerHost` (`start_job` / `is_busy` / `cancel_running` / `shutdown`) per the team
    lead's direction, so every sprite panel refuses a second job the same way.
11. **"Rebuild palette" = clear the lock and re-run.** Per sub-project 4, `locked_palette` is part
    of the pixel-stage fingerprint; the button sets it to `None` and runs the pipeline to `pixel`,
    and `ensure_palette` rebuilds from the fitted binary-alpha frames. The panel never calls
    `rebuild_palette` with cell frames (they are not the frames the quantizer sees). The panel also
    logs the pixel stage's `pixel.json` `warnings` after every run and exposes
    `OutputProfile.upscale_small` as a checkbox.
12. **Sub-project 6 asks adopted (signature per the team lead):**
    `FramesWorkspace.apply_frames(action_id: str, frames, label)` is the public edit path — it
    snapshots, writes `action.frames`, reloads strip + player, and emits `projectChanged()`;
    undo/redo use the private `_replace_frames` (no snapshot). `ExportDialog.notes_label` exists,
    `FrameStrip.refresh()` re-reads thumbnails, and the `PixelView` region selection ships here
    (6 consumes it instead of adding its own). 5a's `SpriteTab.shutdown()` gains one line that
    calls `frames_workspace.shutdown()`.
8. **Export plugin signature follows sub-project 6, not the first draft of this plan.** Format
   callables are `fn(meta: SheetMeta, out_dir: Path) -> List[Path]`; the built-in ids are 6's
   `FORMAT_IDS` (`grid`, `aseprite_json`, `texturepacker_json`, `png_sequence`, `gif`). The
   dialog therefore exposes `options_layout`, `set_grid_options`, `pivot_x_spin`/`pivot_y_spin`,
   `name_template_edit`, and `current_meta()` so 6's engine-preset box can drive it. The pivot
   spins apply one normalized pivot to every exported frame (the design defers a per-frame pivot
   editor to a later pick).
9. **`PixelView` gains a region selection** (`set_select_mode`, `selection_rect`, `clear_selection`)
   because 6's retouch dialog reads `tab.pixel_view.selection_rect()`; the design listed only zoom,
   grid, and checkerboard for the pixel view.
