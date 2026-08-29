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
