"""The Video tab's auto-load key must follow the project the user works on.

Startup reloads ``QSettings("ImageAI", "VideoProjects")/last_project``. Only
the open paths wrote that key. New Project and Save never touched it, so a
session that created and saved a new project still reloaded the previous one
at the next launch. The log for 2026-09-01 shows the old Sora project loading
and its "Provider Removed" warning firing on every start.

WorkspaceWidget is never constructed here (it builds the whole Video tab);
the methods run unbound against a SimpleNamespace stub, as
tests/gui/test_provider_model_sync.py does. The session conftest sandboxes
QSettings, so these writes never reach the developer's real settings.
"""
import types

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QComboBox, QLineEdit

from core.video.project import VideoProject
from gui.video.workspace_widget import WorkspaceWidget


class _Logger:
    def __init__(self):
        self.messages = []

    def info(self, message, *a, **k):
        self.messages.append(message)

    debug = warning = error = info


class _Signal:
    def __init__(self):
        self.emitted = []

    def emit(self, *args):
        self.emitted.append(args)


class _Label:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class _DialogManager:
    def __init__(self):
        self.warnings = []

    def show_warning(self, title, text):
        self.warnings.append((title, text))

    def show_error(self, title, text):
        raise AssertionError(f"unexpected error dialog: {title}: {text}")


def _settings():
    return QSettings("ImageAI", "VideoProjects")


@pytest.fixture(autouse=True)
def _clean_last_project(qapp):
    _settings().remove("last_project")
    yield
    _settings().remove("last_project")


def _base_stub():
    stub = types.SimpleNamespace(logger=_Logger())
    stub.project_changed = _Signal()
    stub.status_label = _Label()
    stub.project_name = QLineEdit()
    stub.update_ui_state = lambda: None
    stub._refresh_wizard = lambda: None
    stub._create_wizard_widget = lambda: None
    stub._remember_last_project = types.MethodType(
        WorkspaceWidget._remember_last_project, stub
    )
    return stub


# ── _remember_last_project ───────────────────────────────────────────────────

def test_remember_last_project_writes_setting(tmp_path):
    stub = _base_stub()
    path = tmp_path / "proj" / "project.iaproj.json"

    WorkspaceWidget._remember_last_project(stub, path)

    assert _settings().value("last_project") == str(path)


def test_remember_last_project_none_clears_setting(tmp_path):
    _settings().setValue("last_project", str(tmp_path / "old.iaproj.json"))
    stub = _base_stub()

    WorkspaceWidget._remember_last_project(stub, None)

    assert _settings().value("last_project") is None


# ── save_project ─────────────────────────────────────────────────────────────

def test_save_project_records_saved_path_as_last_project(tmp_path):
    saved = tmp_path / "New_20260901" / "project.iaproj.json"
    stub = _base_stub()
    stub.current_project = VideoProject(name="New")
    stub.update_project_from_ui = lambda: None
    stub.project_manager = types.SimpleNamespace(save_project=lambda p: saved)

    WorkspaceWidget.save_project(stub)

    assert _settings().value("last_project") == str(saved)


# ── new_project ──────────────────────────────────────────────────────────────

def test_new_project_clears_stale_last_project(tmp_path, monkeypatch):
    """An unsaved new project has no path, so startup must not reload the old one."""
    _settings().setValue("last_project", str(tmp_path / "old" / "project.iaproj.json"))
    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("Fresh", True)),
    )
    monkeypatch.setattr(
        "gui.video.workspace_widget.get_default_llm_provider", lambda cfg: "OpenAI"
    )
    stub = _base_stub()
    stub.current_project = None
    stub.config = None
    stub.input_text = types.SimpleNamespace(clear=lambda: None)
    stub.scene_table = types.SimpleNamespace(setRowCount=lambda n: None)
    stub.llm_provider_combo = QComboBox()
    stub.llm_provider_combo.addItems(["Google", "OpenAI"])

    WorkspaceWidget.new_project(stub)

    assert stub.current_project.name == "Fresh"
    assert _settings().value("last_project") is None


# ── Sora → Omni coercion ─────────────────────────────────────────────────────

def _coercion_stub(monkeypatch, provider):
    dialogs = _DialogManager()
    monkeypatch.setattr(
        "gui.video.workspace_widget.get_dialog_manager", lambda parent: dialogs
    )
    stub = _base_stub()
    stub.current_project = VideoProject(name="Old", video_provider=provider,
                                        video_model="sora-2")
    stub.video_provider_combo = QComboBox()
    stub.video_provider_combo.addItems(["FFmpeg Slideshow", "Gemini Veo", "Gemini Omni"])
    return stub, dialogs


@pytest.mark.parametrize("provider", ["sora", "openai sora"])
def test_sora_coercion_updates_project_in_memory(monkeypatch, provider):
    """The in-memory project must carry the new provider so a save persists it."""
    stub, dialogs = _coercion_stub(monkeypatch, provider)

    coerced = WorkspaceWidget._coerce_legacy_video_provider(stub)

    assert coerced is True
    assert stub.current_project.video_provider == "gemini omni"
    assert stub.current_project.video_model is None
    assert stub.video_provider_combo.currentText() == "Gemini Omni"
    assert [title for title, _ in dialogs.warnings] == ["Provider Removed"]


def test_non_sora_provider_is_left_alone(monkeypatch):
    stub, dialogs = _coercion_stub(monkeypatch, "gemini veo")

    coerced = WorkspaceWidget._coerce_legacy_video_provider(stub)

    assert coerced is False
    assert stub.current_project.video_provider == "gemini veo"
    assert stub.current_project.video_model == "sora-2"
    assert dialogs.warnings == []
