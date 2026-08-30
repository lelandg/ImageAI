"""Frame strip: order, duplicate, delete, insert, duration, per-frame overrides.

Design §4.5 / §1.4: every destructive list edit pushes a `FrameListSnapshot`
through the `UndoController` before the change. Files on disk are never
deleted here; the list only points at them.

Thumbnails are decoded with `QImageReader` at strip-cell size (scaled
proportionally, never cropped or distorted) rather than as full-resolution
`QPixmap`s, and cached per `(path, mtime)` on the strip instance so repeated
`set_frames()`/`refresh()` calls do not re-decode unchanged files.
"""
from __future__ import annotations

import copy
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QImage, QImageReader, QPixmap
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
        # Thumbnail cache: str(source_path) -> (mtime, QPixmap). Avoids
        # re-decoding unchanged files on every set_frames()/refresh() call.
        self._thumb_cache: Dict[str, Tuple[float, QPixmap]] = {}
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
        calls this; the list order and the selection stay as they are. The thumbnail
        cache is keyed by (path, mtime), so a repointed or modified file is
        re-decoded and an unchanged one is served from cache.
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

    def _thumbnail(self, frame: FrameMeta) -> QIcon:
        pixmap = self._cached_thumbnail(frame.source_path)
        if pixmap is None:
            pixmap = QPixmap(THUMB_PX, THUMB_PX)
            pixmap.fill(QColor("#444444"))
        return QIcon(pixmap)

    def _cached_thumbnail(self, source_path: Optional[Path]) -> Optional[QPixmap]:
        """Decode a strip-cell-sized thumbnail via QImageReader, cached by (path, mtime).

        Never decodes the full-resolution image on the UI thread: QImageReader's
        `setScaledSize` downsamples during the read itself. The scaled size
        preserves aspect ratio (Qt.KeepAspectRatio semantics) so thumbnails are
        never cropped or distorted. The cache entry is invalidated whenever the
        file's mtime changes, so a retouch that repoints/rewrites a file is
        re-decoded on the next refresh().
        """
        if not source_path:
            return None
        path = Path(source_path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None
        key = str(path)
        cached = self._thumb_cache.get(key)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        reader = QImageReader(str(path))
        native_size = reader.size()
        if native_size.isValid() and not native_size.isEmpty():
            scaled_size = native_size.scaled(THUMB_PX, THUMB_PX, Qt.KeepAspectRatio)
            reader.setScaledSize(scaled_size)
        image = reader.read()
        if image.isNull():
            self._thumb_cache.pop(key, None)
            return None
        pixmap = QPixmap.fromImage(image)
        self._thumb_cache[key] = (mtime, pixmap)
        return pixmap

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
