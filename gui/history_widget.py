"""Reusable history widget for dialog interactions."""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QPixmap

from .common.dialog_conventions import persist_splitter, restore_splitter, standard_splitter

logger = logging.getLogger(__name__)


class DialogHistoryWidget(QWidget):
    """Reusable widget for showing dialog interaction history."""

    itemSelected = Signal(dict)  # Emitted when an item is selected
    itemDoubleClicked = Signal(dict)  # Emitted when an item is double-clicked

    def __init__(self, dialog_name: str = "dialog", parent=None):
        super().__init__(parent)
        self.dialog_name = dialog_name
        self.history = []  # Full history loaded from file
        self.settings = QSettings("ImageAI", f"{dialog_name}_history")
        self.init_ui()
        self.load_history()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create splitter for table and detail view
        self.splitter = standard_splitter(Qt.Vertical)
        splitter = self.splitter

        # Top section: History table
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # History label
        self.history_label = QLabel(f"History (0 items)")
        top_layout.addWidget(self.history_label)

        # Create table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels([
            "Date & Time", "Input", "Response", "Provider"
        ])

        # Configure table
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSortingEnabled(True)

        # Set column widths
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Date & Time
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Input
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Response
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Provider

        top_layout.addWidget(self.history_table)

        splitter.addWidget(top_widget)

        # Bottom section: Detail view
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        bottom_layout.addWidget(QLabel("Details:"))

        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        bottom_layout.addWidget(self.detail_view)

        splitter.addWidget(bottom_widget)

        # Restore last position; default proportions (70% table, 30% details)
        if not restore_splitter(self.settings, "splitter_state", splitter):
            splitter.setSizes([350, 150])
        splitter.splitterMoved.connect(
            lambda *_: persist_splitter(self.settings, "splitter_state", self.splitter)
        )

        layout.addWidget(splitter)

        # Buttons
        button_layout = QHBoxLayout()
        self.btn_clear = QPushButton("Clear History")
        self.btn_clear.clicked.connect(self.clear_history)
        button_layout.addWidget(self.btn_clear)
        button_layout.addStretch()

        self.btn_export = QPushButton("Export History")
        self.btn_export.clicked.connect(self.export_history)
        button_layout.addWidget(self.btn_export)

        layout.addLayout(button_layout)

        # Connect signals. itemActivated fires for both keyboard Enter and
        # double-click, giving keyboard users parity.
        self.history_table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.history_table.itemActivated.connect(self._on_item_double_clicked)

    def add_entry(self, input_text: str, response_text: str, provider: str = "",
                  model: str = "", metadata: Optional[Dict] = None):
        """Add a new entry to the history."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "input": input_text,
            "response": response_text,
            "provider": provider,
            "model": model,
            "metadata": metadata or {}
        }

        self.history.insert(0, entry)  # Add to beginning
        self.refresh_table()
        self.save_history()

        return entry

    def refresh_table(self):
        """Refresh the history table with current data."""
        # Sorting must be off while populating, or rows get reordered
        # mid-fill and items land in the wrong row.
        self.history_table.setSortingEnabled(False)
        self.history_table.setRowCount(len(self.history))

        for row, item in enumerate(self.history):
            # Date & Time
            timestamp = item.get('timestamp', '')
            datetime_str = ''
            sortable_datetime = None

            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    datetime_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    sortable_datetime = dt
                except:
                    datetime_str = timestamp

            datetime_item = QTableWidgetItem(datetime_str)
            if sortable_datetime:
                datetime_item.setData(Qt.UserRole + 1, sortable_datetime)
            datetime_item.setData(Qt.UserRole, item)  # Store full data
            self.history_table.setItem(row, 0, datetime_item)

            # Input
            input_text = item.get('input', '')
            input_item = QTableWidgetItem(input_text[:100] + '...' if len(input_text) > 100 else input_text)
            input_item.setToolTip(input_text)
            self.history_table.setItem(row, 1, input_item)

            # Response
            response_text = item.get('response', '')
            response_item = QTableWidgetItem(response_text[:100] + '...' if len(response_text) > 100 else response_text)
            response_item.setToolTip(response_text)
            self.history_table.setItem(row, 2, response_item)

            # Provider
            provider = item.get('provider', '')
            model = item.get('model', '')
            provider_text = f"{provider} ({model})" if model else provider
            provider_item = QTableWidgetItem(provider_text)
            self.history_table.setItem(row, 3, provider_item)

        # Update label with total count
        self.history_label.setText(f"History ({len(self.history)} items)")

        # Sort by date descending (newest first)
        self.history_table.setSortingEnabled(True)
        self.history_table.sortByColumn(0, Qt.DescendingOrder)

    def _on_selection_changed(self):
        """Handle selection change in the table."""
        selected = self.history_table.selectedItems()
        if selected:
            # Get the data from the first column of the selected row
            row = selected[0].row()
            item_data = self.history_table.item(row, 0).data(Qt.UserRole)
            if item_data:
                # Update detail view
                details = []
                details.append(f"Time: {item_data.get('timestamp', 'Unknown')}")
                details.append(f"Provider: {item_data.get('provider', 'Unknown')}")
                details.append(f"Model: {item_data.get('model', 'Unknown')}")
                details.append(f"\nInput:\n{item_data.get('input', '')}")
                details.append(f"\nResponse:\n{item_data.get('response', '')}")

                self.detail_view.setPlainText('\n'.join(details))
                self.itemSelected.emit(item_data)

    def _on_item_double_clicked(self, item):
        """Handle double-click on a table item."""
        row = self.history_table.row(item)
        item_data = self.history_table.item(row, 0).data(Qt.UserRole)
        if item_data:
            self.itemDoubleClicked.emit(item_data)

    def clear_history(self):
        """Clear all history (after confirmation — this is destructive)."""
        if not self.history:
            return
        reply = QMessageBox.question(
            self,
            "Clear History",
            f"Delete all {len(self.history)} history entries? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.history = []
        self.refresh_table()
        self.save_history()
        self.detail_view.clear()

    def _history_path(self) -> Path:
        """Path of this dialog's history file."""
        from core.paths import get_data_paths

        return get_data_paths().history_file(self.dialog_name)

    def save_history(self):
        """Save history to settings."""
        # Limit history to 100 most recent items
        if len(self.history) > 100:
            self.history = self.history[:100]

        history_file = self._history_path()
        try:
            history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history to {history_file}: {e}")

    def load_history(self):
        """Load history from settings."""
        history_file = self._history_path()

        if history_file.exists():
            try:
                with open(history_file, 'r') as f:
                    self.history = json.load(f)
                    self.refresh_table()
            except Exception as e:
                logger.error(f"Failed to load history from {history_file}: {e}")
                self.history = []

    def export_history(self):
        """Export history to a file."""
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export History",
            f"{self.dialog_name}_history.json",
            "JSON Files (*.json);;All Files (*.*)"
        )

        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(self.history, f, indent=2)
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Export Error", f"Failed to export history: {str(e)}")

    def get_latest_entry(self) -> Optional[Dict]:
        """Get the most recent history entry."""
        return self.history[0] if self.history else None

    def get_history(self) -> List[Dict]:
        """Get all history entries."""
        return self.history.copy()