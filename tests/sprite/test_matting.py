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
    from core import mediapipe_tasks
    monkeypatch.setattr(mediapipe_tasks, "mediapipe_available", lambda: True)
    monkeypatch.setitem(sys.modules, "mediapipe", _fake_module("mediapipe"))
    monkeypatch.setitem(sys.modules, "rembg", _fake_module("rembg"))
    assert matting.available_backends() == {"mediapipe": True, "rembg": True}


def test_ml_alpha_unknown_backend_raises_and_logs(caplog):
    with caplog.at_level("ERROR"):
        with pytest.raises(matting.MattingUnavailable) as info:
            matting.ml_alpha(Image.new("RGB", (4, 4)), "magic", "x", refine_edges=False)
    assert info.value.user_message and "magic" in caplog.text


def test_ml_alpha_mediapipe_broken_install_raises_matting_unavailable(monkeypatch, caplog):
    """Minor 4 regression: ``_installed`` reports True (the name is present in
    ``sys.modules``, per Python's own re-import-blocking convention of setting
    it to None after a failed import), but the actual ``import`` still raises.
    That must surface as ``MattingUnavailable``, not a bare ``ImportError``."""
    monkeypatch.setitem(sys.modules, "mediapipe", None)
    with caplog.at_level("ERROR"):
        with pytest.raises(matting.MattingUnavailable) as info:
            matting.ml_alpha(Image.new("RGB", (4, 4)), "mediapipe", "", refine_edges=False)
    assert info.value.user_message
    assert "mediapipe" in caplog.text.lower()


def test_ml_alpha_rembg_broken_install_raises_matting_unavailable(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "rembg", None)
    with caplog.at_level("ERROR"):
        with pytest.raises(matting.MattingUnavailable) as info:
            matting.ml_alpha(Image.new("RGB", (4, 4)), "rembg", "u2netp", refine_edges=False)
    assert info.value.user_message
    assert "rembg" in caplog.text.lower()


def test_ml_alpha_missing_backend_names_the_install(monkeypatch, caplog):
    monkeypatch.delitem(sys.modules, "rembg", raising=False)
    monkeypatch.setattr(matting, "_installed", lambda name: False)
    with caplog.at_level("ERROR"):
        with pytest.raises(matting.MattingUnavailable) as info:
            matting.ml_alpha(Image.new("RGB", (4, 4)), "rembg", "u2netp", refine_edges=False)
    assert "requirements-sprite-ml.txt" in info.value.user_message


def _mock_tasks_segmenter(monkeypatch, mask, background_mask=None):
    from core import mediapipe_tasks
    seen = {}

    class FakeSegmenter:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            seen["closed"] = True
            # The caller must own a copy before the task releases its memory.
            mask[:] = 0

        def segment(self, array):
            seen["shape"] = array.shape
            masks = [
                types.SimpleNamespace(numpy_view=lambda: mask),
            ]
            if background_mask is not None:
                masks.insert(0, types.SimpleNamespace(numpy_view=lambda: background_mask))
            return types.SimpleNamespace(confidence_masks=masks)

    monkeypatch.setattr(matting, "_installed", lambda name: True)
    monkeypatch.setattr(mediapipe_tasks, "create_image_segmenter", FakeSegmenter)
    monkeypatch.setattr(mediapipe_tasks, "image_from_rgb", lambda rgb: rgb)
    return seen


@pytest.mark.parametrize("singleton_channel", [False, True])
def test_ml_alpha_mediapipe_tasks_preserve_mask_after_close(monkeypatch, singleton_channel):
    rgb, cov = disc_on_field()
    native_mask = cov.astype(np.float32).copy()
    if singleton_channel:
        native_mask = native_mask[:, :, None]
    seen = _mock_tasks_segmenter(monkeypatch, native_mask)
    alpha = matting.ml_alpha(Image.fromarray(rgb), "mediapipe", "", refine_edges=False)
    assert alpha.dtype == np.float32 and alpha.shape == cov.shape
    assert seen == {"shape": rgb.shape, "closed": True}
    assert np.allclose(alpha, cov)


@pytest.mark.parametrize("singleton_channel", [False, True])
def test_mediapipe_alpha_two_confidence_masks_selects_person_last(monkeypatch, singleton_channel):
    rgb, cov = disc_on_field()
    person = cov.astype(np.float32).copy()
    background = 1.0 - person
    if singleton_channel:
        person = person[:, :, None]
        background = background[:, :, None]
    seen = _mock_tasks_segmenter(monkeypatch, person, background)

    alpha = matting._mediapipe_alpha(rgb, refine_edges=False)

    assert alpha.dtype == np.float32 and alpha.shape == cov.shape
    assert seen == {"shape": rgb.shape, "closed": True}
    np.testing.assert_allclose(alpha, cov)
    assert not np.any(person), "The task released its native mask storage"


def test_mediapipe_alpha_legacy_runtime_import_error_is_logged_and_actionable(monkeypatch, caplog):
    from core import mediapipe_tasks

    legacy = _fake_module("mediapipe")
    legacy.__version__ = "0.10.21"
    monkeypatch.setitem(sys.modules, "mediapipe", legacy)

    with pytest.raises(matting.MattingUnavailable, match="Upgrade MediaPipe") as info:
        matting._mediapipe_alpha(np.zeros((4, 4, 3), dtype=np.uint8), refine_edges=False)

    assert isinstance(info.value.__cause__, ImportError)
    assert mediapipe_tasks.MEDIAPIPE_SPEC in info.value.user_message
    assert matting.INSTALL_HINT in info.value.user_message
    assert "Upgrade MediaPipe" in caplog.text


def test_ml_alpha_mediapipe_refine_edges_tightens_the_mask(monkeypatch):
    rgb, cov = disc_on_field()
    soft = np.clip(cov * 0.6 + 0.2, 0, 1).astype(np.float32)
    _mock_tasks_segmenter(monkeypatch, soft.copy())
    raw = matting.ml_alpha(Image.fromarray(rgb), "mediapipe", "", refine_edges=False)
    _mock_tasks_segmenter(monkeypatch, soft.copy())
    tight = matting.ml_alpha(Image.fromarray(rgb), "mediapipe", "", refine_edges=True)
    assert tight[cov == 0].mean() < raw[cov == 0].mean() * 0.5
    assert tight[cov == 1].mean() > raw[cov == 1].mean()
    assert tight.min() >= 0.0 and tight.max() <= 1.0


@pytest.mark.parametrize("mask", [np.zeros((1, 1)), np.full((4, 4), np.nan)])
def test_ml_alpha_mediapipe_rejects_invalid_masks(monkeypatch, mask, caplog):
    _mock_tasks_segmenter(monkeypatch, mask)
    with pytest.raises(matting.MattingUnavailable, match="invalid segmentation mask"):
        matting.ml_alpha(Image.new("RGB", (4, 4)), "mediapipe", "", refine_edges=False)
    assert "invalid segmentation mask" in caplog.text


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


def test_mediapipe_first_use_network_failure_is_logged_and_actionable(monkeypatch, caplog):
    from core import mediapipe_tasks
    monkeypatch.setattr(matting, "_installed", lambda name: True)

    def offline():
        raise ConnectionError("model download unavailable offline")

    monkeypatch.setattr(mediapipe_tasks, "create_image_segmenter", offline)
    with pytest.raises(matting.MattingUnavailable, match="model download unavailable offline"):
        matting.ml_alpha(Image.new("RGB", (4, 4)), "mediapipe", "", refine_edges=False)
    assert "model download unavailable offline" in caplog.text
