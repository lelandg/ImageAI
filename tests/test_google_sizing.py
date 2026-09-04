"""Google provider sizing: CLI --size parity and edit_image image_config.

Regression tests for the bug where ``size="WxH"`` (as sent by cli/runner.py)
was silently ignored by GoogleProvider.generate(), so Nano Banana Pro CLI
runs always came back at the 1K tier, and GoogleProvider.edit_image()
ignored sizing entirely.
"""

import io
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import core.paths as paths_mod
from core.paths import DataPaths
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
    # generate() and edit_image() both save a DEBUG_RAW_GEMINI_* image under
    # get_data_paths().generated(). That call returns a process-wide singleton,
    # so patching Path.home here did nothing once an earlier test had built the
    # singleton against the real user directory — the suite wrote a file into
    # ~/.config/ImageAI/generated on every run. Replace the singleton instead.
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))
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


class TestDebugImageLocation:
    def test_the_debug_image_follows_the_configured_images_root(
        self, provider, tmp_path
    ):
        """generate() saves DEBUG_RAW_GEMINI_* under the Images root.

        The write must go through get_data_paths(), so a user who moved the
        Images group keeps it there — and the test suite keeps it out of the
        developer's real user directory.
        """
        provider.generate(prompt="a test", model="gemini-2.5-flash-image")
        written = list((tmp_path / "generated").glob("DEBUG_RAW_GEMINI_*"))
        assert written, "no debug image was written under the configured root"


class TestLazyClientInit:
    """Every entry point builds the client when it is missing."""

    ENTRY_POINTS = ["edit_image", "edit_image_region", "generate_video",
                    "create_chat_session", "validate_auth", "start_edit_session"]

    @pytest.mark.parametrize("entry", ENTRY_POINTS)
    def test_entry_point_builds_client_when_missing(self, provider, monkeypatch,
                                                    tmp_path, entry):
        import providers.google as google_mod

        built = []

        def factory(**kwargs):
            client = MagicMock()
            client.api_key = kwargs.get("api_key")
            client.models.generate_content.return_value = _fake_response(_png_bytes())
            built.append(client)
            return client

        monkeypatch.setattr(google_mod, "genai", SimpleNamespace(Client=factory))
        monkeypatch.setattr(google_mod, "GENAI_AVAILABLE", True)
        provider = GoogleProvider({"api_key": "k", "auth_mode": "api-key"})
        provider.client = None
        provider._client_mode = None
        png = _png_bytes()

        if entry == "edit_image":
            provider.edit_image(png, "edit it", "gemini-2.5-flash-image")
        elif entry == "edit_image_region":
            provider.edit_image_region(png, (0, 0, 4, 4), "edit it",
                                       model="gemini-2.5-flash-image")
        elif entry == "generate_video":
            frame = tmp_path / "frame.png"
            frame.write_bytes(png)
            provider.generate_video("a clip", frame, 6.0)
        elif entry == "create_chat_session":
            provider.create_chat_session("gemini-3-pro-image-preview")
        elif entry == "validate_auth":
            ok, msg = provider.validate_auth()
            assert ok, msg
        elif entry == "start_edit_session":
            assert provider.start_edit_session(png)

        assert built, f"{entry} did not build a client"
        assert provider.client is built[-1]
        assert built[-1].api_key == "k"
        assert provider._client_mode == "api_key"


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
