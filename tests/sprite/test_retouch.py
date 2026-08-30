# tests/sprite/test_retouch.py
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

from core.sprite.generation.errors import ProviderError
from core.sprite.generation.retouch import (
    build_region_mask, fit_to_size, next_retouch_path, retouch_frame, validate_retouch,
)
from providers.google import GoogleProvider
from providers.openai import MODEL_CAPS, OpenAIProvider


def _png(w=32, h=32, shade=100) -> bytes:
    arr = np.full((h, w, 4), (shade, shade, shade, 255), dtype=np.uint8)
    # Tint (not just position) the square with `shade` so a shade-only change
    # is still visible to validate_retouch() when the tested region coincides
    # with the square (region tests use (8, 8, 16, 16), exactly this square).
    arr[8:24, 8:24] = (255, shade % 256, shade % 256, 255)
    buf = BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    return buf.getvalue()


def _frames(tmp_path: Path):
    paths = []
    for i in range(1, 4):
        p = tmp_path / f"{i:04d}.png"
        p.write_bytes(_png(shade=100))
        paths.append(p)
    return paths


def _google(reply: bytes):
    provider = MagicMock(spec=GoogleProvider)
    provider.get_default_model.return_value = "default-google-image-model"
    provider.edit_image.return_value = ([], [reply])
    provider.edit_image_region.return_value = ([], [reply])
    return provider


def _openai(reply: bytes):
    provider = MagicMock(spec=OpenAIProvider)
    provider.edit_image.return_value = ([], [reply])
    return provider


def test_next_retouch_path_never_collides(tmp_path):
    frame = tmp_path / "0003.png"
    frame.write_bytes(_png())
    first = next_retouch_path(frame)
    assert first.name == "0003.r1.png"
    first.write_bytes(_png())
    assert next_retouch_path(frame).name == "0003.r2.png"
    assert next_retouch_path(first).name == "0003.r2.png"     # retouch of a retouch keeps the base name


def test_google_whole_frame_uses_neighbors_as_references(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _google(_png(shade=180))
    out = retouch_frame(provider, f2, "fix the left hand", neighbors=[f1, f3])
    assert out == tmp_path / "0002.r1.png" and out.exists()
    assert f2.read_bytes() == _png(shade=100)                   # original untouched
    args, kwargs = provider.edit_image.call_args
    assert args[0] == [f2.read_bytes(), f1.read_bytes(), f3.read_bytes()]
    assert "fix the left hand" in args[1] and "neighboring" in args[1]
    assert kwargs["model"] == "default-google-image-model"
    provider.edit_image_region.assert_not_called()
    sidecar = json.loads((tmp_path / "0002.r1.png.json").read_text(encoding="utf-8"))
    assert sidecar["route"] == "retouch" and sidecar["source_frame"].endswith("0002.png")
    assert len(sidecar["reference_images"]) == 2 and sidecar["region"] is None


def test_google_region_uses_edit_image_region(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _google(_png(shade=180))
    retouch_frame(provider, f2, "add a glove", neighbors=[f1, f3], region=(8, 8, 16, 16))
    args, kwargs = provider.edit_image_region.call_args
    assert args[0] == f2.read_bytes() and args[1] == (8, 8, 16, 16) and "add a glove" in args[2]
    provider.edit_image.assert_not_called()


def test_openai_region_builds_alpha_mask(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _openai(_png(shade=180))
    model = next(m for m, c in MODEL_CAPS.items() if c["supports_mask"] and c["supports_multi_reference"])
    retouch_frame(provider, f2, "add a glove", neighbors=[f1], region=(8, 8, 16, 16), model=model)
    args, kwargs = provider.edit_image.call_args
    assert kwargs["model"] == model and kwargs["n"] == 1 and "size" in kwargs
    mask = Image.open(BytesIO(kwargs["mask"]))
    assert mask.size == (32, 32) and mask.mode == "RGBA"
    assert mask.getpixel((16, 16))[3] == 0            # inside region: editable
    assert mask.getpixel((0, 0))[3] == 255            # far outside: protected
    assert args[0] == [f2.read_bytes(), f1.read_bytes()]


def test_openai_without_region_sends_no_mask(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _openai(_png(shade=180))
    retouch_frame(provider, f2, "brighten the cape", neighbors=[])
    assert provider.edit_image.call_args.kwargs["mask"] is None


def test_build_region_mask_feathers_edge():
    mask = Image.open(BytesIO(build_region_mask((32, 32), (8, 8, 16, 16), feather=4)))
    assert mask.getpixel((7, 16))[3] < 255 and mask.getpixel((7, 16))[3] > 0
    assert mask.getpixel((2, 16))[3] == 255


def test_result_is_repadded_proportionally_when_size_differs(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _google(_png(w=64, h=32, shade=180))   # 2:1 reply for a 1:1 frame
    out = retouch_frame(provider, f2, "x")
    img = Image.open(out)
    assert img.size == (32, 32)
    alpha = np.asarray(img.getchannel("A"))
    assert alpha[0, 16] == 0 and alpha[31, 16] == 0 and alpha[16, 16] == 255   # letterboxed, not stretched


def test_fit_to_size_upscales_small_result():
    small = Image.new("RGBA", (16, 8), (1, 2, 3, 255))
    fitted = fit_to_size(small, (64, 64))
    assert fitted.size == (64, 64)
    assert fitted.getpixel((32, 32))[3] == 255 and fitted.getpixel((32, 2))[3] == 0


def test_validate_retouch_detects_unchanged():
    a = Image.open(BytesIO(_png(shade=100)))
    assert validate_retouch(a, a.copy(), None)[0] is False
    assert validate_retouch(a, Image.open(BytesIO(_png(shade=180))), (0, 0, 8, 8))[0] is True


def test_unchanged_result_retries_then_raises(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _google(_png(shade=100))               # identical to the source
    with pytest.raises(ProviderError):
        retouch_frame(provider, f2, "x", attempts=2)
    assert provider.edit_image.call_count == 2
    assert not (tmp_path / "0002.r1.png").exists()


def test_never_overwrites_existing_output(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    (tmp_path / "custom.png").write_bytes(_png())
    with pytest.raises(FileExistsError):
        retouch_frame(_google(_png(shade=180)), f2, "x", tmp_path / "custom.png")


def test_logs_request_and_response(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    lines = []
    retouch_frame(_google(_png(shade=180)), f2, "x", log=lines.append)
    assert any("request" in l and "prompt:" in l for l in lines)
    assert any("response" in l for l in lines) and any("validation" in l for l in lines)
