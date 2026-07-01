from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from cli.commands.video import _run_omni, _run_veo, VideoCliError


def _ns(**kw):
    base = dict(prompt="p", aspect="16:9", ref_image=None, last_frame=None,
                extend=None, video_model=None, api_key="k", api_key_file=None,
                auth_mode="api-key")
    base.update(kw)
    return Namespace(**base)


def test_run_omni_returns_normalized_result(tmp_path):
    out = tmp_path / "o.mp4"
    fake = MagicMock()
    fake.generate_video.return_value = MagicMock(
        success=True, video_path=out, interaction_id="int-1", error=None)
    fake_cfg = MagicMock(aspect_ratio="16:9", model="gemini-omni-flash-preview")
    with patch("core.video.omni_client.OmniClient", return_value=fake), \
         patch("core.video.omni_client.OmniGenerationConfig", return_value=fake_cfg), \
         patch("cli.commands.video.resolve_api_key", return_value=("k", "config")):
        res = _run_omni(_ns(), out)
    assert res["success"] is True
    assert res["provider"] == "omni"
    assert res["operation_id"] == "int-1"
    fake.generate_video.assert_called_once()


def test_run_omni_rejects_gcloud():
    with patch("cli.commands.video.resolve_api_key", return_value=("k", "config")):
        with pytest.raises(VideoCliError, match="api-key auth only"):
            _run_omni(_ns(auth_mode="gcloud"), Path("o.mp4"))


def test_run_omni_missing_key_errors():
    with patch("cli.commands.video.resolve_api_key", return_value=(None, "none")):
        with pytest.raises(VideoCliError, match="No Google API key"):
            _run_omni(_ns(api_key=None), Path("o.mp4"))


def test_run_veo_copies_output(tmp_path):
    src = tmp_path / "veo_native.mp4"
    src.write_bytes(b"vid")
    out = tmp_path / "final.mp4"
    fake = MagicMock()
    fake.generate_video.return_value = MagicMock(
        success=True, video_path=src, operation_id="op-1", error=None)
    with patch("core.video.veo_client.VeoClient", return_value=fake), \
         patch("cli.commands.video.resolve_api_key", return_value=("k", "config")):
        res = _run_veo(_ns(), out)
    assert res["success"] is True
    assert out.exists() and out.read_bytes() == b"vid"
    assert res["operation_id"] == "op-1"


def test_run_veo_extend_calls_extend(tmp_path):
    prev = tmp_path / "prev.mp4"
    prev.write_bytes(b"old")
    out = tmp_path / "ext.mp4"
    native = tmp_path / "veo_ext.mp4"
    native.write_bytes(b"new")
    fake = MagicMock()
    fake.extend_video.return_value = MagicMock(
        success=True, video_path=native, operation_id="op-2", error=None)
    with patch("core.video.veo_client.VeoClient", return_value=fake), \
         patch("cli.commands.video.resolve_api_key", return_value=("k", "config")):
        res = _run_veo(_ns(extend=str(prev)), out)
    fake.extend_video.assert_called_once()
    assert res["success"] is True


def test_run_veo_extend_missing_file_errors(tmp_path):
    with patch("cli.commands.video.resolve_api_key", return_value=("k", "config")):
        with pytest.raises(VideoCliError, match="extend video not found"):
            _run_veo(_ns(extend=str(tmp_path / "nope.mp4")), tmp_path / "o.mp4")
