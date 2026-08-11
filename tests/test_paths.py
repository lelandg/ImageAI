"""Unit tests for the DataPaths resolver."""
import json
from pathlib import Path

import pytest

from core.paths import (
    DataPaths,
    Group,
    get_data_paths,
    reset_data_paths,
    set_warning_sink,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_data_paths()
    set_warning_sink(None)
    yield
    reset_data_paths()
    set_warning_sink(None)


def _write_config(tmp_path, payload):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(payload), encoding="utf-8")
    return cfg


def test_default_root_is_config_dir_when_no_override(tmp_path):
    cfg = _write_config(tmp_path, {})
    dp = DataPaths(config_path=cfg)
    assert dp.root(Group.IMAGES) == tmp_path


def test_override_is_used_when_reachable(tmp_path):
    dest = tmp_path / "elsewhere"
    dest.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(dest)}})
    dp = DataPaths(config_path=cfg)
    assert dp.root(Group.IMAGES) == dest


def test_override_applies_only_to_its_own_group(tmp_path):
    dest = tmp_path / "elsewhere"
    dest.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(dest)}})
    dp = DataPaths(config_path=cfg)
    assert dp.root(Group.IMAGES) == dest
    assert dp.root(Group.VIDEO) == tmp_path
    assert dp.root(Group.MODELS) == tmp_path
    assert dp.root(Group.SETTINGS) == tmp_path


def test_null_override_falls_back_to_default(tmp_path):
    cfg = _write_config(tmp_path, {"data_roots": {"images": None}})
    dp = DataPaths(config_path=cfg)
    assert dp.root(Group.IMAGES) == tmp_path


def test_unreachable_override_falls_back_and_warns(tmp_path):
    missing = tmp_path / "no" / "such" / "drive"
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(missing)}})
    dp = DataPaths(config_path=cfg)

    assert dp.root(Group.IMAGES) == tmp_path
    warnings = dp.drain_warnings()
    assert len(warnings) == 1
    assert str(missing) in warnings[0]
    assert "images" in warnings[0].lower()


def test_unreachable_override_does_not_rewrite_config(tmp_path):
    missing = tmp_path / "gone"
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(missing)}})
    dp = DataPaths(config_path=cfg)
    dp.root(Group.IMAGES)

    on_disk = json.loads(cfg.read_text(encoding="utf-8"))
    assert on_disk["data_roots"]["images"] == str(missing)


def test_drain_warnings_empties_the_buffer(tmp_path):
    missing = tmp_path / "gone"
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(missing)}})
    dp = DataPaths(config_path=cfg)
    dp.root(Group.IMAGES)

    assert dp.drain_warnings()
    assert dp.drain_warnings() == []


def test_warning_after_sink_install_reaches_the_sink(tmp_path):
    """A root resolved after startup must not land in a buffer nobody reads."""
    missing = tmp_path / "offline_share"
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(missing)}})
    dp = DataPaths(config_path=cfg)

    received = []
    set_warning_sink(received.append)
    dp.root(Group.IMAGES)

    assert len(received) == 1
    assert str(missing) in received[0]
    assert "images" in received[0].lower()


def test_warnings_buffered_before_the_sink_are_still_drained(tmp_path):
    """core.paths resolves the Settings root before the logger exists."""
    missing = tmp_path / "offline_share"
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(missing)}})
    dp = DataPaths(config_path=cfg)
    dp.root(Group.IMAGES)

    received = []
    set_warning_sink(received.append)

    drained = dp.drain_warnings()
    assert len(drained) == 1
    assert str(missing) in drained[0]
    assert received == []


def test_installing_a_sink_twice_does_not_duplicate_delivery(tmp_path):
    missing = tmp_path / "offline_share"
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(missing)}})
    dp = DataPaths(config_path=cfg)

    received = []
    set_warning_sink(received.append)
    set_warning_sink(received.append)
    dp.root(Group.IMAGES)

    assert len(received) == 1


def test_a_broken_sink_leaves_the_warning_in_the_buffer(tmp_path):
    """Path resolution must survive a sink that raises."""
    def _explode(_message):
        raise RuntimeError("sink is broken")

    missing = tmp_path / "offline_share"
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(missing)}})
    dp = DataPaths(config_path=cfg)

    set_warning_sink(_explode)
    assert dp.root(Group.IMAGES) == tmp_path
    assert any(str(missing) in w for w in dp.drain_warnings())


def test_a_reachable_root_raises_no_warning(tmp_path):
    dest = tmp_path / "elsewhere"
    dest.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(dest)}})
    dp = DataPaths(config_path=cfg)

    received = []
    set_warning_sink(received.append)
    dp.root(Group.IMAGES)

    assert received == []


def test_missing_config_file_uses_defaults(tmp_path):
    dp = DataPaths(config_path=tmp_path / "absent.json")
    assert dp.root(Group.IMAGES) == tmp_path
    assert dp.drain_warnings() == []


def test_corrupt_config_uses_defaults_and_warns(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{not json", encoding="utf-8")
    dp = DataPaths(config_path=cfg)

    assert dp.root(Group.IMAGES) == tmp_path
    assert any("config.json" in w for w in dp.drain_warnings())


def test_accessors_sit_under_the_right_roots(tmp_path):
    images = tmp_path / "I"
    video = tmp_path / "V"
    models = tmp_path / "M"
    for d in (images, video, models):
        d.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {
        "images": str(images), "video": str(video), "models": str(models),
    }})
    dp = DataPaths(config_path=cfg)

    assert dp.generated() == images / "generated"
    assert dp.composites() == images / "composites"
    assert dp.styles() == images / "styles"
    assert dp.characters() == images / "Characters"
    assert dp.midjourney_cache() == images / "midjourney_web_cache"

    assert dp.video_projects() == video / "video_projects"
    assert dp.video_cache("thumbnails") == video / "cache" / "thumbnails"
    assert dp.video_events_db() == video / "video_projects" / "events.db"

    assert dp.musetalk() == models / "musetalk"
    assert dp.weights() == models / "weights"
    assert dp.huggingface() == models / "huggingface"

    assert dp.logs() == tmp_path / "logs"
    assert dp.history_file("prompt") == tmp_path / "prompt_history.json"


def test_config_file_never_moves(tmp_path):
    dest = tmp_path / "elsewhere"
    dest.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"settings": str(dest)}})
    dp = DataPaths(config_path=cfg)

    assert dp.root(Group.SETTINGS) == dest
    assert dp.config_file() == cfg
    assert dp.config_file().parent == tmp_path


def test_get_data_paths_returns_a_singleton():
    assert get_data_paths() is get_data_paths()


def test_reset_data_paths_clears_the_singleton():
    first = get_data_paths()
    reset_data_paths()
    assert get_data_paths() is not first


def test_paths_module_imports_no_logging_or_config():
    """core/paths.py must stay importable before the logger exists."""
    import ast
    import pathlib

    source = pathlib.Path("core/paths.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not any("logging_config" in name for name in imported)
    assert not any(name in ("core.config", ".config") for name in imported)


def test_logger_uses_the_settings_root(tmp_path, monkeypatch):
    """setup_logging must write under DataPaths.logs(), not a hardcoded dir."""
    import logging

    import core.paths as paths_mod
    from core.logging_config import setup_logging

    dest = tmp_path / "settings_root"
    dest.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"settings": str(dest)}})

    monkeypatch.setattr(paths_mod, "_INSTANCE", paths_mod.DataPaths(config_path=cfg))
    try:
        log_file = setup_logging(log_level=logging.INFO, log_to_file=True)
        assert log_file is not None
        assert Path(log_file).parent == dest / "logs"
    finally:
        logging.getLogger().handlers.clear()


def test_sink_delivery_keeps_the_message_for_the_gui_widget(tmp_path):
    """The Storage Locations widget drains the buffer to mark unavailable rows."""
    missing = tmp_path / "offline_share"
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(missing)}})
    dp = DataPaths(config_path=cfg)

    received = []
    set_warning_sink(received.append)
    dp.root(Group.IMAGES)

    assert len(received) == 1
    assert any("'images'" in w for w in dp.drain_warnings())


def test_setup_logging_installs_the_sink_for_later_roots(tmp_path, monkeypatch, capsys):
    """A CLI run resolves Images, Video and Models after the logger starts.

    Without the sink the fallback warning stays in the buffer, so the user gets
    a silent fallback. Design section 8 requires one visible line per root.
    """
    import logging

    import core.paths as paths_mod
    from core.logging_config import setup_logging

    settings = tmp_path / "settings_root"
    settings.mkdir()
    missing = tmp_path / "offline_share"
    cfg = _write_config(tmp_path, {"data_roots": {
        "settings": str(settings), "images": str(missing),
    }})

    dp = paths_mod.DataPaths(config_path=cfg)
    monkeypatch.setattr(paths_mod, "_INSTANCE", dp)
    try:
        log_file = setup_logging(log_level=logging.INFO, log_to_file=True)
        capsys.readouterr()  # discard the startup banner

        assert dp.root(Group.IMAGES) == tmp_path

        for handler in logging.getLogger().handlers:
            handler.flush()

        stderr = capsys.readouterr().err
        assert str(missing) in stderr, "the CLI user must see the fallback"
        assert str(missing) in Path(log_file).read_text(encoding="utf-8")
    finally:
        logging.getLogger().handlers.clear()


def test_setup_logging_reports_roots_resolved_before_it_started(tmp_path, monkeypatch, capsys):
    """The Settings root resolves before the logger exists, so it is buffered."""
    import logging

    import core.paths as paths_mod
    from core.logging_config import setup_logging

    missing = tmp_path / "offline_share"
    cfg = _write_config(tmp_path, {"data_roots": {"settings": str(missing)}})

    dp = paths_mod.DataPaths(config_path=cfg)
    monkeypatch.setattr(paths_mod, "_INSTANCE", dp)
    try:
        log_file = setup_logging(log_level=logging.INFO, log_to_file=True)
        for handler in logging.getLogger().handlers:
            handler.flush()

        stderr = capsys.readouterr().err
        assert str(missing) in stderr
        assert str(missing) in Path(log_file).read_text(encoding="utf-8")
    finally:
        logging.getLogger().handlers.clear()


def test_musetalk_keeps_legacy_linux_cache(tmp_path, monkeypatch):
    """An existing ~/.cache/imageai/musetalk must not trigger a 4 GB re-download."""
    import core.paths as paths_mod
    from core.musetalk_installer import get_musetalk_model_path

    legacy = tmp_path / ".cache" / "imageai" / "musetalk"
    legacy.mkdir(parents=True)
    (legacy / "musetalk").mkdir()

    cfg = _write_config(tmp_path, {})
    monkeypatch.setattr(paths_mod, "_INSTANCE", paths_mod.DataPaths(config_path=cfg))
    monkeypatch.setattr(paths_mod.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr("core.musetalk_installer.Path.home", staticmethod(lambda: tmp_path))

    assert get_musetalk_model_path() == legacy


def test_musetalk_uses_models_root_when_no_legacy_dir(tmp_path, monkeypatch):
    import core.paths as paths_mod
    from core.musetalk_installer import get_musetalk_model_path

    models = tmp_path / "M"
    models.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"models": str(models)}})
    monkeypatch.setattr(paths_mod, "_INSTANCE", paths_mod.DataPaths(config_path=cfg))
    monkeypatch.setattr("core.musetalk_installer.Path.home", staticmethod(lambda: tmp_path))

    assert get_musetalk_model_path() == models / "musetalk"


def test_styles_store_uses_the_images_root(tmp_path, monkeypatch):
    import core.paths as paths_mod

    images = tmp_path / "I"
    images.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(images)}})
    monkeypatch.setattr(paths_mod, "_INSTANCE", paths_mod.DataPaths(config_path=cfg))

    from core.styles.store import StyleStore

    assert StyleStore().base_dir == images / "styles"


def test_local_sd_cache_uses_the_models_root(tmp_path, monkeypatch):
    import core.paths as paths_mod

    models = tmp_path / "M"
    models.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"models": str(models)}})
    monkeypatch.setattr(paths_mod, "_INSTANCE", paths_mod.DataPaths(config_path=cfg))

    from providers.local_sd import LocalSDProvider

    provider = LocalSDProvider({})
    assert provider.cache_dir == models / "huggingface"


def test_explicit_cache_dir_config_still_wins(tmp_path, monkeypatch):
    """The pre-existing config key keeps working for anyone who set it."""
    import core.paths as paths_mod

    models = tmp_path / "M"
    custom = tmp_path / "custom"
    for d in (models, custom):
        d.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"models": str(models)}})
    monkeypatch.setattr(paths_mod, "_INSTANCE", paths_mod.DataPaths(config_path=cfg))

    from providers.local_sd import LocalSDProvider

    provider = LocalSDProvider({"cache_dir": str(custom)})
    assert provider.cache_dir == custom


def test_character_animator_keeps_the_shared_hub_path():
    """The shared HuggingFace hub belongs to other tools and must not move."""
    import pathlib

    text = pathlib.Path("core/character_animator/installer.py").read_text(encoding="utf-8")
    assert '".cache" / "huggingface"' in text or '.cache/huggingface' in text
