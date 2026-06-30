"""Unit tests for the Gemini Omni Interactions-API client.

These tests mock the google.genai client entirely — no network is used. They
lock the request shape (response_modalities=['video'], reference-image content
list, previous_interaction_id passthrough) and the response parsing (walking
interaction.steps -> ModelOutputStep -> VideoContent, inline base64 vs URI).
"""

import base64
import types as pytypes

import pytest

from core.video.omni_client import (
    OmniClient,
    OmniGenerationConfig,
    OmniGenerationResult,
)


# --- Fakes that mimic the google.genai Interactions response shape ----------

class _FakeVideoContent:
    def __init__(self, data=None, uri=None, mime_type="video/mp4"):
        self.type = "video"
        self.data = data
        self.uri = uri
        self.mime_type = mime_type


class _FakeModelOutputStep:
    def __init__(self, content):
        self.type = "model_output"
        self.content = content


class _FakeInteraction:
    def __init__(self, id="int_123", status="completed", steps=None, output_video=None):
        self.id = id
        self.status = status
        self.steps = steps or []
        # Documented primary path: interaction.output_video (a VideoContent).
        self.output_video = output_video


class _FakeInteractionsResource:
    def __init__(self, response):
        self._response = response
        self.create_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._response

    def get(self, interaction_id):
        return self._response


class _FakeGenaiClient:
    def __init__(self, response):
        self.interactions = _FakeInteractionsResource(response)
        self.files = None


def _make_client(response):
    client = OmniClient(api_key="test-key")
    client.client = _FakeGenaiClient(response)
    return client


MP4_BYTES = b"\x00\x00\x00\x18ftypmp42fake-omni-video"


# --- Config validation ------------------------------------------------------

def test_text_to_video_kwargs_match_documented_shape():
    cfg = OmniGenerationConfig(prompt="a marble rolling down a track",
                               model="gemini-omni-flash-preview", aspect_ratio="16:9")
    kw = cfg.to_interaction_kwargs()
    assert kw["model"] == "gemini-omni-flash-preview"
    assert kw["input"] == "a marble rolling down a track"
    # Documented shape: response_format is a DICT {"type": "video", ...}; there
    # is no response_modalities key.
    assert kw["response_format"] == {"type": "video", "aspect_ratio": "16:9"}
    assert "response_modalities" not in kw
    # Aspect ratio is never embedded in the prompt text.
    assert "16:9" not in kw["input"]
    assert "previous_interaction_id" not in kw


def test_invalid_aspect_ratio_rejected():
    with pytest.raises(ValueError, match="aspect_ratio"):
        OmniGenerationConfig(prompt="x", aspect_ratio="4:3")


def test_invalid_task_rejected():
    with pytest.raises(ValueError, match="task"):
        OmniGenerationConfig(prompt="x", task="audio_to_video")


def test_image_to_video_requires_reference_image():
    with pytest.raises(ValueError, match="reference_image"):
        OmniGenerationConfig(prompt="x", task="image_to_video")


def test_image_to_video_builds_content_list(tmp_path):
    img = tmp_path / "ref.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfakepng")
    cfg = OmniGenerationConfig(prompt="make it move", task="image_to_video",
                               reference_image=img)
    kw = cfg.to_interaction_kwargs()
    assert isinstance(kw["input"], list)
    assert kw["input"][0]["type"] == "image"
    assert kw["input"][0]["mime_type"] == "image/png"
    assert kw["input"][1] == {"type": "text", "text": "make it move"}


def test_previous_interaction_id_passthrough():
    cfg = OmniGenerationConfig(prompt="make the violin invisible",
                               task="edit", previous_interaction_id="int_prev")
    kw = cfg.to_interaction_kwargs()
    assert kw["previous_interaction_id"] == "int_prev"


def test_default_model_resolves_to_omni():
    cfg = OmniGenerationConfig(prompt="x")
    assert "omni" in cfg.model.lower()


# --- generate_video_async: inline base64 delivery ---------------------------

def test_generate_inline_base64_writes_mp4(tmp_path):
    b64 = base64.b64encode(MP4_BYTES).decode("ascii")
    # Documented primary path: interaction.output_video carries the base64 data.
    interaction = _FakeInteraction(output_video=_FakeVideoContent(data=b64))
    client = _make_client(interaction)
    out = tmp_path / "out.mp4"
    cfg = OmniGenerationConfig(prompt="a sunset")

    result = client.generate_video(cfg, out)

    assert isinstance(result, OmniGenerationResult)
    assert result.success is True
    assert result.video_path == out
    assert out.read_bytes() == MP4_BYTES
    assert result.interaction_id == "int_123"
    # The request used the documented dict response_format.
    assert client.client.interactions.create_calls[0]["response_format"] == {
        "type": "video", "aspect_ratio": "16:9"
    }


def test_generate_reads_video_from_steps_fallback(tmp_path):
    # Defensive fallback: no output_video, but a step carries the video content.
    b64 = base64.b64encode(MP4_BYTES).decode("ascii")
    interaction = _FakeInteraction(
        output_video=None,
        steps=[_FakeModelOutputStep([_FakeVideoContent(data=b64)])],
    )
    client = _make_client(interaction)
    out = tmp_path / "out.mp4"

    result = client.generate_video(OmniGenerationConfig(prompt="a sunset"), out)

    assert result.success is True
    assert out.read_bytes() == MP4_BYTES


def test_generate_failed_status_returns_error(tmp_path):
    interaction = _FakeInteraction(status="failed", steps=[])
    client = _make_client(interaction)
    cfg = OmniGenerationConfig(prompt="a sunset")

    result = client.generate_video(cfg, tmp_path / "out.mp4")

    assert result.success is False
    assert "failed" in result.error.lower()


def test_generate_no_video_content_returns_error(tmp_path):
    interaction = _FakeInteraction(status="completed", steps=[
        _FakeModelOutputStep([])  # No video item.
    ])
    client = _make_client(interaction)
    cfg = OmniGenerationConfig(prompt="a sunset")

    result = client.generate_video(cfg, tmp_path / "out.mp4")

    assert result.success is False
    assert "no video" in result.error.lower()


def test_no_client_configured_returns_error(tmp_path):
    client = OmniClient(api_key=None)  # No client built.
    cfg = OmniGenerationConfig(prompt="a sunset")

    result = client.generate_video(cfg, tmp_path / "out.mp4")

    assert result.success is False
    assert "api key" in result.error.lower()


# --- URI delivery (Files API poll + download) -------------------------------

def test_generate_uri_delivery_downloads(tmp_path):
    interaction = _FakeInteraction(
        output_video=_FakeVideoContent(data=None, uri="files/omnivid123")
    )
    client = _make_client(interaction)

    # Fake Files API: state ACTIVE immediately, download returns bytes.
    active = pytypes.SimpleNamespace(state=pytypes.SimpleNamespace(name="ACTIVE"))
    client.client.files = pytypes.SimpleNamespace(
        get=lambda name: active,
        download=lambda file: MP4_BYTES,
    )
    client.polling_interval = 0

    out = tmp_path / "out.mp4"
    result = client.generate_video(OmniGenerationConfig(prompt="a sunset"), out)

    assert result.success is True
    assert out.read_bytes() == MP4_BYTES
