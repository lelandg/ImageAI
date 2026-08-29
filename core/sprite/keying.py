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
from core.video.ffmpeg_utils import get_ffmpeg_path

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
