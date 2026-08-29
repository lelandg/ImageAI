"""Cancel hook for OmniClient polling (sprite design §1.1)."""
import asyncio
import types as pytypes

import pytest

from core.video.omni_client import OmniClient, OmniGenerationConfig, OmniPollCancelled


class _Interaction:
    def __init__(self, id="int_1", status="in_progress"):
        self.id = id
        self.status = status
        self.steps = []
        self.output_video = None


class _Resource:
    def __init__(self, created, polled=None):
        self._created = created
        self._polled = polled or created
        self.create_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._created

    def get(self, interaction_id):
        return self._polled


def _client(resource):
    client = OmniClient(api_key="test-key")
    client.client = pytypes.SimpleNamespace(interactions=resource, files=None)
    client.polling_interval = 0
    return client


def test_await_terminal_raises_when_cancel_fires():
    client = _client(_Resource(_Interaction()))
    with pytest.raises(OmniPollCancelled):
        asyncio.run(client._await_terminal(_Interaction(), cancel_check=lambda: True))


def test_await_terminal_returns_terminal_interaction_without_cancel():
    done = _Interaction(status="completed")
    client = _client(_Resource(_Interaction(), polled=done))
    result = asyncio.run(client._await_terminal(_Interaction(), cancel_check=lambda: False))
    assert result is done


def test_generate_video_reports_cancelled_and_keeps_interaction_id(tmp_path):
    resource = _Resource(_Interaction(id="int_poll"))
    client = _client(resource)
    calls = {"n": 0}
    def cancel():
        calls["n"] += 1
        return calls["n"] > 1  # pre-flight check passes; the poll loop sees the cancel
    result = client.generate_video(OmniGenerationConfig(prompt="a sunset"),
                                   tmp_path / "out.mp4", cancel_check=cancel)
    assert result.success is False
    assert result.error == "cancelled"
    assert result.interaction_id == "int_poll"
    assert len(resource.create_calls) == 1
    assert not (tmp_path / "out.mp4").exists()


def test_generate_video_skips_create_when_cancelled_before_start(tmp_path):
    resource = _Resource(_Interaction())
    client = _client(resource)
    fired = {"n": 0}
    def cancel():
        fired["n"] += 1
        return True
    result = client.generate_video(OmniGenerationConfig(prompt="a sunset"),
                                   tmp_path / "out.mp4", cancel_check=cancel)
    assert result.success is False and result.error == "cancelled"
    assert resource.create_calls == []
    assert result.interaction_id is None


def test_generate_video_without_cancel_check_still_works(tmp_path):
    import base64
    done = _Interaction(status="completed")
    done.output_video = pytypes.SimpleNamespace(
        type="video", data=base64.b64encode(b"mp4bytes").decode("ascii"),
        uri=None, mime_type="video/mp4")
    client = _client(_Resource(done))
    result = client.generate_video(OmniGenerationConfig(prompt="a sunset"), tmp_path / "o.mp4")
    assert result.success is True
