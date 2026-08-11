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
    """Keep every test away from the real ~/.cache/huggingface and ~/.imageai.

    Those directories exist on a developer machine. A test that does not point
    them somewhere else would list the developer's own data as a move source.
    A test that needs them sets its own value; the later setattr wins.
    """
    absent = tmp_path / "no_legacy_dir"
    monkeypatch.setattr("core.data_migration.legacy_huggingface_dir", lambda: absent)
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


def test_sources_for_models_includes_the_huggingface_cache(tmp_path, paths, monkeypatch):
    _populate(tmp_path, ["musetalk"])
    hf = tmp_path / "hf"
    _populate(hf, ["models--x"])
    monkeypatch.setattr("core.data_migration.legacy_huggingface_dir", lambda: hf)

    entries = dict((name, src) for src, name in sources_for(Group.MODELS, paths))
    assert "musetalk" in entries
    assert entries["huggingface"] == hf


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


def test_models_takes_the_whole_cache_when_the_video_root_differs(tmp_path):
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
    assert (dest / "cache" / "leftover" / "f.bin").exists()
    assert not (tmp_path / "cache").exists()


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
