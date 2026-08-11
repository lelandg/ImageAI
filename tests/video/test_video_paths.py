"""Video subsystem paths must resolve through the Video root."""
import json
from pathlib import Path

import pytest

import core.paths as paths_mod
from core.paths import DataPaths

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def video_root(tmp_path, monkeypatch):
    dest = tmp_path / "V"
    dest.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {"video": str(dest)}}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))
    return dest


def test_project_manager_uses_video_root(video_root):
    from core.video.project_manager import ProjectManager

    assert ProjectManager().base_dir == video_root / "video_projects"


def test_thumbnail_cache_uses_video_root(video_root):
    from core.video.thumbnail_manager import ThumbnailManager

    assert ThumbnailManager().cache_dir == video_root / "cache" / "thumbnails"


def test_image_generator_cache_uses_video_root(video_root):
    from core.video.image_generator import ImageGenerator

    assert ImageGenerator({}).cache_dir == video_root / "cache" / "video"


def test_events_db_uses_video_root(video_root):
    assert paths_mod.get_data_paths().video_events_db() == (
        video_root / "video_projects" / "events.db"
    )


def test_video_config_projects_dir_follows_the_video_root(video_root):
    """VideoConfig must not derive the projects dir from the Settings root."""
    from core.video.config import VideoConfig

    cfg = VideoConfig()
    assert cfg.get_projects_dir() == video_root / "video_projects"


def test_video_config_drops_the_stale_settings_root_default(video_root, tmp_path):
    """A saved value that is only the old auto-derived default must not win.

    Before the Video group could move, the default lived under the Settings
    root and was written into video_config.json. After a Video-only move that
    saved value points at the deleted location.
    """
    from core.video.config import VideoConfig

    settings_root = tmp_path  # config.json's parent, i.e. the Settings root
    stale = settings_root / "video_projects"
    config_file = settings_root / "video_config.json"
    config_file.write_text(
        json.dumps({"video_projects_dir": str(stale)}), encoding="utf-8"
    )

    cfg = VideoConfig(config_file=config_file)
    assert cfg.get_projects_dir() == video_root / "video_projects"


def test_video_config_keeps_an_explicit_user_override(video_root, tmp_path):
    """A directory the user chose must survive a Video-group move."""
    from core.video.config import VideoConfig

    chosen = tmp_path / "my-films"
    chosen.mkdir()
    config_file = tmp_path / "video_config.json"
    config_file.write_text(
        json.dumps({"video_projects_dir": str(chosen)}), encoding="utf-8"
    )

    cfg = VideoConfig(config_file=config_file)
    assert cfg.get_projects_dir() == chosen


def test_video_config_override_survives_a_save_and_reload(video_root, tmp_path):
    from core.video.config import VideoConfig

    chosen = tmp_path / "my-films"
    chosen.mkdir()
    config_file = tmp_path / "video_config.json"

    cfg = VideoConfig(config_file=config_file)
    cfg.set("video_projects_dir", str(chosen))
    assert cfg.save()

    assert VideoConfig(config_file=config_file).get_projects_dir() == chosen


def test_video_config_default_is_not_pinned_into_the_saved_file(video_root, tmp_path):
    """Saving the default must not freeze it, or the next move splits again."""
    from core.video.config import VideoConfig

    config_file = tmp_path / "video_config.json"
    assert VideoConfig(config_file=config_file).save()

    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved["video_projects_dir"] is None


def test_no_dot_imageai_references_remain():
    """Nothing may build a path under ~/.imageai any more."""
    # core/data_migration.py is the one exception: it must name the legacy
    # ~/.imageai tree to find the data it relocates.
    exempt = {REPO_ROOT / "core" / "data_migration.py"}

    offenders = []
    for directory in ("core", "gui", "cli", "providers"):
        for path in (REPO_ROOT / directory).rglob("*.py"):
            if path in exempt:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if '".imageai"' in line or "'.imageai'" in line:
                    offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, "Stale ~/.imageai paths:\n" + "\n".join(offenders)
