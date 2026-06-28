# tests/layout/test_cli_layout_export.py
from argparse import Namespace

import pytest

pytest.importorskip("PySide6")  # export needs Qt; skip in headless-without-Qt envs

import cli.commands.layout as layout_cli
from core.layout import project_io
from core.layout.models import DocumentSpec, PageSpec, Region


class _StubConfig:
    def get_layout_export_dpi(self):
        return 300


def _project(tmp_path):
    doc = DocumentSpec(title="t", pages=[PageSpec(
        page_size_px=(300, 300), background="#FFFFFF",
        regions=[Region(id="r1", kind="image", bbox=(10, 10, 100, 100))])])
    p = tmp_path / "proj.json"
    project_io.save_project(doc, str(p))
    return p


def _args(path, out, dpi=None):
    return Namespace(layout_export=str(path), out=str(out), dpi=dpi)


def test_export_pdf(tmp_path):
    p = _project(tmp_path)
    out = tmp_path / "out.pdf"
    rc = layout_cli.run_export_cmd(_args(p, out), _StubConfig())
    assert rc == 0
    assert out.exists() and out.stat().st_size > 0


def test_export_png(tmp_path):
    p = _project(tmp_path)
    out = tmp_path / "out.png"
    rc = layout_cli.run_export_cmd(_args(p, out), _StubConfig())
    assert rc == 0
    assert out.exists() and out.stat().st_size > 0


def test_export_bad_extension(tmp_path):
    p = _project(tmp_path)
    rc = layout_cli.run_export_cmd(_args(p, tmp_path / "out.gif"), _StubConfig())
    assert rc == 2
