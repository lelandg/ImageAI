"""Generation Settings dialog: every GenerationSettings field + named configurations.

Decision 9: defaults live here, every field is editable, and the user keeps
several named configurations (``NamedConfigStore``). A live cost line shows
``estimate_action`` for one clip of the chosen duration — "unknown" when the
estimator has no verified rate (decision 8: never a guess).
"""
from __future__ import annotations

import logging
import math
from typing import List, Optional, Sequence

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)

from core.sprite.configs import DEFAULT_NAME, NamedConfigStore
from core.sprite.generation.cost import estimate_action
from core.sprite.project import ActionCard, GenerationSettings
from core.sprite.timing import legal_aspect_ratios
from core.video.omni_client import OmniModel
from core.video.veo_client import VeoModel
from gui.common.dialog_conventions import DialogCleanupMixin, bind_primary_action, set_default_button
from gui.dialog_utils import show_error
from gui.sprite.prefs import sprite_settings

logger = logging.getLogger(__name__)

PROVIDERS = ("omni", "veo")
RESOLUTIONS = ("720p", "1080p")
PROVIDER_DEFAULT_LABEL = "(provider default)"
GEOMETRY_KEY = "sprite/gen_settings_geometry"


def model_choices(provider: str) -> List[str]:
    """Model IDs offered for a provider. Omni resolves through the registry."""
    if provider == "veo":
        return [model.value for model in VeoModel]
    return [OmniModel.default_id()]


def _aspect_value(text: str) -> Optional[float]:
    """``"16:9"`` -> 16/9; ``None`` when the text is not ``w:h``."""
    try:
        width, height = (float(part) for part in text.split(":", 1))
    except (ValueError, AttributeError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width / height


def closest_aspect(wanted: str, legal: Sequence[str]) -> str:
    """Legal ratio nearest to ``wanted`` in log(w/h) distance. Tie -> first entry."""
    target = _aspect_value(wanted)
    if target is None:
        return legal[0]

    def distance(candidate: str) -> float:
        value = _aspect_value(candidate)
        if value is None:
            return math.inf
        return round(abs(math.log(value) - math.log(target)), 6)

    return min(legal, key=distance)


class GenerationSettingsDialog(DialogCleanupMixin, QDialog):
    def __init__(self, settings: GenerationSettings, store: NamedConfigStore, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generation Settings")
        self.setMinimumWidth(480)
        self._store = store
        self._plate_color = settings.plate_color
        self._build()
        self._reload_names(select=settings.config_name)
        self.set_settings(settings)
        self._primary = bind_primary_action(self, self.accept)
        set_default_button(self, self.ok_btn, focus=False)
        self.provider_combo.setFocus()
        geometry = sprite_settings().value(GEOMETRY_KEY)
        if geometry is not None:
            self.restoreGeometry(geometry)

    # -- build -------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)

        config_row = QHBoxLayout()
        config_row.addWidget(QLabel("Configuration:"))
        self.config_combo = QComboBox()
        self.config_combo.currentTextChanged.connect(self._on_config_selected)
        config_row.addWidget(self.config_combo, 1)
        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self._on_load)
        self.save_as_btn = QPushButton("Save as…")
        self.save_as_btn.clicked.connect(self._on_save_as)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete)
        for button in (self.load_btn, self.save_as_btn, self.delete_btn):
            config_row.addWidget(button)
        root.addLayout(config_row)

        form = QFormLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(PROVIDERS)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        form.addRow("Provider:", self.provider_combo)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        form.addRow("Model:", self.model_combo)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(RESOLUTIONS)
        form.addRow("Resolution:", self.resolution_combo)
        self.aspect_combo = QComboBox()
        self.aspect_combo.setToolTip("Only the ratios the chosen provider and model accept.")
        form.addRow("Aspect ratio:", self.aspect_combo)
        self.aspect_note = QLabel("")
        self.aspect_note.setWordWrap(True)
        form.addRow("", self.aspect_note)
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 15)
        self.duration_spin.setSuffix(" s")
        form.addRow("Clip duration:", self.duration_spin)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setToolTip("Clip frame rate. Presets: 8, 12, 24, 30, 60.")
        form.addRow("Clip FPS:", self.fps_spin)
        self.loop_check = QCheckBox("Loop conditioning (Veo first+last frame; forces 8 s)")
        form.addRow("", self.loop_check)
        self.plate_color_btn = QPushButton()
        self.plate_color_btn.clicked.connect(self._pick_plate_color)
        form.addRow("Plate color:", self.plate_color_btn)
        self.turnaround_check = QCheckBox("Attach turnaround views as references")
        form.addRow("", self.turnaround_check)
        self.audio_check = QCheckBox("Include audio (Veo only; changes the price)")
        form.addRow("", self.audio_check)
        root.addLayout(form)

        self.cost_label = QLabel("Estimated cost per action: unknown")
        root.addWidget(self.cost_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.ok_btn)
        buttons.addWidget(self.cancel_btn)
        root.addLayout(buttons)

        for signal in (self.model_combo.currentTextChanged, self.model_combo.editTextChanged):
            signal.connect(lambda _text: self._refill_aspects())
        # The refill blocks this signal, so only a hand pick clears the remap note.
        self.aspect_combo.currentTextChanged.connect(lambda _text: self.aspect_note.setText(""))
        for signal in (self.model_combo.currentTextChanged, self.model_combo.editTextChanged,
                       self.resolution_combo.currentTextChanged, self.duration_spin.valueChanged,
                       self.audio_check.toggled):
            signal.connect(self._update_cost)

    # -- models ------------------------------------------------------------

    def _on_provider_changed(self, provider: str) -> None:
        current = self._model_text()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItem(PROVIDER_DEFAULT_LABEL)
        for model_id in model_choices(provider):
            self.model_combo.addItem(model_id)
        self.model_combo.blockSignals(False)
        self._select_model(current)
        self._refill_aspects()
        is_veo = provider == "veo"
        self.audio_check.setEnabled(is_veo)
        self.loop_check.setEnabled(is_veo)
        self._update_cost()

    def _select_model(self, model: str) -> None:
        if not model:
            self.model_combo.setCurrentIndex(0)
            return
        index = self.model_combo.findText(model)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
        else:
            self.model_combo.setEditText(model)

    def _model_text(self) -> str:
        text = self.model_combo.currentText().strip()
        return "" if text == PROVIDER_DEFAULT_LABEL else text

    # -- aspect ratios -----------------------------------------------------

    def _aspect_items(self) -> List[str]:
        return [self.aspect_combo.itemText(i) for i in range(self.aspect_combo.count())]

    def _refill_aspects(self, requested: Optional[str] = None) -> None:
        """Offer only the legal ratios; remap the wanted one when it is not legal.

        ``requested`` is the ratio to apply (``set_settings``); by default the
        current combo text is kept. A remap is logged and shown under the
        combo. The note stays until the legal list or the choice changes.
        """
        provider = self.provider_combo.currentText()
        try:
            legal = list(legal_aspect_ratios(provider, self._model_text()))
        except ValueError as exc:
            logger.error("Aspect ratio list unavailable for %s: %s", provider, exc)
            return
        wanted = self.aspect_combo.currentText() if requested is None else requested
        # An explicit request always goes through, so its note is set or cleared.
        if requested is None and self._aspect_items() == legal and wanted in legal \
                and wanted == self.aspect_combo.currentText():
            return
        if wanted in legal:
            chosen = wanted
        elif not wanted:
            chosen = legal[0]
        else:
            chosen = closest_aspect(wanted, legal)
        self.aspect_combo.blockSignals(True)
        self.aspect_combo.clear()
        self.aspect_combo.addItems(legal)
        self.aspect_combo.setCurrentText(chosen)
        self.aspect_combo.blockSignals(False)
        if wanted and chosen != wanted:
            target = f"{provider}/{self._model_text() or 'default model'}"
            note = f"{wanted} is not supported by {target}; using {chosen}."
            logger.info("Sprite generation settings: aspect ratio %s remapped to %s "
                        "(legal for %s: %s)", wanted, chosen, target, ", ".join(legal))
            self.aspect_note.setText(note)
        else:
            self.aspect_note.setText("")

    # -- settings <-> widgets ---------------------------------------------

    def set_settings(self, settings: GenerationSettings) -> None:
        provider = settings.provider if settings.provider in PROVIDERS else "omni"
        self.provider_combo.setCurrentText(provider)
        self._on_provider_changed(provider)  # populate even when the text did not change
        self._select_model(settings.model)
        self.resolution_combo.setCurrentText(settings.resolution)
        # A non-editable combo keeps its old value on an unknown text, so the
        # requested ratio goes through the remap instead of setCurrentText().
        self._refill_aspects(settings.aspect_ratio)
        self.duration_spin.setValue(int(settings.duration_s))
        self.fps_spin.setValue(int(settings.fps))
        self.loop_check.setChecked(bool(settings.loop_conditioning))
        self._set_plate_color(settings.plate_color)
        self.turnaround_check.setChecked(bool(settings.use_turnaround_refs))
        self.audio_check.setChecked(bool(settings.include_audio))
        index = self.config_combo.findText(settings.config_name)
        if index >= 0:
            self.config_combo.setCurrentIndex(index)
        self._update_cost()

    def settings(self) -> GenerationSettings:
        return GenerationSettings(
            provider=self.provider_combo.currentText(),
            model=self._model_text(),
            resolution=self.resolution_combo.currentText(),
            aspect_ratio=self.aspect_combo.currentText(),
            duration_s=self.duration_spin.value(),
            fps=self.fps_spin.value(),
            loop_conditioning=self.loop_check.isChecked(),
            plate_color=self._plate_color,
            use_turnaround_refs=self.turnaround_check.isChecked(),
            include_audio=self.audio_check.isChecked(),
            config_name=self.config_combo.currentText() or DEFAULT_NAME,
        )

    def _update_cost(self, *_args) -> None:
        try:
            current = self.settings()
            sample = ActionCard(id="preview", name="preview", prompt="",
                                duration_s=current.duration_s)
            usd = estimate_action(current, sample)
        except Exception as exc:  # noqa: BLE001 - a broken estimator must not break the dialog
            logger.warning("Cost estimate failed: %s", exc)
            usd = None
        if usd is None:
            self.cost_label.setText("Estimated cost per action: unknown")
        else:
            self.cost_label.setText(f"Estimated cost per action: ${usd:.2f}")

    # -- plate color -------------------------------------------------------

    def _set_plate_color(self, hex_color: str) -> None:
        self._plate_color = (hex_color or "#00FF00").upper()
        self.plate_color_btn.setText(self._plate_color)
        self.plate_color_btn.setStyleSheet(f"background-color: {self._plate_color};")

    def _pick_plate_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._plate_color), self, "Chroma plate color")
        if color.isValid():
            self._set_plate_color(color.name())

    # -- named configurations ---------------------------------------------

    def _reload_names(self, select: Optional[str] = None) -> None:
        self.config_combo.blockSignals(True)
        self.config_combo.clear()
        self.config_combo.addItems(self._store.list_names())
        self.config_combo.blockSignals(False)
        index = self.config_combo.findText(select) if select else -1
        self.config_combo.setCurrentIndex(index if index >= 0 else 0)
        self._on_config_selected(self.config_combo.currentText())

    def _on_config_selected(self, name: str) -> None:
        # Stay enabled even on "Default": _on_delete() is the single guard that
        # refuses and reports deleting it, so the click always reaches that
        # message instead of being silently swallowed by a disabled button.
        self.delete_btn.setEnabled(bool(name))

    def _on_load(self) -> None:
        name = self.config_combo.currentText()
        try:
            loaded = self._store.get(name)
        except KeyError:
            show_error(self, "Generation Settings", f"Configuration not found: {name}")
            self._reload_names()
            return
        self.set_settings(loaded)
        logger.info("Loaded sprite generation configuration %r", name)

    def _on_save_as(self) -> None:
        name, ok = QInputDialog.getText(self, "Save configuration", "Configuration name:",
                                        text=self.config_combo.currentText())
        if not ok or not name.strip():
            return
        name = name.strip()
        try:
            self._store.save(name, self.settings())
        except (OSError, ValueError) as exc:
            show_error(self, "Generation Settings", f"Could not save configuration: {exc}",
                       exception=exc)
            return
        self._reload_names(select=name)

    def _on_delete(self) -> None:
        name = self.config_combo.currentText()
        if name == DEFAULT_NAME:
            show_error(self, "Generation Settings", 'The "Default" configuration cannot be deleted.')
            return
        reply = QMessageBox.question(self, "Delete configuration", f'Delete "{name}"?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            self._store.delete(name)
        except (KeyError, ValueError, OSError) as exc:
            show_error(self, "Generation Settings", f"Could not delete configuration: {exc}",
                       exception=exc)
            return
        self._reload_names(select=DEFAULT_NAME)

    # -- cleanup -----------------------------------------------------------

    def on_dialog_close(self) -> None:
        settings = sprite_settings()
        settings.setValue(GEOMETRY_KEY, self.saveGeometry())
        settings.sync()
