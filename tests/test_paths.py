"""Unit tests for the DataPaths resolver."""
import json

import pytest

from core.paths import (
    DataPaths,
    Group,
    get_data_paths,
    reset_data_paths,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_data_paths()
    yield
    reset_data_paths()


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
