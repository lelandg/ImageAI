"""Open a Sprite project by its saved name, without browsing storage folders."""
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
)


class SpriteProjectDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open sprite project")
        self.resize(520, 400)
        self._external_path = None
        self._manager = manager
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose a project:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search projects…")
        layout.addWidget(self.search)
        self.project_list = QListWidget()
        layout.addWidget(self.project_list)
        projects = manager.list_projects()
        counts = Counter(str(info["name"]) for info in projects)
        occurrences = Counter()
        for info in projects:
            name = str(info["name"])
            occurrences[name] += 1
            label = name
            if counts[name] > 1:
                # Distinguish even copies made in the same second, without paths.
                label += f" — copy {occurrences[name]} of {counts[name]}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, str(info["path"]))
            self.project_list.addItem(item)
        self.empty_label = QLabel("No saved projects yet." if not projects else "")
        layout.addWidget(self.empty_label)
        browse = QPushButton("Browse for another project…")
        browse.clicked.connect(self._browse)
        layout.addWidget(browse)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Open | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Open).setDefault(True)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.project_list.currentItemChanged.connect(self._update_open)
        self.project_list.itemDoubleClicked.connect(lambda _item: self.accept())
        self.search.textChanged.connect(self._filter)
        self.project_list.setCurrentRow(0)
        self._update_open()

    def _update_open(self, *_args):
        item = self.project_list.currentItem()
        self.buttons.button(QDialogButtonBox.Open).setEnabled(
            item is not None and not item.isHidden())

    def _filter(self, text):
        first = None
        for index in range(self.project_list.count()):
            item = self.project_list.item(index)
            item.setHidden(text.casefold() not in item.text().casefold())
            if not item.isHidden() and first is None:
                first = item
        self.project_list.setCurrentItem(first)
        self._update_open()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open sprite project", str(self._manager.base_dir),
            "Sprite projects (*.iasprite.json)")
        if path:
            self._external_path = Path(path)
            self.accept()

    def selected_path(self):
        if self._external_path is not None:
            return self._external_path
        item = self.project_list.currentItem()
        return Path(item.data(Qt.UserRole)) if item and not item.isHidden() else None
