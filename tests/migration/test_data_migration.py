"""Unit tests for group relocation."""
import json
import logging
import os

import pytest

from core.data_migration import (
    _cleanup_empty_legacy_dirs,
    sources_for,
    tree_size,
    validate_destination,
)
from core.paths import DataPaths, Group


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
    assert "cache" in names


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

    monkeypatch.setattr("core.data_migration.os.replace", boom)

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
