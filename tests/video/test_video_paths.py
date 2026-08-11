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


def test_no_dot_imageai_references_remain():
    """Nothing may build a path under ~/.imageai any more."""
    offenders = []
    for directory in ("core", "gui", "cli", "providers"):
        for path in (REPO_ROOT / directory).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if '".imageai"' in line or "'.imageai'" in line:
                    offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, "Stale ~/.imageai paths:\n" + "\n".join(offenders)
