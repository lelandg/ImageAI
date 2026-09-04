"""Fixtures for the sprite generation route tests (sub-project 2)."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image


@pytest.fixture
def png_file(tmp_path):
    """Factory: write a small RGBA PNG and return its path."""
    def _make(name="char.png", size=(64, 48), color=(200, 40, 40, 255),
              border=None):
        arr = np.zeros((size[1], size[0], 4), dtype=np.uint8)
        arr[..., :4] = color
        if border is not None:
            arr[:4, :, :] = border
            arr[-4:, :, :] = border
            arr[:, :4, :] = border
            arr[:, -4:, :] = border
        path = tmp_path / name
        Image.fromarray(arr).save(path)  # mode comes from the array shape
        return path
    return _make


@pytest.fixture
def make_action():
    """Factory for an ActionCard with sensible defaults."""
    def _make(**overrides):
        from core.sprite.project import ActionCard
        values = dict(id="a1", name="walk", prompt="the hero walks to the right",
                      duration_s=4, loop=True, target_frames=8, fps=12)
        values.update(overrides)
        return ActionCard(**values)
    return _make


@pytest.fixture
def make_project(tmp_path, png_file):
    """Factory for a SpriteProject with a plate and a project dir.

    This factory is the only place that constructs SpriteProject in these
    tests. If sub-project 1 requires more constructor arguments than
    ``name`` and ``project_dir``, extend this factory. Do not change the
    tests.
    """
    def _make(actions=(), provider="omni", plate=True, turnaround=False):
        from core.sprite.project import SpriteProject, GenerationSettings
        project_dir = tmp_path / "hero"
        project_dir.mkdir(parents=True, exist_ok=True)
        project = SpriteProject(name="hero", project_dir=project_dir)
        project.generation = GenerationSettings(provider=provider)
        project.plate_color = "#00FF00"
        if plate:
            project.plate_path = png_file("plate.png", color=(0, 255, 0, 255))
        else:
            project.plate_path = None
        if turnaround:
            project.turnaround = {
                "front": png_file("front.png"),
                "side": png_file("side.png"),
            }
        else:
            project.turnaround = {}
        project.actions = list(actions)
        return project
    return _make
