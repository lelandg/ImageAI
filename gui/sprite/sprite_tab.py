"""Sprite tab: project toolbar, intake / action-card / queue panels, 5b slots, console.

Layout (design §4.5): a horizontal splitter with the left column
[CharacterPanel, ActionCardsPanel, QueuePanel] and the right column
[frame_area, preview_area, processing_area] — three containers sub-project 5b
fills through ``set_frame_widget`` / ``set_preview_widget`` /
``set_processing_widget`` — above a ``DialogStatusConsole``.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from core.paths import get_data_paths
from core.sprite.configs import NamedConfigStore
from core.sprite.project import ActionCard, SpriteProject, SpriteProjectManager
from gui.common.dialog_conventions import persist_splitter, restore_splitter, standard_splitter
from gui.dialog_utils import show_error, show_warning
from gui.llm_utils import DialogStatusConsole
from gui.sprite.action_cards_panel import ActionCardsPanel
from gui.sprite.character_panel import CharacterPanel
from gui.sprite.generation_settings_dialog import GenerationSettingsDialog
from gui.sprite.prefs import sprite_settings
from gui.sprite.queue_panel import QueuePanel
from providers import get_provider

logger = logging.getLogger(__name__)

PROJECT_FILTER = "Sprite projects (*.iasprite.json)"
SPLITTER_KEYS = {
    "main": "sprite/splitter_main",
    "left": "sprite/splitter_left",
    "right": "sprite/splitter_right",
    "console": "sprite/splitter_console",
}
LEVELS = {"INFO": logging.INFO, "SUCCESS": logging.INFO,
          "WARNING": logging.WARNING, "ERROR": logging.ERROR}
NO_PROJECT_TEXT = "No project — click New… or send a character image here"


class SpriteTab(QWidget):
    addToHistoryRequested = Signal(dict)
    projectChanged = Signal()
    actionSelected = Signal(str)   # selected card id from the action-cards table, "" when none

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.project_manager = SpriteProjectManager()
        self.config_store = NamedConfigStore()
        self._project: Optional[SpriteProject] = None
        self.frame_widget: Optional[QWidget] = None
        self.preview_widget: Optional[QWidget] = None
        self.processing_widget: Optional[QWidget] = None
        self._build()
        self._wire()
        self._restore_splitters()
        self._sync_title()
        # Sub-project 5b: strip + preview + processing + export + shortcuts + undo.
        # Local import: frames_workspace imports nothing from sprite_tab at runtime,
        # and this keeps sprite_tab importable on its own.
        from .frames_workspace import FramesWorkspace
        self.frames_workspace = FramesWorkspace(self)

    # -- build -------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        self.toolbar_layout = QHBoxLayout()
        toolbar = self.toolbar_layout
        self.new_btn = QPushButton("New…")
        self.new_btn.clicked.connect(self.new_project)
        self.open_btn = QPushButton("Open…")
        self.open_btn.clicked.connect(self.open_project)
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_project)
        self.save_as_btn = QPushButton("Save As…")
        self.save_as_btn.clicked.connect(self.save_project_as)
        self.settings_btn = QPushButton("Generation Settings…")
        self.settings_btn.clicked.connect(self.open_generation_settings)
        for button in (self.new_btn, self.open_btn, self.save_btn, self.save_as_btn, self.settings_btn):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        self.title_label = QLabel()
        toolbar.addWidget(self.title_label)
        root.addLayout(toolbar)

        self.character_panel = CharacterPanel(self.config)
        self.action_cards_panel = ActionCardsPanel(self.config)
        self.queue_panel = QueuePanel(self.config)
        self.left_splitter = standard_splitter(Qt.Vertical)
        for panel in (self.character_panel, self.action_cards_panel, self.queue_panel):
            self.left_splitter.addWidget(panel)

        self.frame_area = self._make_area("Frame strip (sub-project 5b)")
        self.preview_area = self._make_area("Preview player (sub-project 5b)")
        self.processing_area = self._make_area("Processing (sub-project 5b)")
        self.right_splitter = standard_splitter(Qt.Vertical)
        for area in (self.frame_area, self.preview_area, self.processing_area):
            self.right_splitter.addWidget(area)

        self.main_splitter = standard_splitter(Qt.Horizontal)
        self.main_splitter.addWidget(self.left_splitter)
        self.main_splitter.addWidget(self.right_splitter)

        self.console = DialogStatusConsole("Sprite console")
        self.console_splitter = standard_splitter(Qt.Vertical)
        self.console_splitter.addWidget(self.main_splitter)
        self.console_splitter.addWidget(self.console)
        root.addWidget(self.console_splitter, 1)

    @staticmethod
    def _make_area(text: str) -> QWidget:
        area = QWidget()
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(text)
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: gray; border: 1px dashed gray;")
        layout.addWidget(hint)
        return area

    @staticmethod
    def _fill_area(area: QWidget, widget: QWidget) -> None:
        layout = area.layout()
        while layout.count():
            item = layout.takeAt(0)
            old = item.widget()
            if old is not None:
                old.setParent(None)
                old.deleteLater()
        layout.addWidget(widget)

    def set_frame_widget(self, widget: QWidget) -> None:
        self._fill_area(self.frame_area, widget)
        self.frame_widget = widget

    def set_preview_widget(self, widget: QWidget) -> None:
        self._fill_area(self.preview_area, widget)
        self.preview_widget = widget

    def set_processing_widget(self, widget: QWidget) -> None:
        self._fill_area(self.processing_area, widget)
        self.processing_widget = widget

    def add_toolbar_action(self, text: str, slot) -> QPushButton:
        """Add a toolbar button before the stretch (sub-project 5b adds Export… here)."""
        button = QPushButton(text)
        button.clicked.connect(slot)
        index = self.toolbar_layout.count()
        for i in range(self.toolbar_layout.count()):
            if self.toolbar_layout.itemAt(i).spacerItem() is not None:
                index = i
                break
        self.toolbar_layout.insertWidget(index, button)
        return button

    # -- wiring ------------------------------------------------------------

    def _wire(self) -> None:
        for panel in (self.character_panel, self.action_cards_panel, self.queue_panel):
            panel.logMessage.connect(self.log)
        self.character_panel.historyEntry.connect(self.addToHistoryRequested)
        self.character_panel.sourceChanged.connect(self._on_character_changed)
        self.character_panel.plateReady.connect(self._on_character_changed)
        self.character_panel.turnaroundReady.connect(self._on_character_changed)
        self.character_panel.plateColorChanged.connect(self._on_character_changed)
        self.action_cards_panel.cardsChanged.connect(self._on_cards_changed)
        self.action_cards_panel.renderRequested.connect(self._on_render_requested)
        self.action_cards_panel.refineRequested.connect(self._on_refine_requested)
        self.action_cards_panel.actionSelected.connect(self.actionSelected)
        self.queue_panel.statusChanged.connect(self._on_queue_status_changed)

    def _on_character_changed(self, *_args) -> None:
        self._autosave()
        self.projectChanged.emit()

    def _on_cards_changed(self) -> None:
        self.queue_panel.refresh()
        self._autosave()
        self.projectChanged.emit()

    def _on_render_requested(self, ids) -> None:
        ids = list(ids)
        self.queue_panel.enqueue(ids)
        self.queue_panel.start(ids)

    def _on_refine_requested(self, action_id: str, instruction: str) -> None:
        self.queue_panel.refine(action_id, instruction)

    def _on_queue_status_changed(self) -> None:
        self.action_cards_panel.refresh_status()
        self._autosave()
        self.projectChanged.emit()

    # -- splitters ---------------------------------------------------------

    def _restore_splitters(self) -> None:
        settings = sprite_settings()
        if not restore_splitter(settings, SPLITTER_KEYS["main"], self.main_splitter):
            self.main_splitter.setSizes([480, 820])
        if not restore_splitter(settings, SPLITTER_KEYS["left"], self.left_splitter):
            self.left_splitter.setSizes([260, 320, 220])
        if not restore_splitter(settings, SPLITTER_KEYS["right"], self.right_splitter):
            self.right_splitter.setSizes([220, 360, 220])
        if not restore_splitter(settings, SPLITTER_KEYS["console"], self.console_splitter):
            self.console_splitter.setSizes([640, 160])

    def _persist_splitters(self) -> None:
        settings = sprite_settings()
        persist_splitter(settings, SPLITTER_KEYS["main"], self.main_splitter)
        persist_splitter(settings, SPLITTER_KEYS["left"], self.left_splitter)
        persist_splitter(settings, SPLITTER_KEYS["right"], self.right_splitter)
        persist_splitter(settings, SPLITTER_KEYS["console"], self.console_splitter)
        settings.sync()

    # -- console -----------------------------------------------------------

    def log(self, message: str, level: str = "INFO") -> None:
        self.console.log(message, level)
        logger.log(LEVELS.get(level, logging.INFO), "sprite: %s", message)

    def _report_error(self, what: str, exc: Exception) -> None:
        message = f"Could not {what}: {exc}"
        self.console.log(message, "ERROR")
        show_error(self, "Sprite", message, exception=exc)

    # -- project -----------------------------------------------------------

    @property
    def current_project(self) -> Optional[SpriteProject]:
        return self._project

    def current_action(self) -> Optional[ActionCard]:
        """The card selected in the action-cards table, or None."""
        ids = self.action_cards_panel.selected_ids()
        return self.action_cards_panel.card_by_id(ids[0]) if ids else None

    def make_provider(self, name: str = "google"):
        """Build an image provider with this tab's credentials.

        Raises ValueError with a user-facing message when no key is configured;
        call it inside a worker job so the message reaches ``failed(str)``.
        """
        api_key = self.config.get_api_key(name)
        if not api_key:
            raise ValueError(f"No {name} API key is configured. Add one in Settings.")
        return get_provider(name, {"api_key": api_key, "auth_mode": self.config.get_auth_mode(name)})

    def _shutdown_panel_workers(self) -> None:
        """Cancel and join any in-flight panel job before the project is replaced.

        A worker still running against the OLD project must never deliver its
        ``finished``/``failed`` result after the panels have been repointed at
        a NEW project — that result would be written against the wrong
        project (cross-project data corruption). ``WorkerHost.shutdown()``
        cancels and bound-waits the worker, so by the time this returns, the
        job either already finished (and its callback already ran, against
        the still-current OLD project) or it will emit ``cancelled()`` — never
        a late ``finished``/``failed`` against the new project. A job whose
        result was already queued (but not yet delivered) when ``shutdown()``
        runs is caught separately: ``WorkerHost._guarded`` drops any
        finished/failed/cancelled event for a worker that is no longer the
        panel's live ``_worker`` (review finding, fix round 2).
        """
        for panel in (self.character_panel, self.action_cards_panel, self.queue_panel):
            label = panel.busy_label
            stopped = panel.shutdown()
            if label is not None:
                self.log(f"Cancelled running {label} job to switch project", "WARNING")
            if not stopped:
                # The worker is now an orphan of its panel: it keeps the panel
                # busy (so no second job writes the same paths) and its events
                # are dropped by _guarded, but it still holds the OLD project.
                self.log(f"The {label} job is still finishing; it cannot start again "
                         "until it stops.", "WARNING")

    def _apply_project(self, project: SpriteProject) -> None:
        self._shutdown_panel_workers()
        self._project = project
        self.character_panel.set_project(project)
        self.action_cards_panel.set_project(project)
        self.queue_panel.set_project(project)
        self._sync_title()
        self.log(f"Project: {project.name} ({project.project_dir})", "INFO")
        self.projectChanged.emit()

    def _sync_title(self) -> None:
        has_project = self._project is not None
        if has_project:
            self.title_label.setText(f"{self._project.name} — {self._project.project_dir}")
        else:
            self.title_label.setText(NO_PROJECT_TEXT)
        for button in (self.save_btn, self.save_as_btn, self.settings_btn):
            button.setEnabled(has_project)

    def _autosave(self) -> None:
        if self._project is None:
            return
        try:
            self.project_manager.save_project(self._project)
        except Exception as exc:  # noqa: BLE001 - reported, never raised out of a slot
            self._report_error("save project", exc)

    def new_project(self) -> None:
        name, ok = QInputDialog.getText(self, "New sprite project", "Project name:", text="sprite")
        if ok and name.strip():
            self.new_project_named(name.strip())

    def new_project_named(self, name: str) -> Optional[SpriteProject]:
        try:
            project = self.project_manager.create_project(name)
        except Exception as exc:  # noqa: BLE001
            self._report_error("create project", exc)
            return None
        self._apply_project(project)
        return project

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open sprite project", str(get_data_paths().sprite_projects()), PROJECT_FILTER)
        if path:
            self.open_project_from(path)

    def open_project_from(self, path) -> Optional[SpriteProject]:
        try:
            project = self.project_manager.load_project(Path(path))
        except Exception as exc:  # noqa: BLE001
            self._report_error("open project", exc)
            return None
        self._apply_project(project)
        return project

    def save_project(self) -> Optional[Path]:
        if self._project is None:
            show_warning(self, "Sprite", "There is no project to save.")
            return None
        try:
            saved = self.project_manager.save_project(self._project)
        except Exception as exc:  # noqa: BLE001
            self._report_error("save project", exc)
            return None
        self.log(f"Saved → {saved}", "SUCCESS")
        self._sync_title()
        return Path(saved)

    def save_project_as(self) -> None:
        if self._project is None:
            show_warning(self, "Sprite", "There is no project to save.")
            return
        start = str(self._project.project_dir or get_data_paths().sprite_projects())
        path, _ = QFileDialog.getSaveFileName(self, "Save sprite project as", start, PROJECT_FILTER)
        if path:
            self.save_project_to(path)

    def save_project_to(self, path) -> Optional[Path]:
        if self._project is None:
            return None
        try:
            saved = self._project.save(Path(path))
        except Exception as exc:  # noqa: BLE001
            self._report_error("save project", exc)
            return None
        self.log(f"Saved → {saved}", "SUCCESS")
        self._sync_title()
        return Path(saved)

    def open_generation_settings(self) -> None:
        if self._project is None:
            show_warning(self, "Sprite", "Open a sprite project first.")
            return
        dialog = GenerationSettingsDialog(self._project.generation, self.config_store, self)
        if dialog.exec() != QDialog.Accepted:
            return
        settings = dialog.settings()
        self._project.generation = settings
        self.log(f"Generation settings [{settings.config_name}]: {settings.provider}/"
                 f"{settings.model or 'default'} {settings.resolution} {settings.aspect_ratio} "
                 f"{settings.duration_s}s @ {settings.fps} fps, plate {settings.plate_color}", "INFO")
        self.queue_panel.refresh()
        self.action_cards_panel.refresh_hint()
        self._autosave()
        self.projectChanged.emit()

    # -- cross-tab entry ---------------------------------------------------

    def set_character_source(self, path: Path) -> None:
        """Entry point for "Send to Sprite": creates a project when none is open."""
        path = Path(path)
        if self._project is None and self.new_project_named(path.stem or "sprite") is None:
            return
        self.log(f"Character source: {path}", "INFO")
        self.character_panel.set_source(path)

    # -- lifecycle ---------------------------------------------------------

    def shutdown(self) -> bool:
        """Cancel every running worker and persist layout. MainWindow calls this on close.

        Returns True only when every panel and the 5b workspace joined its worker
        inside the bound. A False result means at least one worker is an orphan;
        the caller must call ``join_orphans()`` before this widget tree is
        destroyed, or Qt aborts on a running QThread (final review, Important 1).
        """
        # The 5b workspace first: it hosts the processing panel's pipeline worker and
        # any open export dialog, which must stop before this widget tree goes down.
        workspace_stopped = self.frames_workspace.shutdown()
        stopped = [panel.shutdown()
                   for panel in (self.character_panel, self.action_cards_panel, self.queue_panel)]
        self._persist_splitters()
        return workspace_stopped and all(stopped)

    def join_orphans(self, timeout_ms: Optional[int] = None) -> bool:
        """Wait for every panel's orphaned worker. ``None`` waits without a bound."""
        joined = [panel.join_orphans(timeout_ms)
                  for panel in (self.character_panel, self.action_cards_panel, self.queue_panel)]
        joined.append(self.frames_workspace.join_orphans(timeout_ms))
        return all(joined)

    def closeEvent(self, event) -> None:
        if not self.shutdown():
            logger.warning("A sprite worker did not stop in time; waiting for it before close")
            self.join_orphans()
        super().closeEvent(event)
