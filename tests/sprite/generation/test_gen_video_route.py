"""Tests for core/sprite/generation/video_route.py (video-route-rendering)."""
from pathlib import Path

import pytest

from core.sprite.generation.errors import ProviderError
from core.sprite.generation.prompts import CHROMA_SUFFIX, LOOP_SUFFIX
from core.sprite.generation.video_route import (
    RenderRequest,
    build_omni_config,
    build_veo_config,
    validate_generation_settings,
)
from core.sprite.project import GenerationSettings
from core.video.veo_client import VeoModel

VEO_STD = VeoModel.VEO_3_1_GENERATE.value
VEO_FAST = VeoModel.VEO_3_1_FAST.value


@pytest.fixture
def request_for(png_file, make_action, tmp_path):
    def _make(provider="omni", refs=2, **settings):
        plate = png_file("plate.png", color=(0, 255, 0, 255))
        ref_paths = [png_file(f"ref{i}.png") for i in range(refs)]
        gen = GenerationSettings(provider=provider, **settings)
        return RenderRequest(action=make_action(), plate=plate, refs=ref_paths,
                             settings=gen, out_mp4=tmp_path / "clips" / "a1.mp4")
    return _make


# --- Omni ---------------------------------------------------------------------

def test_omni_config_prompt_refs_and_aspect(request_for):
    req = request_for("omni", refs=1, aspect_ratio="9:16")
    cfg = build_omni_config(req)
    assert cfg.aspect_ratio == "9:16"
    assert cfg.reference_images[0] == req.plate
    assert cfg.reference_images[1:] == req.refs
    assert cfg.task == "reference_to_video"
    assert CHROMA_SUFFIX.format(color_name="green", hex="#00FF00") in cfg.prompt
    assert LOOP_SUFFIX in cfg.prompt
    assert "4 seconds" in cfg.prompt
    assert "9:16" not in cfg.prompt and "transparent" not in cfg.prompt.lower()


def test_omni_config_caps_reference_images_at_three(request_for):
    req = request_for("omni", refs=4)
    cfg = build_omni_config(req)
    assert len(cfg.reference_images) == 3
    assert cfg.reference_images[0] == req.plate


def test_omni_config_uses_settings_model_and_no_loop_suffix(request_for, make_action):
    req = request_for("omni", refs=0, model="omni-custom")
    req.action = make_action(loop=False, duration_s=12)
    cfg = build_omni_config(req)
    assert cfg.model == "omni-custom"
    assert cfg.task == "image_to_video"
    assert LOOP_SUFFIX not in cfg.prompt
    assert "10 seconds" in cfg.prompt   # snapped to the Omni maximum


def test_omni_config_rejects_unsupported_aspect(request_for):
    req = request_for("omni", aspect_ratio="4:3")
    with pytest.raises(ProviderError, match="aspect"):
        build_omni_config(req)


def test_validate_generation_settings_reports_illegal_aspect():
    message = validate_generation_settings(GenerationSettings(provider="omni", aspect_ratio="1:1"))
    assert message is not None
    assert "1:1" in message and "omni" in message and "16:9" in message
    fast = validate_generation_settings(GenerationSettings(provider="veo", model=VEO_FAST,
                                                           aspect_ratio="1:1"))
    assert fast is not None and VEO_FAST in fast


def test_validate_generation_settings_accepts_legal_aspect():
    assert validate_generation_settings(GenerationSettings(provider="omni", aspect_ratio="16:9")) is None
    assert validate_generation_settings(GenerationSettings(provider="veo", model=VEO_STD,
                                                           aspect_ratio="1:1")) is None


def test_validate_generation_settings_reports_unknown_provider():
    message = validate_generation_settings(GenerationSettings(provider="sora"))
    assert message is not None and "sora" in message


# --- Veo ----------------------------------------------------------------------

def test_veo_config_loop_conditioning_forces_first_last_and_8s(request_for):
    seen = []
    req = request_for("veo", model=VEO_FAST, duration_s=4, loop_conditioning=True,
                      include_audio=False, resolution="720p")
    cfg = build_veo_config(req, log=seen.append)
    assert cfg.model == VeoModel.VEO_3_1_FAST
    assert cfg.image == req.plate and cfg.last_frame == req.plate
    assert cfg.duration == 8
    assert cfg.include_audio is False
    assert cfg.reference_images == req.refs
    assert any("8" in line and "loop" in line.lower() for line in seen)


def test_veo_config_without_loop_conditioning_snaps_duration(request_for, make_action):
    req = request_for("veo", model=VEO_FAST, loop_conditioning=False, resolution="720p")
    req.action = make_action(duration_s=5)
    cfg = build_veo_config(req)
    assert cfg.image is None and cfg.last_frame is None
    assert cfg.duration == 6


def test_veo_config_default_model_and_resolution_fallback(request_for):
    req = request_for("veo", model="", resolution="1080p", loop_conditioning=False)
    cfg = build_veo_config(req)
    assert cfg.model == VeoModel.VEO_3_1_GENERATE
    assert cfg.duration == 8 and cfg.resolution == "1080p"
    fast = request_for("veo", model=VEO_FAST, resolution="1080p", loop_conditioning=False)
    cfg_fast = build_veo_config(fast)
    assert cfg_fast.resolution == "720p"     # Fast is 720p only; snapped with a log line


def test_veo_config_rejects_unknown_model(request_for):
    req = request_for("veo", model="veo-9-imaginary")
    with pytest.raises(ProviderError, match="Unknown Veo model"):
        build_veo_config(req)


def test_veo_config_prompt_has_chroma_and_no_sizes(request_for):
    cfg = build_veo_config(request_for("veo", model=VEO_STD, resolution="1080p"))
    assert CHROMA_SUFFIX.format(color_name="green", hex="#00FF00") in cfg.prompt
    assert "16:9" not in cfg.prompt and "px" not in cfg.prompt.lower()


# --- render / refine / trim ---------------------------------------------------
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
from PIL import Image

from core.sprite.extract import ExtractResult
from core.sprite.generation import video_route
from core.sprite.generation.errors import QuotaExceeded
from core.sprite.generation.video_route import (
    find_loop_seam,
    refine_action,
    render_action,
    seam_scores,
    trim_to_loop,
)
from core.sprite.pipeline import CancelToken, Cancelled
from core.sprite.project import ClipRecord


def _omni_client(monkeypatch, *, success=True, error=None, interaction_id="int-1",
                 generation_time=1.5, has_synthid=True, metadata=None):
    """Install a fake Omni client factory; returns the MagicMock client."""
    client = MagicMock()
    captured = {}
    metadata = {"safety_ratings": "none"} if metadata is None else metadata

    def generate_video(cfg, out_path, cancel_check=None):
        captured["cfg"] = cfg
        captured["cancel_check"] = cancel_check
        if success:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_bytes(b"omni-mp4")
        return SimpleNamespace(success=success, video_path=Path(out_path) if success else None,
                               interaction_id=interaction_id, error=error,
                               generation_time=generation_time, has_synthid=has_synthid,
                               metadata=metadata)
    client.generate_video.side_effect = generate_video
    client.captured = captured
    monkeypatch.setattr(video_route, "_make_omni_client", lambda api_key: client)
    return client


def test_render_omni_writes_clip_record_and_sidecar(request_for, monkeypatch):
    client = _omni_client(monkeypatch)
    req = request_for("omni", refs=1)
    seen, progress = [], []
    record = render_action(req, api_key="k", log=seen.append,
                           progress=lambda *a: progress.append(a))
    assert isinstance(record, ClipRecord)
    assert record.path == req.out_mp4 and req.out_mp4.read_bytes() == b"omni-mp4"
    assert record.provider == "omni" and record.operation_id == "int-1"
    assert record.params["aspect_ratio"] == "16:9" and record.params["duration_s"] == 4
    assert record.prompt == client.captured["cfg"].prompt
    assert record.actual_usd is None
    assert callable(client.captured["cancel_check"]) or client.captured["cancel_check"] is None
    sidecar = req.out_mp4.with_suffix(".json")
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    assert meta["status"] == "completed" and meta["operation_id"] == "int-1"
    assert meta["action_id"] == "a1" and meta["prompt"] == record.prompt
    assert "estimated_usd" in meta
    joined = "\n".join(seen)
    assert "=== Video render request" in joined and record.prompt in joined
    assert progress[0][0] == "render" and progress[-1][1:3] == (1, 1)
    # The full provider response (not just a one-line summary) must be logged.
    assert "=== Video render response" in joined
    assert "operation_id=int-1" in joined
    assert "generation_time=1.5" in joined and "has_synthid=True" in joined
    assert '"safety_ratings": "none"' in joined


def test_render_veo_copies_native_file(request_for, monkeypatch, tmp_path):
    native = tmp_path / "veo_native.mp4"
    native.write_bytes(b"veo-mp4")
    client = MagicMock()
    client.generate_video.return_value = SimpleNamespace(
        success=True, video_path=native, video_url="https://example/veo.mp4", operation_id="op-7",
        error=None, generation_time=4.2, has_synthid=True, metadata={"model_version": "veo-3.1"})
    factory_args = {}
    def factory(api_key, auth_mode):
        factory_args.update(api_key=api_key, auth_mode=auth_mode)
        return client
    monkeypatch.setattr(video_route, "_make_veo_client", factory)
    req = request_for("veo", model=VEO_FAST, resolution="720p", loop_conditioning=True)
    seen = []
    record = render_action(req, api_key="k", auth_mode="api-key", log=seen.append)
    assert factory_args == {"api_key": "k", "auth_mode": "api-key"}
    assert req.out_mp4.read_bytes() == b"veo-mp4"
    assert record.provider == "veo" and record.model == VEO_FAST
    assert record.operation_id == "op-7"
    assert record.params["duration_s"] == 8 and record.params["loop_conditioning"] is True
    assert record.params["last_frame"] == str(req.plate)
    assert "cancel_check" in client.generate_video.call_args.kwargs
    # The full provider response (not just a one-line summary) must be logged.
    joined = "\n".join(seen)
    assert "=== Video render response" in joined
    assert "operation_id=op-7" in joined and "video_url=https://example/veo.mp4" in joined
    assert "generation_time=4.2" in joined and "has_synthid=True" in joined
    assert '"model_version": "veo-3.1"' in joined


def test_render_cancelled_raises_and_keeps_operation_id(request_for, monkeypatch):
    _omni_client(monkeypatch, success=False, error="cancelled", interaction_id="int-9")
    req = request_for("omni")
    seen = []
    with pytest.raises(Cancelled, match="int-9"):
        render_action(req, api_key="k", log=seen.append)
    meta = json.loads(req.out_mp4.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["status"] == "cancelled" and meta["operation_id"] == "int-9"
    assert any("int-9" in line for line in seen)


def test_render_failure_is_classified_with_operation_id(request_for, monkeypatch):
    _omni_client(monkeypatch, success=False, error="429 RESOURCE_EXHAUSTED", interaction_id="int-3")
    seen = []
    with pytest.raises(QuotaExceeded) as info:
        render_action(request_for("omni"), api_key="k", log=seen.append)
    assert info.value.operation_id == "int-3"
    assert any("failed" in line.lower() for line in seen)


def test_render_raw_exception_is_classified(request_for, monkeypatch):
    client = MagicMock()
    client.generate_video.side_effect = RuntimeError("blocked by safety filters")
    monkeypatch.setattr(video_route, "_make_omni_client", lambda api_key: client)
    from core.sprite.generation.errors import SafetyRefusal
    with pytest.raises(SafetyRefusal):
        render_action(request_for("omni"), api_key="k")


def test_render_checks_token_before_calling_provider(request_for, monkeypatch):
    client = _omni_client(monkeypatch)
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        render_action(request_for("omni"), api_key="k", token=token)
    client.generate_video.assert_not_called()


def test_render_cancel_check_reflects_token(request_for, monkeypatch):
    client = _omni_client(monkeypatch)
    token = CancelToken()
    render_action(request_for("omni"), api_key="k", token=token)
    check = client.captured["cancel_check"]
    assert check() is False
    token.cancel()
    assert check() is True


def test_render_unknown_provider(request_for):
    with pytest.raises(ProviderError, match="Unknown sprite video provider"):
        render_action(request_for("sora"), api_key="k")


def _clip(tmp_path, provider="omni", operation_id="int-1"):
    path = tmp_path / "clips" / "a1.mp4"
    return ClipRecord(path=path, provider=provider, model="omni-model", operation_id=operation_id,
                      params={"aspect_ratio": "9:16", "duration_s": 4}, prompt="p",
                      generated_at="2026-08-29T10:00:00", estimated_usd=0.4, actual_usd=None)


def test_refine_requires_omni_clip_with_interaction_id(tmp_path):
    with pytest.raises(ProviderError, match="Omni"):
        refine_action(_clip(tmp_path, provider="veo"), "longer cape", tmp_path / "r.mp4", api_key="k")
    with pytest.raises(ProviderError, match="interaction"):
        refine_action(_clip(tmp_path, operation_id=None), "longer cape", tmp_path / "r.mp4", api_key="k")


def test_refine_chains_previous_interaction(tmp_path, monkeypatch):
    client = _omni_client(monkeypatch, interaction_id="int-2")
    monkeypatch.setattr(video_route, "price_per_second", lambda *a, **k: 0.1)
    out = tmp_path / "clips" / "a1.r1.mp4"
    record = refine_action(_clip(tmp_path), "make the cape longer, transparent look",
                           out, api_key="k")
    cfg = client.captured["cfg"]
    assert cfg.previous_interaction_id == "int-1" and cfg.task == "edit"
    assert cfg.aspect_ratio == "9:16" and cfg.model == "omni-model"
    assert "transparent" not in cfg.prompt
    assert record.operation_id == "int-2" and record.path == out
    assert record.params["refined_from"].endswith("a1.mp4")
    assert record.params["previous_interaction_id"] == "int-1"
    assert record.estimated_usd == pytest.approx(0.4)
    meta = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["status"] == "completed" and meta["operation_id"] == "int-2"


def _square_frames(tmp_path, count=10, seam_at=7):
    """Frame k shows a square shifted by k px; frame ``seam_at`` repeats frame 0."""
    paths = []
    for k in range(count):
        shift = 0 if k == seam_at else k
        arr = np.zeros((32, 32, 3), dtype=np.uint8)
        arr[8:16, 4 + shift:12 + shift] = (255, 255, 255)
        path = tmp_path / f"{k:04d}.png"
        Image.fromarray(arr).save(path)
        paths.append(path)
    return paths


def test_seam_scores_and_find_loop_seam(tmp_path):
    frames = _square_frames(tmp_path)
    scores = seam_scores(frames)
    assert scores[0] == 0.0 and scores[7] == 0.0 and all(0.0 <= s <= 1.0 for s in scores)
    assert scores[9] > 0.0
    idx, score = find_loop_seam(frames)
    assert idx == 7 and score == 0.0
    # Search window starts at 50%; frame 0 is never a candidate.
    assert find_loop_seam(frames[:2]) == (1, scores[1])


def test_trim_to_loop_cuts_at_best_seam(tmp_path, monkeypatch):
    frames = _square_frames(tmp_path)  # seam_at=7 (default): frame 7 repeats frame 0
    monkeypatch.setattr(video_route, "extract_frames",
                        lambda video, out_dir, settings, **kw: ExtractResult(
                            frames=frames, source_fps=10.0, source_frames=10, duration_s=1.0))
    cuts = []
    def fake_cut(src, dst, end_s):
        cuts.append((Path(src), Path(dst), end_s))
        Path(dst).write_bytes(b"cut")
    monkeypatch.setattr(video_route, "_cut_video", fake_cut)
    clip = tmp_path / "a1.mp4"
    clip.write_bytes(b"full")
    out, score = trim_to_loop(clip, tmp_path / "a1.loop.mp4")
    fps = 10.0
    seam_index = 7  # matches test_seam_scores_and_find_loop_seam's find_loop_seam(frames) == (7, 0.0)
    # Exclusive cut: end_s covers frames 0..seam_index-1 only, so the near-duplicate
    # seam frame (index 7, which matches frame 0) is excluded from the trimmed clip.
    assert cuts == [(clip, out, pytest.approx(seam_index / fps))]
    assert score == 0.0 and out.read_bytes() == b"cut"
    kept_frame_count = round(cuts[0][2] * fps)
    last_kept_index = kept_frame_count - 1
    assert last_kept_index == seam_index - 1


def test_trim_to_loop_copies_when_tail_is_already_seamless(tmp_path, monkeypatch):
    frames = _square_frames(tmp_path, count=6, seam_at=5)
    monkeypatch.setattr(video_route, "extract_frames",
                        lambda video, out_dir, settings, **kw: ExtractResult(
                            frames=frames, source_fps=10.0, source_frames=6, duration_s=0.6))
    monkeypatch.setattr(video_route, "_cut_video",
                        lambda *a: (_ for _ in ()).throw(AssertionError("must not cut")))
    clip = tmp_path / "a1.mp4"
    clip.write_bytes(b"full")
    out, score = trim_to_loop(clip, tmp_path / "a1.loop.mp4", seam_threshold=0.08)
    assert out.read_bytes() == b"full" and score == 0.0
