# tests/sprite/gui/test_sprite_prefs.py
"""Sticky purge-after-export preference (design §1.6)."""
from PySide6.QtWidgets import QMessageBox

import gui.sprite.prefs as prefs


def test_purge_defaults_to_off(qapp):
    prefs.sprite_settings().remove(prefs.PURGE_KEY)
    assert prefs.purge_after_export_enabled() is False


def test_purge_setting_is_sticky(qapp):
    prefs.set_purge_after_export(True)
    assert prefs.purge_after_export_enabled() is True
    prefs.set_purge_after_export(False)
    assert prefs.purge_after_export_enabled() is False


def test_purge_reads_ini_string_booleans(qapp):
    # QSettings' INI backend hands strings back; "true"/"false" must round-trip.
    settings = prefs.sprite_settings()
    settings.setValue(prefs.PURGE_KEY, "true")
    assert prefs.purge_after_export_enabled() is True
    settings.setValue(prefs.PURGE_KEY, "false")
    assert prefs.purge_after_export_enabled() is False
    settings.remove(prefs.PURGE_KEY)


def test_confirm_purge_names_deleted_folders(qapp, monkeypatch):
    asked = {}

    def fake_question(parent, title, text, buttons, default):
        asked.update(title=title, text=text, default=default)
        return QMessageBox.Yes

    monkeypatch.setattr(prefs.QMessageBox, "question", staticmethod(fake_question))
    assert prefs.confirm_purge(None) is True
    assert "clips/" in asked["text"] and "stages/" in asked["text"]
    assert "recycle bin" in asked["text"].lower()
    assert asked["default"] == QMessageBox.No  # Enter never enables the purge


def test_confirm_purge_no_returns_false(qapp, monkeypatch):
    monkeypatch.setattr(prefs.QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.No))
    assert prefs.confirm_purge(None) is False


def test_generic_pref_roundtrip(qapp):
    prefs.set_pref(prefs.LLM_PROVIDER_KEY, "openai")
    assert prefs.get_pref(prefs.LLM_PROVIDER_KEY, "google") == "openai"
    prefs.sprite_settings().remove(prefs.LLM_PROVIDER_KEY)
    assert prefs.get_pref(prefs.LLM_PROVIDER_KEY, "google") == "google"
