# tests/sprite/gui/test_sprite_tab_smoke.py
"""SpriteTab: construction, project toolbar, 5b slots, routing, console."""
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton

import gui.sprite.sprite_tab as st
from core.sprite.project import ActionCard, GenerationSettings
from gui.sprite import SpriteTab
from gui.sprite.character_panel import CharacterPanel
from gui.sprite.prefs import sprite_settings


def test_construction_has_console_slots_and_no_project(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    assert tab.current_project is None
    assert tab.console.console.isReadOnly()
    for area in (tab.frame_area, tab.preview_area, tab.processing_area):
        assert area.layout().count() == 1  # placeholder label
    assert tab.main_splitter.count() == 2 and tab.left_splitter.count() == 3
    assert not tab.save_btn.isEnabled()


def test_new_project_named_creates_and_broadcasts(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    changed = []
    tab.projectChanged.connect(lambda: changed.append(1))
    project = tab.new_project_named("hero")
    assert project is tab.current_project and project.name == "hero"
    assert Path(project.project_dir).exists()
    assert tab.character_panel.project is project
    assert tab.action_cards_panel.project is project
    assert tab.queue_panel.project is project
    assert changed and "hero" in tab.title_label.text()
    assert tab.save_btn.isEnabled()


def test_save_then_open_roundtrip(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    tab.new_project_named("roundtrip")
    saved = tab.save_project()
    assert saved is not None and Path(saved).exists()
    other = SpriteTab(config=fake_config)
    loaded = other.open_project_from(saved)
    assert loaded is not None and loaded.name == "roundtrip"
    assert other.current_project is loaded


def test_open_malformed_file_is_reported(qapp, fake_config, tmp_path, monkeypatch):
    bad = tmp_path / "bad.iasprite.json"
    bad.write_text("{ not json", encoding="utf-8")
    reported = {}
    monkeypatch.setattr(SpriteTab, "_report_error",
                        lambda self, what, exc: reported.update(what=what, exc=exc))
    tab = SpriteTab(config=fake_config)
    assert tab.open_project_from(bad) is None
    assert reported.get("what") == "open project"
    assert isinstance(reported.get("exc"), Exception)


def test_5b_slots_replace_placeholders(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    first, second = QLabel("strip"), QLabel("strip v2")
    tab.set_frame_widget(first)
    assert tab.frame_widget is first
    assert tab.frame_area.layout().count() == 1
    assert tab.frame_area.layout().itemAt(0).widget() is first
    tab.set_frame_widget(second)
    assert tab.frame_widget is second and tab.frame_area.layout().count() == 1
    preview, processing = QLabel("preview"), QLabel("processing")
    tab.set_preview_widget(preview)
    tab.set_processing_widget(processing)
    assert tab.preview_widget is preview and tab.processing_widget is processing


def test_set_character_source_auto_creates_project(qapp, fake_config, png, monkeypatch):
    calls = []
    monkeypatch.setattr(CharacterPanel, "set_source", lambda self, path: calls.append(Path(path)))
    tab = SpriteTab(config=fake_config)
    tab.set_character_source(png)
    assert tab.current_project is not None and tab.current_project.name == png.stem
    assert calls == [png]
    tab.set_character_source(png)  # second call keeps the existing project
    assert len(calls) == 2


def test_panel_signals_are_routed(qapp, fake_config, monkeypatch):
    tab = SpriteTab(config=fake_config)
    tab.new_project_named("route")
    log = {"enqueue": [], "start": [], "refine": []}
    monkeypatch.setattr(tab.queue_panel, "enqueue", lambda ids: log["enqueue"].append(list(ids)))
    monkeypatch.setattr(tab.queue_panel, "start", lambda ids=None: log["start"].append(list(ids or [])))
    monkeypatch.setattr(tab.queue_panel, "refine", lambda cid, text: log["refine"].append((cid, text)))
    tab.action_cards_panel.renderRequested.emit(["a1"])
    tab.action_cards_panel.refineRequested.emit("a1", "swing")
    assert log == {"enqueue": [["a1"]], "start": [["a1"]], "refine": [("a1", "swing")]}


def test_console_and_history_forwarding(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    got = []
    tab.addToHistoryRequested.connect(lambda entry: got.append(entry))
    tab.character_panel.logMessage.emit("plate started", "INFO")
    tab.queue_panel.logMessage.emit("queue failed", "ERROR")
    assert "plate started" in tab.console.console.toPlainText()
    assert "queue failed" in tab.console.console.toPlainText()
    tab.character_panel.historyEntry.emit({"path": Path("x.png"), "source_tab": "sprite"})
    assert got == [{"path": Path("x.png"), "source_tab": "sprite"}]


def test_generation_settings_dialog_updates_project(qapp, fake_config, monkeypatch):
    class _FakeDialog:
        def __init__(self, settings, store, parent=None):
            self.initial = settings

        def exec(self):
            return QDialog.Accepted

        def settings(self):
            return GenerationSettings(duration_s=5, provider="veo")

    monkeypatch.setattr(st, "GenerationSettingsDialog", _FakeDialog)
    tab = SpriteTab(config=fake_config)
    tab.new_project_named("cfg")
    tab.open_generation_settings()
    assert tab.current_project.generation.duration_s == 5
    assert tab.current_project.generation.provider == "veo"


def test_shutdown_persists_splitters_and_is_safe_without_project(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    tab.shutdown()
    settings = sprite_settings()
    for key in st.SPLITTER_KEYS.values():
        assert settings.value(key) is not None


def test_current_action_follows_card_selection(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    tab.new_project_named("sel")
    card = tab.action_cards_panel.add_card()
    got = []
    tab.actionSelected.connect(lambda cid: got.append(cid))
    tab.action_cards_panel.table.selectRow(0)
    assert tab.current_action() is card
    assert got[-1] == card.id
    tab.action_cards_panel.table.clearSelection()
    assert tab.current_action() is None and got[-1] == ""


def test_add_toolbar_action_inserts_before_stretch(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    hits = []
    button = tab.add_toolbar_action("Export…", lambda: hits.append(1))
    assert isinstance(button, QPushButton)
    layout = tab.toolbar_layout
    index = next(i for i in range(layout.count()) if layout.itemAt(i).widget() is button)
    stretch = next(i for i in range(layout.count()) if layout.itemAt(i).spacerItem() is not None)
    assert index < stretch
    button.click()
    assert hits == [1]


def test_make_provider_uses_config_keys(qapp, fake_config, monkeypatch):
    import pytest
    seen = {}

    def fake_get_provider(name, cfg):
        seen.update(name=name, cfg=cfg)
        return "provider"

    monkeypatch.setattr(st, "get_provider", fake_get_provider)
    tab = SpriteTab(config=fake_config)
    assert tab.make_provider("google") == "provider"
    assert seen == {"name": "google", "cfg": {"api_key": "test-key", "auth_mode": "api-key"}}
    fake_config.api_key = None
    with pytest.raises(ValueError, match="API key"):
        tab.make_provider("google")


def test_project_switch_cancels_running_worker_before_swap(qapp, fake_config):
    """Fix round 1: a worker still running against the OLD project must never
    deliver its result after the panel has been repointed at a NEW project.

    ``on_finished`` here mirrors the real bug: it mutates whatever project the
    panel is CURRENTLY pointed at (as ``_on_cards_done`` does with
    ``self.project.actions.append(...)``), which is exactly what corrupts the
    new project if a stale job's ``finished`` fires after the swap.
    """
    tab = SpriteTab(config=fake_config)
    old_project = tab.new_project_named("old")

    finished_calls = []

    def slow_job(progress, token):
        # Bounded: checks the cancel token every 5 ms for up to 1.5 s, so
        # WorkerHost.shutdown()'s bounded wait (default 5000 ms) always wins.
        for _ in range(300):
            token.raise_if_cancelled()
            time.sleep(0.005)
        return "unexpected-completion"

    def on_finished(result):
        finished_calls.append(result)
        if tab.action_cards_panel.project is not None:
            tab.action_cards_panel.project.actions.append(
                ActionCard(id="stale", name="stale", prompt=""))

    worker = tab.action_cards_panel.start_job(
        slow_job, label="test-slow", on_finished=on_finished,
        on_failed=lambda m: None, on_cancelled=lambda: None)
    assert worker is not None
    assert tab.action_cards_panel.is_busy()

    new_project = tab.new_project_named("new")

    for _ in range(5):
        QApplication.processEvents()

    assert not tab.action_cards_panel.is_busy()
    assert finished_calls == []  # the stale job was cancelled, never finished
    assert new_project.actions == []
    assert old_project.actions == []
    assert tab.action_cards_panel.project is new_project


def test_project_switch_drops_stale_finished_event_from_instant_job(qapp, fake_config):
    """Fix round 2: an instant job that finishes right before the switch still
    has its ``finished`` queued when ``_apply_project`` swaps the project —
    ``shutdown()`` releases the worker before that queued event is drained,
    so ``WorkerHost._guarded`` must drop it instead of letting it mutate the
    NEW project (the sub-case fix round 1's ``is_busy()``/``shutdown()`` call
    alone does not catch, since the worker is no longer running by then).
    """
    tab = SpriteTab(config=fake_config)
    old_project = tab.new_project_named("old")

    finished_calls = []

    def instant_job(progress, token):
        return "instant-result"

    def on_finished(result):
        finished_calls.append(result)
        if tab.action_cards_panel.project is not None:
            tab.action_cards_panel.project.actions.append(
                ActionCard(id="stale2", name="stale2", prompt=""))

    worker = tab.action_cards_panel.start_job(
        instant_job, label="test-instant", on_finished=on_finished,
        on_failed=lambda m: None, on_cancelled=lambda: None)
    assert worker is not None
    assert worker.wait(5000)  # thread joined; finished is queued, not yet delivered

    new_project = tab.new_project_named("new")  # _apply_project shuts the worker down first

    for _ in range(5):
        QApplication.processEvents()  # now deliver the stale queued event, if any

    assert finished_calls == []
    assert new_project.actions == []
    assert old_project.actions == []
