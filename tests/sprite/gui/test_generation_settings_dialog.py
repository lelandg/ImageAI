# tests/sprite/gui/test_generation_settings_dialog.py
"""GenerationSettingsDialog: every field editable, named configs, cost line, Ctrl+Enter."""
from PySide6.QtWidgets import QDialog

import gui.sprite.generation_settings_dialog as gsd
from core.sprite.configs import DEFAULT_NAME, NamedConfigStore
from core.sprite.project import GenerationSettings
from gui.sprite.generation_settings_dialog import (
    PROVIDER_DEFAULT_LABEL, GenerationSettingsDialog, model_choices,
)

VEO_STD = "veo-3.1-generate-001"
VEO_FAST = "veo-3.1-fast-generate-001"


def _dialog(tmp_path, settings=None):
    store = NamedConfigStore(tmp_path / "configs.json")
    return GenerationSettingsDialog(settings or GenerationSettings(), store), store


def test_defaults_roundtrip_with_provider_default_model(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path)
    assert dialog.provider_combo.currentText() == "omni"
    assert dialog.model_combo.currentText() == PROVIDER_DEFAULT_LABEL
    assert dialog.settings() == GenerationSettings()


def test_every_field_roundtrips(qapp, tmp_path):
    custom = GenerationSettings(provider="veo", model="veo-3.1-fast-generate-001",
                                resolution="1080p", aspect_ratio="9:16", duration_s=6, fps=30,
                                loop_conditioning=False, plate_color="#0000FF",
                                use_turnaround_refs=False, include_audio=True,
                                config_name=DEFAULT_NAME)
    dialog, _ = _dialog(tmp_path)
    dialog.set_settings(custom)
    assert dialog.settings() == custom


def test_provider_switch_repopulates_models(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path)
    dialog.provider_combo.setCurrentText("veo")
    items = [dialog.model_combo.itemText(i) for i in range(dialog.model_combo.count())]
    assert items[0] == PROVIDER_DEFAULT_LABEL
    assert "veo-3.1-generate-001" in items
    assert dialog.audio_check.isEnabled()
    dialog.provider_combo.setCurrentText("omni")
    items = [dialog.model_combo.itemText(i) for i in range(dialog.model_combo.count())]
    assert items == [PROVIDER_DEFAULT_LABEL] + model_choices("omni")
    assert not dialog.audio_check.isEnabled()


def _aspects(dialog):
    return [dialog.aspect_combo.itemText(i) for i in range(dialog.aspect_combo.count())]


def test_omni_offers_no_square(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path)
    assert dialog.provider_combo.currentText() == "omni"
    assert _aspects(dialog) == ["16:9", "9:16"]
    assert dialog.aspect_note.text() == ""


def test_veo_standard_offers_square(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path, GenerationSettings(provider="veo", model=VEO_STD))
    assert "1:1" in _aspects(dialog)
    dialog.aspect_combo.setCurrentText("1:1")
    assert dialog.settings().aspect_ratio == "1:1"


def test_veo_fast_hides_square(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path, GenerationSettings(provider="veo", model=VEO_STD,
                                                     aspect_ratio="1:1"))
    assert dialog.aspect_combo.currentText() == "1:1"
    dialog.model_combo.setCurrentText(VEO_FAST)
    assert "1:1" not in _aspects(dialog)
    assert dialog.aspect_combo.currentText() == "16:9"
    assert dialog.settings().aspect_ratio == "16:9"


def test_provider_switch_remaps_square_and_logs(qapp, tmp_path, caplog):
    dialog, _ = _dialog(tmp_path, GenerationSettings(provider="veo", model=VEO_STD,
                                                     aspect_ratio="1:1"))
    with caplog.at_level("INFO", logger=gsd.__name__):
        dialog.provider_combo.setCurrentText("omni")
    assert dialog.aspect_combo.currentText() == "16:9"
    assert any(r.levelno == 20 and "1:1" in r.getMessage() for r in caplog.records)
    assert "1:1" in dialog.aspect_note.text()
    # Going back to a model that allows 1:1 clears the note; the choice stays 16:9.
    dialog.provider_combo.setCurrentText("veo")
    assert dialog.aspect_combo.currentText() == "16:9"
    assert dialog.aspect_note.text() == ""


def test_set_settings_with_illegal_aspect_remaps(qapp, tmp_path):
    # The sprite-alpha project: provider omni with a saved 1:1 aspect.
    dialog, _ = _dialog(tmp_path, GenerationSettings(provider="omni", aspect_ratio="1:1"))
    assert dialog.settings().aspect_ratio == "16:9"
    assert "1:1" in dialog.aspect_note.text()


def test_hand_pick_clears_the_remap_note(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path, GenerationSettings(provider="omni", aspect_ratio="1:1"))
    assert "1:1" in dialog.aspect_note.text()
    dialog.aspect_combo.setCurrentText("9:16")
    assert dialog.settings().aspect_ratio == "9:16"
    assert dialog.aspect_note.text() == ""


def test_set_settings_with_a_legal_aspect_clears_an_old_note(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path, GenerationSettings(provider="omni", aspect_ratio="1:1"))
    assert "1:1" in dialog.aspect_note.text()
    dialog.set_settings(GenerationSettings(provider="omni", aspect_ratio="16:9"))
    assert dialog.settings().aspect_ratio == "16:9"
    assert dialog.aspect_note.text() == ""


def test_custom_model_text_is_kept(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path)
    dialog.model_combo.setEditText("my-custom-model")
    assert dialog.settings().model == "my-custom-model"


def test_save_as_adds_named_config(qapp, tmp_path, monkeypatch):
    dialog, store = _dialog(tmp_path)
    monkeypatch.setattr(gsd.QInputDialog, "getText", staticmethod(lambda *a, **k: ("Fast", True)))
    dialog.duration_spin.setValue(4)
    dialog.save_as_btn.click()
    assert "Fast" in store.list_names()
    assert store.get("Fast").duration_s == 4
    assert dialog.config_combo.currentText() == "Fast"
    assert dialog.settings().config_name == "Fast"


def test_load_applies_named_config(qapp, tmp_path):
    dialog, store = _dialog(tmp_path)
    store.save("Tall", GenerationSettings(aspect_ratio="9:16", fps=12))
    dialog._reload_names(select="Tall")
    dialog.load_btn.click()
    assert dialog.aspect_combo.currentText() == "9:16"
    assert dialog.fps_spin.value() == 12


def test_delete_default_is_refused_and_reported(qapp, tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(gsd, "show_error",
                        lambda parent, title, message, exception=None: seen.append(message))
    dialog, store = _dialog(tmp_path)
    dialog.delete_btn.click()
    assert seen and "Default" in seen[0]
    assert store.list_names() == [DEFAULT_NAME]


def test_delete_named_config_after_confirmation(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    dialog, store = _dialog(tmp_path)
    store.save("Temp", GenerationSettings())
    dialog._reload_names(select="Temp")
    monkeypatch.setattr(gsd.QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    dialog.delete_btn.click()
    assert store.list_names() == [DEFAULT_NAME]
    assert dialog.config_combo.currentText() == DEFAULT_NAME


def test_cost_line_shows_estimate_or_unknown(qapp, tmp_path, monkeypatch):
    dialog, _ = _dialog(tmp_path)
    monkeypatch.setattr(gsd, "estimate_action", lambda settings, action: 0.5)
    dialog._update_cost()
    assert "$0.50" in dialog.cost_label.text()
    monkeypatch.setattr(gsd, "estimate_action", lambda settings, action: None)
    dialog._update_cost()
    assert "unknown" in dialog.cost_label.text()


def test_cost_estimator_error_is_logged_not_raised(qapp, tmp_path, monkeypatch, caplog):
    dialog, _ = _dialog(tmp_path)

    def broken(settings, action):
        raise RuntimeError("no price table")

    monkeypatch.setattr(gsd, "estimate_action", broken)
    with caplog.at_level("WARNING"):
        dialog._update_cost()
    assert "unknown" in dialog.cost_label.text()
    assert any("no price table" in record.message for record in caplog.records)


def test_ctrl_enter_accepts(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path)
    dialog.show()
    dialog._primary._activated()
    assert dialog.result() == QDialog.Accepted


def test_geometry_saved_on_close(qapp, tmp_path):
    from gui.sprite.prefs import sprite_settings
    dialog, _ = _dialog(tmp_path)
    dialog.show()
    dialog.reject()
    assert sprite_settings().value(gsd.GEOMETRY_KEY) is not None
