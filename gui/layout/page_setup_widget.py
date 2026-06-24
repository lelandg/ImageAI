"""Page-setup controls: orientation, size (presets + freeform), unit, DPI."""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QSpinBox, QPushButton, QLabel,
)
from PySide6.QtCore import Signal

from core.layout.models import PageSize
from core.layout import page_sizes as ps


class PageSetupWidget(QWidget):
    pageSizeChanged = Signal(object)  # emits PageSize

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._dpi = config.get_layout_config().get("export_dpi", 300) if config else 300
        self._orientation = "portrait"
        self._build()
        self._reload_presets()
        self._emit_current()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.addWidget(QLabel("Size:"))
        self.size_combo = QComboBox()
        self.size_combo.setEditable(True)
        self.size_combo.activated.connect(lambda *_: self._on_preset_selected())
        self.size_combo.lineEdit().returnPressed.connect(self._on_freeform_entered)
        lay.addWidget(self.size_combo, 2)

        lay.addWidget(QLabel("Unit:"))
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["in", "mm", "pt", "px"])
        lay.addWidget(self.unit_combo)

        lay.addWidget(QLabel("DPI:"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(1, 2400)
        self.dpi_spin.setValue(self._dpi)
        self.dpi_spin.valueChanged.connect(self._on_dpi_changed)
        lay.addWidget(self.dpi_spin)

        self.portrait_btn = QPushButton("Portrait")
        self.portrait_btn.clicked.connect(self._on_portrait)
        self.landscape_btn = QPushButton("Landscape")
        self.landscape_btn.clicked.connect(self._on_landscape)
        lay.addWidget(self.portrait_btn)
        lay.addWidget(self.landscape_btn)

    def _reload_presets(self):
        self.size_combo.blockSignals(True)
        self.size_combo.clear()
        self._presets = list(ps.PRESETS) + ps.load_custom_sizes(self._config)
        for p in self._presets:
            self.size_combo.addItem(f'{p["name"]} ({p["width"]}x{p["height"]} {p["unit"]})')
        self.size_combo.blockSignals(False)

    def _current_preset(self):
        idx = self.size_combo.currentIndex()
        if 0 <= idx < len(self._presets):
            return self._presets[idx]
        return self._presets[0]

    def page_size(self) -> PageSize:
        p = self._current_preset()
        return ps.preset_to_page_size(p, self._orientation, self.dpi_spin.value())

    def set_page_size(self, page: PageSize) -> None:
        """Display `page` as the current selection.

        Transient: shows the size in the combo but does NOT persist it as a
        custom preset (use add_custom_from_text to persist). Emits
        pageSizeChanged exactly once, after all controls are updated.
        """
        self._orientation = page.orientation
        widgets = (self.unit_combo, self.dpi_spin, self.size_combo)
        for w in widgets:
            w.blockSignals(True)
        self.unit_combo.setCurrentText(page.unit)
        self.dpi_spin.setValue(page.dpi)
        name = f"Custom {page.width}x{page.height}"
        preset = {"name": name, "width": page.width, "height": page.height, "unit": page.unit}
        self._presets = [preset] + [p for p in self._presets if p.get("name") != name]
        self.size_combo.clear()
        for p in self._presets:
            self.size_combo.addItem(f'{p["name"]} ({p["width"]}x{p["height"]} {p["unit"]})')
        self.size_combo.setCurrentIndex(0)
        for w in widgets:
            w.blockSignals(False)
        self._emit_current()

    def add_custom_from_text(self, text: str) -> bool:
        parsed = ps.parse_size_text(text)
        if not parsed:
            return False
        w, h = parsed
        preset = {"name": f"Custom {w}x{h}", "width": w, "height": h,
                  "unit": self.unit_combo.currentText()}
        ps.save_custom_size(self._config, preset)
        self._reload_presets()
        for i, p in enumerate(self._presets):
            if p["name"] == preset["name"]:
                self.size_combo.setCurrentIndex(i)
                break
        self._emit_current()
        return True

    # --- slots ---
    def _on_preset_selected(self):
        self._emit_current()

    def _on_freeform_entered(self):
        self.add_custom_from_text(self.size_combo.currentText())

    def _on_dpi_changed(self, _):
        self._emit_current()

    def _on_portrait(self):
        self._orientation = "portrait"
        self._emit_current()

    def _on_landscape(self):
        self._orientation = "landscape"
        self._emit_current()

    def _emit_current(self):
        self.pageSizeChanged.emit(self.page_size())
