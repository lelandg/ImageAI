import sys
from pathlib import Path

from core.sprite import ml_install

REPO = Path(__file__).resolve().parents[2]


def test_python_supports_rembg_window(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 10, 9, "final", 0))
    assert ml_install.python_supports_rembg() is False
    monkeypatch.setattr(sys, "version_info", (3, 11, 0, "final", 0))
    assert ml_install.python_supports_rembg() is True
    monkeypatch.setattr(sys, "version_info", (3, 13, 2, "final", 0))
    assert ml_install.python_supports_rembg() is True
    monkeypatch.setattr(sys, "version_info", (3, 14, 0, "final", 0))
    assert ml_install.python_supports_rembg() is False


def test_sprite_ml_packages_on_supported_python(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 12, 3, "final", 0))
    packages, index_url = ml_install.sprite_ml_packages()
    assert packages == [ml_install.MEDIAPIPE_SPEC, ml_install.REMBG_SPEC]
    assert index_url == ""


def test_sprite_ml_packages_drops_rembg_on_old_python(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 10, 0, "final", 0))
    packages, _ = ml_install.sprite_ml_packages()
    assert packages == [ml_install.MEDIAPIPE_SPEC]


def test_requirements_file_matches_the_constants():
    path = ml_install.requirements_file()
    assert path == REPO / "requirements-sprite-ml.txt"
    specs = ml_install.parse_requirements(path.read_text(encoding="utf-8"))
    assert specs == [ml_install.MEDIAPIPE_SPEC, ml_install.REMBG_SPEC]


def test_parse_requirements_skips_comments_and_blank_lines():
    text = "# c\n\nfoo>=1  # inline\n  bar[cpu]==2.0\n"
    assert ml_install.parse_requirements(text) == ["foo>=1", "bar[cpu]==2.0"]


def test_forbidden_packages_never_appear():
    """Only real requirement lines count; comments may name bria-rmbg to say it is excluded."""
    specs = []
    for name in ("requirements-sprite-ml.txt", "requirements.txt"):
        specs += ml_install.parse_requirements((REPO / name).read_text(encoding="utf-8"))
    joined = " ".join(specs).lower()
    for forbidden in ("imagequant", "corridorkey", "bria"):
        assert forbidden not in joined
