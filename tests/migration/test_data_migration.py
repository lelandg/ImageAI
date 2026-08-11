"""Unit tests for group relocation."""
import json
import logging
import os
from pathlib import Path

import pytest

from core.data_migration import (
    LEGACY_IMAGEAI_NAME,
    ConfigError,
    _cleanup_empty_legacy_dirs,
    duplicate_destination_names,
    sources_for,
    tree_size,
    validate_destination,
)
from core.paths import DataPaths, Group


@pytest.fixture(autouse=True)
def isolated_legacy_dirs(tmp_path, monkeypatch):
    """Keep every test away from the developer's real home directory.

    ~/.imageai exists on a developer machine, and a test that does not point it
    somewhere else would list the developer's own data as a move source. The
    fake home closes the same hole for every other ``Path.home()`` caller this
    module reaches. A test that needs a legacy tree sets its own value; the
    later setattr wins.
    """
    absent = tmp_path / "no_legacy_dir"
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setattr("core.data_migration.legacy_dot_imageai_dir", lambda: absent)


@pytest.fixture
def paths(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    return DataPaths(config_path=cfg)


def _populate(root, names, size=1024):
    for name in names:
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "f.bin").write_bytes(b"x" * size)


def test_tree_size_counts_files_and_bytes(tmp_path):
    _populate(tmp_path, ["a", "b"], size=100)
    assert tree_size(tmp_path) == (2, 200)


def test_tree_size_of_missing_dir_is_zero(tmp_path):
    assert tree_size(tmp_path / "nope") == (0, 0)


def test_sources_for_images_lists_only_existing_dirs(tmp_path, paths):
    _populate(tmp_path, ["generated", "styles"])
    names = [name for _src, name in sources_for(Group.IMAGES, paths)]
    assert sorted(names) == ["generated", "styles"]


def test_sources_for_models_takes_the_imageai_owned_huggingface_dir(tmp_path, paths):
    """ImageAI downloads into <models root>/huggingface, so that one moves."""
    _populate(tmp_path, ["musetalk", "huggingface"])

    entries = dict((name, src) for src, name in sources_for(Group.MODELS, paths))

    assert entries["musetalk"] == tmp_path / "musetalk"
    assert entries["huggingface"] == tmp_path / "huggingface"


def test_sources_for_video_includes_the_dot_imageai_tree(tmp_path, paths, monkeypatch):
    _populate(tmp_path, ["video_projects"])
    legacy = tmp_path / "dot"
    _populate(legacy, ["cache"])
    monkeypatch.setattr("core.data_migration.legacy_dot_imageai_dir", lambda: legacy)

    names = [name for _src, name in sources_for(Group.VIDEO, paths)]
    assert "video_projects" in names
    assert f"{LEGACY_IMAGEAI_NAME}/cache" in names


def test_validate_rejects_a_destination_equal_to_the_source(tmp_path, paths):
    _populate(tmp_path, ["generated"])
    error = validate_destination(Group.IMAGES, tmp_path, paths)
    assert error and "same" in error.lower()


def test_validate_rejects_a_destination_inside_the_source(tmp_path, paths):
    _populate(tmp_path, ["generated"])
    inside = tmp_path / "generated" / "sub"
    error = validate_destination(Group.IMAGES, inside, paths)
    assert error and "inside" in error.lower()


def test_validate_rejects_an_unwritable_parent(tmp_path, paths):
    _populate(tmp_path, ["generated"])
    error = validate_destination(Group.IMAGES, tmp_path / "no" / "such" / "parent", paths)
    assert error and ("does not exist" in error.lower() or "writable" in error.lower())


def test_validate_rejects_insufficient_free_space(tmp_path, paths, monkeypatch):
    import collections

    _populate(tmp_path, ["generated"], size=4096)
    dest = tmp_path / "dest"
    dest.mkdir()

    Usage = collections.namedtuple("Usage", "total used free")
    monkeypatch.setattr("core.data_migration.shutil.disk_usage",
                        lambda _p: Usage(total=100, used=99, free=1))

    error = validate_destination(Group.IMAGES, dest, paths)
    assert error and "space" in error.lower()


def test_validate_accepts_a_good_destination(tmp_path, paths):
    _populate(tmp_path, ["generated"])
    dest = tmp_path / "dest"
    dest.mkdir()
    assert validate_destination(Group.IMAGES, dest, paths) is None


import sqlite3
import threading

from core.data_migration import MoveResult, move_group


def _read_roots(paths):
    return json.loads(paths.config_file().read_text(encoding="utf-8")).get("data_roots", {})


def test_move_relocates_files_and_updates_config(tmp_path, paths):
    _populate(tmp_path, ["generated", "styles"], size=64)
    dest = tmp_path / "dest"

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert result.ok, result.error
    assert (dest / "generated" / "f.bin").read_bytes() == b"x" * 64
    assert (dest / "styles" / "f.bin").exists()
    assert not (tmp_path / "generated").exists()
    assert _read_roots(paths)["images"] == str(dest)


def test_move_reports_counts(tmp_path, paths):
    _populate(tmp_path, ["generated", "styles"], size=64)
    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)
    assert result.files_moved == 2
    assert result.bytes_moved == 128


def test_move_uses_rename_on_the_same_volume(tmp_path, paths):
    _populate(tmp_path, ["generated"], size=64)
    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)
    assert result.ok
    assert result.used_rename is True


def test_move_reports_progress(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated", "styles"], size=64)

    seen = []
    move_group(Group.IMAGES, tmp_path / "dest", paths=paths,
               progress_cb=lambda *a: seen.append(a))

    assert seen
    assert seen[-1][0] == seen[-1][1]  # files_done reached files_total


def test_cancel_aborts_and_leaves_the_source_intact(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated", "styles", "images"], size=64)
    dest = tmp_path / "dest"

    flag = threading.Event()

    def cb(files_done, *_rest):
        if files_done >= 1:
            flag.set()

    result = move_group(Group.IMAGES, dest, paths=paths, progress_cb=cb, cancel=flag)

    assert not result.ok
    assert "cancel" in result.error.lower()
    assert (tmp_path / "generated" / "f.bin").exists()
    assert not (dest / "generated").exists()
    assert not (dest / "images").exists()
    assert "images" not in _read_roots(paths)


def test_verify_mismatch_aborts_and_keeps_the_source(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated"], size=64)
    monkeypatch.setattr("core.data_migration.tree_size",
                        lambda p: (99, 99) if "dest" in str(p) else (1, 64))

    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)

    assert not result.ok
    assert "verif" in result.error.lower()
    assert (tmp_path / "generated" / "f.bin").exists()


def test_move_refuses_an_invalid_destination(tmp_path, paths):
    _populate(tmp_path, ["generated"])
    result = move_group(Group.IMAGES, tmp_path, paths=paths)
    assert not result.ok
    assert "same" in result.error.lower()


def test_move_copies_sqlite_sidecars(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    monkeypatch.setattr("core.data_migration.legacy_dot_imageai_dir",
                        lambda: tmp_path / "absent")

    projects = tmp_path / "video_projects"
    projects.mkdir()
    db = projects / "events.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (a INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()

    dest = tmp_path / "dest"
    result = move_group(Group.VIDEO, dest, paths=paths)

    assert result.ok, result.error
    moved = sqlite3.connect(dest / "video_projects" / "events.db")
    assert moved.execute("SELECT a FROM t").fetchone() == (1,)
    moved.close()


def test_pre_move_hook_runs_before_any_copy(tmp_path, paths):
    _populate(tmp_path, ["generated"], size=64)
    calls = []
    move_group(Group.IMAGES, tmp_path / "dest", paths=paths,
               pre_move=lambda: calls.append("closed"))
    assert calls == ["closed"]


# -- Bug 1: cleanup must not destroy unrelated data in the destination -------

def test_validate_rejects_a_destination_holding_a_colliding_entry(tmp_path, paths):
    _populate(tmp_path, ["generated"])
    dest = tmp_path / "dest"
    (dest / "generated").mkdir(parents=True)

    error = validate_destination(Group.IMAGES, dest, paths)

    assert error and "generated" in error


def test_cancel_keeps_unrelated_files_in_the_destination(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated", "images", "composites"], size=64)
    dest = tmp_path / "dest"
    dest.mkdir()
    keep = dest / "tax_return.pdf"
    keep.write_bytes(b"important")
    (dest / "holiday").mkdir()
    (dest / "holiday" / "photo.jpg").write_bytes(b"pic")

    flag = threading.Event()

    def cb(files_done, *_rest):
        if files_done >= 1:
            flag.set()

    result = move_group(Group.IMAGES, dest, paths=paths, progress_cb=cb, cancel=flag)

    assert not result.ok
    assert keep.read_bytes() == b"important"
    assert (dest / "holiday" / "photo.jpg").read_bytes() == b"pic"
    assert not (dest / "generated").exists()
    assert (tmp_path / "generated" / "f.bin").exists()


def test_copy_failure_keeps_unrelated_files_in_the_destination(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated"], size=64)
    dest = tmp_path / "dest"
    dest.mkdir()
    keep = dest / "notes.txt"
    keep.write_text("keep me", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise OSError("disk on fire")

    monkeypatch.setattr("core.data_migration._copy_entry", boom)

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert not result.ok
    assert keep.read_text(encoding="utf-8") == "keep me"
    assert (tmp_path / "generated" / "f.bin").exists()


# -- Bug 2: a partial rename must be rolled back -----------------------------

def test_partial_rename_is_rolled_back_before_the_copy_fallback(tmp_path, paths, monkeypatch):
    _populate(tmp_path, ["generated", "images"], size=64)
    dest = tmp_path / "dest"

    real_rename = os.rename
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError(18, "Invalid cross-device link")
        return real_rename(src, dst)

    monkeypatch.setattr("core.data_migration.os.rename", flaky)

    def boom(*_args, **_kwargs):
        raise OSError("disk on fire")

    monkeypatch.setattr("core.data_migration._copy_entry", boom)

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert not result.ok
    assert (tmp_path / "generated" / "f.bin").read_bytes() == b"x" * 64
    assert (tmp_path / "images" / "f.bin").read_bytes() == b"x" * 64


def test_rename_rollback_failure_names_the_directory_holding_the_data(tmp_path, paths, monkeypatch):
    _populate(tmp_path, ["generated", "images"], size=64)
    dest = tmp_path / "dest"

    real_rename = os.rename
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_rename(src, dst)
        raise OSError("device busy")

    monkeypatch.setattr("core.data_migration.os.rename", flaky)

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert not result.ok
    assert str(dest / "generated") in result.error
    assert (dest / "generated" / "f.bin").exists()


# -- Bug 3: config.json must survive a failed write --------------------------

def test_move_aborts_when_config_json_cannot_be_parsed(tmp_path, paths):
    _populate(tmp_path, ["generated"], size=64)
    paths.config_file().write_text("{not json", encoding="utf-8")

    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)

    assert not result.ok
    assert (tmp_path / "generated" / "f.bin").exists()
    assert paths.config_file().read_text(encoding="utf-8") == "{not json"


def test_config_write_failure_does_not_truncate_config_json(tmp_path, paths, monkeypatch):
    original = json.dumps({"api_key": "secret", "provider": "google"}, indent=2)
    paths.config_file().write_text(original, encoding="utf-8")
    _populate(tmp_path, ["generated"], size=64)
    dest = tmp_path / "dest"

    def boom(_src, _dst):
        raise OSError("no space left on device")

    # The migrator writes through core.config_io, so the failure has to be
    # injected where that module replaces the file.
    monkeypatch.setattr("core.config_io.os.replace", boom)

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert not result.ok
    assert paths.config_file().read_text(encoding="utf-8") == original
    assert (tmp_path / "generated" / "f.bin").exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_a_missing_config_file_is_treated_as_a_fresh_install(tmp_path, paths):
    _populate(tmp_path, ["generated"], size=64)
    paths.config_file().unlink()
    dest = tmp_path / "dest"

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert result.ok, result.error
    assert _read_roots(paths)["images"] == str(dest)


def test_the_move_preserves_unrelated_config_keys(tmp_path, paths):
    paths.config_file().write_text(
        json.dumps({"api_key": "secret", "data_roots": {"video": "/elsewhere"}}),
        encoding="utf-8",
    )
    _populate(tmp_path, ["generated"], size=64)
    dest = tmp_path / "dest"

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert result.ok, result.error
    data = json.loads(paths.config_file().read_text(encoding="utf-8"))
    assert data["api_key"] == "secret"
    assert data["data_roots"] == {"video": "/elsewhere", "images": str(dest)}


# -- Bug 4: verification must not race live files ----------------------------

def test_source_growth_during_the_copy_does_not_fail_verification(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated", "images"], size=64)
    dest = tmp_path / "dest"
    extra = b"a live log record\n"
    grown = {"done": False}

    def cb(*_args):
        if not grown["done"]:
            with open(tmp_path / "images" / "f.bin", "ab") as handle:
                handle.write(extra)
            grown["done"] = True

    result = move_group(Group.IMAGES, dest, paths=paths, progress_cb=cb)

    assert result.ok, result.error
    assert grown["done"]
    assert (dest / "images" / "f.bin").stat().st_size == 64 + len(extra)


def test_verification_fails_when_a_copied_file_disappears(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated", "images"], size=64)
    dest = tmp_path / "dest"

    def cb(files_done, *_rest):
        if files_done == 2:
            (dest / "generated" / "f.bin").unlink()

    result = move_group(Group.IMAGES, dest, paths=paths, progress_cb=cb)

    assert not result.ok
    assert "verif" in result.error.lower()
    assert (tmp_path / "generated" / "f.bin").exists()
    assert (tmp_path / "images" / "f.bin").exists()


# -- Bug 5: the legacy cleanup failure must reach the file logger ------------

def test_legacy_cleanup_failure_is_logged_at_warning(tmp_path, monkeypatch, caplog):
    legacy = tmp_path / "dot_imageai"
    legacy.mkdir()
    monkeypatch.setattr("core.data_migration.legacy_dot_imageai_dir", lambda: legacy)

    def boom(_path):
        raise OSError("directory not empty")

    monkeypatch.setattr("core.data_migration.os.rmdir", boom)

    with caplog.at_level(logging.DEBUG, logger="core.data_migration"):
        _cleanup_empty_legacy_dirs(Group.VIDEO)

    records = [r for r in caplog.records if "dot_imageai" in r.getMessage()]
    assert records, "the failure was not logged at all"
    assert records[0].levelno >= logging.WARNING


# -- Bug 6: a failed rollback must not abandon the earlier sources -----------

def _flaky_rename(monkeypatch, failing_calls):
    """Make the Nth call to os.rename fail, for each N in ``failing_calls``."""
    real_rename = os.rename
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] in failing_calls:
            raise OSError(13, "Permission denied", str(src))
        return real_rename(src, dst)

    monkeypatch.setattr("core.data_migration.os.rename", flaky)
    return calls


def test_a_failed_rollback_still_restores_every_other_source(
    tmp_path, paths, monkeypatch, caplog
):
    _populate(tmp_path, ["generated", "images", "composites"], size=64)
    dest = tmp_path / "dest"

    # 1: generated moves. 2: images moves. 3: composites fails, so the move
    # rolls back. 4: the rollback of images fails. 5: generated must still be
    # rolled back, and it is the call that proves the loop did not stop.
    _flaky_rename(monkeypatch, {3, 4})

    with caplog.at_level(logging.ERROR, logger="core.data_migration"):
        result = move_group(Group.IMAGES, dest, paths=paths)

    assert not result.ok
    assert (tmp_path / "generated" / "f.bin").exists()
    assert not (dest / "generated").exists()
    assert (tmp_path / "composites" / "f.bin").exists()
    # The one directory that could not be rolled back is named, with the place
    # it sits now and the place it belongs.
    assert str(dest / "images") in result.error
    assert str(tmp_path / "images") in result.error
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert str(dest / "images") in logged
    assert str(tmp_path / "images") in logged


def test_a_failed_rollback_reports_every_stranded_directory(tmp_path, paths, monkeypatch):
    _populate(tmp_path, ["generated", "images", "composites"], size=64)
    dest = tmp_path / "dest"

    # 3 fails, and both rollbacks (4 and 5) fail too.
    _flaky_rename(monkeypatch, {3, 4, 5})

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert not result.ok
    for name in ("generated", "images"):
        assert str(dest / name) in result.error
        assert str(tmp_path / name) in result.error
    assert sorted(result.stranded) == sorted(
        [(str(dest / "generated"), str(tmp_path / "generated")),
         (str(dest / "images"), str(tmp_path / "images"))]
    )


def test_a_config_failure_after_the_renames_reports_every_stranded_source(
    tmp_path, paths, monkeypatch
):
    _populate(tmp_path, ["generated", "images"], size=64)
    dest = tmp_path / "dest"

    def boom(*_args, **_kwargs):
        raise ConfigError("no space left on device")

    monkeypatch.setattr("core.data_migration._write_root", boom)
    # Both renames succeed; both rollbacks fail.
    _flaky_rename(monkeypatch, {3, 4})

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert not result.ok
    for name in ("generated", "images"):
        assert str(dest / name) in result.error
        assert str(tmp_path / name) in result.error


# -- Bug 7: the cleanup must delete only what this move created --------------

@pytest.mark.skipif(os.name == "nt", reason="symlinks need a privileged account")
def test_validate_rejects_a_destination_holding_a_broken_symlink(tmp_path, paths):
    _populate(tmp_path, ["generated"])
    dest = tmp_path / "dest"
    dest.mkdir()
    # The user's own redirect to a drive that is currently unplugged.
    os.symlink(str(tmp_path / "offline_drive" / "generated"), str(dest / "generated"))

    error = validate_destination(Group.IMAGES, dest, paths)

    assert error and "generated" in error


@pytest.mark.skipif(os.name == "nt", reason="symlinks need a privileged account")
def test_a_cancelled_move_keeps_a_users_symlink_in_the_destination(
    tmp_path, paths, monkeypatch
):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated", "images"], size=64)
    dest = tmp_path / "dest"
    dest.mkdir()
    os.symlink(str(tmp_path / "offline_drive" / "images"), str(dest / "images"))

    calls = {"n": 0}

    def cancel():
        calls["n"] += 1
        return calls["n"] > 1

    result = move_group(Group.IMAGES, dest, paths=paths, cancel=cancel)

    assert not result.ok
    assert (dest / "images").is_symlink()
    assert (tmp_path / "images" / "f.bin").exists()


def test_cancel_keeps_an_entry_that_appeared_during_the_copy(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated", "images", "composites"], size=64)
    dest = tmp_path / "dest"
    dest.mkdir()

    flag = threading.Event()

    def cb(_files_done, *_rest):
        # A second application window writes into the destination while the
        # long copy runs.
        intruder = dest / "composites"
        if not intruder.exists():
            intruder.mkdir()
            (intruder / "other.bin").write_bytes(b"not ours")
        flag.set()

    result = move_group(Group.IMAGES, dest, paths=paths, progress_cb=cb, cancel=flag)

    assert not result.ok
    assert (dest / "composites" / "other.bin").read_bytes() == b"not ours"
    assert (tmp_path / "generated" / "f.bin").exists()


def test_an_entry_that_appears_during_the_copy_aborts_the_move(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated", "images", "composites"], size=64)
    dest = tmp_path / "dest"
    dest.mkdir()

    def cb(_files_done, *_rest):
        intruder = dest / "composites"
        if not intruder.exists():
            intruder.mkdir()
            (intruder / "other.bin").write_bytes(b"not ours")

    result = move_group(Group.IMAGES, dest, paths=paths, progress_cb=cb)

    assert not result.ok
    assert "composites" in result.error
    assert (dest / "composites" / "other.bin").read_bytes() == b"not ours"
    assert (tmp_path / "generated" / "f.bin").exists()
    assert (tmp_path / "images" / "f.bin").exists()
    assert "images" not in _read_roots(paths)


# -- Bug 8: two sources must never claim one destination name ----------------

def test_video_sources_never_share_a_destination_name(tmp_path, paths, monkeypatch):
    _populate(tmp_path, ["video_projects"], size=64)
    legacy = tmp_path / "dot"
    _populate(legacy, ["video_projects"], size=32)
    monkeypatch.setattr("core.data_migration.legacy_dot_imageai_dir", lambda: legacy)

    entries = sources_for(Group.VIDEO, paths)
    names = [name for _src, name in entries]

    assert len(names) == len(set(names))
    assert duplicate_destination_names(entries) == []


def test_a_legacy_video_tree_does_not_merge_into_the_app_tree(tmp_path, paths, monkeypatch):
    app = tmp_path / "video_projects"
    app.mkdir()
    (app / "current.bin").write_bytes(b"a" * 10)
    legacy = tmp_path / "dot"
    (legacy / "video_projects").mkdir(parents=True)
    (legacy / "video_projects" / "old.bin").write_bytes(b"b" * 20)
    monkeypatch.setattr("core.data_migration.legacy_dot_imageai_dir", lambda: legacy)
    dest = tmp_path / "dest"

    result = move_group(Group.VIDEO, dest, paths=paths)

    assert result.ok, result.error
    assert (dest / "video_projects" / "current.bin").read_bytes() == b"a" * 10
    assert not (dest / "video_projects" / "old.bin").exists()
    kept = dest / LEGACY_IMAGEAI_NAME / "video_projects" / "old.bin"
    assert kept.read_bytes() == b"b" * 20


def test_two_sources_with_one_name_abort_the_move(tmp_path, paths, monkeypatch):
    _populate(tmp_path, ["generated"], size=64)
    other = tmp_path / "other" / "generated"
    other.mkdir(parents=True)
    (other / "f.bin").write_bytes(b"z" * 64)

    monkeypatch.setattr(
        "core.data_migration.sources_for",
        lambda _group, _paths=None: [
            (tmp_path / "generated", "generated"),
            (other, "generated"),
        ],
    )

    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)

    assert not result.ok
    assert "generated" in result.error
    assert (tmp_path / "generated" / "f.bin").exists()
    assert (other / "f.bin").exists()


def test_a_name_nested_inside_another_name_is_a_duplicate(tmp_path):
    entries = [(tmp_path / "cache", "cache"), (tmp_path / "cache" / "video", "cache/video")]
    assert duplicate_destination_names(entries)


# -- Bug 9: a shared cache directory must split by owner ---------------------

def test_moving_models_leaves_the_video_cache_behind(tmp_path, paths):
    _populate(tmp_path / "cache", ["ai_visemes", "video", "thumbnails"], size=32)
    _populate(tmp_path, ["musetalk"], size=32)
    dest = tmp_path / "dest"

    result = move_group(Group.MODELS, dest, paths=paths)

    assert result.ok, result.error
    assert (dest / "cache" / "ai_visemes" / "f.bin").exists()
    assert not (dest / "cache" / "video").exists()
    assert (tmp_path / "cache" / "video" / "f.bin").exists()
    assert (tmp_path / "cache" / "thumbnails" / "f.bin").exists()


def test_moving_video_takes_only_the_video_cache(tmp_path, paths):
    _populate(tmp_path / "cache", ["ai_visemes", "video", "veo_videos"], size=32)
    _populate(tmp_path, ["video_projects"], size=32)
    dest = tmp_path / "dest"

    result = move_group(Group.VIDEO, dest, paths=paths)

    assert result.ok, result.error
    assert (dest / "cache" / "video" / "f.bin").exists()
    assert (dest / "cache" / "veo_videos" / "f.bin").exists()
    assert not (dest / "cache" / "ai_visemes").exists()
    assert (tmp_path / "cache" / "ai_visemes" / "f.bin").exists()


def test_models_takes_only_its_own_cache_when_the_video_root_differs(tmp_path):
    """A different Video root must not turn the whole cache into Models data.

    The old rule handed the whole ``cache`` directory to the group whose root
    it sat under as soon as the two roots differed. A subdirectory that no
    group claims then travelled with the second move, silently, after the first
    move had already reported it as left behind.
    """
    video_root = tmp_path / "video_root"
    video_root.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {"video": str(video_root)}}), encoding="utf-8")
    own_paths = DataPaths(config_path=cfg)
    _populate(tmp_path / "cache", ["ai_visemes", "leftover"], size=32)
    dest = tmp_path / "dest"

    result = move_group(Group.MODELS, dest, paths=own_paths)

    assert result.ok, result.error
    assert (dest / "cache" / "ai_visemes" / "f.bin").exists()
    assert not (dest / "cache" / "leftover").exists()
    assert (tmp_path / "cache" / "leftover" / "f.bin").exists()


def test_an_unclaimed_cache_subdirectory_is_logged(tmp_path, paths, caplog):
    _populate(tmp_path / "cache", ["ai_visemes", "mystery"], size=32)
    _populate(tmp_path, ["musetalk"], size=32)

    with caplog.at_level(logging.WARNING, logger="core.data_migration"):
        result = move_group(Group.MODELS, tmp_path / "dest", paths=paths)

    assert result.ok, result.error
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "mystery" in logged


# -- Bug 10: config.json goes through the shared locked writer ---------------

def test_the_migrator_writes_config_through_the_shared_writer(tmp_path, paths, monkeypatch):
    import core.config_io as config_io

    _populate(tmp_path, ["generated"], size=64)
    seen = {}
    real_update = config_io.update_config

    def spy(path, mutate, *args, **kwargs):
        seen["path"] = Path(path)
        return real_update(path, mutate, *args, **kwargs)

    monkeypatch.setattr("core.config_io.update_config", spy)

    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)

    assert result.ok, result.error
    assert seen["path"] == paths.config_file()


def test_a_config_lock_timeout_aborts_the_move_and_keeps_the_source(
    tmp_path, paths, monkeypatch
):
    import core.config_io as config_io

    assert issubclass(config_io.ConfigLockError, ConfigError)
    _populate(tmp_path, ["generated"], size=64)

    def boom(*_args, **_kwargs):
        raise config_io.ConfigLockError("another writer still holds the lock")

    monkeypatch.setattr("core.config_io.update_config", boom)

    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)

    assert not result.ok
    assert (tmp_path / "generated" / "f.bin").exists()
    assert "images" not in _read_roots(paths)


# -- Bug 11: the machine-wide HuggingFace cache is not ImageAI's to move ------

def test_the_shared_huggingface_cache_is_never_a_move_source(tmp_path, paths):
    """~/.cache/huggingface belongs to every transformers tool on the machine.

    Nothing sets HF_HOME or HUGGINGFACE_HUB_CACHE, so a move of that directory
    makes every other tool re-download its models. ImageAI passes an explicit
    cache_dir= at each of its own download sites, so its own weights already
    live under the Models root and still travel with the group.
    """
    shared = Path.home() / ".cache" / "huggingface"
    _populate(shared, ["models--stabilityai--stable-diffusion-2-1"], size=64)
    _populate(tmp_path, ["musetalk"], size=64)

    entries = sources_for(Group.MODELS, paths)

    assert [name for _src, name in entries] == ["musetalk"]
    assert all(shared not in src.parents and src != shared for src, _n in entries)


def test_the_migrator_exposes_no_shared_huggingface_helper():
    """A helper that names the shared cache invites the annexation back."""
    import core.data_migration as migration

    assert not hasattr(migration, "legacy_huggingface_dir")


def test_a_models_move_leaves_the_shared_huggingface_cache_alone(tmp_path, paths):
    shared = Path.home() / ".cache" / "huggingface"
    _populate(shared, ["hub"], size=64)
    _populate(tmp_path, ["musetalk"], size=64)

    result = move_group(Group.MODELS, tmp_path / "dest", paths=paths)

    assert result.ok, result.error
    assert (shared / "hub" / "f.bin").exists()


# -- Bug 12: an interrupted rename move must leave a journal ------------------

from core.data_migration import (  # noqa: E402 - grouped with the tests it serves
    MOVE_INTENT_SUFFIX,
    _write_root,
    recover_interrupted_move,
)


def _intent_file(paths):
    config = paths.config_file()
    return config.with_name(config.name + MOVE_INTENT_SUFFIX)


def _crash_after_the_renames(monkeypatch):
    """Stop the process the way a power loss does: after the last rename.

    ``move_group`` catches ConfigError around the config write, so the crash
    has to be something it does not catch. The on-disk state that results is
    the state the repro produced with os._exit: every directory at the
    destination, config.json untouched.
    """
    class _PowerLoss(BaseException):
        pass

    def boom(*_args, **_kwargs):
        raise _PowerLoss()

    monkeypatch.setattr("core.data_migration._write_root", boom)
    return _PowerLoss


def test_a_completed_rename_move_leaves_no_intent_file(tmp_path, paths):
    _populate(tmp_path, ["generated", "images"], size=64)

    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)

    assert result.ok, result.error
    assert not _intent_file(paths).exists()


def test_the_intent_file_exists_while_the_renames_are_committed(tmp_path, paths, monkeypatch):
    _populate(tmp_path, ["generated"], size=64)
    seen = {}
    real = _write_root

    def spy(paths_arg, group, dest):
        seen["present"] = _intent_file(paths_arg).exists()
        seen["record"] = json.loads(_intent_file(paths_arg).read_text(encoding="utf-8"))
        return real(paths_arg, group, dest)

    monkeypatch.setattr("core.data_migration._write_root", spy)

    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)

    assert result.ok, result.error
    assert seen["present"], "no journal covered the window before the config write"
    assert seen["record"]["group"] == "images"
    assert seen["record"]["dest"] == str(tmp_path / "dest")
    assert [str(tmp_path / "generated"), str(tmp_path / "dest" / "generated")] \
        in [list(pair) for pair in seen["record"]["entries"]]


def test_an_interrupted_rename_move_is_detectable_on_the_next_start(
    tmp_path, paths, monkeypatch
):
    _populate(tmp_path, ["generated", "images"], size=64)
    dest = tmp_path / "dest"
    power_loss = _crash_after_the_renames(monkeypatch)

    with pytest.raises(power_loss):
        move_group(Group.IMAGES, dest, paths=paths)

    # The state the repro produced: data at the destination, config untouched.
    assert (dest / "generated" / "f.bin").exists()
    assert not (tmp_path / "generated").exists()
    assert "images" not in _read_roots(paths)
    # ...and a record of it that the next start can find.
    assert _intent_file(paths).exists()


def test_recovery_finishes_a_move_whose_data_already_reached_the_destination(
    tmp_path, paths, monkeypatch, caplog
):
    _populate(tmp_path, ["generated", "images"], size=64)
    dest = tmp_path / "dest"
    power_loss = _crash_after_the_renames(monkeypatch)
    with pytest.raises(power_loss):
        move_group(Group.IMAGES, dest, paths=paths)
    monkeypatch.undo()

    fresh = DataPaths(config_path=paths.config_file())
    with caplog.at_level(logging.INFO, logger="core.data_migration"):
        summary = recover_interrupted_move(fresh)

    assert summary
    assert _read_roots(fresh)["images"] == str(dest)
    assert not _intent_file(fresh).exists()
    assert (dest / "generated" / "f.bin").exists()
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert str(dest) in logged


def test_recovery_rolls_a_half_finished_move_back(tmp_path, paths, caplog):
    _populate(tmp_path, ["generated", "images"], size=64)
    dest = tmp_path / "dest"
    dest.mkdir()
    # One entry made it across before the power went out; the other did not.
    os.rename(str(tmp_path / "generated"), str(dest / "generated"))
    _intent_file(paths).write_text(json.dumps({
        "version": 1,
        "group": "images",
        "dest": str(dest),
        "entries": [
            [str(tmp_path / "generated"), str(dest / "generated")],
            [str(tmp_path / "images"), str(dest / "images")],
        ],
    }), encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="core.data_migration"):
        summary = recover_interrupted_move(paths)

    assert summary
    assert (tmp_path / "generated" / "f.bin").exists()
    assert (tmp_path / "images" / "f.bin").exists()
    assert not (dest / "generated").exists()
    assert "images" not in _read_roots(paths)
    assert not _intent_file(paths).exists()


def test_recovery_is_a_no_op_without_an_intent_file(tmp_path, paths):
    _populate(tmp_path, ["generated"], size=64)
    assert recover_interrupted_move(paths) is None
    assert "images" not in _read_roots(paths)


def test_recovery_reports_and_clears_an_unreadable_intent_file(tmp_path, paths, caplog):
    _intent_file(paths).write_text("{ not json", encoding="utf-8")

    with caplog.at_level(logging.ERROR, logger="core.data_migration"):
        summary = recover_interrupted_move(paths)

    assert summary
    assert not _intent_file(paths).exists()
    records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert records, "an unreadable journal was not logged"


def test_a_failed_rollback_during_recovery_keeps_the_intent_file(
    tmp_path, paths, monkeypatch, caplog
):
    """A journal the recovery could not act on must survive for the next try."""
    _populate(tmp_path, ["generated", "images"], size=64)
    dest = tmp_path / "dest"
    dest.mkdir()
    os.rename(str(tmp_path / "generated"), str(dest / "generated"))
    _intent_file(paths).write_text(json.dumps({
        "version": 1,
        "group": "images",
        "dest": str(dest),
        "entries": [
            [str(tmp_path / "generated"), str(dest / "generated")],
            [str(tmp_path / "images"), str(dest / "images")],
        ],
    }), encoding="utf-8")

    def boom(_src, _dst):
        raise OSError(16, "Device or resource busy")

    monkeypatch.setattr("core.data_migration.os.rename", boom)

    with caplog.at_level(logging.ERROR, logger="core.data_migration"):
        summary = recover_interrupted_move(paths)

    assert summary
    assert _intent_file(paths).exists()
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert str(dest / "generated") in logged


def test_the_intent_file_is_never_a_settings_move_source(tmp_path, paths):
    """The journal sits beside config.json, which never moves."""
    _populate(tmp_path, ["logs"], size=64)
    _intent_file(paths).write_text(json.dumps({"version": 1}), encoding="utf-8")

    names = [name for _src, name in sources_for(Group.SETTINGS, paths)]

    assert MOVE_INTENT_SUFFIX.lstrip(".") not in " ".join(names)
    assert all(not name.endswith(MOVE_INTENT_SUFFIX) for name in names)


def test_an_unwritable_journal_stops_the_move_before_any_rename(
    tmp_path, paths, monkeypatch
):
    _populate(tmp_path, ["generated"], size=64)

    def boom(path, _data):
        if str(path).endswith(MOVE_INTENT_SUFFIX):
            raise ConfigError("read-only file system")
        raise AssertionError("only the journal write should reach this stub")

    monkeypatch.setattr("core.config_io.write_config", boom)

    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)

    assert not result.ok
    assert (tmp_path / "generated" / "f.bin").exists()
    assert "images" not in _read_roots(paths)


def test_main_checks_for_an_interrupted_move_at_startup():
    """The recovery has to run from the startup path, inside a guard.

    main.py cannot be imported in a test process: it installs a global import
    hook and replaces builtins.print. The call is therefore pinned in the
    source tree instead.
    """
    import ast

    source = (Path(__file__).resolve().parents[2] / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main_fn = next(n for n in tree.body
                   if isinstance(n, ast.FunctionDef) and n.name == "main")

    guarded = []
    for node in ast.walk(main_fn):
        if not isinstance(node, ast.Try):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) \
                    and inner.func.id == "recover_interrupted_move":
                guarded.append(node)

    assert guarded, "main() never calls recover_interrupted_move inside a try block"
    assert any(handler.type is not None or handler.body for node in guarded
               for handler in node.handlers), "the call has no handler"


# -- Bug 13: cancel must stop the rename fast path ---------------------------

def test_cancel_stops_the_rename_fast_path_before_any_rename(tmp_path, paths):
    _populate(tmp_path, ["generated", "images"], size=64)
    dest = tmp_path / "dest"

    result = move_group(Group.IMAGES, dest, paths=paths, cancel=lambda: True)

    assert not result.ok
    assert "cancel" in result.error.lower()
    assert (tmp_path / "generated" / "f.bin").exists()
    assert (tmp_path / "images" / "f.bin").exists()
    assert "images" not in _read_roots(paths)


def test_cancel_during_the_rename_fast_path_puts_every_entry_back(tmp_path, paths):
    _populate(tmp_path, ["generated", "images", "composites"], size=64)
    dest = tmp_path / "dest"
    calls = {"n": 0}

    def cancel():
        calls["n"] += 1
        return calls["n"] > 1

    result = move_group(Group.IMAGES, dest, paths=paths, cancel=cancel)

    assert not result.ok
    assert "cancel" in result.error.lower()
    for name in ("generated", "images", "composites"):
        assert (tmp_path / name / "f.bin").exists()
    assert "images" not in _read_roots(paths)


def test_a_cancelled_rename_leaves_no_destination_folder_behind(tmp_path, paths):
    _populate(tmp_path, ["generated", "images"], size=64)
    dest = tmp_path / "dest"

    result = move_group(Group.IMAGES, dest, paths=paths, cancel=lambda: True)

    assert not result.ok
    assert not dest.exists()


def test_a_config_failure_on_the_rename_path_leaves_no_destination_behind(
    tmp_path, paths, monkeypatch
):
    _populate(tmp_path, ["generated"], size=64)
    dest = tmp_path / "dest"

    def boom(*_args, **_kwargs):
        raise ConfigError("no space left on device")

    monkeypatch.setattr("core.data_migration._write_root", boom)

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert not result.ok
    assert (tmp_path / "generated" / "f.bin").exists()
    assert not dest.exists()


# -- Bug 14: destination shapes and symlinks ---------------------------------

def test_validate_rejects_a_destination_that_is_a_file(tmp_path, paths):
    _populate(tmp_path, ["generated"], size=64)
    dest = tmp_path / "notes.txt"
    dest.write_text("my notes", encoding="utf-8")

    error = validate_destination(Group.IMAGES, dest, paths)

    assert error and "folder" in error.lower()


def test_a_file_destination_returns_a_clean_error_not_an_exception(tmp_path, paths):
    _populate(tmp_path, ["generated"], size=64)
    dest = tmp_path / "notes.txt"
    dest.write_text("my notes", encoding="utf-8")

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert not result.ok
    assert dest.read_text(encoding="utf-8") == "my notes"
    assert (tmp_path / "generated" / "f.bin").exists()


@pytest.mark.skipif(os.name == "nt", reason="symlinks need a privileged account")
def test_a_broken_symlink_destination_returns_a_clean_error(tmp_path, paths):
    _populate(tmp_path, ["generated"], size=64)
    dest = tmp_path / "dest"
    os.symlink(str(tmp_path / "offline_share"), str(dest))

    error = validate_destination(Group.IMAGES, dest, paths)
    assert error

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert not result.ok
    assert os.path.islink(str(dest))
    assert (tmp_path / "generated" / "f.bin").exists()


@pytest.mark.skipif(os.name == "nt", reason="symlinks need a privileged account")
def test_a_symlink_to_a_real_folder_is_a_usable_destination(tmp_path, paths):
    _populate(tmp_path, ["generated"], size=64)
    real = tmp_path / "real_dest"
    real.mkdir()
    dest = tmp_path / "dest"
    os.symlink(str(real), str(dest))

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert result.ok, result.error
    assert (real / "generated" / "f.bin").exists()


@pytest.mark.skipif(os.name == "nt", reason="symlinks need a privileged account")
def test_a_broken_symlink_inside_the_source_does_not_abort_the_move(
    tmp_path, paths, monkeypatch
):
    """Cross-volume is the whole point of the feature; one dead link cannot
    make every move of the group fail forever."""
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated"], size=64)
    os.symlink(str(tmp_path / "nowhere"), str(tmp_path / "generated" / "old.png"))
    dest = tmp_path / "dest"

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert result.ok, result.error
    assert (dest / "generated" / "f.bin").exists()
    assert os.path.islink(str(dest / "generated" / "old.png"))
    assert os.readlink(str(dest / "generated" / "old.png")) == str(tmp_path / "nowhere")
    assert not (tmp_path / "generated").exists()


@pytest.mark.skipif(os.name == "nt", reason="symlinks need a privileged account")
def test_a_link_inside_the_source_is_copied_as_a_link(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated"], size=64)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"y" * 4096)
    os.symlink(str(outside), str(tmp_path / "generated" / "link.bin"))
    dest = tmp_path / "dest"

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert result.ok, result.error
    assert os.path.islink(str(dest / "generated" / "link.bin"))
    assert os.readlink(str(dest / "generated" / "link.bin")) == str(outside)
    # The link's target was not dragged into the group's tree.
    assert result.bytes_moved == 64


@pytest.mark.skipif(os.name == "nt", reason="symlinks need a privileged account")
def test_a_source_that_is_a_symlink_does_not_leave_a_second_copy(
    tmp_path, paths, monkeypatch
):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    real = tmp_path / "real_projects"
    real.mkdir()
    (real / "clip.mp4").write_bytes(b"v" * 4096)
    os.symlink(str(real), str(tmp_path / "video_projects"))
    dest = tmp_path / "dest"

    result = move_group(Group.VIDEO, dest, paths=paths)

    assert result.ok, result.error
    # The link moved, so the data still exists exactly once.
    assert os.path.islink(str(dest / "video_projects"))
    assert (dest / "video_projects" / "clip.mp4").read_bytes() == b"v" * 4096
    assert not os.path.lexists(str(tmp_path / "video_projects"))
    assert (real / "clip.mp4").exists()


# -- Bug 15: one group's destination must not nest in another group's root ----

def _paths_with_roots(tmp_path, roots):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {k: str(v) for k, v in roots.items()}}),
                   encoding="utf-8")
    return DataPaths(config_path=cfg)


def test_validate_rejects_a_destination_inside_another_groups_root(tmp_path):
    images_root = tmp_path / "IMG"
    images_root.mkdir()
    own = _paths_with_roots(tmp_path, {"images": images_root})
    _populate(tmp_path, ["video_projects"], size=64)

    error = validate_destination(Group.VIDEO, images_root / "generated" / "vids", own)

    assert error and "images" in error.lower()


def test_validate_rejects_a_destination_that_holds_another_groups_root(tmp_path):
    video_root = tmp_path / "outer" / "VID"
    video_root.mkdir(parents=True)
    own = _paths_with_roots(tmp_path, {"video": video_root})
    _populate(tmp_path, ["generated"], size=64)

    error = validate_destination(Group.IMAGES, tmp_path / "outer", own)

    assert error and "video" in error.lower()


def test_two_groups_may_share_one_root(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    own = _paths_with_roots(tmp_path, {"video": shared})
    _populate(tmp_path, ["generated"], size=64)

    assert validate_destination(Group.IMAGES, shared, own) is None


def test_a_nested_destination_cannot_carry_another_groups_data_away(tmp_path):
    """The exact sequence the repro used: Video nested inside the Images root,
    then a second Images move carries the video data off inside generated/."""
    images_root = tmp_path / "IMG"
    images_root.mkdir()
    (images_root / "generated").mkdir()
    own = _paths_with_roots(tmp_path, {"images": images_root})
    _populate(tmp_path, ["video_projects"], size=64)

    result = move_group(Group.VIDEO, images_root / "generated" / "vids", paths=own)

    assert not result.ok
    assert (tmp_path / "video_projects" / "f.bin").exists()
    assert not (images_root / "generated" / "vids").exists()


# -- Bug 16: an unclaimed cache subdirectory must never travel silently -------

def test_an_unclaimed_cache_subdir_stays_behind_after_both_groups_move(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    _populate(tmp_path / "cache",
              ["ai_visemes", "video", "thumbnails", "veo_videos", "mystery"], size=32)
    _populate(tmp_path, ["musetalk", "video_projects"], size=32)

    first = move_group(Group.MODELS, tmp_path / "M", paths=DataPaths(config_path=cfg))
    assert first.ok, first.error

    second = move_group(Group.VIDEO, tmp_path / "V", paths=DataPaths(config_path=cfg))
    assert second.ok, second.error

    assert (tmp_path / "cache" / "mystery" / "f.bin").exists()
    assert not (tmp_path / "M" / "cache" / "mystery").exists()
    assert not (tmp_path / "V" / "cache" / "mystery").exists()


def test_the_second_move_still_reports_the_unclaimed_cache_subdir(tmp_path, caplog):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {"models": str(tmp_path / "M")}}),
                   encoding="utf-8")
    _populate(tmp_path / "cache", ["video", "mystery"], size=32)
    _populate(tmp_path, ["video_projects"], size=32)

    with caplog.at_level(logging.WARNING, logger="core.data_migration"):
        result = move_group(Group.VIDEO, tmp_path / "V", paths=DataPaths(config_path=cfg))

    assert result.ok, result.error
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "mystery" in logged


# -- Bug 17: CACHE_OWNERS must name every cache the application creates -------

def test_cache_owners_covers_every_model_cache_and_video_cache_call_site():
    """A new cache name that no group owns is data a move leaves behind."""
    import re

    from core.data_migration import CACHE_OWNERS

    repo = Path(__file__).resolve().parents[2]
    pattern = re.compile(r"\.(model_cache|video_cache)\(\s*[\"']([^\"']+)[\"']")
    owner_of = {"model_cache": Group.MODELS, "video_cache": Group.VIDEO}

    missing = []
    for directory in ("core", "gui", "cli", "providers"):
        for path in sorted((repo / directory).rglob("*.py")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                for accessor, name in pattern.findall(line):
                    if name not in CACHE_OWNERS[owner_of[accessor]]:
                        missing.append(
                            f"{path.relative_to(repo).as_posix()}:{lineno}: "
                            f"{accessor}({name!r}) has no owner"
                        )

    assert not missing, (
        "Add these names to CACHE_OWNERS in core/data_migration.py, or a move "
        "leaves the data behind:\n" + "\n".join(missing)
    )


def test_every_owned_cache_name_is_owned_by_exactly_one_group():
    from core.data_migration import CACHE_OWNERS

    models = set(CACHE_OWNERS[Group.MODELS])
    video = set(CACHE_OWNERS[Group.VIDEO])
    assert not models & video


def test_an_unrepaired_journal_stops_a_new_move(tmp_path, paths):
    """One journal describes one move; a second move must not overwrite it."""
    _populate(tmp_path, ["generated"], size=64)
    _intent_file(paths).write_text(json.dumps({
        "version": 1,
        "group": "video",
        "dest": str(tmp_path / "old_dest"),
        "entries": [[str(tmp_path / "video_projects"),
                     str(tmp_path / "old_dest" / "video_projects")]],
    }), encoding="utf-8")

    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)

    assert not result.ok
    assert "interrupted" in result.error.lower()
    assert (tmp_path / "generated" / "f.bin").exists()
    assert not (tmp_path / "dest").exists()
    # The record of the earlier move is still there for the recovery to use.
    assert _intent_file(paths).exists()


def test_recovery_reports_data_that_is_at_neither_location(tmp_path, paths, caplog):
    dest = tmp_path / "dest"
    _intent_file(paths).write_text(json.dumps({
        "version": 1,
        "group": "images",
        "dest": str(dest),
        "entries": [[str(tmp_path / "generated"), str(dest / "generated")]],
    }), encoding="utf-8")

    with caplog.at_level(logging.ERROR, logger="core.data_migration"):
        summary = recover_interrupted_move(paths)

    assert summary and str(dest) in summary
    assert [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert not _intent_file(paths).exists()


def test_a_stranded_rollback_keeps_the_journal_for_the_next_start(
    tmp_path, paths, monkeypatch
):
    """Data split across two places is exactly what the journal describes."""
    _populate(tmp_path, ["generated", "images", "composites"], size=64)
    dest = tmp_path / "dest"
    # 3 fails, and both rollbacks (4 and 5) fail too.
    _flaky_rename(monkeypatch, {3, 4, 5})

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert not result.ok
    assert result.stranded
    assert _intent_file(paths).exists()

    # The next start puts the stranded directories back on its own.
    monkeypatch.undo()
    summary = recover_interrupted_move(DataPaths(config_path=paths.config_file()))

    assert summary
    for name in ("generated", "images"):
        assert (tmp_path / name / "f.bin").exists()
        assert not (dest / name).exists()
    assert "images" not in _read_roots(paths)
    assert not _intent_file(paths).exists()


def test_a_rolled_back_rename_clears_the_journal(tmp_path, paths, monkeypatch):
    """A move that put everything back has nothing left to describe."""
    _populate(tmp_path, ["generated", "images"], size=64)
    _flaky_rename(monkeypatch, {2})

    def boom(*_args, **_kwargs):
        raise OSError("disk on fire")

    monkeypatch.setattr("core.data_migration._copy_entry", boom)

    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)

    assert not result.ok
    assert not _intent_file(paths).exists()
    assert (tmp_path / "generated" / "f.bin").exists()
    assert (tmp_path / "images" / "f.bin").exists()
