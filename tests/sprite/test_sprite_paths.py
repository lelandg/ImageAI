"""Sprite paths must resolve through the Images and Settings roots."""
import json

import core.paths as paths_mod
from core.paths import DataPaths


def test_sprite_project_manager_uses_the_images_root(tmp_path, monkeypatch):
    images = tmp_path / "I"
    images.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {"images": str(images)}}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    from core.sprite.project import SpriteProjectManager

    assert SpriteProjectManager().base_dir == images / "sprites"


def test_sprite_configs_follow_the_settings_root(tmp_path, monkeypatch):
    settings = tmp_path / "S"
    settings.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {"settings": str(settings)}}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    assert paths_mod.get_data_paths().sprite_configs() == settings / "sprite_configs.json"


def test_reanchor_marker_matches_the_accessor_leaf():
    """project._reanchored heals paths by the sprites/ marker; keep them in sync."""
    from core.sprite.project import SPRITES_DIR_NAME

    assert SPRITES_DIR_NAME == paths_mod.get_data_paths().sprite_projects().name


def test_core_sprite_imports_no_qt():
    """core/sprite is headless by design (design section 1).

    Repo-absolute so this pins the global constraint from any cwd; a
    cwd-relative glob would silently pass with an empty offender list when
    run from anywhere other than the repo root (M3).
    """
    import pathlib

    sprite_dir = pathlib.Path(__file__).resolve().parents[2] / "core" / "sprite"
    offenders = []
    for path in sprite_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "PySide6" in text or "PyQt" in text:
            offenders.append(str(path))
    assert not offenders, f"Qt import in core/sprite: {offenders}"
