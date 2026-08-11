"""ConfigManager.save() must never clobber another writer's config.json.

The migrator writes ``data_roots`` straight to disk while the GUI holds a
ConfigManager whose in-memory dict predates that write. A later save() from the
GUI must keep the new roots, or the relocated data is stranded.
"""
import json
import logging
import threading
import time
from pathlib import Path

import pytest

import core.paths as paths_mod
from core import config_io
from core.paths import DataPaths


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    """Point the DataPaths singleton at a throw-away config.json."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"provider": "google"}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))
    return cfg


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _manager():
    from core.config import ConfigManager

    return ConfigManager()


def test_save_keeps_data_roots_written_by_another_writer(config_path, tmp_path):
    """The move flow writes data_roots to disk; save() must not erase it."""
    manager = _manager()

    # The migrator relocates the Images group behind the manager's back.
    moved = tmp_path / "moved-images"
    moved.mkdir()
    on_disk = _read(config_path)
    on_disk["data_roots"] = {"images": str(moved)}
    _write(config_path, on_disk)

    # The app closes normally and flushes its own settings.
    manager.set("provider", "openai")
    manager.save()

    result = _read(config_path)
    assert result["data_roots"] == {"images": str(moved)}
    assert result["provider"] == "openai"


def test_save_keeps_data_roots_when_nothing_changed_in_memory(config_path, tmp_path):
    """closeEvent saves even when the user changed no setting."""
    manager = _manager()

    moved = tmp_path / "moved-video"
    moved.mkdir()
    on_disk = _read(config_path)
    on_disk["data_roots"] = {"video": str(moved)}
    _write(config_path, on_disk)

    manager.save()

    assert _read(config_path)["data_roots"] == {"video": str(moved)}


def test_save_persists_ordinary_settings(config_path):
    manager = _manager()
    manager.set("provider", "stability")
    manager.set("model", "sd3")
    manager.save()

    result = _read(config_path)
    assert result["provider"] == "stability"
    assert result["model"] == "sd3"


def test_nested_provider_settings_survive_a_save(config_path):
    manager = _manager()
    manager.set_provider_config("openai", {"model": "gpt-image-2"})
    manager.save()

    assert _read(config_path)["providers"]["openai"] == {"model": "gpt-image-2"}


def test_explicit_data_roots_wins_only_for_the_keys_it_names(config_path, tmp_path):
    """An in-memory data_roots edit wins; groups it never names come from disk."""
    manager = _manager()

    chosen = tmp_path / "chosen-images"
    chosen.mkdir()
    manager.set("data_roots", {"images": str(chosen)})

    # Another writer moves a different group in the meantime.
    other = tmp_path / "other-video"
    other.mkdir()
    on_disk = _read(config_path)
    on_disk["data_roots"] = {"images": str(tmp_path / "stale"), "video": str(other)}
    _write(config_path, on_disk)

    manager.save()

    roots = _read(config_path)["data_roots"]
    assert roots["images"] == str(chosen)
    assert roots["video"] == str(other)


def test_key_deleted_in_memory_is_removed_from_disk(config_path):
    manager = _manager()
    assert manager.get("provider") == "google"
    del manager.config["provider"]
    manager.save()

    assert "provider" not in _read(config_path)


def test_corrupt_config_is_preserved_before_a_save_replaces_it(config_path, caplog):
    """A truncated config.json must survive as a sidecar, not vanish.

    A power loss leaves a half-written file that still holds the API key and
    the data_roots entry. Reading it fails, so the merge sees nothing on disk
    and the save would otherwise write only this session's settings over it.
    """
    manager = _manager()
    manager.set("window_geometry", {"x": 1, "y": 2})

    corrupt = ('{"data_roots": {"images": "/mnt/big/ImageAI/Images"}, '
               '"providers": {"openai": {"api_key": "sk-REAL"}}, ')
    config_path.write_text(corrupt, encoding="utf-8")

    with caplog.at_level(logging.ERROR):
        manager.save()

    sidecars = sorted(config_path.parent.glob("config.json.corrupt-*"))
    assert len(sidecars) == 1, "the unreadable original must be preserved"
    assert sidecars[0].read_text(encoding="utf-8") == corrupt
    assert "sk-REAL" in sidecars[0].read_text(encoding="utf-8")
    assert any("config.json" in record.getMessage() for record in caplog.records), (
        "an unreadable config.json must be logged at error level"
    )
    assert any(record.levelno >= logging.ERROR for record in caplog.records)

    # The session keeps working: the replacement holds this session's settings.
    assert _read(config_path)["window_geometry"] == {"x": 1, "y": 2}


def test_save_refuses_to_write_when_the_original_cannot_be_preserved(
    config_path, monkeypatch, caplog
):
    """No copy means no overwrite. The only copy of the keys must stay put."""
    manager = _manager()
    manager.set("window_geometry", {"x": 1, "y": 2})

    corrupt = '{"providers": {"openai": {"api_key": "sk-REAL"}}, '
    config_path.write_text(corrupt, encoding="utf-8")

    def _boom(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(config_io.shutil, "copy2", _boom)

    with caplog.at_level(logging.ERROR):
        manager.save()

    assert config_path.read_text(encoding="utf-8") == corrupt
    assert any(record.levelno >= logging.ERROR for record in caplog.records)


def test_missing_config_is_still_a_fresh_install(tmp_path, monkeypatch):
    """A config.json that was never created must not look like a corrupt one."""
    cfg = tmp_path / "fresh" / "config.json"
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    manager = _manager()
    manager.set("provider", "google")
    manager.save()

    assert _read(cfg)["provider"] == "google"
    assert not list(cfg.parent.glob("config.json.corrupt-*"))


def test_failed_write_leaves_the_previous_file_intact(config_path, monkeypatch):
    """A crash mid-write must not truncate config.json."""
    manager = _manager()
    manager.set("provider", "openai")
    manager.save()
    before = config_path.read_text(encoding="utf-8")

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(config_io.json, "dump", _boom)
    manager.set("provider", "stability")
    with pytest.raises(config_io.ConfigWriteError):
        manager.save()

    assert config_path.read_text(encoding="utf-8") == before
    assert not list(config_path.parent.glob("*.tmp*")), "temp file left behind"


def test_save_serialises_against_a_concurrent_config_io_writer(
    config_path, tmp_path, monkeypatch
):
    """The migrator records data_roots while a worker thread saves.

    ``ConfigManager.save()`` is a read-modify-write. Without one lock held
    across the whole cycle, the save writes a document it read before the
    migrator's write and the new root disappears, which strands the moved data.
    """
    manager = _manager()
    manager.set("last_prompt", "cat")

    moved = tmp_path / "moved-images"
    moved.mkdir()

    inside_save = threading.Event()
    slowed = []
    real_read = config_io.read_config

    def slow_read(path, *args, **kwargs):
        data = real_read(path, *args, **kwargs)
        if not slowed:
            slowed.append(True)
            inside_save.set()
            # Hold the read-modify-write window open. An unsynchronised save
            # loses the competing write every run.
            time.sleep(0.4)
        return data

    monkeypatch.setattr(config_io, "read_config", slow_read)

    def migrator():
        assert inside_save.wait(10)

        def mutate(data):
            data.setdefault("data_roots", {})["images"] = str(moved)

        config_io.update_config(config_path, mutate, timeout=30)

    thread = threading.Thread(target=migrator)
    thread.start()
    manager.save()
    thread.join(30)
    assert not thread.is_alive()

    result = _read(config_path)
    assert result["data_roots"] == {"images": str(moved)}, (
        "the migrator's new root must survive a concurrent save"
    )
    assert result["last_prompt"] == "cat"


def test_a_key_another_writer_deleted_stays_deleted(config_path):
    """The merge must not resurrect a key this process never touched."""
    manager = _manager()
    assert manager.get("provider") == "google"

    _write(config_path, {})  # another writer removed the setting

    manager.save()

    assert "provider" not in _read(config_path)
    assert "provider" not in manager.config


def test_a_key_added_here_survives_a_concurrent_rewrite(config_path):
    """The other half of the rule: a real local edit still wins."""
    manager = _manager()
    manager.set("new_setting", "value")

    _write(config_path, {})

    manager.save()

    assert _read(config_path)["new_setting"] == "value"


def test_a_key_edited_here_survives_a_concurrent_delete(config_path):
    manager = _manager()
    manager.set("provider", "openai")

    _write(config_path, {})

    manager.save()

    assert _read(config_path)["provider"] == "openai"


def test_save_keeps_live_references_to_nested_sections(config_path):
    """Callers hold the dict get_layout_config() returns; save must not orphan it."""
    manager = _manager()
    manager.set_layout_config({"export_dpi": 300})
    manager.save()

    section = manager.get_layout_config()
    manager.save()
    section["export_dpi"] = 600
    manager.save()

    assert _read(config_path)["layout"]["export_dpi"] == 600


def test_save_refreshes_the_in_memory_dict_with_the_merged_result(
    config_path, tmp_path
):
    manager = _manager()

    moved = tmp_path / "moved-models"
    moved.mkdir()
    on_disk = _read(config_path)
    on_disk["data_roots"] = {"models": str(moved)}
    _write(config_path, on_disk)

    manager.save()

    assert manager.get("data_roots") == {"models": str(moved)}
