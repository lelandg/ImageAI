"""Tests for core/sprite/generation/turnaround.py (character-turnaround-pack)."""
import io
import json
from unittest.mock import MagicMock

import pytest
from PIL import Image

from core.sprite.generation.errors import QuotaExceeded
from core.sprite.generation.turnaround import (
    VIEW_PHRASES,
    VIEWS,
    build_view_prompt,
    generate_turnaround,
)
from core.sprite.pipeline import CancelToken, Cancelled


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (0, 255, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _provider():
    provider = MagicMock()
    provider.get_default_model.return_value = "img-default"
    provider.edit_image.return_value = (["ok"], [_png_bytes()])
    return provider


def test_views_and_phrases_cover_each_other():
    assert VIEWS == ("front", "side", "back", "three_quarter")
    assert set(VIEW_PHRASES) == set(VIEWS)


def test_build_view_prompt_lists_do_not_change_and_color():
    prompt = build_view_prompt("side", "#00ff00", ("face", "hair", "outfit"))
    assert VIEW_PHRASES["side"] in prompt
    assert "green background #00FF00" in prompt
    assert "Do not change the face, hair, and outfit." in prompt
    assert "transparent" not in prompt.lower() and ":" not in prompt.replace("#00FF00", "")


def test_build_view_prompt_rejects_unknown_view():
    with pytest.raises(ValueError):
        build_view_prompt("top", "#00FF00", ("face",))


def test_generate_turnaround_writes_each_view_with_sidecar(png_file, tmp_path):
    provider = _provider()
    out_dir = tmp_path / "turnaround"
    seen = []
    result = generate_turnaround(provider, png_file(), out_dir, plate_color="#00FF00",
                                 log=seen.append)
    assert list(result) == list(VIEWS)
    for view, path in result.items():
        assert path == out_dir / f"{view}.png" and path.exists()
        meta = json.loads(path.with_suffix(".png.json").read_text(encoding="utf-8"))
        assert meta["view"] == view and meta["kind"] == "turnaround"
        assert meta["plate_color"] == "#00FF00"
        assert meta["prompt"] == build_view_prompt(view, "#00FF00",
                                                   ("face", "hair", "proportions", "outfit"))
    assert provider.edit_image.call_count == 4
    _, kwargs = provider.edit_image.call_args
    assert kwargs["aspect_ratio"] == "1:1"
    assert sum("Turnaround request" in line for line in seen) == 4


def test_generate_turnaround_subset_and_model(png_file, tmp_path):
    provider = _provider()
    result = generate_turnaround(provider, png_file(), tmp_path / "t", views=("front",),
                                 plate_color="#0000FF", model="img-x")
    assert list(result) == ["front"]
    args, _ = provider.edit_image.call_args
    assert args[2] == "img-x" and "blue background #0000FF" in args[1]


def test_generate_turnaround_honors_cancel_token(png_file, tmp_path):
    provider = _provider()
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        generate_turnaround(provider, png_file(), tmp_path / "t", plate_color="#00FF00",
                            token=token)
    provider.edit_image.assert_not_called()


def test_generate_turnaround_classifies_errors_and_stops(png_file, tmp_path):
    provider = _provider()
    provider.edit_image.side_effect = [(["ok"], [_png_bytes()]),
                                       RuntimeError("429 quota exceeded")]
    with pytest.raises(QuotaExceeded):
        generate_turnaround(provider, png_file(), tmp_path / "t", plate_color="#00FF00")
    assert (tmp_path / "t" / "front.png").exists()
    assert not (tmp_path / "t" / "side.png").exists()
