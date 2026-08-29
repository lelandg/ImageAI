# tests/sprite/test_matting.py
import importlib.machinery
import os
import sys
import types

import numpy as np
import pytest
from PIL import Image

from core.paths import get_data_paths
from core.sprite import matting
from tests.sprite.keying_fixtures import disc_on_field


def _fake_module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__spec__ = importlib.machinery.ModuleSpec(name, None)
    return mod


@pytest.fixture(autouse=True)
def _fresh_sessions():
    matting.clear_sessions()
    yield
    matting.clear_sessions()


def test_rembg_models_table_marks_bria_non_default():
    assert matting.REMBG_MODELS["isnet-anime"]["default_ok"] is True
    assert matting.REMBG_MODELS["u2netp"]["default_ok"] is True
    assert matting.REMBG_MODELS["bria-rmbg"]["default_ok"] is False
    assert "NC" in matting.REMBG_MODELS["bria-rmbg"]["license"]
    for info in matting.REMBG_MODELS.values():
        assert set(info) >= {"size_mb", "license", "default_ok", "description"}
    assert matting.DEFAULT_REMBG_MODEL == "isnet-anime"
    assert matting.REMBG_MODELS[matting.DEFAULT_REMBG_MODEL]["default_ok"] is True


def test_rembg_model_dir_is_the_models_cache():
    assert matting.rembg_model_dir() == get_data_paths().model_cache("rembg")
    assert matting.rembg_model_dir().is_dir()


def test_available_backends_reports_missing_modules(monkeypatch):
    monkeypatch.delitem(sys.modules, "mediapipe", raising=False)
    monkeypatch.delitem(sys.modules, "rembg", raising=False)
    monkeypatch.setattr(matting, "_installed", lambda name: False)
    assert matting.available_backends() == {"mediapipe": False, "rembg": False}


def test_available_backends_sees_injected_modules(monkeypatch):
    monkeypatch.setitem(sys.modules, "mediapipe", _fake_module("mediapipe"))
    monkeypatch.setitem(sys.modules, "rembg", _fake_module("rembg"))
    assert matting.available_backends() == {"mediapipe": True, "rembg": True}


def test_ml_alpha_unknown_backend_raises_and_logs(caplog):
    with caplog.at_level("ERROR"):
        with pytest.raises(matting.MattingUnavailable) as info:
            matting.ml_alpha(Image.new("RGB", (4, 4)), "magic", "x", refine_edges=False)
    assert info.value.user_message and "magic" in caplog.text


def test_ml_alpha_missing_backend_names_the_install(monkeypatch, caplog):
    monkeypatch.delitem(sys.modules, "rembg", raising=False)
    monkeypatch.setattr(matting, "_installed", lambda name: False)
    with caplog.at_level("ERROR"):
        with pytest.raises(matting.MattingUnavailable) as info:
            matting.ml_alpha(Image.new("RGB", (4, 4)), "rembg", "u2netp", refine_edges=False)
    assert "requirements-sprite-ml.txt" in info.value.user_message


def test_ml_alpha_mediapipe_uses_selfie_segmentation(monkeypatch):
    rgb, cov = disc_on_field()
    seen = {}

    class FakeSeg:
        def __init__(self, model_selection):
            seen["model_selection"] = model_selection

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def process(self, array):
            seen["shape"] = array.shape
            return types.SimpleNamespace(segmentation_mask=cov.astype(np.float32))

    mp = _fake_module("mediapipe")
    mp.solutions = types.SimpleNamespace(selfie_segmentation=types.SimpleNamespace(SelfieSegmentation=FakeSeg))
    monkeypatch.setitem(sys.modules, "mediapipe", mp)
    alpha = matting.ml_alpha(Image.fromarray(rgb), "mediapipe", "", refine_edges=False)
    assert alpha.dtype == np.float32 and alpha.shape == cov.shape
    assert seen["model_selection"] == 1 and seen["shape"] == rgb.shape
    assert np.allclose(alpha, cov)


def test_ml_alpha_mediapipe_refine_edges_tightens_the_mask(monkeypatch):
    rgb, cov = disc_on_field()
    soft = np.clip(cov * 0.6 + 0.2, 0, 1).astype(np.float32)   # blurry mask: 0.2 background, 0.8 subject

    class FakeSeg:
        def __init__(self, model_selection):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def process(self, array):
            return types.SimpleNamespace(segmentation_mask=soft)

    mp = _fake_module("mediapipe")
    mp.solutions = types.SimpleNamespace(selfie_segmentation=types.SimpleNamespace(SelfieSegmentation=FakeSeg))
    monkeypatch.setitem(sys.modules, "mediapipe", mp)
    raw = matting.ml_alpha(Image.fromarray(rgb), "mediapipe", "", refine_edges=False)
    tight = matting.ml_alpha(Image.fromarray(rgb), "mediapipe", "", refine_edges=True)
    # Means, not extremes: the 1 px blur leaves a small halo right next to the edge.
    assert tight[cov == 0].mean() < raw[cov == 0].mean() * 0.5
    assert tight[cov == 1].mean() > raw[cov == 1].mean()
    assert tight.min() >= 0.0 and tight.max() <= 1.0


def test_ml_alpha_rembg_sets_model_dir_and_caches_sessions(monkeypatch):
    rgb, cov = disc_on_field()
    monkeypatch.delenv("U2NET_HOME", raising=False)
    made = []
    removed = []

    def new_session(model_name):
        made.append(model_name)
        return object()

    def remove(img, session=None, only_mask=False, alpha_matting=False, **kw):
        removed.append((only_mask, alpha_matting, os.environ.get("U2NET_HOME")))
        return Image.fromarray((cov * 255).astype(np.uint8))      # 2-D uint8 -> mode "L"

    rembg = _fake_module("rembg")
    rembg.new_session = new_session
    rembg.remove = remove
    monkeypatch.setitem(sys.modules, "rembg", rembg)
    a1 = matting.ml_alpha(Image.fromarray(rgb), "rembg", "u2netp", refine_edges=False)
    a2 = matting.ml_alpha(Image.fromarray(rgb), "rembg", "u2netp", refine_edges=True)
    assert made == ["u2netp"]                              # session cached
    assert removed[0][:2] == (True, False) and removed[1][:2] == (True, True)
    assert removed[0][2] == str(matting.rembg_model_dir())
    assert a1.dtype == np.float32 and np.allclose(a1, cov, atol=1 / 255) and np.allclose(a2, cov, atol=1 / 255)


def test_ml_alpha_rembg_warns_on_non_default_model(monkeypatch, caplog):
    rgb, cov = disc_on_field()
    rembg = _fake_module("rembg")
    rembg.new_session = lambda name: object()
    rembg.remove = lambda img, **kw: Image.fromarray((cov * 255).astype(np.uint8))
    monkeypatch.setitem(sys.modules, "rembg", rembg)
    with caplog.at_level("WARNING"):
        matting.ml_alpha(Image.fromarray(rgb), "rembg", "bria-rmbg", refine_edges=False)
    assert "non-commercial" in caplog.text.lower()


def test_ml_alpha_rembg_unknown_model_raises(monkeypatch):
    rembg = _fake_module("rembg")
    rembg.new_session = lambda name: object()
    rembg.remove = lambda img, **kw: Image.new("L", (4, 4))
    monkeypatch.setitem(sys.modules, "rembg", rembg)
    with pytest.raises(matting.MattingUnavailable):
        matting.ml_alpha(Image.new("RGB", (4, 4)), "rembg", "not-a-model", refine_edges=False)
