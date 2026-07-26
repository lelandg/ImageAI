"""--style-create: image collection, derivation, persistence."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PIL import Image

from cli.parser import build_arg_parser
from cli.commands.style import StyleCliError, _collect_images, run_style_cmd
from core.styles.models import DESCRIPTOR_KEYS
from core.styles.store import StyleStore


def _args(*argv):
    return build_arg_parser().parse_args(list(argv))


def _mk(path, size=(32, 32)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (5, 5, 5)).save(path)
    return path


def test_collect_images_files_dirs_globs(tmp_path):
    a = _mk(tmp_path / "a.png")
    _mk(tmp_path / "d" / "b.jpg")
    _mk(tmp_path / "d" / "c.webp")
    (tmp_path / "d" / "notes.txt").write_text("x")
    got = _collect_images([str(a), str(tmp_path / "d"),
                           str(tmp_path / "d" / "*.jpg")])  # glob dupes b.jpg
    assert [p.name for p in got] == ["a.png", "b.jpg", "c.webp"]


def test_collect_images_none_raises(tmp_path):
    with pytest.raises(StyleCliError):
        _collect_images([str(tmp_path / "empty-dir")])


def test_create_derives_and_saves(tmp_path):
    imgs = [_mk(tmp_path / f"i{n}.png") for n in range(4)]
    store = StyleStore(base_dir=tmp_path / "styles")
    derived = {"descriptor": {k: "v" for k in DESCRIPTOR_KEYS},
               "prompt_text": "derived text"}
    svc = SimpleNamespace(provider="openai", model="m",
                          derive=lambda paths, progress_cb=None: derived)
    with patch("cli.commands.style.StyleStore", return_value=store), \
         patch("cli.commands.style.StyleAnalysisService", return_value=svc):
        rc = run_style_cmd(
            _args("--style-create", "Water", "--style-images", str(tmp_path)),
            SimpleNamespace())
    assert rc == 0
    saved = store.get_by_name("Water")
    assert saved is not None
    assert saved.prompt_text == "derived text"
    assert len(saved.reference_images) == 4
    assert saved.exemplars == saved.reference_images[:3]  # auto-pick first 3
    assert saved.source["image_count"] == 4


def test_create_requires_images_flag(tmp_path, capsys):
    rc = run_style_cmd(_args("--style-create", "W"), SimpleNamespace())
    assert rc == 2
    assert "--style-images" in capsys.readouterr().out


def test_create_analysis_failure_saves_nothing(tmp_path):
    _mk(tmp_path / "i.png")
    store = StyleStore(base_dir=tmp_path / "styles")
    from core.styles.analyzer import StyleAnalysisError
    with patch("cli.commands.style.StyleStore", return_value=store), \
         patch("cli.commands.style.StyleAnalysisService",
               side_effect=StyleAnalysisError("No openai API key configured")):
        rc = run_style_cmd(
            _args("--style-create", "W", "--style-images", str(tmp_path)),
            SimpleNamespace())
    assert rc == 2
    assert store.list_styles() == []
