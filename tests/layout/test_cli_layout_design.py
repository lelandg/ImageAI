# tests/layout/test_cli_layout_design.py
from argparse import Namespace

import cli.commands.layout as layout_cli
from core.layout import project_io


class _StubConfig:
    def get_layout_llm_provider(self):
        return "google"


def _args(**kw):
    base = dict(layout_design="a comic page", out=None, content_kind="comic",
                page_size="Letter", orientation="portrait", dpi=300,
                layout_llm_provider="google", layout_llm_model=None)
    base.update(kw)
    return Namespace(**base)


def test_design_writes_project(tmp_path, monkeypatch):
    out = tmp_path / "proj.iaiproj.json"
    fake_json = (
        '{"layout": {"regions": ['
        '{"id": "r1", "kind": "image", "bbox": [0,0,500,500]}]}}'
    )
    monkeypatch.setattr(layout_cli.designer, "run_completion",
                        lambda *a, **k: fake_json)
    rc = layout_cli.run_design_cmd(_args(out=str(out)), _StubConfig())
    assert rc == 0
    assert out.exists()
    doc = project_io.load_project(str(out))
    assert doc.content_kind == "comic"
    assert any(r.id == "r1" for r in doc.pages[0].regions)


def test_design_requires_out():
    rc = layout_cli.run_design_cmd(_args(out=None), _StubConfig())
    assert rc == 2


def test_design_llm_failure_returns_3(tmp_path, monkeypatch):
    out = tmp_path / "p.json"
    def _boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(layout_cli.designer, "run_completion", _boom)
    rc = layout_cli.run_design_cmd(_args(out=str(out)), _StubConfig())
    assert rc == 3
