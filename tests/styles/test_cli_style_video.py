"""--style on the video CLI (Gemini Omni + Veo)."""
import json
from argparse import Namespace
from unittest.mock import patch

from cli.commands.video import _resolve_style, run_video_cmd, VideoCliError
from core.styles.models import Style
from core.styles.store import StyleStore


def _ns(**kw):
    base = dict(prompt="a fox", out=None, aspect="16:9", ref_image=None, last_frame=None,
                extend=None, video_model=None, api_key="k", api_key_file=None,
                auth_mode="api-key", video_provider="veo", json=False, style=None)
    base.update(kw)
    return Namespace(**base)


def _seed_store(tmp_path, style=None):
    store = StyleStore(base_dir=tmp_path / "styles")
    store.save(style or Style(id="water", name="Water", prompt_text="washes"))
    return store


def _patched_store_init(tmp_path):
    """Redirect StyleStore()'s default base_dir into tmp_path (mirrors
    tests/styles/test_cli_style_generation.py's pattern for the same reason:
    capture the un-patched __init__ before patching to avoid infinite recursion)."""
    _orig_init = StyleStore.__init__
    return patch("core.styles.store.StyleStore.__init__",
                 lambda self, base_dir=None: _orig_init(self, base_dir=tmp_path / "styles"))


def _ok(out):
    return {"success": True, "output_path": str(out), "provider": "veo",
            "model": "veo-3.1-generate-001", "aspect_ratio": "16:9",
            "operation_id": "op-1", "error": None}


# ---- _resolve_style (unit) -------------------------------------------------

def test_resolve_style_none_when_flag_absent():
    assert _resolve_style(_ns(style=None)) is None


def test_resolve_style_returns_known_style(tmp_path):
    _seed_store(tmp_path)
    with _patched_store_init(tmp_path):
        style = _resolve_style(_ns(style="Water"))
    assert style is not None
    assert style.id == "water"


def test_resolve_style_unknown_name_raises_with_available_names(tmp_path):
    _seed_store(tmp_path)
    with _patched_store_init(tmp_path):
        try:
            _resolve_style(_ns(style="Nope"))
            assert False, "expected VideoCliError"
        except VideoCliError as e:
            assert "Nope" in str(e)
            assert "Water" in str(e)


# ---- run_video_cmd wiring (no real clients invoked: _run_veo is mocked) ----

def test_run_video_cmd_unknown_style_exits_2(tmp_path, capsys):
    _seed_store(tmp_path)
    out = tmp_path / "v.mp4"
    with _patched_store_init(tmp_path):
        rc = run_video_cmd(_ns(out=str(out), style="Nope", json=True))
    assert rc == 2
    obj = json.loads(capsys.readouterr().out)
    assert "Nope" in obj["error"]
    assert not out.with_suffix(".json").exists()  # no generation attempted


def test_run_video_cmd_styles_prompt_before_dispatch(tmp_path):
    """The prompt reaching the provider dispatch is styled text-only."""
    _seed_store(tmp_path)
    out = tmp_path / "v.mp4"
    captured = {}

    def _fake_run_veo(args, out_path):
        captured["prompt"] = args.prompt
        return _ok(out)

    with _patched_store_init(tmp_path), \
         patch("cli.commands.video._run_veo", side_effect=_fake_run_veo):
        rc = run_video_cmd(_ns(out=str(out), style="Water"))
    assert rc == 0
    assert captured["prompt"] == "a fox. In this style: washes"


def test_run_video_cmd_no_style_leaves_prompt_unstyled(tmp_path):
    out = tmp_path / "v.mp4"
    captured = {}

    def _fake_run_veo(args, out_path):
        captured["prompt"] = args.prompt
        return _ok(out)

    with patch("cli.commands.video._run_veo", side_effect=_fake_run_veo):
        rc = run_video_cmd(_ns(out=str(out)))
    assert rc == 0
    assert captured["prompt"] == "a fox"


def test_run_video_cmd_adds_style_applied_to_payload(tmp_path):
    _seed_store(tmp_path)
    out = tmp_path / "v.mp4"
    with _patched_store_init(tmp_path), \
         patch("cli.commands.video._run_veo", return_value=_ok(out)):
        rc = run_video_cmd(_ns(out=str(out), style="Water"))
    assert rc == 0
    data = json.loads(out.with_suffix(".json").read_text())
    # Unified provenance shape (issue #37): same dict as image sidecars.
    assert data["style_applied"]["style_id"] == "water"
    assert data["style_applied"]["smart_merge_used"] is False
    assert data["style_applied"]["exemplars_attached"] == 0


def test_run_video_cmd_no_style_omits_style_applied(tmp_path):
    out = tmp_path / "v.mp4"
    with patch("cli.commands.video._run_veo", return_value=_ok(out)):
        rc = run_video_cmd(_ns(out=str(out)))
    assert rc == 0
    data = json.loads(out.with_suffix(".json").read_text())
    assert "style_applied" not in data
