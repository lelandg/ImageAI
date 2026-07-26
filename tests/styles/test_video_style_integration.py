"""Stored-style injection into video scene prompts (pure function)."""
import pytest

pytest.importorskip("PySide6")

from types import SimpleNamespace

from core.styles.models import Style


def _scenes(*prompts):
    return [SimpleNamespace(prompt=p) for p in prompts]


def test_apply_stored_style_to_scenes():
    from gui.video.workspace_widget import apply_stored_style_to_scenes
    style = Style(id="w", name="W", prompt_text="washes")
    scenes = _scenes("a fox", "[Chorus]", "a river")
    n = apply_stored_style_to_scenes(scenes, style)
    assert n == 2
    assert scenes[0].prompt == "a fox. In this style: washes"
    assert scenes[1].prompt == "[Chorus]"  # section marker untouched
    assert scenes[2].prompt == "a river. In this style: washes"


def test_apply_stored_style_none_is_noop():
    from gui.video.workspace_widget import apply_stored_style_to_scenes
    scenes = _scenes("a fox")
    assert apply_stored_style_to_scenes(scenes, None) == 0
    assert scenes[0].prompt == "a fox"
