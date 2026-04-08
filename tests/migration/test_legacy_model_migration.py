"""Tests for legacy model migration shims (June 30 2026 GA deprecation)."""

import json
from pathlib import Path

import pytest

from core.video.config import VideoConfig


@pytest.fixture
def tmp_video_config(tmp_path: Path) -> Path:
    """Write a video_config.json containing legacy Veo IDs."""
    cfg = {
        "veo_model": "veo-3.0-generate-001",
        "veo_settings": {
            "models": {
                "veo-3.0-generate-001": {"duration": 8},
                "veo-2.0-generate-001": {"duration": 5},
            }
        },
    }
    target = tmp_path / "video_config.json"
    target.write_text(json.dumps(cfg))
    return target


def test_video_config_migrates_legacy_veo_default(tmp_video_config: Path):
    cfg = VideoConfig(config_file=tmp_video_config)
    assert cfg.get("veo_model") == "veo-3.1-generate-001"


def test_video_config_drops_legacy_veo_model_entries(tmp_video_config: Path):
    cfg = VideoConfig(config_file=tmp_video_config)
    models = cfg.get("veo_settings.models") or {}
    assert "veo-3.0-generate-001" not in models
    assert "veo-3.0-fast-generate-001" not in models
    assert "veo-2.0-generate-001" not in models
    assert "veo-3.1-generate-001" in models


def test_video_config_persists_migration(tmp_video_config: Path):
    VideoConfig(config_file=tmp_video_config).save()
    on_disk = json.loads(tmp_video_config.read_text())
    assert on_disk["veo_model"] == "veo-3.1-generate-001"
