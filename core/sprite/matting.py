# core/sprite/matting.py
"""ML background removal and difference matting for sprite frames.

Both ML backends are optional extras (requirements-sprite-ml.txt) and load
lazily. Nothing here imports Qt.

Design: Plans/2026-08-29-sprite-tab-design.md §1.7, §4.3.
"""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

import cv2
import numpy as np
from PIL import Image

from core.paths import get_data_paths

logger = logging.getLogger(__name__)

ML_BACKENDS = ("mediapipe", "rembg")
DEFAULT_REMBG_MODEL = "isnet-anime"
INSTALL_HINT = ("Install the optional ML extras: "
                "python -m pip install -r requirements-sprite-ml.txt "
                "(or use Sprite > Install ML backends).")

# Never ship weights, never make a model a dependency. ``default_ok`` False means the
# UI must not preselect the model and must show its license.
REMBG_MODELS: Dict[str, Dict[str, Any]] = {
    "isnet-anime": {"size_mb": 168, "license": "MIT", "default_ok": True,
                    "description": "Anime / illustrated characters (default)"},
    "u2netp": {"size_mb": 4.4, "license": "Apache-2.0", "default_ok": True,
               "description": "Small general model, fast download"},
    "bria-rmbg": {"size_mb": 1000, "license": "CC BY-NC (paid commercial)", "default_ok": False,
                  "description": "High quality; non-commercial license, never default"},
}

_REMBG_SESSIONS: Dict[str, Any] = {}


class MattingUnavailable(RuntimeError):
    """A matting backend is missing or refused the request. ``user_message`` is UI-safe."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


def _installed(name: str) -> bool:
    """True when ``name`` is importable. Does not import it."""
    if name in sys.modules:
        return True
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def available_backends() -> Dict[str, bool]:
    return {name: _installed(name) for name in ML_BACKENDS}


def rembg_model_dir() -> Path:
    """Where rembg keeps its ONNX models: <Models root>/cache/rembg (moves with the group)."""
    path = get_data_paths().model_cache("rembg")
    path.mkdir(parents=True, exist_ok=True)
    return path


def clear_sessions() -> None:
    _REMBG_SESSIONS.clear()


def _fail(message: str) -> MattingUnavailable:
    logger.error("Matting unavailable: %s", message)
    return MattingUnavailable(message)


def _tighten(mask: np.ndarray) -> np.ndarray:
    """Cheap edge refinement for a blurry segmentation mask: contrast stretch + 1 px blur."""
    stretched = np.clip((mask - 0.5) * 4.0 + 0.5, 0.0, 1.0).astype(np.float32)
    return np.clip(cv2.GaussianBlur(stretched, (0, 0), sigmaX=1.0), 0.0, 1.0).astype(np.float32)


def _mediapipe_alpha(rgb: np.ndarray, refine_edges: bool) -> np.ndarray:
    if not _installed("mediapipe"):
        raise _fail(f"MediaPipe is not installed. {INSTALL_HINT}")
    import mediapipe as mp  # lazy: heavy import
    solutions = getattr(mp, "solutions", None)
    if solutions is None or not hasattr(solutions, "selfie_segmentation"):
        raise _fail("This MediaPipe build has no mp.solutions.selfie_segmentation; "
                    "install mediapipe>=0.10.0,<0.10.15 from requirements-sprite-ml.txt.")
    with solutions.selfie_segmentation.SelfieSegmentation(model_selection=1) as seg:
        result = seg.process(np.ascontiguousarray(rgb))
    mask = getattr(result, "segmentation_mask", None)
    if mask is None:
        raise _fail("MediaPipe returned no segmentation mask for this frame.")
    alpha = np.clip(np.asarray(mask, dtype=np.float32), 0.0, 1.0)
    return _tighten(alpha) if refine_edges else alpha


def _rembg_alpha(image: Image.Image, model: str, refine_edges: bool) -> np.ndarray:
    if not _installed("rembg"):
        raise _fail(f"rembg is not installed (needs Python 3.11-3.13). {INSTALL_HINT}")
    if model not in REMBG_MODELS:
        raise _fail(f"Unknown rembg model {model!r}; choose one of {sorted(REMBG_MODELS)}.")
    info = REMBG_MODELS[model]
    if not info["default_ok"]:
        logger.warning("rembg model %s is %s - non-commercial use only; you chose it explicitly.",
                       model, info["license"])
    os.environ["U2NET_HOME"] = str(rembg_model_dir())
    from rembg import new_session, remove  # lazy: heavy import
    session = _REMBG_SESSIONS.get(model)
    if session is None:
        logger.info("rembg: loading model %s (%s MB) from %s", model, info["size_mb"], rembg_model_dir())
        session = new_session(model)
        _REMBG_SESSIONS[model] = session
    mask = remove(image.convert("RGB"), session=session, only_mask=True, alpha_matting=bool(refine_edges))
    return np.asarray(mask.convert("L"), dtype=np.float32) / 255.0


def ml_alpha(image: Image.Image, backend: str, model: str, *, refine_edges: bool) -> np.ndarray:
    """Foreground alpha (float32 HxW, 0..1) from an ML backend."""
    if backend == "mediapipe":
        return _mediapipe_alpha(np.asarray(image.convert("RGB")), refine_edges)
    if backend == "rembg":
        return _rembg_alpha(image, model or DEFAULT_REMBG_MODEL, refine_edges)
    raise _fail(f"Unknown matting backend {backend!r}; choose one of {ML_BACKENDS}.")


# --- difference matte (image route) ---------------------------------------------------

def difference_matte(on_white: Image.Image, on_black: Image.Image) -> Image.Image:
    """Recover RGBA from the same subject rendered on white and on black.

    alpha = 1 - mean(white - black); color = black / alpha (0 where alpha is 0).
    """
    white = np.asarray(on_white.convert("RGB"), dtype=np.float32) / 255.0
    black = np.asarray(on_black.convert("RGB"), dtype=np.float32) / 255.0
    if white.shape != black.shape:
        raise ValueError(f"Size mismatch: on_white {white.shape[:2]} vs on_black {black.shape[:2]}")
    alpha = np.clip(1.0 - (white - black).mean(axis=2), 0.0, 1.0)
    safe = np.maximum(alpha, 1.0 / 255.0)[:, :, None]
    color = np.where(alpha[:, :, None] > 0.0, black / safe, 0.0)
    rgba = np.concatenate([np.clip(color, 0.0, 1.0), alpha[:, :, None]], axis=2)
    return Image.fromarray(np.round(rgba * 255.0).astype(np.uint8))
