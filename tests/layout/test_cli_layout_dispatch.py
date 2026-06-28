# tests/layout/test_cli_layout_dispatch.py
# Note: lambdas use dict.update() (returns None) so `None or 0` yields 0.
# Brief used setdefault(..., True) which returns True; True or 0 → True ≠ 0.
from cli.parser import build_arg_parser
from cli.runner import run_cli
import cli.runner as runner


def test_dispatch_routes_design(monkeypatch):
    called = {}
    monkeypatch.setattr("cli.commands.layout.run_design_cmd",
                        lambda args, config: called.update({"design": True}) or 0)
    args = build_arg_parser().parse_args(
        ["--layout-design", "x", "-o", "p.json"])
    assert run_cli(args) == 0
    assert called.get("design")


def test_dispatch_routes_export(monkeypatch):
    called = {}
    monkeypatch.setattr("cli.commands.layout.run_export_cmd",
                        lambda args, config: called.update({"export": True}) or 0)
    args = build_arg_parser().parse_args(
        ["--layout-export", "p.json", "-o", "o.pdf"])
    assert run_cli(args) == 0
    assert called.get("export")
