# tests/layout/test_cli_layout_fill.py
from argparse import Namespace
from pathlib import Path

import cli.commands.layout as layout_cli
from core.layout import project_io
from core.layout.models import DocumentSpec, PageSpec, Region


class _StubConfig:
    def __init__(self, images_dir):
        self._d = images_dir
    def get_images_dir(self):
        return self._d


class _FakeProvider:
    def get_default_model(self):
        return "fake-model"
    def generate(self, prompt, model=None, **kwargs):
        return ([], [b"PNGBYTES"])


def _project(tmp_path):
    doc = DocumentSpec(title="t", pages=[PageSpec(
        page_size_px=(500, 500),
        regions=[
            Region(id="r1", kind="image", bbox=(0, 0, 200, 200), prompt="a cat"),
            Region(id="r2", kind="image", bbox=(0, 0, 200, 200), prompt=""),  # skipped
            Region(id="t1", kind="text", bbox=(0, 0, 200, 50), text="hi"),    # ignored
        ])])
    p = tmp_path / "proj.json"
    project_io.save_project(doc, str(p))
    return p


def _args(path, **kw):
    base = dict(layout_fill=str(path), out=None, provider="google", model=None,
                api_key="dummy", api_key_file=None, auth_mode="api-key")
    base.update(kw)
    return Namespace(**base)


def test_fill_sets_image_ref_and_saves(tmp_path, monkeypatch):
    images = tmp_path / "images"; images.mkdir()
    p = _project(tmp_path)
    monkeypatch.setattr(layout_cli, "get_provider", lambda prov, cfg: _FakeProvider())
    rc = layout_cli.run_fill_cmd(_args(p), _StubConfig(images))
    assert rc == 0
    doc = project_io.load_project(str(p))  # saved in-place
    r1 = next(r for r in doc.pages[0].regions if r.id == "r1")
    r2 = next(r for r in doc.pages[0].regions if r.id == "r2")
    assert r1.image_ref and Path(r1.image_ref).exists()
    assert not r2.image_ref  # no prompt -> skipped


def test_fill_failure_returns_4(tmp_path, monkeypatch):
    images = tmp_path / "images"; images.mkdir()
    p = _project(tmp_path)
    class _Boom(_FakeProvider):
        def generate(self, prompt, model=None, **kwargs):
            raise RuntimeError("api error")
    monkeypatch.setattr(layout_cli, "get_provider", lambda prov, cfg: _Boom())
    rc = layout_cli.run_fill_cmd(_args(p), _StubConfig(images))
    assert rc == 4
