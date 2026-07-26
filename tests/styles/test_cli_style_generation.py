"""--style NAME on the -p generation path."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cli.parser import build_arg_parser
from cli.runner import run_cli
from core.styles.models import Style
from core.styles.store import StyleStore


def _args(*argv):
    return build_arg_parser().parse_args(list(argv))


def _fake_provider():
    prov = MagicMock()
    prov.get_default_model.return_value = "fake-model"
    prov.generate.return_value = (["ok"], [b"PNGDATA"])
    return prov


def _run(tmp_path, *argv):
    store = StyleStore(base_dir=tmp_path / "styles")
    store.save(Style(id="water", name="Water", prompt_text="washes"))
    prov = _fake_provider()
    cfg = MagicMock()
    cfg.get_images_dir.return_value = tmp_path / "out"
    (tmp_path / "out").mkdir(exist_ok=True)
    # Capture the original __init__ before patching: a lambda that calls
    # `StyleStore.__init__` from inside the patch context would look up the
    # (already patched) class attribute and recurse into itself forever.
    _orig_init = StyleStore.__init__
    with patch("cli.runner.get_provider", return_value=prov), \
         patch("cli.runner.resolve_api_key", return_value=("k", "test")), \
         patch("cli.runner.ConfigManager", return_value=cfg), \
         patch("core.styles.store.StyleStore.__init__",
               lambda self, base_dir=None: _orig_init(
                   self, base_dir=tmp_path / "styles")):
        rc = run_cli(_args(*argv))
    return rc, prov, tmp_path / "out"


def test_style_applied_to_generation_prompt(tmp_path):
    rc, prov, out_dir = _run(tmp_path, "-p", "a fox", "--style", "Water")
    assert rc == 0
    sent = prov.generate.call_args.kwargs["prompt"]
    assert sent == "a fox. In this style: washes"


def test_sidecar_keeps_original_prompt_and_provenance(tmp_path):
    rc, prov, out_dir = _run(tmp_path, "-p", "a fox", "--style", "Water")
    sidecars = list(out_dir.glob("*.png.json"))
    assert len(sidecars) == 1
    meta = json.loads(sidecars[0].read_text())
    assert meta["prompt"] == "a fox"  # un-styled
    assert meta["style_applied"]["style_id"] == "water"
    assert meta["style_applied"]["smart_merge_used"] is False


def test_unknown_style_exits_2(tmp_path, capsys):
    rc, _prov, _ = _run(tmp_path, "-p", "a fox", "--style", "Nope")
    assert rc == 2
    assert "Nope" in capsys.readouterr().out
