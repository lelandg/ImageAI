"""Sprite storage joins the relocatable Images and Settings groups (design 1.6)."""
import json

from core.data_migration import GROUP_CONTENTS, SETTINGS_FILES, sources_for
from core.paths import DataPaths, Group


def test_sprites_travel_with_the_images_group():
    assert "sprites" in GROUP_CONTENTS[Group.IMAGES]


def test_sprite_configs_travel_with_the_settings_group():
    assert "sprite_configs.json" in SETTINGS_FILES


def test_group_contents_name_every_sprite_accessor_leaf(tmp_path):
    """The migrator only moves directories it knows; the accessor must match."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    dp = DataPaths(config_path=cfg)
    assert dp.sprite_projects().name in GROUP_CONTENTS[Group.IMAGES]
    assert dp.sprite_configs().name in SETTINGS_FILES


def test_sources_for_images_includes_an_existing_sprites_dir(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    dp = DataPaths(config_path=cfg)
    (tmp_path / "sprites").mkdir()
    names = [name for _, name in sources_for(Group.IMAGES, dp)]
    assert "sprites" in names


def test_sources_for_settings_includes_sprite_configs(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    dp = DataPaths(config_path=cfg)
    (tmp_path / "sprite_configs.json").write_text("{}", encoding="utf-8")
    names = [name for _, name in sources_for(Group.SETTINGS, dp)]
    assert "sprite_configs.json" in names
