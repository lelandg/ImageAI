"""The image provider and the image model must never disagree.

A mismatch sends a foreign model id to a provider. The log for 2026-08-31
shows ``gpt-image-2`` sent to Google, which answers ``404 NOT_FOUND`` and
wastes the generation. Two paths produced it: a history restore that applied
the model before the provider, and the Settings tab provider combo, which
changed the provider without rebuilding the model list.

MainWindow is never constructed here (it scans history and builds every tab);
the methods run unbound against a SimpleNamespace stub, as
tests/sprite/gui/test_main_window_sprite_wiring.py does.
"""
import types

import pytest
from PySide6.QtWidgets import QComboBox

from gui.main_window import MainWindow


# Index 0 is the provider default, as ``_update_model_list`` leaves it. The
# Google entry below asks for the SECOND model on purpose: an order that
# applies the model first loses it to the rebuild and keeps the default.
MODELS = {
    "google": [("Gemini 3.1 Flash Image (gemini-3.1-flash-image-preview)",
                "gemini-3.1-flash-image-preview"),
               ("Gemini 3 Pro Image (gemini-3-pro-image-preview)",
                "gemini-3-pro-image-preview")],
    "openai": [("GPT Image 2 (gpt-image-2)", "gpt-image-2")],
}


def _fill(combo, provider):
    combo.clear()
    for text, model_id in MODELS[provider]:
        combo.addItem(text, model_id)
    combo.setCurrentIndex(0)  # the provider default


def _stub(provider="openai"):
    """A stub whose provider combo rebuilds the model combo, as the app does."""
    stub = types.SimpleNamespace(current_provider=provider)

    stub.provider_combo = QComboBox()
    stub.provider_combo.addItems(["google", "openai"])
    stub.provider_combo.setCurrentText(provider)

    stub.model_combo = QComboBox()
    _fill(stub.model_combo, provider)

    def on_provider(text):
        stub.current_provider = text
        _fill(stub.model_combo, text)

    stub.provider_combo.currentTextChanged.connect(on_provider)
    stub._find_model_in_combo = types.MethodType(
        MainWindow._find_model_in_combo, stub
    )
    return stub


def test_restore_applies_provider_before_model(qapp):
    """A Google history entry must land on Google's model, not OpenAI's."""
    stub = _stub("openai")

    MainWindow._restore_provider_and_model(
        stub, "google", "gemini-3-pro-image-preview"
    )

    assert stub.current_provider == "google"
    assert stub.model_combo.currentData() == "gemini-3-pro-image-preview"


def test_restore_keeps_selection_when_model_is_unknown(qapp, caplog):
    """An entry whose model the provider dropped keeps the provider's default."""
    stub = _stub("openai")

    with caplog.at_level("WARNING"):
        MainWindow._restore_provider_and_model(stub, "google", "dall-e-2")

    assert stub.current_provider == "google"
    assert stub.model_combo.currentData() == "gemini-3.1-flash-image-preview"
    assert "dall-e-2" in caplog.text


def test_restore_ignores_a_provider_that_is_not_installed(qapp, caplog):
    """An unknown provider leaves the current provider and model untouched."""
    stub = _stub("openai")

    with caplog.at_level("WARNING"):
        MainWindow._restore_provider_and_model(stub, "midjourney", "gpt-image-2")

    assert stub.current_provider == "openai"
    assert stub.model_combo.currentData() == "gpt-image-2"
    assert "midjourney" in caplog.text


def test_settings_provider_change_runs_the_image_tab_handler(qapp):
    """The Settings combo must rebuild the model list through one handler."""
    calls = []
    stub = types.SimpleNamespace(
        current_provider="openai",
        image_provider_combo=QComboBox(),
        config=types.SimpleNamespace(set=lambda *a: None),
        save_config=lambda: None,
        _update_use_current_button_state=lambda: None,
        _on_image_provider_changed=lambda name: calls.append(name),
    )
    stub.image_provider_combo.addItems(["google", "openai"])
    stub.image_provider_combo.setCurrentText("openai")

    emitted = []
    stub.image_provider_combo.currentTextChanged.connect(emitted.append)

    MainWindow._on_provider_changed(stub, "Google")

    assert calls == ["google"]
    assert stub.current_provider == "google"
    assert stub.image_provider_combo.currentText() == "google"
    assert emitted == []  # the sync must not re-enter the Image tab handler


class _FakeProvider:
    def __init__(self, models):
        self._models = models

    def get_models_with_details(self):
        return {m: {"name": m} for m in self._models}


@pytest.mark.parametrize(
    "model_id, expected", [("gemini-3-pro-image-preview", True),
                           ("gpt-image-2", False),
                           ("", False)]
)
def test_model_matches_provider(monkeypatch, model_id, expected):
    monkeypatch.setattr(
        "gui.main_window.get_provider",
        lambda name, cfg: _FakeProvider(["gemini-3-pro-image-preview"]),
    )
    assert MainWindow._model_matches_provider(
        types.SimpleNamespace(), model_id, "google"
    ) is expected


def test_model_matches_provider_defers_when_it_cannot_check(monkeypatch):
    """A provider that cannot list models reports the error itself."""
    def boom(name, cfg):
        raise RuntimeError("no api key")

    monkeypatch.setattr("gui.main_window.get_provider", boom)
    assert MainWindow._model_matches_provider(
        types.SimpleNamespace(), "gpt-image-2", "openai"
    ) is True
