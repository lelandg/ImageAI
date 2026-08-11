"""ConfigManager.save() must never clobber another writer's config.json.

The migrator writes ``data_roots`` straight to disk while the GUI holds a
ConfigManager whose in-memory dict predates that write. A later save() from the
GUI must keep the new roots, or the relocated data is stranded.
"""
import json
import logging
from pathlib import Path

import pytest

import core.paths as paths_mod
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


def test_corrupt_config_on_disk_does_not_discard_in_memory_settings(
    config_path, caplog
):
    manager = _manager()
    manager.set("provider", "openai")

    config_path.write_text("{ this is not json", encoding="utf-8")

    with caplog.at_level(logging.ERROR, logger="core.config"):
        manager.save()

    result = _read(config_path)
    assert result["provider"] == "openai"
    assert any("config.json" in record.message for record in caplog.records), (
        "an unreadable config.json must be logged"
    )


def test_failed_write_leaves_the_previous_file_intact(config_path, monkeypatch):
    """A crash mid-write must not truncate config.json."""
    manager = _manager()
    manager.set("provider", "openai")
    manager.save()
    before = config_path.read_text(encoding="utf-8")

    import core.config as config_mod

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(config_mod.json, "dump", _boom)
    manager.set("provider", "stability")
    with pytest.raises(OSError):
        manager.save()

    assert config_path.read_text(encoding="utf-8") == before
    assert not list(config_path.parent.glob("*.tmp*")), "temp file left behind"


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
