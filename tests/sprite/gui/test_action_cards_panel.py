# tests/sprite/gui/test_action_cards_panel.py
"""ActionCardsPanel: brief → cards, editable table, per-card render/refine."""
import threading

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import gui.sprite.action_cards_panel as acp
from core.sprite.generation.action_cards import ActionCardDraft, default_chat_model
from gui.sprite.action_cards_panel import (
    COL_ACTIONS, COL_FPS, COL_LOOP, COL_NAME, COL_SECONDS, COL_STATUS, ActionCardsPanel,
)


def _panel(fake_config, fake_project):
    panel = ActionCardsPanel(fake_config)
    panel.set_project(fake_project)
    return panel


def test_genres_come_from_the_llm_contract(qapp, fake_config):
    panel = ActionCardsPanel(fake_config)
    genres = [panel.genre_combo.itemText(i) for i in range(panel.genre_combo.count())]
    assert "sidescroller" in genres and genres == sorted(genres)
    assert not panel.generate_btn.isEnabled()  # no project yet


def test_set_project_fills_rows_and_brief(qapp, fake_config, fake_project):
    fake_project.brief = "a knight"
    panel = _panel(fake_config, fake_project)
    assert panel.table.rowCount() == 2
    assert panel.table.item(0, COL_NAME).text() == "idle"
    assert panel.table.item(1, COL_STATUS).text() == "draft"
    assert panel.brief_edit.text() == "a knight"
    assert panel.generate_btn.isEnabled()


def test_editing_cells_writes_back_to_cards(qapp, fake_config, fake_project):
    panel = _panel(fake_config, fake_project)
    changed = []
    panel.cardsChanged.connect(lambda: changed.append(1))
    panel.table.item(0, COL_SECONDS).setText("6")
    panel.table.item(0, COL_FPS).setText("24")
    panel.table.item(0, COL_LOOP).setCheckState(Qt.Unchecked)
    panel.table.item(0, COL_NAME).setText("idle_stand")
    card = fake_project.actions[0]
    assert card.duration_s == 6 and card.fps == 24 and card.loop is False
    assert card.name == "idle_stand"
    assert len(changed) == 4


def test_invalid_edits_are_reverted_and_logged(qapp, fake_config, fake_project):
    panel = _panel(fake_config, fake_project)
    lines = []
    panel.logMessage.connect(lambda m, level: lines.append((level, m)))
    panel.table.item(0, COL_SECONDS).setText("forty")
    assert fake_project.actions[0].duration_s == 8
    assert panel.table.item(0, COL_SECONDS).text() == "8"
    panel.table.item(1, COL_NAME).setText("idle")  # duplicate of row 0
    assert fake_project.actions[1].name == "walk"
    panel.table.item(1, COL_NAME).setText("Bad Name")  # not snake_case
    assert fake_project.actions[1].name == "walk"
    assert [level for level, _ in lines].count("WARNING") == 3


def test_add_and_remove_cards(qapp, fake_config, fake_project):
    panel = _panel(fake_config, fake_project)
    card = panel.add_card()
    assert card in fake_project.actions and panel.table.rowCount() == 3
    assert card.name not in ("idle", "walk")
    panel.table.selectRow(2)
    assert panel.remove_selected() == 1
    assert card not in fake_project.actions and panel.table.rowCount() == 2


def test_render_requests_emit_ids(qapp, fake_config, fake_project):
    panel = _panel(fake_config, fake_project)
    got = []
    panel.renderRequested.connect(lambda ids: got.append(list(ids)))
    panel.request_render("a1")
    fake_project.actions[1].status = "rendered"
    panel.request_rerender("a2")
    assert got == [["a1"], ["a2"]]
    assert fake_project.actions[1].status == "draft"  # re-render resets the card
    panel.render_all_btn.click()
    assert got[-1] == ["a1", "a2"]


def test_refine_asks_for_instruction(qapp, fake_config, fake_project, monkeypatch):
    panel = _panel(fake_config, fake_project)
    got = []
    panel.refineRequested.connect(lambda cid, text: got.append((cid, text)))
    monkeypatch.setattr(acp.QInputDialog, "getMultiLineText",
                        staticmethod(lambda *a, **k: ("make the cape swing", True)))
    panel.request_refine("a1")
    assert got == [("a1", "make the cape swing")]
    monkeypatch.setattr(acp.QInputDialog, "getMultiLineText",
                        staticmethod(lambda *a, **k: ("", False)))
    panel.request_refine("a1")
    assert len(got) == 1


def test_generate_cards_appends_unique_names(qapp, fake_config, fake_project, monkeypatch,
                                             wait_for_worker):
    captured = {}

    def fake_generate(brief, genre, *, provider, model, api_key, plate_color,
                      auth_mode=None, completion_fn=None, log=None, token=None):
        captured.update(brief=brief, genre=genre, provider=provider, model=model,
                        api_key=api_key, plate_color=plate_color, auth_mode=auth_mode,
                        token=token)
        log("contract ok")
        return [ActionCardDraft(name="idle", prompt="stands still", duration_s=4, loop=True,
                                target_frames=6, fps=12),
                ActionCardDraft(name="jump", prompt="jumps", duration_s=6, loop=False,
                                target_frames=10, fps=12)]

    monkeypatch.setattr(acp, "generate_action_cards", fake_generate)
    monkeypatch.setattr(acp, "default_chat_model", lambda provider: "chat-model")
    panel = _panel(fake_config, fake_project)
    panel.brief_edit.setText("a brave knight")
    panel.genre_combo.setCurrentText("sidescroller")
    changed = []
    panel.cardsChanged.connect(lambda: changed.append(1))
    panel.generate_cards()
    wait_for_worker(panel)
    names = [card.name for card in fake_project.actions]
    assert names == ["idle", "walk", "idle_2", "jump"]
    assert fake_project.brief == "a brave knight" and fake_project.genre_preset == "sidescroller"
    assert captured["model"] == "chat-model" and captured["api_key"] == "test-key"
    assert captured["plate_color"] == "#00FF00"
    # Minor 2: the worker's cancel token reaches the completion call.
    assert captured["token"] is not None and hasattr(captured["token"], "raise_if_cancelled")
    assert panel.table.rowCount() == 4 and changed


def test_generate_cards_reads_the_google_key_under_its_config_name(qapp, fake_project,
                                                                    monkeypatch, wait_for_worker):
    """Important 2: the combo id is "gemini"; Settings stores the key as "google"."""
    captured = {}
    lookups = []

    class KeyConfig:
        def get_api_key(self, provider):
            lookups.append(provider)
            return "k" if provider == "google" else None

        def get_auth_mode(self, provider="google"):
            return "gcloud" if provider == "google" else "api_key"

        def get(self, key, default=None):
            return default

        def set(self, key, value):
            pass

    def fake_generate(brief, genre, **kwargs):
        captured.update(kwargs)
        return [ActionCardDraft(name="idle", prompt="stands still", duration_s=4, loop=True,
                                target_frames=6, fps=12)]

    monkeypatch.setattr(acp, "generate_action_cards", fake_generate)
    monkeypatch.setattr(acp, "default_chat_model", lambda provider: "chat-model")
    panel = _panel(KeyConfig(), fake_project)
    index = panel.llm_combo.findData("gemini")
    assert index >= 0, "the LLM combo no longer offers the gemini provider id"
    panel.llm_combo.setCurrentIndex(index)
    assert panel.llm_provider() == "gemini"
    assert ActionCardsPanel._config_key_for("gemini") == "google"
    assert ActionCardsPanel._config_key_for("openai") == "openai"
    panel.brief_edit.setText("a brave knight")
    panel.generate_cards()
    wait_for_worker(panel)
    assert lookups == ["google"]
    assert captured["api_key"] == "k"
    assert captured["auth_mode"] == "gcloud"
    assert captured["provider"] == "gemini"  # the provider id itself is unchanged


def test_cancel_button_cancels_running_generation(qapp, fake_config, fake_project, monkeypatch):
    """Minor 2 + T4: a Cancel button stops a slow LLM call and re-enables the panel."""
    release = threading.Event()
    lines = []

    def blocking_generate(brief, genre, *, token=None, **kwargs):
        while not release.wait(0.005):
            if token is not None:
                token.raise_if_cancelled()
        return []

    monkeypatch.setattr(acp, "generate_action_cards", blocking_generate)
    monkeypatch.setattr(acp, "default_chat_model", lambda provider: "chat-model")
    panel = _panel(fake_config, fake_project)
    panel.logMessage.connect(lambda m, level: lines.append((level, m)))
    assert not panel.cancel_btn.isEnabled()   # idle: nothing to cancel
    panel.brief_edit.setText("a brave knight")
    panel.generate_cards()
    worker = panel._worker
    assert worker is not None
    assert panel.cancel_btn.isEnabled() and not panel.generate_btn.isEnabled()
    panel.cancel_btn.click()
    assert worker.token.cancelled
    assert worker.wait(10000)
    release.set()
    for _ in range(5):
        QApplication.processEvents()
    assert ("WARNING", "Card generation cancelled.") in lines
    assert panel.generate_btn.isEnabled() and not panel.cancel_btn.isEnabled()
    assert panel.progress.isHidden()
    assert not panel.is_busy()


def _recording_generate(captured):
    def fake_generate(brief, genre, **kwargs):
        captured.update(kwargs)
        return [ActionCardDraft(name="idle", prompt="stands still", duration_s=4, loop=True,
                                target_frames=6, fps=12)]
    return fake_generate


def _select_provider(panel, provider_id):
    index = panel.llm_combo.findData(provider_id)
    assert index >= 0, f"the LLM combo no longer offers the {provider_id} provider id"
    panel.llm_combo.setCurrentIndex(index)
    assert panel.llm_provider() == provider_id


@pytest.mark.parametrize("provider_id", ["gemini", "openai"])
def test_generate_cards_resolves_a_real_chat_model(qapp, fake_config, fake_project, monkeypatch,
                                                   wait_for_worker, provider_id):
    """T6: the model is a registry id, never the family name "chat" (cf. 0a655b4)."""
    captured = {}
    lines = []
    monkeypatch.setattr(acp, "generate_action_cards", _recording_generate(captured))
    panel = _panel(fake_config, fake_project)
    panel.logMessage.connect(lambda m, level: lines.append(m))
    _select_provider(panel, provider_id)
    panel.brief_edit.setText("a brave knight")
    panel.generate_cards()
    wait_for_worker(panel)
    expected = default_chat_model(provider_id)
    assert captured["provider"] == provider_id
    assert captured["model"] == expected
    assert captured["model"] != "chat"
    # The status line names the resolved id so the log shows what was asked.
    assert any(f"{provider_id}/{expected}" in line for line in lines)


def test_generate_cards_reports_a_provider_without_a_chat_model(qapp, fake_config, fake_project,
                                                                monkeypatch):
    """No default chat model: no worker, and the error reaches the log and the dialog."""
    shown = []
    lines = []
    called = []

    def no_model(provider):
        raise ValueError(f"No default chat model for provider {provider!r}.")

    monkeypatch.setattr(acp, "default_chat_model", no_model)
    monkeypatch.setattr(acp, "generate_action_cards",
                        lambda *a, **k: called.append(1) or [])
    monkeypatch.setattr(acp, "show_error",
                        lambda parent, title, message, exception=None: shown.append(message))
    panel = _panel(fake_config, fake_project)
    panel.logMessage.connect(lambda m, level: lines.append((level, m)))
    panel.brief_edit.setText("a brave knight")
    panel.generate_cards()
    assert panel._worker is None and not called
    assert shown and "No default chat model" in shown[0]
    assert any(level == "ERROR" and "No default chat model" in m for level, m in lines)
    assert panel.generate_btn.isEnabled() and not panel.is_busy()


def test_generate_cards_requires_brief(qapp, fake_config, fake_project, monkeypatch):
    seen = []
    monkeypatch.setattr(acp, "show_warning",
                        lambda parent, title, message, log_level=None: seen.append(message))
    panel = _panel(fake_config, fake_project)
    panel.brief_edit.setText("   ")
    panel.generate_cards()
    assert seen and panel._worker is None


def test_hint_uses_timing_helper(qapp, fake_config, fake_project, monkeypatch):
    monkeypatch.setattr(acp, "suggest_clip_duration",
                        lambda frames, fps, provider, model: 8)
    panel = _panel(fake_config, fake_project)
    panel.table.selectRow(1)
    panel.refresh_hint()
    assert "8 s" in panel.hint_label.text() and "walk" in panel.hint_label.text()


def test_llm_provider_choice_is_sticky(qapp, fake_config, fake_project):
    from gui.sprite.prefs import LLM_PROVIDER_KEY, sprite_settings
    panel = _panel(fake_config, fake_project)
    assert panel.llm_combo.count() > 0
    panel.llm_combo.setCurrentIndex(panel.llm_combo.count() - 1)
    panel._on_llm_changed(panel.llm_combo.currentIndex())  # explicit: a 1-item combo emits nothing
    chosen = panel.llm_provider()
    assert sprite_settings().value(LLM_PROVIDER_KEY) == chosen
    other = ActionCardsPanel(fake_config)
    assert other.llm_provider() == chosen


def test_selection_emits_action_id(qapp, fake_config, fake_project):
    panel = _panel(fake_config, fake_project)
    got = []
    panel.actionSelected.connect(lambda cid: got.append(cid))
    panel.table.selectRow(1)
    assert got[-1] == "a2"
    panel.table.clearSelection()
    assert got[-1] == ""


def test_add_card_action_adds_button_to_every_row(qapp, fake_config, fake_project):
    from PySide6.QtWidgets import QPushButton
    panel = _panel(fake_config, fake_project)
    clicked = []
    panel.add_card_action("Render (image)", lambda card: clicked.append(card.id))
    for row in range(panel.table.rowCount()):
        buttons = panel.table.cellWidget(row, COL_ACTIONS).findChildren(QPushButton)
        assert [b.text() for b in buttons] == ["Render", "Re-render", "Refine…", "Render (image)"]
    panel.table.cellWidget(1, COL_ACTIONS).findChildren(QPushButton)[-1].click()
    assert clicked == ["a2"]
    panel.add_card()  # future rows get the button too
    last = panel.table.rowCount() - 1
    last_buttons = panel.table.cellWidget(last, COL_ACTIONS).findChildren(QPushButton)
    assert last_buttons[-1].text() == "Render (image)"
