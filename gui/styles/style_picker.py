"""Compact reusable style picker: Style: [None v] [Manage...] [ ] Smart merge.

Dropped into the Generate tab, video workspace, and (via the Generate tab)
layout fill. Selection and smart-merge state persist per surface.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel,
                               QPushButton, QWidget)

from core.styles.models import Style
from core.styles.store import StyleStore

logger = logging.getLogger(__name__)


class StylePickerWidget(QWidget):
    style_changed = Signal(str)  # style id or "" for None

    def __init__(self, config, surface: str, parent=None, show_smart: bool = True):
        super().__init__(parent)
        self.config = config
        self.surface = surface
        self._store = StyleStore()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Style:"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(160)
        layout.addWidget(self.combo)
        self.manage_btn = QPushButton("Manage…")
        layout.addWidget(self.manage_btn)
        self.smart_check: Optional[QCheckBox] = None
        if show_smart:
            self.smart_check = QCheckBox("Smart merge")
            self.smart_check.setToolTip(
                "Fuse prompt and style with the configured LLM "
                "(falls back to plain concat on failure)")
            self.smart_check.setChecked(
                bool(self.config.get(f"style_smart_{surface}", False)))
            self.smart_check.toggled.connect(self._on_smart_toggled)
            layout.addWidget(self.smart_check)
        layout.addStretch()

        self.manage_btn.clicked.connect(self._open_manager)
        self.combo.currentIndexChanged.connect(self._on_changed)
        self.refresh()

    # -- store injection for tests / shared instances ----------------------
    def set_store(self, store: StyleStore) -> None:
        self._store = store

    def refresh(self) -> None:
        """Reload styles; keep the current selection when it still exists."""
        wanted = (self.combo.currentData()
                  or self.config.get(f"style_selected_{self.surface}", ""))
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("None", "")
        for s in self._store.list_styles():
            self.combo.addItem(s.name, s.id)
            idx = self.combo.count() - 1
            tip = s.description or (s.prompt_text or "")[:120]
            if tip:
                self.combo.setItemData(idx, tip, role=Qt.ToolTipRole)
        pos = self.combo.findData(wanted) if wanted else 0
        self.combo.setCurrentIndex(pos if pos >= 0 else 0)
        self.combo.blockSignals(False)

    def current_style(self) -> Optional[Style]:
        sid = self.combo.currentData()
        return self._store.get(sid) if sid else None

    def smart_merge_enabled(self) -> bool:
        return bool(self.smart_check and self.smart_check.isChecked())

    # -- slots -------------------------------------------------------------
    def _on_changed(self, _idx: int) -> None:
        sid = self.combo.currentData() or ""
        self.config.set(f"style_selected_{self.surface}", sid)
        self.config.save()
        self.style_changed.emit(sid)

    def _on_smart_toggled(self, checked: bool) -> None:
        self.config.set(f"style_smart_{self.surface}", bool(checked))
        self.config.save()

    def _open_manager(self) -> None:
        from gui.styles.style_manager_dialog import StyleManagerDialog
        dlg = StyleManagerDialog(self.config, store=self._store, parent=self)
        dlg.exec()
        self.refresh()
