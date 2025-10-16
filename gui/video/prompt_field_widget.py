"""
Prompt field widget with LLM generation and undo/redo support.

This module provides a reusable widget for prompt editing with:
- Text input field
- ✨ LLM generation button
- ↶ Undo button
- ↷ Redo button
- Prompt history management (up to 256 levels)
"""

import logging
from typing import Optional, Callable

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton
from PySide6.QtCore import Signal

from core.video.project import PromptHistory


class PromptFieldWidget(QWidget):
    """
    Reusable prompt field with LLM generation and undo/redo.

    Signals:
        text_changed: Emitted when text changes (str)
        llm_requested: Emitted when LLM button clicked
        undo_clicked: Emitted when undo button clicked
        redo_clicked: Emitted when redo button clicked
    """

    # Signals
    text_changed = Signal(str)
    llm_requested = Signal()
    undo_clicked = Signal()
    redo_clicked = Signal()

    def __init__(self, placeholder: str = "", parent=None):
        """
        Initialize prompt field widget.

        Args:
            placeholder: Placeholder text for the text field
            parent: Parent widget
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.history = PromptHistory(max_size=256)

        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Text edit field
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText(placeholder)
        self.text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.text_edit, stretch=1)  # Take most space

        # LLM button
        self.llm_button = QPushButton("✨")
        self.llm_button.setToolTip("Generate with LLM")
        self.llm_button.setMaximumWidth(30)
        self.llm_button.setStyleSheet("QPushButton { padding: 2px; margin: 0px; font-size: 16px; }")
        self.llm_button.clicked.connect(self.llm_requested.emit)
        layout.addWidget(self.llm_button)

        # Undo button
        self.undo_button = QPushButton("↶")
        self.undo_button.setToolTip("Undo")
        self.undo_button.setMaximumWidth(30)
        self.undo_button.setStyleSheet("QPushButton { padding: 2px; margin: 0px; font-size: 16px; }")
        self.undo_button.clicked.connect(self._on_undo)
        self.undo_button.setEnabled(False)
        layout.addWidget(self.undo_button)

        # Redo button
        self.redo_button = QPushButton("↷")
        self.redo_button.setToolTip("Redo")
        self.redo_button.setMaximumWidth(30)
        self.redo_button.setStyleSheet("QPushButton { padding: 2px; margin: 0px; font-size: 16px; }")
        self.redo_button.clicked.connect(self._on_redo)
        self.redo_button.setEnabled(False)
        layout.addWidget(self.redo_button)

    def _on_text_changed(self, text: str):
        """Handle text change"""
        # Only add to history if it's a significant change (not every keystroke)
        # We'll add to history when LLM generates or when user explicitly commits
        self.text_changed.emit(text)
        self._update_button_states()

    def set_text(self, text: str, add_to_history: bool = False):
        """
        Set text programmatically.

        Args:
            text: Text to set
            add_to_history: If True, add current text to history before changing
        """
        if add_to_history:
            current = self.text_edit.text()
            if current and current != text:
                self.history.add(current)

        # Temporarily block signals to avoid recursive updates
        self.text_edit.blockSignals(True)
        self.text_edit.setText(text)
        self.text_edit.blockSignals(False)

        self._update_button_states()

    def get_text(self) -> str:
        """Get current text"""
        return self.text_edit.text()

    def commit_to_history(self):
        """Commit current text to history"""
        text = self.text_edit.text()
        if text:
            self.history.add(text)
            self._update_button_states()

    def _on_undo(self):
        """Handle undo button click"""
        # First, save current state if not already in history
        current = self.text_edit.text()
        if current and (not self.history.history or self.history.get_current() != current):
            self.history.add(current)

        previous = self.history.undo()
        if previous is not None:
            self.set_text(previous, add_to_history=False)
            self.text_changed.emit(previous)

        self._update_button_states()
        self.undo_clicked.emit()

    def _on_redo(self):
        """Handle redo button click"""
        next_text = self.history.redo()
        if next_text is not None:
            self.set_text(next_text, add_to_history=False)
            self.text_changed.emit(next_text)

        self._update_button_states()
        self.redo_clicked.emit()

    def _update_button_states(self):
        """Update undo/redo button enabled states"""
        self.undo_button.setEnabled(self.history.can_undo())
        self.redo_button.setEnabled(self.history.can_redo())

    def get_history(self) -> PromptHistory:
        """Get the history object (for serialization)"""
        return self.history

    def set_history(self, history: PromptHistory):
        """Set the history object (for deserialization)"""
        self.history = history
        self._update_button_states()
