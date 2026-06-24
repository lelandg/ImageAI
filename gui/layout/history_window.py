"""Browsable iteration-history window for the layout designer."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel,
)
from PySide6.QtCore import Signal, Qt


class HistoryWindow(QDialog):
    restoreRequested = Signal(str)  # snapshot id

    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Layout History")
        self.resize(420, 360)
        self._history = history
        self._build()
        self.set_history(history)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Iterations (newest last):"))
        self.list_widget = QListWidget()
        lay.addWidget(self.list_widget, 1)
        row = QHBoxLayout()
        self.restore_btn = QPushButton("Restore selected")
        self.restore_btn.clicked.connect(self._on_restore)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(self.restore_btn)
        row.addWidget(close_btn)
        lay.addLayout(row)

    def set_history(self, history):
        self._history = history
        self.list_widget.clear()
        for s in history.snapshots():
            label = f"[{s.timestamp}] {s.prompt[:60]}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, s.id)
            self.list_widget.addItem(item)

    def _on_restore(self):
        item = self.list_widget.currentItem()
        if item is None:
            return
        self.restoreRequested.emit(item.data(Qt.UserRole))
