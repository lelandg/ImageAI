"""run_cli routes style verbs to run_style_cmd; verbs work against a real store."""
from types import SimpleNamespace
from unittest.mock import patch

from cli.parser import build_arg_parser
from cli.runner import run_cli
from core.styles.models import Style
from core.styles.store import StyleStore


def _args(*argv):
    return build_arg_parser().parse_args(list(argv))


def test_run_cli_dispatches_to_style_cmd():
    with patch("cli.commands.style.run_style_cmd", return_value=0) as cmd:
        assert run_cli(_args("--style-list")) == 0
    cmd.assert_called_once()


def test_list_show_delete(tmp_path, capsys):
    from cli.commands.style import run_style_cmd
    store = StyleStore(base_dir=tmp_path / "styles")
    store.save(Style(id="water", name="Water", prompt_text="washes"))
    config = SimpleNamespace()  # unused by these verbs

    with patch("cli.commands.style.StyleStore", return_value=store):
        assert run_style_cmd(_args("--style-list"), config) == 0
        out = capsys.readouterr().out
        assert "water" in out and "Water" in out

        assert run_style_cmd(_args("--style-show", "Water"), config) == 0
        assert "washes" in capsys.readouterr().out

        assert run_style_cmd(_args("--style-show", "nope"), config) == 2
        assert run_style_cmd(_args("--style-delete", "water"), config) == 0
        assert store.get("water") is None
        assert run_style_cmd(_args("--style-delete", "water"), config) == 2
