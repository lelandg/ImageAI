# core/sprite/keying.py
"""Chroma keying, despill, and alpha cleanup for sprite frames.

Pure numpy / OpenCV / Pillow. No Qt. Every function is stateless. Arrays:
``rgb`` is uint8 HxWx3 (an HxWx4 input is accepted and its alpha ignored),
``alpha`` is float32 HxW in 0..1 where 0 means keyed out.

Design: Plans/2026-08-29-sprite-tab-design.md §4.3.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

from core.sprite.models import FrameMeta
from core.sprite.project import KeySettings, OutputProfile

logger = logging.getLogger(__name__)

KEY_METHODS = ("chroma", "ml", "none")
DESPILL_MODES = ("none", "average", "double", "limit")
OVERRIDE_KEYS = ("key_color", "tolerance", "softness")

# BT.601 full-range chroma and luma weights. A constant offset on all three
# RGB channels changes Y only; Cb and Cr stay the same.
_CB = np.array([-0.168736, -0.331264, 0.5], dtype=np.float32)
_CR = np.array([0.5, -0.418688, -0.081312], dtype=np.float32)
_Y = np.array([0.299, 0.587, 0.114], dtype=np.float32)


class KeyingError(RuntimeError):
    """A keying step failed. ``user_message`` is safe to show in the UI or CLI."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


# --- colors ------------------------------------------------------------------

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Parse ``#RRGGBB``, ``RRGGBB``, or ``#RGB``. Raise ValueError otherwise."""
    text = str(hex_color).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
        raise ValueError(f"Not a #RRGGBB color: {hex_color!r}")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def rgb_to_hex(rgb: Sequence[int]) -> str:
    r, g, b = (max(0, min(255, int(round(v)))) for v in rgb[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


# --- array helpers -----------------------------------------------------------

def _as_float_rgb(rgb: np.ndarray) -> np.ndarray:
    arr = np.asarray(rgb)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError(f"Expected an HxWx3 RGB array, got shape {arr.shape}")
    return arr[:, :, :3].astype(np.float32)


def _chroma(rgb_f: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return (Cb, Cr) arrays for a float RGB array (any leading shape)."""
    return rgb_f @ _CB, rgb_f @ _CR


# --- keyer -------------------------------------------------------------------

def chroma_alpha(rgb: np.ndarray, key_rgb: Tuple[int, int, int],
                 tolerance: float, softness: float) -> np.ndarray:
    """Soft alpha from the (Cb, Cr) distance to the key color.

    Distance is Euclidean in the Cb/Cr plane, normalized by 255 (0..~0.71).
    Pixels closer than ``tolerance`` get alpha 0. Alpha ramps linearly to 1
    over ``softness``. ``softness == 0`` gives a hard step.
    """
    rgb_f = _as_float_rgb(rgb)
    cb, cr = _chroma(rgb_f)
    key = np.array(key_rgb, dtype=np.float32).reshape(1, 1, 3)
    kcb, kcr = _chroma(key)
    dist = np.sqrt((cb - kcb) ** 2 + (cr - kcr) ** 2) / 255.0
    tol = max(0.0, float(tolerance))
    soft = max(0.0, float(softness))
    if soft <= 0.0:
        return (dist > tol).astype(np.float32)
    return np.clip((dist - tol) / soft, 0.0, 1.0).astype(np.float32)


# --- despill and edge decontamination ------------------------------------------

def despill(rgb: np.ndarray, key_rgb: Tuple[int, int, int], mode: str) -> np.ndarray:
    """Limit the key's dominant channel and restore the luminance the clamp removed.

    mode: none | average | double | limit (weakest to strongest).
    """
    if mode not in DESPILL_MODES:
        raise ValueError(f"Unknown despill mode {mode!r}; choose one of {DESPILL_MODES}")
    src = _as_float_rgb(rgb)
    if mode == "none":
        return np.clip(src, 0, 255).astype(np.uint8)
    k = int(np.argmax(np.asarray(key_rgb, dtype=np.float32)))
    others = [c for c in range(3) if c != k]
    a = src[:, :, others[0]]
    b = src[:, :, others[1]]
    if mode == "average":
        limit = (a + b) / 2.0
    elif mode == "double":
        limit = (2.0 * np.maximum(a, b) + np.minimum(a, b)) / 3.0
    else:  # limit
        limit = np.maximum(a, b)
    out = src.copy()
    y_before = src @ _Y
    out[:, :, k] = np.minimum(src[:, :, k], limit)
    y_after = out @ _Y
    out += (y_before - y_after)[:, :, None]
    return np.clip(out, 0, 255).astype(np.uint8)


def decontaminate_edges(rgb: np.ndarray, alpha: np.ndarray,
                        key_rgb: Tuple[int, int, int]) -> np.ndarray:
    """Un-mix the key color from semi-transparent pixels: F = (C - (1-a)K) / a.

    Pixels with alpha 0 or 1 are returned unchanged. The result is clamped to 0..255.
    """
    src = _as_float_rgb(rgb)
    a = np.asarray(alpha, dtype=np.float32)
    if a.shape != src.shape[:2]:
        raise ValueError(f"alpha shape {a.shape} does not match image {src.shape[:2]}")
    key = np.array(key_rgb, dtype=np.float32).reshape(1, 1, 3)
    a3 = a[:, :, None]
    fixed = (src - (1.0 - a3) * key) / np.maximum(a3, 1.0 / 255.0)
    edge = (a > (1.0 / 255.0)) & (a < 1.0)
    out = src.copy()
    out[edge] = fixed[edge]
    return np.clip(out, 0, 255).astype(np.uint8)


# --- alpha cleanup ---------------------------------------------------------------

def _kernel(px: int) -> np.ndarray:
    size = 2 * int(px) + 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def choke_feather(alpha: np.ndarray, choke_px: int, feather_px: int,
                  despeckle_px: int) -> np.ndarray:
    """Despeckle (open), then choke (erode; negative spreads), then feather (Gaussian)."""
    a = np.asarray(alpha, dtype=np.float32)
    if despeckle_px > 0:
        a = cv2.morphologyEx(a, cv2.MORPH_OPEN, _kernel(despeckle_px))
    if choke_px > 0:
        a = cv2.erode(a, _kernel(choke_px))
    elif choke_px < 0:
        a = cv2.dilate(a, _kernel(-choke_px))
    if feather_px > 0:
        a = cv2.GaussianBlur(a, (0, 0), sigmaX=float(feather_px))
    return np.clip(a, 0.0, 1.0).astype(np.float32)


def binary_alpha(alpha: np.ndarray, threshold: int = 128, defringe_px: int = 0) -> np.ndarray:
    """Hard 0/1 alpha: ``alpha * 255 >= threshold``. ``defringe_px`` erodes the result."""
    a = np.asarray(alpha)
    a255 = a.astype(np.float32) if a.dtype == np.uint8 else np.asarray(a, dtype=np.float32) * 255.0
    hard = (a255 >= float(threshold)).astype(np.float32)
    if defringe_px > 0:
        hard = cv2.erode(hard, _kernel(defringe_px))
    return hard.astype(np.float32)


# --- RGBA helpers ------------------------------------------------------------------

def compose_rgba(rgb: np.ndarray, alpha: np.ndarray) -> Image.Image:
    """Build an RGBA image from uint8 RGB and float 0..1 alpha."""
    rgb_u8 = np.asarray(rgb)[:, :, :3].astype(np.uint8)
    a_u8 = np.clip(np.round(np.asarray(alpha, dtype=np.float32) * 255.0), 0, 255).astype(np.uint8)
    rgba = np.concatenate([rgb_u8, a_u8[:, :, None]], axis=2)
    return Image.fromarray(np.ascontiguousarray(rgba))


def split_rgba(image: Image.Image) -> Tuple[np.ndarray, np.ndarray]:
    """Return (rgb uint8 HxWx3, alpha float32 HxW). An image without alpha is opaque."""
    rgba = np.asarray(image.convert("RGBA"))
    return rgba[:, :, :3].copy(), rgba[:, :, 3].astype(np.float32) / 255.0


def apply_profile_alpha(image: Image.Image, profile: OutputProfile) -> Image.Image:
    """Binarize alpha only when the profile asks for it. The hd profile keeps soft alpha."""
    if not profile.binary_alpha:
        return image
    rgb, alpha = split_rgba(image)
    hard = binary_alpha(alpha, profile.alpha_threshold, profile.defringe_px)
    return compose_rgba(rgb, hard)


# --- settings, overrides, and the three passes -------------------------------------

def resolve_key_settings(settings: KeySettings, plate_color: str) -> KeySettings:
    """Return settings with ``key_color`` filled from the plate color when it is None."""
    if settings.key_color:
        return settings
    return replace(settings, key_color=plate_color)


def apply_overrides(settings: KeySettings, overrides: Dict[str, Any]) -> KeySettings:
    """Apply per-frame overrides (``key_color``, ``tolerance``, ``softness``)."""
    if not overrides:
        return settings
    changes: Dict[str, Any] = {}
    for key, value in overrides.items():
        if value is None:
            continue
        if key == "key_color":
            changes[key] = str(value)
        elif key in ("tolerance", "softness"):
            changes[key] = float(value)
        else:
            logger.debug("Ignoring unknown per-frame override %r", key)
    return replace(settings, **changes) if changes else settings


def frame_overrides(frames: Sequence[FrameMeta], index: int) -> Dict[str, Any]:
    """Overrides recorded on the frame at ``index``; ``{}`` when there is none."""
    if 0 <= index < len(frames):
        return dict(frames[index].overrides or {})
    return {}


def _ml_alpha(image: Image.Image, backend: str, model: str, refine_edges: bool) -> np.ndarray:
    """Indirection so the ML backends load lazily (Task 6 creates core.sprite.matting)."""
    from core.sprite.matting import ml_alpha
    return ml_alpha(image, backend, model, refine_edges=refine_edges)


def key_pass(image: Image.Image, settings: KeySettings,
             overrides: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray, Optional[Tuple[int, int, int]]]:
    """Stage ``key``: estimate alpha and despill. Returns (rgb uint8, alpha float32, key_rgb)."""
    eff = apply_overrides(settings, overrides)
    if eff.method not in KEY_METHODS:
        msg = f"Unknown key method {eff.method!r}; choose one of {KEY_METHODS}"
        logger.error(msg)
        raise KeyingError(msg)
    if eff.method == "none":
        rgb, alpha = split_rgba(image)
        return rgb, alpha, None
    rgb = np.asarray(image.convert("RGB")).copy()
    if eff.method == "ml":
        alpha = np.asarray(_ml_alpha(image, eff.ml_backend, eff.ml_model, eff.ml_refine_edges),
                           dtype=np.float32)
        return rgb, np.clip(alpha, 0.0, 1.0), None
    if eff.key_color:
        key_rgb = hex_to_rgb(eff.key_color)
    else:
        picked = pick_key_color(image, (0, 0), radius=2)
        logger.warning("No key color set; sampled the top-left corner: %s", picked)
        key_rgb = hex_to_rgb(picked)
    alpha = chroma_alpha(rgb, key_rgb, eff.tolerance, eff.softness)
    rgb = despill(rgb, key_rgb, eff.despill)
    return rgb, alpha, key_rgb


def cleanup_pass(alpha: np.ndarray, settings: KeySettings) -> np.ndarray:
    """Stage ``cleanup``: despeckle, choke, feather."""
    return choke_feather(alpha, settings.choke_px, settings.feather_px, settings.despeckle_px)


def alpha_pass(rgb: np.ndarray, alpha: np.ndarray, key_rgb: Optional[Tuple[int, int, int]],
               settings: KeySettings) -> Image.Image:
    """Stage ``alpha``: decontaminate edge colors against the key, then compose RGBA."""
    if settings.edge_decontaminate and key_rgb is not None:
        rgb = decontaminate_edges(rgb, alpha, key_rgb)
    return compose_rgba(rgb, alpha)


def key_frame(image: Image.Image, settings: KeySettings, overrides: Dict[str, Any]) -> Image.Image:
    """One-shot keyer for previews, the CLI, and tests: key -> cleanup -> alpha."""
    rgb, alpha, key_rgb = key_pass(image, settings, overrides)
    alpha = cleanup_pass(alpha, settings)
    return alpha_pass(rgb, alpha, key_rgb, apply_overrides(settings, overrides))


def pick_key_color(image: Image.Image, xy: Tuple[int, int], radius: int = 2) -> str:
    """Average color in a (2*radius+1)^2 window around ``xy`` as ``#RRGGBB``."""
    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    x, y = int(xy[0]), int(xy[1])
    if not (0 <= x < w and 0 <= y < h):
        raise ValueError(f"Point {xy} lies outside the {w}x{h} image")
    r = max(0, int(radius))
    patch = rgb[max(0, y - r): y + r + 1, max(0, x - r): x + r + 1]
    return rgb_to_hex(patch.reshape(-1, 3).mean(axis=0))


# --- ffmpeg preview --------------------------------------------------------------------

def get_ffmpeg_path() -> Optional[str]:
    """Lazy indirection to ``core.video.ffmpeg_utils.get_ffmpeg_path``.

    ``core.video``'s package import loads ``google.genai``, which costs
    seconds. Importing it only when this function runs keeps ``core.sprite``
    (and ``core.sprite.pipeline``, which imports this module) free of that
    cost on plain package import (tests/sprite/test_package.py).
    """
    from core.video.ffmpeg_utils import get_ffmpeg_path as _get_ffmpeg_path
    return _get_ffmpeg_path()


def ffmpeg_chromakey_preview(video: Path, out_mp4: Path, key_color: str,
                             similarity: float, blend: float) -> Path:
    """Render a quick keyed preview MP4: ffmpeg ``chromakey`` composited over neutral grey.

    ``similarity`` (0.01..1) and ``blend`` (0..1) are the ffmpeg filter parameters.
    """
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        msg = "FFmpeg is not available; install it from the Video tab or put ffmpeg on PATH."
        logger.error("Chromakey preview failed: %s", msg)
        raise KeyingError(msg)
    r, g, b = hex_to_rgb(key_color)
    color = f"0x{r:02X}{g:02X}{b:02X}"
    similarity = min(1.0, max(0.01, float(similarity)))
    blend = min(1.0, max(0.0, float(blend)))
    graph = (
        "[0:v]split[bg_in][fg_in];"
        "[bg_in]drawbox=color=0x7F7F7F:t=fill[bg];"
        f"[fg_in]chromakey={color}:{similarity:.3f}:{blend:.3f}[fg];"
        "[bg][fg]overlay=format=auto,format=yuv420p"
    )
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
           "-filter_complex", graph, "-c:v", "libx264", "-preset", "veryfast", "-an", str(out_mp4)]
    logger.info("Chromakey preview: %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        msg = f"Chromakey preview could not run ffmpeg: {exc}"
        logger.error(msg)
        raise KeyingError(msg) from exc
    if result.returncode != 0:
        tail = (result.stderr or "").strip()[-800:]
        msg = f"Chromakey preview failed (ffmpeg exit {result.returncode}): {tail}"
        logger.error(msg)
        raise KeyingError(msg)
    return out_mp4
