"""Unit tests for the Gemini Omni Interactions-API client.

These tests mock the google.genai client entirely — no network is used. They
lock the documented request shape (response_format={"type":"video",...} dict,
reference-image content list, previous_interaction_id passthrough) and the
response parsing (interaction.output_video primary, steps-walk fallback, inline
base64 vs Files-API URI), plus the polling and download-failure branches.
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


def test_uri_download_fails_cleanly_if_never_active(tmp_path):
    # Files API stays PROCESSING forever -> must fail, not write a partial file.
    interaction = _FakeInteraction(
        output_video=_FakeVideoContent(data=None, uri="files/omnivid123")
    )
    client = _make_client(interaction)
    downloaded = {"called": False}

    def _download(file):
        downloaded["called"] = True
        return MP4_BYTES

    processing = pytypes.SimpleNamespace(state=pytypes.SimpleNamespace(name="PROCESSING"))
    client.client.files = pytypes.SimpleNamespace(get=lambda name: processing, download=_download)
    client.polling_interval = 0
    client.timeout = 0  # deadline already passed -> loop body never marks ACTIVE

    out = tmp_path / "out.mp4"
    result = client.generate_video(OmniGenerationConfig(prompt="a sunset"), out)

    assert result.success is False
    assert downloaded["called"] is False  # never downloaded a non-ACTIVE file
    assert not out.exists()


def test_uri_download_fails_on_files_failed_state(tmp_path):
    interaction = _FakeInteraction(
        output_video=_FakeVideoContent(data=None, uri="files/omnivid123")
    )
    client = _make_client(interaction)
    failed = pytypes.SimpleNamespace(state=pytypes.SimpleNamespace(name="FAILED"))
    client.client.files = pytypes.SimpleNamespace(
        get=lambda name: failed,
        download=lambda file: MP4_BYTES,
    )
    client.polling_interval = 0

    result = client.generate_video(OmniGenerationConfig(prompt="a sunset"), tmp_path / "out.mp4")
    assert result.success is False


def test_await_terminal_polls_until_completed(tmp_path):
    # create() returns in_progress; get() flips to completed with output_video.
    b64 = base64.b64encode(MP4_BYTES).decode("ascii")
    in_progress = _FakeInteraction(id="int_poll", status="in_progress")
    completed = _FakeInteraction(id="int_poll", status="completed",
                                 output_video=_FakeVideoContent(data=b64))

    client = OmniClient(api_key="test-key")
    res = _FakeInteractionsResource(in_progress)
    res.get = lambda interaction_id: completed  # type: ignore[assignment]
    client.client = pytypes.SimpleNamespace(interactions=res, files=None)
    client.polling_interval = 0

    out = tmp_path / "out.mp4"
    result = client.generate_video(OmniGenerationConfig(prompt="a sunset"), out)

    assert result.success is True
    assert out.read_bytes() == MP4_BYTES


def test_reference_image_mime_detection(tmp_path):
    webp = tmp_path / "ref.webp"
    webp.write_bytes(b"RIFFfakewebp")
    cfg = OmniGenerationConfig(prompt="go", task="image_to_video", reference_image=webp)
    kw = cfg.to_interaction_kwargs()
    assert kw["input"][0]["mime_type"] == "image/webp"


# --- Multi-reference images (reference_to_video) -----------------------------

def _write_png(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"\x89PNG\r\n\x1a\nfakepng-" + name.encode())
    return p


def test_multiple_reference_images_build_content_list(tmp_path):
    cat = _write_png(tmp_path, "cat.png")
    yarn = _write_png(tmp_path, "yarn.png")
    cfg = OmniGenerationConfig(prompt="A cat playfully batting at a ball of yarn.",
                               reference_images=[cat, yarn])
    kw = cfg.to_interaction_kwargs()
    # Documented shape: N image items followed by exactly one text item.
    assert [item["type"] for item in kw["input"]] == ["image", "image", "text"]
    assert kw["input"][2]["text"] == "A cat playfully batting at a ball of yarn."
    # Two subject references => reference_to_video (inferred).
    assert cfg.task == "reference_to_video"


def test_single_reference_image_infers_image_to_video(tmp_path):
    ref = _write_png(tmp_path, "ref.png")
    cfg = OmniGenerationConfig(prompt="make it move", reference_images=[ref])
    assert cfg.task == "image_to_video"


def test_legacy_reference_image_folds_into_list(tmp_path):
    ref = _write_png(tmp_path, "ref.png")
    cfg = OmniGenerationConfig(prompt="go", task="image_to_video", reference_image=ref)
    assert cfg.reference_images == [ref]
    kw = cfg.to_interaction_kwargs()
    assert [item["type"] for item in kw["input"]] == ["image", "text"]


def test_too_many_reference_images_rejected(tmp_path):
    refs = [_write_png(tmp_path, f"r{i}.png") for i in range(4)]
    with pytest.raises(ValueError, match="reference image"):
        OmniGenerationConfig(prompt="x", reference_images=refs)


def test_previous_interaction_id_infers_edit_task():
    cfg = OmniGenerationConfig(prompt="make the violin invisible",
                               previous_interaction_id="int_prev")
    assert cfg.task == "edit"


def test_validate_config_checks_all_reference_images_exist(tmp_path):
    ok = _write_png(tmp_path, "ok.png")
    missing = tmp_path / "missing.png"
    cfg = OmniGenerationConfig(prompt="x", reference_images=[ok])
    cfg.reference_images.append(missing)  # bypass __post_init__ to hit validate_config
    client = OmniClient(api_key="test-key")
    is_valid, error = client.validate_config(cfg)
    assert is_valid is False
    assert "missing.png" in error


# --- Explicit generation_config.video_config.task ----------------------------

def test_task_sent_in_generation_config_text_to_video():
    cfg = OmniGenerationConfig(prompt="a sunset")
    kw = cfg.to_interaction_kwargs()
    assert kw["generation_config"] == {"video_config": {"task": "text_to_video"}}


def test_task_sent_in_generation_config_reference_to_video(tmp_path):
    refs = [_write_png(tmp_path, f"s{i}.png") for i in range(2)]
    cfg = OmniGenerationConfig(prompt="together in a park", reference_images=refs)
    kw = cfg.to_interaction_kwargs()
    # Disambiguates subject references from a first-frame image (identical
    # input shapes otherwise).
    assert kw["generation_config"]["video_config"]["task"] == "reference_to_video"
