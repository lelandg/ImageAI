"""Builds the 5b widgets and wires them into SpriteTab (design §4.5).

The workspace owns the strip, player (with its PixelView), processing panel,
undo controller, and shortcuts. It listens to the tab's project/action
signals and keeps `ActionCard.frames` as the single source of truth.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Union

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QImage, QPixmap
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
SHUTDOWN_TIMEOUT_MS = 5000


class FramesWorkspace(QObject):
    """Right-hand working area: strip + preview + processing, with undo and shortcuts."""

    export_dialog_factory: Callable[[SpriteProject, QWidget], ExportDialog]

    def __init__(self, tab: "SpriteTab"):
        super().__init__(tab)
        self.tab = tab
        self._action: Optional[ActionCard] = None
        self._project: Optional[SpriteProject] = None
        self._syncing = False
        self._export_dialog: Optional[ExportDialog] = None
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
        # The toolbar Export button follows the panel's own Export button, which
        # ProcessingPanel gates on "a project is open and no job runs"
        # (`ProcessingPanel._sync_enabled`). The panel has no running-state
        # signal, so the workspace watches that button's EnabledChange event
        # instead of keeping a second copy of the running state, which could
        # drift from the panel's (final review, Important 3).
        self.panel.export_btn.installEventFilter(self)
        self._sync_export_enabled()

        tab.projectChanged.connect(self._on_project_changed)
        tab.actionSelected.connect(self._on_action_selected)
        tab.queue_panel.statusChanged.connect(self.refresh_frames)
        self.strip.framesChanged.connect(self._on_frames_changed)
        self.strip.frameSelected.connect(self._on_strip_selected)
        self.strip.logMessage.connect(tab.log)
        self.player.frameChanged.connect(self._on_player_frame)
        self.player.sourceChanged.connect(self._on_source_changed)
        self.player.decodeFailed.connect(self._on_decode_failed)
        self.panel.pipelineFinished.connect(self._on_pipeline_finished)
        self.panel.logMessage.connect(tab.log)
        self.panel.exportRequested.connect(self.open_export_dialog)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    # ----- tab events -------------------------------------------------
    def current_action(self) -> Optional[ActionCard]:
        return self._action

    def eventFilter(self, obj, event) -> bool:
        """Mirror the panel's Export button onto the toolbar Export button."""
        if obj is self.panel.export_btn and event.type() == QEvent.EnabledChange:
            self._sync_export_enabled()
        return super().eventFilter(obj, event)

    def _sync_export_enabled(self) -> None:
        self.export_btn.setEnabled(self.panel.export_btn.isEnabled())

    def _on_project_changed(self) -> None:
        """Rebind the panels when the project object changes; re-read frames otherwise.

        The tab emits ``projectChanged`` for every project-level edit, not only for a
        switch. Rebinding on each one would delete and rebuild every profile editor and
        reload the strip a second time after an edit that already reloaded it. So the
        project identity decides: a new object rebinds, the same object only re-reads
        ``ActionCard.frames``. A change of the selected card arrives on ``actionSelected``
        (``ActionCardsPanel`` emits it whenever the table selection changes, including
        when a removed card clears it), so no action can be missed here.
        """
        project = self.tab.current_project
        if project is self._project:
            self.refresh_frames()
            return
        self._project = project
        self.panel.set_project(project)
        self._set_action(self.tab.current_action() if project is not None else None)

    def _on_action_selected(self, action_id: str) -> None:
        self._set_action(self._find_action(action_id))

    def _find_action(self, action_id: str) -> Optional[ActionCard]:
        project = self.tab.current_project
        if project is None:
            return None
        return next((a for a in project.actions if a.id == action_id), None)

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
                # The player is a preview; the export warns about a fallback.
                meta = project.sheet_meta(source, warn=False)
            except Exception as exc:  # noqa: BLE001 - reported, never raised out of a slot
                logger.error("sheet_meta(%s) failed: %s", source, exc, exc_info=True)
                self.tab.log(f"Cannot load profile '{source}': {exc}", "ERROR")
                frames, tags = [], []
            else:
                frames, tags = list(meta.frames), list(meta.tags)
        self.player.set_frames(frames)
        self.player.set_tags(tags)

    def _on_source_changed(self, _name: str) -> None:
        self._reload_player()

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

    # ----- decode failures (logged AND shown) -------------------------
    def _on_decode_failed(self, source: str) -> None:
        """A preview frame did not decode. `PreviewPlayer` logged it; show it too."""
        self.tab.log(f"Cannot decode frame image: {source or '(no file)'}", "WARNING")

    def set_view_image(self, source: Union[Path, str, QImage, QPixmap, None]) -> bool:
        """Show `source` in the pixel view; report a decode failure to the console.

        `PixelView.set_image` returns False and keeps the old image when a file does
        not decode, and it only writes to the file log. Every caller inside the tab —
        including sub-project 6's retouch preview — goes through here, so the user
        always sees why the view did not change.
        """
        ok = self.view.set_image(source)
        if not ok:
            logger.warning("PixelView could not decode %s", source)
            self.tab.log(f"Cannot decode image: {source}", "WARNING")
        return ok

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

    def _replace_frames(self, action: ActionCard, frames: List[FrameMeta], label: str,
                        *, reload: bool = True) -> None:
        """Write `action.frames` (no snapshot, no signal); reload the widgets when asked.

        `reload=False` writes a card the widgets are not showing: the strip and the player
        follow the selected action, so pushing another action's frames into them would show
        the wrong card.
        """
        action.frames = list(frames)
        if reload:
            self.strip.set_frames(action.frames)
            self._reload_player()
        self.tab.log(f"{label}: '{action.name}' now has {len(action.frames)} frames")

    def apply_frames(self, action_id: str, frames: List[FrameMeta], label: str) -> None:
        """Public edit path for sub-project 6 (retouch, image route).

        Pushes a snapshot of the action's current list, replaces it with `frames`, saves the
        project through `SpriteTab.save_current_project()`, and emits `tab.projectChanged()`.
        The strip and the player reload only when `action_id` is the selected action; they
        always show the selected card. Pass a NEW list (deep-copied frames with the new
        `source_path`); do not push a snapshot yourself and do not edit the current FrameMeta
        objects in place — the snapshot must hold the list as it was before the change.
        """
        action = self._find_action(action_id)
        if action is None:
            logger.error("apply_frames: unknown action id %r", action_id)
            self.tab.log(f"{label}: action {action_id!r} not found", "ERROR")
            return
        current = self._action
        self.undo_controller.snapshot(action.id, action.frames, label)
        self._replace_frames(action, frames, label,
                             reload=current is not None and current.id == action.id)
        self.tab.save_current_project()
        self.tab.projectChanged.emit()

    # ----- export -----------------------------------------------------
    def open_export_dialog(self) -> Optional[ExportDialog]:
        """Open the export dialog for the current project.

        The dialog is a child of the tab and the workspace holds it while it is open.
        A parentless dialog that owns worker plumbing is freed by the cyclic garbage
        collector at an arbitrary later time, and freeing that tree while another
        worker runs Qt code crashes the process (5b Task 7 finding).

        The `finally` drops the reference for every exit path, not only for a dialog
        that emits `finished`: a dialog closed without that signal — or one that
        raises out of `exec()` — must not stay held for the life of the tab, or the
        workspace refuses every later export and `shutdown()` keeps poking a closed
        dialog. See `test_export_dialog_reference_is_released_even_without_a_finished_signal`.
        `deleteLater()` runs after `exec()` returns, so the object the caller receives
        is still readable; sub-project 6 registers its export formats on it.

        The export is refused while the processing panel or the render queue runs.
        `run_pipeline` rewrites `action.frames`, the locked palette and the stage
        directories that the export reads, and no lock guards `SpriteProject` (final
        review, Important 3). The queue runs `run_pipeline` on its own worker thread
        after every clip, and the export itself runs the missing profile stages
        (`ensure_profile_stages`), so the queue must be idle too.
        """
        project = self.tab.current_project
        if project is None:
            logger.warning("Export requested with no project open")
            self.tab.log("Export: open or create a sprite project first.", "WARNING")
            QMessageBox.warning(self.tab, "Export", "Open or create a sprite project first.")
            return None
        if self.panel.is_busy():
            label = self.panel.busy_label or "processing"
            logger.warning("Export refused: the %r job is still running", label)
            self.tab.log(f"Wait for the running {label} job to finish before exporting",
                         "WARNING")
            return None
        if self.tab.queue_panel.is_busy():
            logger.warning("Export refused: the render queue is still running")
            self.tab.log("Wait for the render queue to finish before exporting", "WARNING")
            return None
        open_dialog = self._export_dialog
        if open_dialog is not None:
            logger.info("Export dialog is already open")
            return open_dialog
        dialog = self.export_dialog_factory(project, self.tab)
        self._export_dialog = dialog
        dialog.logMessage.connect(self.tab.log)
        try:
            dialog.exec()
        finally:
            self._release_export_dialog(dialog)
        return dialog

    def _release_export_dialog(self, dialog: Any) -> None:
        """Drop the workspace's reference and schedule the closed dialog for deletion."""
        if self._export_dialog is dialog:
            self._export_dialog = None
        dialog.deleteLater()

    # ----- lifecycle --------------------------------------------------
    def shutdown(self, timeout_ms: int = SHUTDOWN_TIMEOUT_MS) -> bool:
        """Pause playback and stop every worker this workspace hosts.

        Returns True only when the processing panel and any open export dialog joined
        their workers inside the bound. False means at least one worker is now an
        orphan of its host: the caller must call `join_orphans()` before this widget
        tree is destroyed, or Qt aborts on a running QThread.
        """
        self.player.pause()
        stopped = self.panel.shutdown(timeout_ms)
        dialog = self._export_dialog
        if dialog is not None:
            stopped = bool(dialog.shutdown(timeout_ms)) and stopped
        return stopped

    def join_orphans(self, timeout_ms: Optional[int] = None) -> bool:
        """Wait for every orphaned worker of this workspace. `None` waits without a bound."""
        joined = [self.panel.join_orphans(timeout_ms)]
        dialog = self._export_dialog
        if dialog is not None:
            joined.append(dialog.join_orphans(timeout_ms))
        return all(joined)
