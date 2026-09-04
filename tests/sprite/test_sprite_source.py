"""Tests for core/sprite/source.py (character-source-import)."""
import json

import numpy as np
import pytest
from PIL import Image

from core.sprite.source import SourceAnalysis, analyze_source, normalize_source


def _write(tmp_path, name, arr):
    path = tmp_path / name
    Image.fromarray(arr).save(path)  # mode comes from the array shape
    return path


def test_analyze_uniform_green_border_no_alpha(tmp_path):
    arr = np.zeros((60, 80, 3), dtype=np.uint8)
    arr[...] = (0, 255, 0)
    arr[20:40, 30:50] = (200, 30, 30)
    path = _write(tmp_path, "green.png", arr)
    info = analyze_source(path)
    assert isinstance(info, SourceAnalysis)
    assert info.has_alpha is False
    assert info.border_uniform is True
    assert info.border_color == "#00FF00"
    assert info.size == (80, 60)


def test_analyze_detects_alpha(tmp_path):
    arr = np.zeros((32, 32, 4), dtype=np.uint8)
    arr[8:24, 8:24] = (255, 0, 0, 255)
    path = _write(tmp_path, "alpha.png", arr)
    info = analyze_source(path)
    assert info.has_alpha is True
    assert info.size == (32, 32)


def test_analyze_noisy_border_is_not_uniform(tmp_path):
    rng = np.random.default_rng(1)
    arr = rng.integers(0, 255, size=(40, 40, 3), dtype=np.uint8)
    path = _write(tmp_path, "noise.png", arr)
    info = analyze_source(path)
    assert info.border_uniform is False
    assert info.border_color is None


def test_normalize_pads_to_target_aspect_and_writes_sidecar(tmp_path):
    arr = np.zeros((100, 100, 4), dtype=np.uint8)
    arr[...] = (10, 20, 30, 255)
    src = _write(tmp_path, "square.png", arr)
    out = tmp_path / "source" / "character.png"
    result = normalize_source(src, out, aspect_ratio="16:9")
    assert result == out and out.exists()
    with Image.open(out) as img:
        w, h = img.size
        assert img.mode == "RGBA"
        assert abs((w / h) - (16 / 9)) < 0.02
        assert w >= 100 and h >= 100          # never cropped
        assert img.getpixel((0, 0))[3] == 0    # transparent padding
        assert img.getpixel((w // 2, h // 2)) == (10, 20, 30, 255)
    sidecar = out.with_suffix(".png.json")
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    assert meta["aspect_ratio"] == "16:9"
    assert meta["source"] == str(src)
    assert meta["kind"] == "character_source"


def test_normalize_keeps_matching_aspect_unchanged(tmp_path):
    arr = np.zeros((90, 160, 3), dtype=np.uint8)
    arr[...] = (5, 5, 5)
    src = _write(tmp_path, "wide.png", arr)
    out = tmp_path / "character.png"
    normalize_source(src, out, aspect_ratio="16:9")
    with Image.open(out) as img:
        assert img.size == (160, 90)
        assert img.mode == "RGBA"


def test_normalize_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        normalize_source(tmp_path / "nope.png", tmp_path / "out.png")
