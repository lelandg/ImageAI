"""Action cards panel: brief + genre → LLM action cards → editable table.

Per-card buttons emit ``renderRequested([id])`` / ``refineRequested(id, text)``;
the tab routes them to the queue panel. The LLM call runs in a SpriteWorker
with full request/response logging inside ``generate_action_cards``.
"""
from __future__ import annotations

import logging
import re
from typing import Callable, List, Optional, Tuple
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core.llm_models import get_all_provider_ids, get_provider_display_name
from core.sprite.generation.action_cards import (
    GENRE_CHECKLISTS, default_chat_model, generate_action_cards,
)
from core.sprite.project import ActionCard
from core.sprite.timing import suggest_clip_duration
from gui.common.dialog_conventions import bind_primary_action
from gui.dialog_utils import show_error, show_warning
from gui.sprite.prefs import LLM_PROVIDER_KEY, get_pref, set_pref
from gui.sprite.workers import WorkerHost

logger = logging.getLogger(__name__)

COL_NAME, COL_PROMPT, COL_SECONDS, COL_LOOP, COL_FRAMES, COL_FPS, COL_STATUS, COL_ACTIONS = range(8)
HEADERS = ("Name", "Prompt", "Seconds", "Loop", "Frames", "FPS", "Status", "")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
# The LLM combo carries ``core.llm_models`` provider ids; the Settings tab
# stores keys under the app's own provider names. The only mismatch today is
# Google: combo id "gemini" vs config key "google" (``gui/main_window.py``
# ``_save_and_test``). ollama/lmstudio need no key (final review, Important 2).
CONFIG_KEY_BY_PROVIDER_ID = {"gemini": "google"}
INT_LIMITS = {COL_SECONDS: (1, 15), COL_FRAMES: (1, 64), COL_FPS: (1, 60)}
RERENDER_STATES = ("rendered", "processed", "failed")


class ActionCardsPanel(WorkerHost, QGroupBox):
    renderRequested = Signal(list)       # [action_id, ...]
    refineRequested = Signal(str, str)   # action_id, instruction
    cardsChanged = Signal()
    actionSelected = Signal(str)         # selected card id, "" when nothing is selected
    logMessage = Signal(str, str)

    def __init__(self, config, parent=None):
        super().__init__("Action cards", parent)
        self.config = config
        self.project = None
        self._loading = False
        # (label, callback) pairs rendered as extra buttons on every row (5b/6 hooks)
        self.extra_row_actions: List[Tuple[str, Callable[[ActionCard], None]]] = []
        self._build()
        self._primary = bind_primary_action(self, self.generate_cards,
                                            context=Qt.WidgetWithChildrenShortcut)
        self._sync_enabled()

    # -- build -------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Brief:"))
        self.brief_edit = QLineEdit()
        self.brief_edit.setPlaceholderText("e.g. a small armored knight with a red cape")
        top.addWidget(self.brief_edit, 1)
        self.genre_combo = QComboBox()
        self.genre_combo.addItems(sorted(GENRE_CHECKLISTS))
        top.addWidget(self.genre_combo)
        self.llm_combo = QComboBox()
        for provider_id in get_all_provider_ids():
            self.llm_combo.addItem(get_provider_display_name(provider_id), provider_id)
        saved = get_pref(LLM_PROVIDER_KEY, "google")
        index = self.llm_combo.findData(saved)
        self.llm_combo.setCurrentIndex(index if index >= 0 else 0)
        self.llm_combo.currentIndexChanged.connect(self._on_llm_changed)
        top.addWidget(self.llm_combo)
        self.generate_btn = QPushButton("Generate cards")
        self.generate_btn.setToolTip("Ctrl+Enter")
        self.generate_btn.clicked.connect(self.generate_cards)
        top.addWidget(self.generate_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setToolTip("Stop the running card generation")
        self.cancel_btn.clicked.connect(self.cancel_running)
        top.addWidget(self.cancel_btn)
        root.addLayout(top)

        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_PROMPT, QHeaderView.Stretch)
        for column in (COL_NAME, COL_SECONDS, COL_LOOP, COL_FRAMES, COL_FPS, COL_STATUS, COL_ACTIONS):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.add_btn = QPushButton("Add card")
        self.add_btn.clicked.connect(self.add_card)
        self.remove_btn = QPushButton("Remove selected")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.render_all_btn = QPushButton("Render all")
        self.render_all_btn.clicked.connect(self._render_all)
        for button in (self.add_btn, self.remove_btn, self.render_all_btn):
            bottom.addWidget(button)
        bottom.addStretch(1)
        self.hint_label = QLabel("")
        bottom.addWidget(self.hint_label)
        root.addLayout(bottom)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)
        self.status_label = QLabel("")
        root.addWidget(self.status_label)

    def _sync_enabled(self) -> None:
        has_project = self.project is not None
        busy = self.is_busy()
        for widget in (self.generate_btn, self.add_btn, self.remove_btn, self.render_all_btn,
                       self.brief_edit, self.genre_combo, self.table):
            widget.setEnabled(has_project and not busy)
        self.cancel_btn.setEnabled(busy)
        if hasattr(self, "_primary"):
            self._primary.set_enabled(has_project and not busy)

    # -- project / cards ---------------------------------------------------

    def _cards(self) -> List[ActionCard]:
        return list(self.project.actions) if self.project is not None else []

    def card_by_id(self, action_id: str) -> Optional[ActionCard]:
        for card in self._cards():
            if card.id == action_id:
                return card
        return None

    def set_project(self, project) -> None:
        self.project = project
        if project is not None:
            self.brief_edit.setText(getattr(project, "brief", "") or "")
            genre = getattr(project, "genre_preset", "") or ""
            if self.genre_combo.findText(genre) >= 0:
                self.genre_combo.setCurrentText(genre)
        self.refresh()
        self._sync_enabled()

    def refresh(self) -> None:
        self._loading = True
        try:
            self.table.setRowCount(0)
            for card in self._cards():
                row = self.table.rowCount()
                self.table.insertRow(row)
                self._set_text(row, COL_NAME, card.name, card.id)
                self._set_text(row, COL_PROMPT, card.prompt, card.id)
                self._set_text(row, COL_SECONDS, str(card.duration_s), card.id)
                loop_item = QTableWidgetItem()
                loop_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                loop_item.setCheckState(Qt.Checked if card.loop else Qt.Unchecked)
                loop_item.setData(Qt.UserRole, card.id)
                self.table.setItem(row, COL_LOOP, loop_item)
                self._set_text(row, COL_FRAMES, str(card.target_frames), card.id)
                self._set_text(row, COL_FPS, str(card.fps), card.id)
                status = self._set_text(row, COL_STATUS, card.status, card.id)
                status.setFlags(status.flags() & ~Qt.ItemIsEditable)
                self.table.setCellWidget(row, COL_ACTIONS, self._row_buttons(card))
        finally:
            self._loading = False
        self.refresh_hint()

    def refresh_status(self) -> None:
        """Update the status column and row buttons without rebuilding the rows."""
        self._loading = True
        try:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, COL_NAME)
                card = self.card_by_id(item.data(Qt.UserRole)) if item else None
                if card is None:
                    continue
                self.table.item(row, COL_STATUS).setText(card.status)
                self.table.setCellWidget(row, COL_ACTIONS, self._row_buttons(card))
        finally:
            self._loading = False

    def _set_text(self, row: int, column: int, text: str, action_id: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setData(Qt.UserRole, action_id)
        self.table.setItem(row, column, item)
        return item

    def _row_buttons(self, card: ActionCard) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        render = QPushButton("Render")
        render.clicked.connect(lambda _checked=False, cid=card.id: self.request_render(cid))
        rerender = QPushButton("Re-render")
        rerender.setEnabled(card.status in RERENDER_STATES)
        rerender.clicked.connect(lambda _checked=False, cid=card.id: self.request_rerender(cid))
        refine = QPushButton("Refine…")
        refine.setEnabled(card.clip is not None and self._provider() == "omni")
        refine.setToolTip("Conversational refine (Omni only)")
        refine.clicked.connect(lambda _checked=False, cid=card.id: self.request_refine(cid))
        for button in (render, rerender, refine):
            layout.addWidget(button)
        for label, callback in self.extra_row_actions:
            extra = QPushButton(label)
            extra.clicked.connect(
                lambda _checked=False, cid=card.id, cb=callback: self._run_card_action(cid, cb))
            layout.addWidget(extra)
        return box

    def add_card_action(self, label: str, callback: Callable[[ActionCard], None]) -> None:
        """Add a button to every card row (existing and future); it calls ``callback(card)``."""
        self.extra_row_actions.append((label, callback))
        self.refresh_status()

    def _run_card_action(self, action_id: str, callback: Callable[[ActionCard], None]) -> None:
        card = self.card_by_id(action_id)
        if card is not None:
            callback(card)

    def _provider(self) -> str:
        generation = getattr(self.project, "generation", None)
        return getattr(generation, "provider", "omni") if generation is not None else "omni"

    def _model(self) -> str:
        generation = getattr(self.project, "generation", None)
        return getattr(generation, "model", "") if generation is not None else ""

    def _unique_name(self, base: str) -> str:
        base = base if NAME_RE.match(base or "") else "action"
        taken = {card.name for card in self._cards()}
        if base not in taken:
            return base
        index = 2
        while f"{base}_{index}" in taken:
            index += 1
        return f"{base}_{index}"

    # -- editing -----------------------------------------------------------

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading:
            return
        card = self.card_by_id(item.data(Qt.UserRole))
        if card is None:
            return
        column = item.column()
        text = item.text().strip()
        if column == COL_NAME:
            others = {c.name for c in self._cards() if c is not card}
            if not NAME_RE.match(text) or text in others:
                self._revert(item, card.name, f"Card name must be unique snake_case: {text!r}")
                return
            card.name = text
        elif column == COL_PROMPT:
            card.prompt = text
        elif column in INT_LIMITS:
            low, high = INT_LIMITS[column]
            current = {COL_SECONDS: card.duration_s, COL_FRAMES: card.target_frames,
                       COL_FPS: card.fps}[column]
            try:
                value = int(text)
                if not low <= value <= high:
                    raise ValueError(text)
            except ValueError:
                self._revert(item, str(current), f"Value must be an integer {low}-{high}: {text!r}")
                return
            if column == COL_SECONDS:
                card.duration_s = value
            elif column == COL_FRAMES:
                card.target_frames = value
            else:
                card.fps = value
        elif column == COL_LOOP:
            card.loop = item.checkState() == Qt.Checked
        else:
            return
        self.cardsChanged.emit()
        self.refresh_hint()

    def _revert(self, item: QTableWidgetItem, text: str, message: str) -> None:
        logger.warning(message)
        self.logMessage.emit(message, "WARNING")
        self._loading = True
        try:
            item.setText(text)
        finally:
            self._loading = False

    # -- public actions ----------------------------------------------------

    def add_card(self) -> Optional[ActionCard]:
        if self.project is None:
            return None
        card = ActionCard(id=uuid4().hex, name=self._unique_name("action"), prompt="")
        self.project.actions.append(card)
        self.refresh()
        self.cardsChanged.emit()
        return card

    def selected_ids(self) -> List[str]:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        ids = []
        for row in rows:
            item = self.table.item(row, COL_NAME)
            if item is not None:
                ids.append(item.data(Qt.UserRole))
        return ids

    def remove_selected(self) -> int:
        ids = set(self.selected_ids())
        if not ids or self.project is None:
            return 0
        before = len(self.project.actions)
        self.project.actions[:] = [c for c in self.project.actions if c.id not in ids]
        removed = before - len(self.project.actions)
        self.refresh()
        self.cardsChanged.emit()
        self.logMessage.emit(f"Removed {removed} card(s)", "INFO")
        return removed

    def request_render(self, action_id: str) -> None:
        if self.card_by_id(action_id) is None:
            return
        self.renderRequested.emit([action_id])

    def request_rerender(self, action_id: str) -> None:
        card = self.card_by_id(action_id)
        if card is None:
            return
        card.status = "draft"
        card.error = None
        self.refresh_status()
        self.renderRequested.emit([action_id])

    def request_refine(self, action_id: str) -> None:
        card = self.card_by_id(action_id)
        if card is None:
            return
        text, ok = QInputDialog.getMultiLineText(
            self, "Refine clip", f"Instruction for the model ({card.name}):")
        if not ok or not text.strip():
            return
        self.refineRequested.emit(action_id, text.strip())

    def _render_all(self) -> None:
        ids = [card.id for card in self._cards() if card.status in ("draft", "failed")]
        if not ids:
            self.logMessage.emit("No draft or failed cards to render.", "WARNING")
            return
        self.renderRequested.emit(ids)

    def llm_provider(self) -> str:
        data = self.llm_combo.currentData()
        return str(data) if data else "google"

    @staticmethod
    def _config_key_for(provider_id: str) -> str:
        """The ``ConfigManager`` key name for an ``llm_models`` provider id.

        ``get_all_provider_ids()`` yields "gemini" for Google, but the Settings
        tab writes that key (and its auth mode) under "google". Every other
        chat caller maps the name before the lookup
        (``gui/layout/text_gen_dialog.py``, ``CharacterPanel._provider_config``);
        this panel did not, so an API-key Google user got ``api_key=None`` and
        LiteLLM fell to the ``vertex_ai/`` route (final review, Important 2).
        """
        return CONFIG_KEY_BY_PROVIDER_ID.get(provider_id, provider_id)

    def _on_llm_changed(self, _index: int) -> None:
        set_pref(LLM_PROVIDER_KEY, self.llm_provider())

    def refresh_hint(self) -> None:
        ids = self.selected_ids()
        card = self.card_by_id(ids[0]) if ids else None
        if card is None:
            self.hint_label.setText("")
            return
        try:
            seconds = suggest_clip_duration(card.target_frames, card.fps,
                                            self._provider(), self._model())
            self.hint_label.setText(
                f"{card.name}: {card.target_frames} frames @ {card.fps} fps → "
                f"suggested clip {seconds} s on {self._provider()}")
        except Exception as exc:  # noqa: BLE001 - hint only
            logger.warning("Timing hint failed: %s", exc)
            self.hint_label.setText("")

    def _on_selection_changed(self) -> None:
        ids = self.selected_ids()
        self.actionSelected.emit(ids[0] if ids else "")
        self.refresh_hint()

    # -- LLM generation ----------------------------------------------------

    def generate_cards(self) -> None:
        if self.project is None:
            show_error(self, "Sprite", "Open a sprite project before generating cards.")
            return
        brief = self.brief_edit.text().strip()
        if not brief:
            show_warning(self, "Sprite", "Write a one-line brief for the character first.")
            return
        if self.is_busy():
            self.logMessage.emit("Card generation is already running.", "WARNING")
            return
        genre = self.genre_combo.currentText()
        provider = self.llm_provider()
        try:
            # Registry id per provider family; "chat" is not a registry family.
            model = default_chat_model(provider)
        except Exception as exc:  # noqa: BLE001 - surface every resolver failure
            logger.error("Chat model resolution failed for %s: %s", provider, exc)
            self._on_failed(f"Cannot pick a chat model for {provider}: {exc}")
            return
        config_key = self._config_key_for(provider)
        api_key = self.config.get_api_key(config_key)
        auth_mode = self.config.get_auth_mode(config_key)
        plate_color = getattr(self.project, "plate_color", "#00FF00")
        self.project.brief = brief
        self.project.genre_preset = genre

        def job(progress, token):
            progress("cards", 0, 0, f"Asking {provider}/{model} for {genre} action cards")
            drafts = generate_action_cards(brief, genre, provider=provider, model=model,
                                           api_key=api_key, auth_mode=auth_mode,
                                           plate_color=plate_color,
                                           log=lambda m: progress("cards", 0, 0, m),
                                           token=token)
            token.raise_if_cancelled()
            return list(drafts)

        self.logMessage.emit(f"Generating action cards ({genre}) via {provider}/{model}", "INFO")
        worker = self.start_job(job, label="action cards", on_finished=self._on_cards_done,
                                on_failed=self._on_failed, on_cancelled=self._on_cancelled,
                                on_progress=self._on_progress)
        if worker is not None:
            self.progress.setRange(0, 0)
            self.progress.setVisible(True)
            self._sync_enabled()

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        self.status_label.setText(f"{stage}: {message}")
        self.logMessage.emit(f"[{stage}] {message}", "INFO")

    def _finish(self) -> None:
        self.progress.setVisible(False)
        self.status_label.setText("")
        self._sync_enabled()

    def _on_worker_idle(self) -> None:
        """A worker orphaned by a timed-out ``shutdown()`` finally stopped."""
        self._sync_enabled()

    def _on_cards_done(self, drafts) -> None:
        added = 0
        for draft in drafts:
            card = ActionCard(id=uuid4().hex, name=self._unique_name(draft.name),
                              prompt=draft.prompt, duration_s=int(draft.duration_s),
                              loop=bool(draft.loop), target_frames=int(draft.target_frames),
                              fps=int(draft.fps))
            self.project.actions.append(card)
            added += 1
        self._finish()
        self.refresh()
        self.logMessage.emit(f"Added {added} action card(s)", "SUCCESS")
        self.cardsChanged.emit()

    def _on_failed(self, message: str) -> None:
        self._finish()
        self.logMessage.emit(message, "ERROR")
        show_error(self, "Sprite", message)

    def _on_cancelled(self) -> None:
        self._finish()
        self.logMessage.emit("Card generation cancelled.", "WARNING")
