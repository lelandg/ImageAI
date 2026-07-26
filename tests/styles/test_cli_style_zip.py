"""--style-export / --style-import round trip through the CLI."""
from types import SimpleNamespace
from unittest.mock import patch

from cli.parser import build_arg_parser
from cli.commands.style import run_style_cmd
from core.styles.models import Style
from core.styles.store import StyleStore


def _args(*argv):
    return build_arg_parser().parse_args(list(argv))


def test_export_then_import(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    store.save(Style(id="water", name="Water", prompt_text="washes"))
    zip_path = tmp_path / "water.zip"
    with patch("cli.commands.style.StyleStore", return_value=store):
        assert run_style_cmd(
            _args("--style-export", "Water", "-o", str(zip_path)),
            SimpleNamespace()) == 0
        assert zip_path.exists()
        assert run_style_cmd(
            _args("--style-import", str(zip_path)), SimpleNamespace()) == 0
    assert store.get("water-2") is not None


def test_export_requires_out(tmp_path, capsys):
    store = StyleStore(base_dir=tmp_path / "styles")
    store.save(Style(id="water", name="Water"))
    with patch("cli.commands.style.StyleStore", return_value=store):
        assert run_style_cmd(_args("--style-export", "Water"),
                             SimpleNamespace()) == 2
    assert "-o" in capsys.readouterr().out


def test_import_missing_file(tmp_path):
    with patch("cli.commands.style.StyleStore",
               return_value=StyleStore(base_dir=tmp_path / "s")):
        assert run_style_cmd(_args("--style-import", str(tmp_path / "no.zip")),
                             SimpleNamespace()) == 2
