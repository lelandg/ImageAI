"""Tests for core/sprite/generation/plate.py (chroma-plate-prep)."""
import io
import json
from unittest.mock import MagicMock

import pytest
from PIL import Image

from core.sprite.generation.errors import ProviderError, SafetyRefusal
from core.sprite.generation.plate import PLATE_PROMPT, make_chroma_plate
from core.sprite.pipeline import Cancelled, CancelToken


def _png_bytes(color=(0, 255, 0)):
    buf = io.BytesIO()
    Image.new("RGB", (16, 9), color).save(buf, format="PNG")
    return buf.getvalue()


def _provider(images=None, texts=None, raises=None):
    provider = MagicMock()
    provider.get_default_model.return_value = "image-model-default"
    if raises is not None:
        provider.edit_image.side_effect = raises
    else:
        provider.edit_image.return_value = (texts or [], images if images is not None else [_png_bytes()])
    return provider


def test_make_plate_calls_edit_image_with_prompt_and_aspect(png_file, tmp_path):
    src = png_file()
    provider = _provider(texts=["done"])
    out = tmp_path / "source" / "plate.png"
    seen = []
    result = make_chroma_plate(provider, src, out, "#00ff00", log=seen.append)
    assert result == out and out.exists()
    args, kwargs = provider.edit_image.call_args
    assert args[0] == src
    assert args[1] == PLATE_PROMPT.format(color_name="green", hex="#00FF00")
    assert args[2] == "image-model-default"
    assert kwargs["aspect_ratio"] == "16:9"
    # Prompt hygiene: no forbidden words, no aspect, no pixels.
    assert "transparent" not in args[1].lower() and "16:9" not in args[1]
    with Image.open(out) as img:
        assert img.mode == "RGBA"
    meta = json.loads(out.with_suffix(".png.json").read_text(encoding="utf-8"))
    assert meta["plate_color"] == "#00FF00"
    assert meta["kind"] == "chroma_plate"
    assert meta["model"] == "image-model-default"
    assert meta["prompt"] == args[1]
    assert meta["response_texts"] == ["done"]
    joined = "\n".join(seen)
    assert "Chroma plate request" in joined and "done" in joined


def test_make_plate_honors_model_and_aspect(png_file, tmp_path):
    provider = _provider()
    make_chroma_plate(provider, png_file(), tmp_path / "p.png", model="custom-image",
                      aspect_ratio="1:1")
    args, kwargs = provider.edit_image.call_args
    assert args[2] == "custom-image" and kwargs["aspect_ratio"] == "1:1"


def test_make_plate_raises_provider_error_when_no_image(png_file, tmp_path):
    provider = _provider(images=[])
    with pytest.raises(ProviderError, match="no image"):
        make_chroma_plate(provider, png_file(), tmp_path / "p.png")
    assert not (tmp_path / "p.png").exists()


def test_make_plate_classifies_provider_exceptions(png_file, tmp_path):
    provider = _provider(raises=RuntimeError("Google image editing failed: blocked by safety"))
    seen = []
    with pytest.raises(SafetyRefusal):
        make_chroma_plate(provider, png_file(), tmp_path / "p.png", log=seen.append)
    assert any("failed" in line.lower() for line in seen)


def test_make_plate_rejects_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        make_chroma_plate(_provider(), tmp_path / "missing.png", tmp_path / "p.png")


def test_make_plate_raises_before_the_provider_call_when_cancelled(png_file, tmp_path):
    """Minor 2: a cancelled token stops the plate before any money is spent."""
    provider = _provider()
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        make_chroma_plate(provider, png_file(), tmp_path / "p.png", token=token)
    assert provider.edit_image.call_count == 0
    assert not (tmp_path / "p.png").exists()


def test_make_plate_raises_after_the_provider_call_when_cancelled(png_file, tmp_path):
    """Cancel during a slow image call is honored as soon as the call returns."""
    provider = _provider()
    token = CancelToken()

    def cancel_then_return(*args, **kwargs):
        token.cancel()  # the user clicks Cancel while the image call runs
        return [], [_png_bytes()]

    provider.edit_image.side_effect = cancel_then_return
    with pytest.raises(Cancelled):
        make_chroma_plate(provider, png_file(), tmp_path / "p.png", token=token)
    assert provider.edit_image.call_count == 1
    assert not (tmp_path / "p.png").exists()  # no half-written plate, no sidecar
