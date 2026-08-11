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


def test_failed_write_leaves_the_previous_file_intact(config_path, monkeypatch, caplog):
    """A crash mid-write must not truncate config.json, and must not raise.

    ``save()`` runs from Qt slots and from ``__init__``. A write failure that
    escapes aborts the slot halfway or stops the application from starting, so
    it is logged and reported through the return value instead.
    """
    manager = _manager()
    manager.set("provider", "openai")
    manager.save()
    before = config_path.read_text(encoding="utf-8")

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(config_io.json, "dump", _boom)
    manager.set("provider", "stability")
    with caplog.at_level(logging.ERROR):
        assert manager.save() is False

    assert config_path.read_text(encoding="utf-8") == before
    assert not list(config_path.parent.glob("*.tmp*")), "temp file left behind"
    assert any(record.levelno >= logging.ERROR for record in caplog.records), (
        "a failed write must reach the logger"
    )
    assert manager.last_save_error, "the failure must be readable by the caller"


def test_save_reports_a_lock_timeout_the_same_way(config_path, monkeypatch, caplog):
    """The lock failure and the write failure must behave alike."""
    manager = _manager()
    manager.set("provider", "openai")

    def _boom(*args, **kwargs):
        raise config_io.ConfigLockError("another writer holds it")

    monkeypatch.setattr(config_io, "config_lock", _boom)

    with caplog.at_level(logging.ERROR):
        assert manager.save() is False

    assert manager.last_save_error
    assert any(record.levelno >= logging.ERROR for record in caplog.records)


def test_a_successful_save_reports_success(config_path):
    manager = _manager()
    manager.set("provider", "openai")

    assert manager.save() is True
    assert manager.last_save_error is None


def test_construction_survives_a_config_directory_it_cannot_write(
    config_path, monkeypatch, caplog
):
    """A readable but unwritable config directory must not stop startup.

    ``__init__`` normalises ``auth_mode`` and migrates legacy API keys, and
    both call ``save()``. A write failure there used to kill the application
    before its first window opened.
    """
    _write(config_path, {"auth_mode": "API Key", "google_api_key": "AIza-LEGACY"})

    def _boom(*args, **kwargs):
        raise config_io.ConfigWriteError("read-only file system")

    monkeypatch.setattr(config_io, "write_config", _boom)

    with caplog.at_level(logging.ERROR):
        manager = _manager()

    assert manager.get("auth_mode") == "api-key"
    assert any(record.levelno >= logging.ERROR for record in caplog.records), (
        "a failed write during startup must reach the logger"
    )


def test_save_keeps_every_key_when_config_json_was_deleted(config_path, tmp_path):
    """A sync client or a backup restore can remove config.json mid-session.

    A missing file is not a writer that deleted every key. This process still
    holds the whole document, so the save must write it back whole.
    """
    _write(config_path, {
        "providers": {"google": {"api_key": "AIza-SECRET"}},
        "data_roots": {"models": str(tmp_path / "models")},
        "auth_mode": "api-key",
    })
    manager = _manager()

    config_path.unlink()

    manager.set("last_prompt", "a cat")
    assert manager.save() is True

    result = _read(config_path)
    assert result["providers"] == {"google": {"api_key": "AIza-SECRET"}}
    assert result["data_roots"] == {"models": str(tmp_path / "models")}
    assert result["auth_mode"] == "api-key"
    assert result["last_prompt"] == "a cat"
    # The live dict must keep them too, or no later save can recover them.
    assert manager.get_api_key("google") == "AIza-SECRET"


def test_save_keeps_every_key_when_config_json_was_corrupted(config_path, tmp_path,
                                                             caplog):
    """The sidecar holds the damaged bytes; the intact copy in memory wins."""
    _write(config_path, {
        "providers": {"openai": {"api_key": "sk-SECRET"}},
        "data_roots": {"images": str(tmp_path / "images")},
        "auth_mode": "api-key",
    })
    manager = _manager()

    corrupt = '{"providers": {"openai": {"api_ke'
    config_path.write_text(corrupt, encoding="utf-8")

    manager.set("last_prompt", "a dog")
    with caplog.at_level(logging.ERROR):
        assert manager.save() is True

    result = _read(config_path)
    assert result["providers"] == {"openai": {"api_key": "sk-SECRET"}}
    assert result["data_roots"] == {"images": str(tmp_path / "images")}
    assert result["last_prompt"] == "a dog"

    sidecars = sorted(config_path.parent.glob("config.json.corrupt-*"))
    assert len(sidecars) == 1
    assert sidecars[0].read_text(encoding="utf-8") == corrupt


def test_corrupt_config_is_not_rewritten_at_startup(config_path, caplog):
    """Constructing ConfigManager is all main.py does before the first window.

    A failed load must not normalise, migrate or save anything, because each
    of those writes an empty document over the file that still holds the API
    keys and the recorded data locations.
    """
    whole = json.dumps({
        "providers": {"google": {"api_key": "AIza-SECRET"}},
        "data_roots": {"models": "/mnt/big/ImageAI/models"},
        "auth_mode": "api-key",
    }, indent=2)
    truncated = whole[: len(whole) // 2]
    config_path.write_text(truncated, encoding="utf-8")

    with caplog.at_level(logging.ERROR):
        manager = _manager()

    assert config_path.read_text(encoding="utf-8") == truncated, (
        "startup must leave a config.json it could not read untouched"
    )

    sidecars = sorted(config_path.parent.glob("config.json.corrupt-*"))
    assert len(sidecars) == 1, "the original must be preserved at startup"
    assert sidecars[0].read_text(encoding="utf-8") == truncated
    assert manager.preserved_config_path == sidecars[0]

    messages = [record.getMessage() for record in caplog.records
                if record.levelno >= logging.ERROR]
    assert any(sidecars[0].name in message for message in messages), (
        "the log must name the preserved copy so the user can recover the keys"
    )


def test_startup_on_a_corrupt_config_does_not_migrate_legacy_keys(config_path):
    """A migration on a fresh empty document would write that document out."""
    config_path.write_text('{"google_api_key": "AIza-LEGACY", ', encoding="utf-8")

    manager = _manager()

    assert manager.load_error, "the failed load must be recorded"
    assert config_path.read_text(encoding="utf-8") == (
        '{"google_api_key": "AIza-LEGACY", '
    )


def test_a_second_save_reuses_the_first_sidecar(config_path):
    """Unchanged damaged bytes must not pile up one sidecar per save."""
    config_path.write_text('{"providers": {"google": ', encoding="utf-8")

    manager = _manager()
    manager.set("last_prompt", "a cat")
    manager.save()

    assert len(sorted(config_path.parent.glob("config.json.corrupt-*"))) == 1


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
    real_read = config_io.read_config_document

    def slow_read(path, *args, **kwargs):
        data = real_read(path, *args, **kwargs)
        if not slowed:
            slowed.append(True)
            inside_save.set()
            # Hold the read-modify-write window open. An unsynchronised save
            # loses the competing write every run.
            time.sleep(0.4)
        return data

    monkeypatch.setattr(config_io, "read_config_document", slow_read)

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


# --- a config.json the user deleted on purpose ------------------------------
#
# A missing file is protected the same way a damaged one is: the whole
# in-memory document goes back to disk, so a sync client or a backup restore
# cannot cost the user the API keys. The user who deletes config.json to reset
# the application or to purge the stored keys gets that same write-back, and
# nothing on disk tells the two apart. The log line must therefore say plainly
# what happened, so the user can act on it.


def _messages(caplog, level=logging.WARNING) -> str:
    return " ".join(
        record.getMessage() for record in caplog.records if record.levelno >= level
    )


def test_a_deleted_config_is_reported_when_the_save_rewrites_it(config_path, caplog):
    """The rewrite is data-loss protection, and it must not be silent."""
    _write(config_path, {
        "providers": {"google": {"api_key": "AIza-SECRET"}},
        "auth_mode": "api-key",
    })
    manager = _manager()

    config_path.unlink()  # the user resets the app, or a sync client removes it

    manager.set("last_prompt", "a cat")
    with caplog.at_level(logging.WARNING):
        assert manager.save() is True

    reported = _messages(caplog)
    assert str(config_path) in reported
    assert "missing" in reported.lower(), "the message must name the condition"
    assert "api key" in reported.lower(), "the user must learn the keys came back"
    assert "close" in reported.lower(), "the message must say how to reset the app"
    # The protection itself still holds.
    assert _read(config_path)["providers"] == {"google": {"api_key": "AIza-SECRET"}}


def test_an_intact_config_reports_nothing_about_a_missing_file(config_path, caplog):
    """The warning must mean something, so an ordinary save must not raise it."""
    manager = _manager()
    manager.set("provider", "openai")

    with caplog.at_level(logging.WARNING):
        assert manager.save() is True

    assert "missing" not in _messages(caplog).lower()


def test_a_corrupt_config_is_not_reported_as_a_missing_one(config_path, caplog):
    """A damaged file has its own message and its own sidecar."""
    manager = _manager()
    config_path.write_text('{"providers": {"openai": ', encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        assert manager.save() is True

    reported = _messages(caplog)
    assert "could not be read" in reported.lower()
    assert "missing at save time" not in reported.lower()


# --- the attributes the GUI reads -------------------------------------------
#
# load_error, preserved_config_path and last_save_error are the only report of
# a quarantined config.json or a save that never reached disk. The GUI surfaces
# them, so they must hold whatever really happened.


def test_a_corrupt_load_sets_the_load_error_and_the_preserved_path(config_path):
    config_path.write_text('{"providers": ', encoding="utf-8")

    manager = _manager()

    assert manager.load_error, "a load failure must be readable by the caller"
    assert manager.preserved_config_path is not None
    assert manager.preserved_config_path.exists()
    assert manager.last_save_error is None


def test_load_error_stays_set_after_a_later_successful_save(config_path):
    """load_error is the startup fact. A later save does not undo it."""
    config_path.write_text("{not json", encoding="utf-8")
    manager = _manager()
    first = manager.load_error

    assert manager.save() is True
    assert manager.load_error == first
    assert manager.last_save_error is None


def test_last_save_error_is_cleared_by_the_next_successful_save(
    config_path, monkeypatch
):
    manager = _manager()

    def _boom(*args, **kwargs):
        raise config_io.ConfigWriteError("read-only file system")

    monkeypatch.setattr(config_io, "write_config", _boom)
    assert manager.save() is False
    assert manager.last_save_error

    monkeypatch.undo()
    assert manager.save() is True
    assert manager.last_save_error is None


def test_save_reports_an_unexpected_failure_instead_of_raising(
    config_path, monkeypatch, caplog
):
    """save() runs from about forty Qt slots. Nothing may escape it."""
    manager = _manager()

    def _boom(*args, **kwargs):
        raise RuntimeError("something nobody predicted")

    monkeypatch.setattr(type(manager), "_merge_over_disk", staticmethod(_boom))

    with caplog.at_level(logging.ERROR):
        assert manager.save() is False

    assert manager.last_save_error
    assert any(record.levelno >= logging.ERROR for record in caplog.records)


@pytest.mark.skipif(hasattr(__import__("os"), "geteuid")
                    and __import__("os").geteuid() == 0,
                    reason="root ignores the directory mode")
def test_a_read_only_config_directory_reports_every_lost_save(config_path, caplog):
    """The session cannot keep a setting, and the caller must be able to say so.

    ``save()`` returns False and sets ``last_save_error`` for every attempt,
    because the GUI has nothing else to show the user.
    """
    import os
    import stat

    manager = _manager()
    directory = config_path.parent
    before = stat.S_IMODE(directory.stat().st_mode)
    os.chmod(directory, 0o555)
    try:
        manager.set("provider", "openai")
        with caplog.at_level(logging.ERROR):
            assert manager.save() is False
        assert manager.last_save_error
        assert any(record.levelno >= logging.ERROR for record in caplog.records)

        # A second attempt reports the same way; nothing is remembered as done.
        manager.set("provider", "stability")
        assert manager.save() is False
        assert manager.last_save_error
    finally:
        os.chmod(directory, before)


def test_a_fresh_install_is_not_reported_as_a_deleted_config(tmp_path, monkeypatch,
                                                             caplog):
    """The first run writes config.json for the first time. Nothing is lost.

    ``__init__`` normalises auth_mode and saves, and at that point the file
    does not exist yet. That is not a file anyone removed.
    """
    cfg = tmp_path / "fresh" / "config.json"
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    with caplog.at_level(logging.WARNING):
        manager = _manager()
        manager.set("provider", "google")
        assert manager.save() is True

    assert "missing" not in _messages(caplog).lower()
    assert cfg.exists()


def test_a_config_deleted_after_the_first_write_is_still_reported(tmp_path,
                                                                  monkeypatch,
                                                                  caplog):
    """Once this session wrote the file, a later disappearance is an event."""
    cfg = tmp_path / "fresh" / "config.json"
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    manager = _manager()
    manager.set("provider", "google")
    assert manager.save() is True

    cfg.unlink()
    with caplog.at_level(logging.WARNING):
        manager.set("provider", "openai")
        assert manager.save() is True

    assert "missing at save time" in _messages(caplog).lower()


def test_one_damaged_file_makes_one_sidecar_across_managers(config_path):
    """ConfigManager is constructed in about a dozen places.

    Each GUI worker run, each provider call and each CLI command builds one, so
    a per-instance record of what was already copied aside minted a fresh
    timestamped sidecar per construction and buried the first copy under
    identical ones.
    """
    # The record is keyed by config path, and this fixture gives every test its
    # own throw-away one, so no reset is needed to isolate this test.
    config_path.write_text("{not json", encoding="utf-8")

    first = _manager()
    second = _manager()
    third = _manager()

    sidecars = sorted(config_path.parent.glob("config.json.corrupt-*"))
    assert len(sidecars) == 1, f"one damaged file, one copy; got {sidecars}"
    # Every manager still reports where the copy is, so the GUI can name it.
    assert first.preserved_config_path == sidecars[0]
    assert second.preserved_config_path == sidecars[0]
    assert third.preserved_config_path == sidecars[0]
    assert sidecars[0].read_text(encoding="utf-8") == "{not json"
