"""Project style editor: per-role font family/size/color + palette."""
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QComboBox, QLineEdit, QSpinBox, QLabel,
)
from PySide6.QtCore import Signal

from core.layout.models import ProjectStyle, TextStyle


class StylePanel(QWidget):
    styleChanged = Signal(object)  # ProjectStyle

    def __init__(self, parent=None):
        super().__init__(parent)
        self._style = ProjectStyle()
        self._build()

    def _build(self):
        form = QFormLayout(self)
        self.role_combo = QComboBox()
        self.role_combo.currentTextChanged.connect(self._on_role_selected)
        form.addRow(QLabel("Role:"), self.role_combo)
        self.family_edit = QLineEdit()
        self.family_edit.editingFinished.connect(self._on_field_changed)
        form.addRow(QLabel("Font family:"), self.family_edit)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 2000)
        self.size_spin.editingFinished.connect(self._on_field_changed)
        form.addRow(QLabel("Size (px):"), self.size_spin)
        self.color_edit = QLineEdit()
        self.color_edit.editingFinished.connect(self._on_field_changed)
        form.addRow(QLabel("Color (hex):"), self.color_edit)

    def set_style(self, style: ProjectStyle):
        self._style = style
        self.role_combo.blockSignals(True)
        self.role_combo.clear()
        self.role_combo.addItems(sorted(style.font_roles.keys()))
        self.role_combo.blockSignals(False)
        if self.role_combo.count():
            self._load_role(self.role_combo.currentText())

    def style(self) -> ProjectStyle:
        return self._style

    def _load_role(self, role: str):
        ts = self._style.font_roles.get(role)
        if ts is None:
            return
        for w in (self.family_edit, self.size_spin, self.color_edit):
            w.blockSignals(True)
        self.family_edit.setText(ts.family[0] if ts.family else "")
        self.size_spin.setValue(ts.size_px)
        self.color_edit.setText(ts.color)
        for w in (self.family_edit, self.size_spin, self.color_edit):
            w.blockSignals(False)

    def _on_role_selected(self, role: str):
        if role:
            self._load_role(role)

    def _on_field_changed(self):
        role = self.role_combo.currentText()
        if not role or role not in self._style.font_roles:
            return
        old = self._style.font_roles[role]
        self._style.font_roles[role] = TextStyle(
            family=[self.family_edit.text() or "Arial"],
            weight=old.weight, italic=old.italic,
            size_px=self.size_spin.value(),
            line_height=old.line_height,
            color=self.color_edit.text() or "#111111",
            align=old.align, wrap=old.wrap, letter_spacing=old.letter_spacing,
        )
        self.styleChanged.emit(self._style)
