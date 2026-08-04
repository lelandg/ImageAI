"""Google provider sizing: CLI --size parity and edit_image image_config.

Regression tests for the bug where ``size="WxH"`` (as sent by cli/runner.py)
was silently ignored by GoogleProvider.generate(), so Nano Banana Pro CLI
runs always came back at the 1K tier, and GoogleProvider.edit_image()
ignored sizing entirely.
"""

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from providers.google import GoogleProvider


def _png_bytes(w: int = 8, h: int = 8) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), "red").save(buf, format="PNG")
    return buf.getvalue()


def _fake_response(png: bytes) -> SimpleNamespace:
    part = SimpleNamespace(text=None, inline_data=SimpleNamespace(data=png))
    cand = SimpleNamespace(content=SimpleNamespace(parts=[part]),
                           finish_reason="STOP")
    return SimpleNamespace(candidates=[cand])


@pytest.fixture
def provider(tmp_path, monkeypatch):
    # Keep the provider's DEBUG_RAW_GEMINI_* writes out of the real home dir.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr("providers.google.rate_limiter", MagicMock())
    p = GoogleProvider({"api_key": "test-key", "auth_mode": "api-key"})
    p.client = MagicMock()
    p._client_mode = "api_key"
    p.client.models.generate_content.return_value = _fake_response(_png_bytes())
    return p


class TestParseSize:
    def test_parses_width_x_height(self):
        assert GoogleProvider._parse_size("2160x3840") == (2160, 3840)

    def test_uppercase_x(self):
        assert GoogleProvider._parse_size("1024X768") == (1024, 768)

    @pytest.mark.parametrize("bad", ["banana", "", None, "12x", "0x100",
                                     "axb", 1024, "10x10x10"])
    def test_rejects_garbage(self, bad):
        assert GoogleProvider._parse_size(bad) is None


class TestClosestAspectRatio:
    @pytest.mark.parametrize("w,h,expected", [
        (2160, 3840, "9:16"),
        (3840, 2160, "16:9"),
        (1024, 768, "4:3"),
        (800, 800, "1:1"),
        (3072, 5504, "9:16"),
        (1024, 439, "21:9"),
    ])
    def test_mapping(self, w, h, expected):
        assert GoogleProvider.closest_aspect_ratio(w, h) == expected


class TestNbpImageSize:
    @pytest.mark.parametrize("w,h,expected", [
        (1024, 1024, "1K"),
        (2048, 1024, "2K"),
        (2160, 3840, "4K"),
        (None, None, "1K"),
    ])
    def test_tier(self, w, h, expected):
        assert GoogleProvider._nbp_image_size(w, h) == expected


class TestGenerateSizeKwarg:
    def test_size_string_selects_4k_and_aspect(self, provider):
        texts, images = provider.generate(
            prompt="a test", model="gemini-3-pro-image-preview",
            size="2160x3840")
        cfg = provider.client.models.generate_content.call_args.kwargs["config"]
        assert cfg.image_config.image_size == "4K"
        assert cfg.image_config.aspect_ratio == "9:16"
        assert images

    def test_explicit_width_height_beats_size(self, provider):
        provider.generate(
            prompt="a test", model="gemini-3-pro-image-preview",
            size="1024x1024", width=2160, height=3840)
        cfg = provider.client.models.generate_content.call_args.kwargs["config"]
        assert cfg.image_config.image_size == "4K"
        assert cfg.image_config.aspect_ratio == "9:16"


class TestEditImageSizing:
    def test_explicit_size_builds_image_config(self, provider):
        texts, images = provider.edit_image(
            image=_png_bytes(), prompt="edit it",
            model="gemini-3-pro-image-preview", size="2160x3840")
        kwargs = provider.client.models.generate_content.call_args.kwargs
        cfg = kwargs.get("config")
        assert cfg is not None
        assert cfg.image_config.image_size == "4K"
        assert cfg.image_config.aspect_ratio == "9:16"
        assert images

    def test_no_size_keeps_default_behavior(self, provider):
        provider.edit_image(
            image=_png_bytes(), prompt="edit it",
            model="gemini-2.5-flash-image")
        kwargs = provider.client.models.generate_content.call_args.kwargs
        assert kwargs.get("config") is None
