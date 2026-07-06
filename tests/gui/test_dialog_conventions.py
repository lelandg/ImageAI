# tests/gui/test_dialog_conventions.py
"""Unit tests for gui.common.dialog_conventions, plus offscreen construction
smoke tests for the dialogs migrated in the dialog-UX TLC work.

The smoke tests exist because construction-time bugs (imports removed
mid-migration, calls to not-yet-defined methods) don't surface anywhere else
in the suite — most dialogs are never instantiated by other tests.
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from gui.common.dialog_conventions import (
    DialogCleanupMixin,
    bind_primary_action,
    persist_splitter,
    restore_splitter,
    set_default_button,
    standard_splitter,
)


@pytest.fixture
def sandbox_settings(tmp_path):
    """Route all QSettings for the test into a temp dir (never the real user config)."""
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    yield
    QSettings.setDefaultFormat(QSettings.NativeFormat)


def _two_pane_splitter(orientation=Qt.Vertical):
    splitter = standard_splitter(orientation)
    splitter.addWidget(QLabel("top"))
    splitter.addWidget(QLabel("bottom"))
    return splitter


# ---------------------------------------------------------------------------
# standard_splitter / persist_splitter / restore_splitter
# ---------------------------------------------------------------------------

def test_standard_splitter_is_styled_and_non_collapsible(qapp):
    splitter = _two_pane_splitter()
    assert not splitter.childrenCollapsible()
    assert splitter.handleWidth() >= 6
    assert splitter.styleSheet()  # canonical style applied


def test_restore_splitter_returns_false_on_first_run(qapp, sandbox_settings):
    settings = QSettings("ImageAI", "ConventionsTest")
    splitter = _two_pane_splitter()
    # No saved state: caller must apply its own hardcoded default sizes
    assert restore_splitter(settings, "missing_key", splitter) is False


def test_persist_then_restore_roundtrip(qapp, sandbox_settings):
    settings = QSettings("ImageAI", "ConventionsTest")

    source = _two_pane_splitter()
    source.resize(100, 400)
    source.setSizes([300, 100])
    persist_splitter(settings, "state", source)

    target = _two_pane_splitter()
    target.resize(100, 400)
    assert restore_splitter(settings, "state", target) is True
    assert target.sizes() == source.sizes()


# ---------------------------------------------------------------------------
# PrimaryAction
# ---------------------------------------------------------------------------

def test_primary_action_binds_both_return_and_keypad_enter(qapp):
    widget = QDialog()
    action = bind_primary_action(widget, lambda: None)
    sequences = {shortcut.key().toString() for shortcut in action._shortcuts}
    assert sequences == {"Ctrl+Return", "Ctrl+Enter"}


def test_primary_action_retarget_switches_slot(qapp):
    widget = QDialog()
    first, second = MagicMock(), MagicMock()
    action = bind_primary_action(widget, first)

    action._activated()
    assert first.call_count == 1

    action.retarget(second)
    action._activated()
    assert first.call_count == 1  # old slot no longer fires
    assert second.call_count == 1


def test_primary_action_set_enabled_toggles_both_shortcuts(qapp):
    widget = QDialog()
    action = bind_primary_action(widget, lambda: None)
    action.set_enabled(False)
    assert all(not s.isEnabled() for s in action._shortcuts)
    action.set_enabled(True)
    assert all(s.isEnabled() for s in action._shortcuts)


# ---------------------------------------------------------------------------
# set_default_button
# ---------------------------------------------------------------------------

def test_set_default_button_leaves_exactly_one_default(qapp):
    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    buttons = [QPushButton(name, dialog) for name in ("one", "two", "three")]
    for button in buttons:
        layout.addWidget(button)

    set_default_button(dialog, buttons[1], focus=False)

    assert buttons[1].isDefault()
    assert not buttons[0].isDefault() and not buttons[2].isDefault()
    assert not buttons[0].autoDefault() and not buttons[2].autoDefault()


# ---------------------------------------------------------------------------
# DialogCleanupMixin
# ---------------------------------------------------------------------------

class _CleanupDialog(DialogCleanupMixin, QDialog):
    def __init__(self):
        super().__init__()
        self.cleanups = 0

    def on_dialog_close(self):
        self.cleanups += 1


def test_cleanup_runs_once_even_when_done_and_close_both_fire(qapp):
    dialog = _CleanupDialog()
    dialog.show()
    dialog.done(0)
    dialog.close()  # closeEvent after done() must not double-run cleanup
    assert dialog.cleanups == 1


def test_cleanup_runs_on_accept_path(qapp):
    dialog = _CleanupDialog()
    dialog.show()
    dialog.accept()
    assert dialog.cleanups == 1


def test_cleanup_reruns_after_dialog_is_reshown(qapp):
    dialog = _CleanupDialog()
    dialog.show()
    dialog.done(0)
    dialog.show()  # showEvent re-arms the idempotence flag
    dialog.done(1)
    assert dialog.cleanups == 2


# ---------------------------------------------------------------------------
# Dialog construction smoke tests (offscreen)
# ---------------------------------------------------------------------------

def test_prompt_generation_dialog_constructs(qapp, sandbox_settings):
    from gui.prompt_generation_dialog import PromptGenerationDialog

    dialog = PromptGenerationDialog(config={})
    assert dialog.main_splitter is not None
    assert dialog.generate_splitter is not None
    assert dialog.results_splitter is not None
    assert dialog.generate_btn.isDefault()
    dialog.done(0)  # cleanup path must not raise


def test_text_generation_dialog_constructs(qapp, sandbox_settings):
    from core.layout.models import TextBlock
    from gui.layout.text_gen_dialog import TextGenerationDialog

    config = MagicMock()
    config.get_layout_llm_provider.return_value = "google"
    block = TextBlock(id="b1", rect=(0, 0, 100, 50), text="hello")

    dialog = TextGenerationDialog(config, block, provider="google", model="test-model")
    assert dialog.main_splitter is not None
    assert dialog.generate_btn.isDefault()
    dialog.done(0)


def test_start_prompt_dialog_constructs(qapp, sandbox_settings, monkeypatch):
    from gui.video.start_prompt_dialog import StartPromptDialog

    # __init__ auto-starts LLM generation; stub it for construction testing
    monkeypatch.setattr(StartPromptDialog, "generate_prompt", lambda self: None)

    dialog = StartPromptDialog(
        MagicMock(), "source text", "current prompt", "google", "test-model", "key"
    )
    assert dialog.main_splitter is not None
    assert dialog.ok_btn is not None
    dialog.done(0)


def test_video_prompt_dialog_constructs(qapp, sandbox_settings, monkeypatch):
    from gui.video.video_prompt_dialog import VideoPromptDialog

    monkeypatch.setattr(VideoPromptDialog, "generate_prompt", lambda self: None)

    dialog = VideoPromptDialog(MagicMock(), "start prompt", 5.0, "google", "test-model")
    assert dialog.main_splitter is not None
    assert dialog.ok_btn is not None
    dialog.done(0)


def test_refine_image_dialog_constructs(qapp, sandbox_settings):
    from gui.refine_image_dialog import RefineImageDialog

    conversation = MagicMock()
    conversation.current_image_bytes = None
    conversation.messages = []
    conversation.get_message_count.return_value = 0

    dialog = RefineImageDialog(conversation=conversation)
    assert dialog.console_splitter is not None
    assert dialog.main_splitter is not None
    assert dialog.chat_splitter is not None
    dialog.done(0)
