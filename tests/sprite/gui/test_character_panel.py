# tests/sprite/gui/test_character_panel.py
"""CharacterPanel: intake, normalize, chroma plate, turnaround (offscreen)."""
import shutil
import types
from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl

import gui.sprite.character_panel as cp
from gui.sprite.character_panel import CharacterPanel, paths_from_mime


def test_reference_follows_splitter_and_can_shrink_again(qapp, fake_config, png):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QSplitter, QWidget

    splitter = QSplitter(Qt.Vertical)
    panel = CharacterPanel(fake_config)
    splitter.addWidget(panel)
    splitter.addWidget(QWidget())
    splitter.resize(720, 900)
    panel._show_thumbnail(png)
    splitter.show()
    splitter.setSizes([350, 550])
    qapp.processEvents()
    small = panel.drop_label.pixmap().size()
    splitter.setSizes([650, 250])
    qapp.processEvents()
    large = panel.drop_label.pixmap().size()
    assert large.height() > small.height()
    assert large.width() > 200
    assert abs(large.width() / large.height() - 64 / 48) < 0.02
    assert large.width() <= panel.drop_label.contentsRect().width()
    assert large.height() <= panel.drop_label.contentsRect().height()
    splitter.setSizes([350, 550])
    qapp.processEvents()
    assert panel.drop_label.pixmap().size() == small
    panel._show_thumbnail(None)
    splitter.setSizes([650, 250])
    qapp.processEvents()
    assert panel.drop_label.text() == cp.DROP_HINT
    assert panel.drop_label.pixmap().isNull()
    splitter.close()


def _analysis(size=(64, 48)):
    return types.SimpleNamespace(has_alpha=False, border_color="#FFFFFF",
                                 border_uniform=True, size=size)


def _patch_source(monkeypatch):
    def fake_normalize(image, out_png, aspect_ratio="16:9"):
        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(image, out_png)
        return Path(out_png)

    monkeypatch.setattr(cp, "normalize_source", fake_normalize)
    monkeypatch.setattr(cp, "analyze_source", lambda image: _analysis())


def _capture_errors(monkeypatch):
    seen = []
    monkeypatch.setattr(cp, "show_error",
                        lambda parent, title, message, exception=None: seen.append(message))
    return seen


def test_construction_without_project_disables_actions(qapp, fake_config):
    panel = CharacterPanel(fake_config)
    assert not panel.browse_btn.isEnabled()
    assert not panel.plate_btn.isEnabled()
    assert not panel.turnaround_btn.isEnabled()
    assert panel.plate_color == "#00FF00"


def test_set_project_enables_browse_only(qapp, fake_config, fake_project):
    panel = CharacterPanel(fake_config)
    panel.set_project(fake_project)
    assert panel.browse_btn.isEnabled()
    assert not panel.plate_btn.isEnabled()  # no character yet


def test_set_source_normalizes_into_project_and_emits(qapp, fake_config, fake_project, png,
                                                      monkeypatch, wait_for_worker):
    _patch_source(monkeypatch)
    panel = CharacterPanel(fake_config)
    panel.set_project(fake_project)
    got = []
    panel.sourceChanged.connect(lambda p: got.append(p))
    panel.set_source(png)
    wait_for_worker(panel)
    expected = fake_project.project_dir / "source" / "character.png"
    assert expected.exists()
    assert fake_project.character_source == expected
    assert got == [expected]
    assert "64×48" in panel.analysis_label.text()
    assert panel.plate_btn.isEnabled() and panel.turnaround_btn.isEnabled()


def test_set_source_missing_file_reports_error_without_worker(qapp, fake_config, fake_project,
                                                              monkeypatch, tmp_path):
    seen = _capture_errors(monkeypatch)
    panel = CharacterPanel(fake_config)
    panel.set_project(fake_project)
    panel.set_source(tmp_path / "nope.png")
    assert seen and "nope.png" in seen[0]
    assert panel._worker is None


def test_set_source_without_project_reports_error(qapp, fake_config, png, monkeypatch):
    seen = _capture_errors(monkeypatch)
    panel = CharacterPanel(fake_config)
    panel.set_source(png)
    assert seen and "project" in seen[0].lower()


def test_make_plate_requires_api_key(qapp, fake_project, png, monkeypatch):
    seen = _capture_errors(monkeypatch)
    config = types.SimpleNamespace(get_api_key=lambda p: None, get_auth_mode=lambda p="google": "api-key")
    panel = CharacterPanel(config)
    fake_project.character_source = png
    panel.set_project(fake_project)
    panel.make_plate()
    assert seen and "api key" in seen[0].lower()
    assert panel._worker is None


def test_make_plate_runs_in_worker_and_records_plate(qapp, fake_config, fake_project, png,
                                                     monkeypatch, wait_for_worker):
    calls = {}

    def fake_make_plate(provider, character, out_png, plate_color="#00FF00", *, model=None,
                        log=None, token=None):
        calls.update(character=character, out=out_png, color=plate_color, token=token)
        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(character, out_png)
        log("plate done")
        return Path(out_png)

    monkeypatch.setattr(cp, "make_chroma_plate", fake_make_plate)
    monkeypatch.setattr(cp, "get_provider", lambda name, cfg: object())
    panel = CharacterPanel(fake_config)
    fake_project.character_source = png
    panel.set_project(fake_project)
    ready, history, lines = [], [], []
    panel.plateReady.connect(lambda p: ready.append(p))
    panel.historyEntry.connect(lambda e: history.append(e))
    panel.logMessage.connect(lambda m, level: lines.append(m))
    panel.make_plate()
    wait_for_worker(panel)
    expected = fake_project.project_dir / "source" / "plate.png"
    assert calls["out"] == expected and calls["color"] == "#00FF00"
    assert fake_project.plate_path == expected
    assert ready == [expected]
    assert history and history[0]["path"] == expected and history[0]["source_tab"] == "sprite"
    assert any("plate done" in line for line in lines)
    # Minor 2: the worker's cancel token reaches the provider call.
    assert calls["token"] is not None and hasattr(calls["token"], "raise_if_cancelled")


def test_make_plate_reaches_model_through_stale_cached_provider(qapp, fake_config, fake_project,
                                                                png, monkeypatch, wait_for_worker):
    """A provider cached with an empty key must still reach the model after the key is set.

    Uses the real ``get_provider`` so the cache-hit path is exercised end to end.
    """
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    import providers
    import providers.google as google_mod

    def _fake_response(data):
        part = SimpleNamespace(text=None, inline_data=SimpleNamespace(data=data))
        cand = SimpleNamespace(content=SimpleNamespace(parts=[part]), finish_reason="STOP")
        return SimpleNamespace(candidates=[cand])

    built = []

    def factory(**kwargs):
        client = MagicMock()
        client.api_key = kwargs.get("api_key")
        client.models.generate_content.return_value = _fake_response(png.read_bytes())
        built.append(client)
        return client

    providers.clear_provider_cache()
    monkeypatch.setattr(google_mod, "genai", SimpleNamespace(Client=factory))
    monkeypatch.setattr(google_mod, "GENAI_AVAILABLE", True)
    monkeypatch.setattr(google_mod, "rate_limiter", MagicMock())
    try:
        stale = providers.get_provider("google", {"api_key": ""})
        assert stale.client is None

        seen = _capture_errors(monkeypatch)
        panel = CharacterPanel(fake_config)
        fake_project.character_source = png
        panel.set_project(fake_project)
        panel.make_plate()
        wait_for_worker(panel)

        assert seen == []
        assert built and built[-1].api_key == fake_config.api_key
        built[-1].models.generate_content.assert_called_once()
        assert fake_project.plate_path == fake_project.project_dir / "source" / "plate.png"
        assert fake_project.plate_path.exists()
    finally:
        providers.clear_provider_cache()


def test_worker_failure_is_shown_and_logged(qapp, fake_config, fake_project, png,
                                            monkeypatch, wait_for_worker):
    def boom(*a, **k):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(cp, "make_chroma_plate", boom)
    monkeypatch.setattr(cp, "get_provider", lambda name, cfg: object())
    seen = _capture_errors(monkeypatch)
    panel = CharacterPanel(fake_config)
    fake_project.character_source = png
    panel.set_project(fake_project)
    panel.make_plate()
    # Minor 12: isHidden() (not isVisible()) is the assertion with teeth — an
    # unshown parent makes isVisible() False whatever setVisible() did.
    assert not panel.progress.isHidden()
    wait_for_worker(panel)
    assert seen == ["provider exploded"]
    assert panel.progress.isHidden()


def test_generate_turnaround_stores_views(qapp, fake_config, fake_project, png,
                                          monkeypatch, wait_for_worker):
    def fake_turnaround(provider, character, out_dir, views=("front", "side"), *, plate_color,
                        do_not_change=(), model=None, log=None, token=None):
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        result = {}
        for view in ("front", "side"):
            target = Path(out_dir) / f"{view}.png"
            shutil.copy(character, target)
            result[view] = target
        return result

    monkeypatch.setattr(cp, "generate_turnaround", fake_turnaround)
    monkeypatch.setattr(cp, "get_provider", lambda name, cfg: object())
    panel = CharacterPanel(fake_config)
    fake_project.character_source = png
    panel.set_project(fake_project)
    got = []
    panel.turnaroundReady.connect(lambda d: got.append(d))
    panel.generate_turnaround()
    wait_for_worker(panel)
    assert set(fake_project.turnaround) == {"front", "side"}
    assert got and set(got[0]) == {"front", "side"}


def test_plate_color_change_updates_project_and_emits(qapp, fake_config, fake_project, monkeypatch):
    from PySide6.QtGui import QColor
    monkeypatch.setattr(cp.QColorDialog, "getColor",
                        staticmethod(lambda *a, **k: QColor("#ff00ff")))
    panel = CharacterPanel(fake_config)
    panel.set_project(fake_project)
    got = []
    panel.plateColorChanged.connect(lambda c: got.append(c))
    panel.plate_color_btn.click()
    assert panel.plate_color == "#FF00FF"
    assert fake_project.plate_color == "#FF00FF"
    assert got == ["#FF00FF"]


def test_paths_from_mime_filters_images(qapp, tmp_path):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path / "a.png")),
                  QUrl.fromLocalFile(str(tmp_path / "b.txt"))])
    assert paths_from_mime(mime) == [tmp_path / "a.png"]



def test_original_background_disables_plate_generation(qapp, fake_config, fake_project, png, monkeypatch):
    fake_project.background.mode = "original"
    fake_project.character_source = png
    panel = CharacterPanel(fake_config)
    panel.set_project(fake_project)
    assert not panel.plate_btn.isEnabled()
    assert not panel.plate_color_btn.isEnabled()
    assert not panel.turnaround_btn.isEnabled()
    calls = []
    monkeypatch.setattr(panel, "_ready_for_provider", lambda what: calls.append(what))
    panel.make_plate()
    panel.generate_turnaround()
    assert calls == []
