"""Cancel hook for VeoClient polling (sprite design §1.1)."""
import asyncio
import logging
from types import SimpleNamespace

import pytest

from core.video.veo_client import (
    VeoClient,
    VeoGenerationConfig,
    VeoModel,
    VeoPollCancelled,
)


def _client():
    # Bypass __init__: no network region lookup, no genai client required.
    client = VeoClient.__new__(VeoClient)
    client.logger = logging.getLogger("test.veo")
    client.poll_interval = 0
    client.person_generation_allowed = True
    client.region = "US"
    client.auth_mode = "api-key"
    client.api_key = "k"
    return client


def _pending_operation():
    return SimpleNamespace(name="op-1", done=False, error=None, response=None)


def test_poll_raises_when_cancel_fires():
    client = _client()
    op = _pending_operation()
    client.client = SimpleNamespace(operations=SimpleNamespace(get=lambda o: o))
    with pytest.raises(VeoPollCancelled):
        asyncio.run(client._poll_for_completion(op, max_wait=5, cancel_check=lambda: True))


def test_poll_finishes_when_cancel_never_fires():
    client = _client()
    video = SimpleNamespace(uri="https://example.invalid/v.mp4", video_bytes=None)
    done = SimpleNamespace(name="op-1", done=True, error=None,
                           response=SimpleNamespace(generated_videos=[SimpleNamespace(video=video)]))
    pending = _pending_operation()
    client.client = SimpleNamespace(operations=SimpleNamespace(get=lambda o: done))
    result = asyncio.run(client._poll_for_completion(pending, max_wait=5, cancel_check=lambda: False))
    assert result == "https://example.invalid/v.mp4"


def test_poll_returns_finished_video_even_if_cancel_fires_after_done():
    client = _client()
    video = SimpleNamespace(uri="https://example.invalid/v.mp4", video_bytes=None)
    done = SimpleNamespace(name="op-1", done=True, error=None,
                           response=SimpleNamespace(generated_videos=[SimpleNamespace(video=video)]))
    calls = {"n": 0}
    def cancel():
        calls["n"] += 1
        return calls["n"] > 1  # first check False, later True
    client.client = SimpleNamespace(operations=SimpleNamespace(get=lambda o: done))
    result = asyncio.run(client._poll_for_completion(done, max_wait=5, cancel_check=cancel))
    assert result == "https://example.invalid/v.mp4"


def test_generate_video_reports_cancelled_and_keeps_operation_id():
    pytest.importorskip("google.genai")
    client = _client()
    started = []
    def generate_videos(**kwargs):
        started.append(kwargs)
        return _pending_operation()
    client.client = SimpleNamespace(
        models=SimpleNamespace(generate_videos=generate_videos),
        operations=SimpleNamespace(get=lambda o: o),
    )
    cfg = VeoGenerationConfig(model=VeoModel.VEO_3_1_FAST, prompt="p", duration=4,
                              resolution="720p", include_audio=False)
    calls = {"n": 0}
    def cancel():
        calls["n"] += 1
        return calls["n"] > 1  # pre-flight check passes; the poll loop sees the cancel
    result = client.generate_video(cfg, cancel_check=cancel)
    assert result.success is False
    assert result.error == "cancelled"
    assert result.operation_id == "op-1"
    assert len(started) == 1


def test_generate_video_skips_provider_call_when_cancelled_before_start():
    pytest.importorskip("google.genai")
    client = _client()
    started = []
    client.client = SimpleNamespace(
        models=SimpleNamespace(generate_videos=lambda **kw: started.append(kw)),
        operations=SimpleNamespace(get=lambda o: o),
    )
    fired = {"n": 0}
    def cancel():
        fired["n"] += 1
        return True
    cfg = VeoGenerationConfig(model=VeoModel.VEO_3_1_FAST, prompt="p", duration=4,
                              resolution="720p", include_audio=False)
    # Fire before the request is sent: the pre-flight check runs first.
    result = client.generate_video(cfg, cancel_check=cancel)
    assert result.success is False and result.error == "cancelled"
    assert started == []
    assert result.operation_id is None


def test_generate_video_without_cancel_check_keeps_old_signature():
    pytest.importorskip("google.genai")
    client = _client()
    client.client = SimpleNamespace(
        models=SimpleNamespace(generate_videos=lambda **kw: SimpleNamespace(
            name="op-2", done=True, error="boom", response=None)),
        operations=SimpleNamespace(get=lambda o: o),
    )
    cfg = VeoGenerationConfig(model=VeoModel.VEO_3_1_FAST, prompt="p", duration=4,
                              resolution="720p", include_audio=False)
    result = client.generate_video(cfg)
    assert result.success is False and result.error != "cancelled"
