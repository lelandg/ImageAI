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
from dataclasses import dataclass, replace
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


def parse_key_color(hex_color: str, *, context: str = "") -> Tuple[int, int, int]:
    """``hex_to_rgb`` for callers that must not leak a bare ``ValueError``.

    Logs and re-raises a parse failure as ``KeyingError`` naming the offending
    value (and ``context``, e.g. a frame name, when given) so it carries a
    ``user_message`` and is caught by the same handling as every other keying
    failure (I1).
    """
    try:
        return hex_to_rgb(hex_color)
    except ValueError as exc:
        where = f" ({context})" if context else ""
        msg = f"Invalid key color {hex_color!r}{where}: {exc}"
        logger.error(msg)
        raise KeyingError(msg) from exc


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


NEUTRAL_KEY_CHROMA = 0.06   # (Cb, Cr) magnitude / 255 below which a key counts as gray


def key_chroma(key_rgb: Sequence[int]) -> float:
    """(Cb, Cr) magnitude of a color, normalized by 255. 0 for any gray."""
    key = np.array(key_rgb, dtype=np.float32).reshape(1, 3)
    kcb, kcr = _chroma(key)
    return float(np.sqrt(kcb ** 2 + kcr ** 2)[0] / 255.0)


def is_neutral_key(key_rgb: Sequence[int]) -> bool:
    return key_chroma(key_rgb) < NEUTRAL_KEY_CHROMA


MUTED_KEY_CHROMA = 0.35              # keys below this chroma are "muted" and get the clamp
MUTED_KEY_TOLERANCE_FRACTION = 0.6   # tolerance never exceeds this fraction of the key chroma
MUTED_KEY_REACH_FRACTION = 0.9       # tolerance + softness never exceeds this fraction


def effective_key_tolerance(key_rgb: Sequence[int], tolerance: float,
                            softness: float) -> Tuple[float, float, bool]:
    """Clamp (tolerance, softness) so a muted key never reaches the grays.

    Every gray sits at distance ``key_chroma`` from the key in (Cb, Cr). A
    muted plate (a model returned #75BB65 for a #00FF00 request) has a chroma
    of about 0.16, below the default tolerance of 0.2, so the default would
    key the subject's white beard and gray pants along with the plate. The
    clamp keeps ``tolerance + softness`` under the key chroma. A saturated
    key (chroma at or above ``MUTED_KEY_CHROMA``) keeps the values as given,
    so a deliberate wide tolerance on a real green plate still works. Neutral
    keys use luminance instead and are not clamped. An explicit per-frame
    override bypasses the clamp in ``key_pass``. Returns ``(tolerance,
    softness, clamped)``.
    """
    tol = max(0.0, float(tolerance))
    soft = max(0.0, float(softness))
    if is_neutral_key(key_rgb):
        return tol, soft, False
    chroma = key_chroma(key_rgb)
    if chroma >= MUTED_KEY_CHROMA:
        return tol, soft, False
    max_tol = chroma * MUTED_KEY_TOLERANCE_FRACTION
    max_reach = chroma * MUTED_KEY_REACH_FRACTION
    if tol <= max_tol and tol + soft <= max_reach:
        return tol, soft, False
    tol = min(tol, max_tol)
    soft = max(0.0, min(soft, max_reach - tol))
    return tol, soft, True


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
    dist_sq = (cb - kcb) ** 2 + (cr - kcr) ** 2
    if is_neutral_key(key_rgb):
        # White, gray or black plate: every gray shares its (Cb, Cr), so the
        # luminance is the only signal that separates the subject from the plate.
        dist_sq = dist_sq + (rgb_f @ _Y - key @ _Y) ** 2
    dist = np.sqrt(dist_sq) / 255.0
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
    if mode == "none" or is_neutral_key(key_rgb):
        # A neutral plate has no dominant channel to limit; the clamp would
        # only desaturate the subject.
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


def apply_overrides(settings: KeySettings, overrides: Dict[str, Any], *,
                    frame_name: str = "") -> KeySettings:
    """Apply per-frame overrides (``OVERRIDE_KEYS``: key_color, tolerance, softness).

    ``frame_name`` is used only to name the frame in a parse-failure message
    (I1); it never changes the result.
    """
    if not overrides:
        return settings
    changes: Dict[str, Any] = {}
    for key, value in overrides.items():
        if value is None:
            continue
        if key not in OVERRIDE_KEYS:
            logger.debug("Ignoring unknown per-frame override %r", key)
            continue
        if key == "key_color":
            changes[key] = str(value)
            continue
        try:
            changes[key] = float(value)
        except (TypeError, ValueError) as exc:
            where = f" for frame {frame_name!r}" if frame_name else ""
            msg = f"Invalid {key} override {value!r}{where}: {exc}"
            logger.error(msg)
            raise KeyingError(msg) from exc
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


def key_pass(image: Image.Image, settings: KeySettings, overrides: Dict[str, Any],
             *, frame_name: str = "") -> Tuple[np.ndarray, np.ndarray, Optional[Tuple[int, int, int]]]:
    """Stage ``key``: estimate alpha and despill. Returns (rgb uint8, alpha float32, key_rgb).

    ``frame_name`` (e.g. the source filename) is used only to name the frame
    in a parse-failure message raised as ``KeyingError`` (I1).
    """
    eff = apply_overrides(settings, overrides, frame_name=frame_name)
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
        key_rgb = parse_key_color(eff.key_color, context=frame_name)
    else:
        picked = pick_key_color(image, (0, 0), radius=2)
        logger.warning("No key color set; sampled the top-left corner: %s", picked)
        key_rgb = hex_to_rgb(picked)
    tol, soft = eff.tolerance, eff.softness
    if "tolerance" not in overrides and "softness" not in overrides:
        tol, soft, _clamped = effective_key_tolerance(key_rgb, tol, soft)
    alpha = chroma_alpha(rgb, key_rgb, tol, soft)
    alpha = clear_edge_bands(alpha, detect_edge_bands(rgb, tolerance=eff.tolerance))
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


def key_frame(image: Image.Image, settings: KeySettings, overrides: Dict[str, Any],
              *, frame_name: str = "") -> Image.Image:
    """One-shot keyer for previews, the CLI, and tests: key -> cleanup -> alpha."""
    rgb, alpha, key_rgb = key_pass(image, settings, overrides, frame_name=frame_name)
    alpha = cleanup_pass(alpha, settings)
    return alpha_pass(rgb, alpha, key_rgb, apply_overrides(settings, overrides, frame_name=frame_name))


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


# --- auto key color ------------------------------------------------------------------------

KEY_AUTO_BORDER_PX = 8           # width of the border strip the sampler reads
KEY_AUTO_MIN_UNIFORMITY = 0.6    # below this the border is not one color; use the plate color


EDGE_BAND_MAX_FRACTION = 0.49   # a band never covers half of its dimension
EDGE_BAND_MIN_AGREEMENT = 0.9   # a bar row has at least this fraction of pixels near the edge color
EDGE_BAND_PROBE_PX = 8          # rows sampled just inside a run to decide whether it is a bar

Bands = Tuple[int, int, int, int]   # top, bottom, left, right


@dataclass(frozen=True)
class KeyEstimate:
    """Plate color of a frame, sampled inside any uniform edge bands."""
    color: str          # #RRGGBB, median of the inner border strip
    uniformity: float   # fraction of strip pixels within the tolerance of ``color``
    bands: Bands = (0, 0, 0, 0)   # uniform rows/cols at the edges (letterbox, pillarbox)
    edge_color: Optional[str] = None   # color of those bands, when any exist


def _ycc_distance(rows: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Full YCbCr distance / 255 between ``rows`` (Nx3 float) and one ``ref`` color."""
    d = rows - ref.reshape(1, 3)
    return np.sqrt((d @ _Y) ** 2 + (d @ _CB) ** 2 + (d @ _CR) ** 2) / 255.0


def _bar_run(rows: np.ndarray, limit: int, tolerance: float) -> int:
    """Length of a bar at the start of ``rows`` (N x M x 3 float), or 0.

    A bar row has at least ``EDGE_BAND_MIN_AGREEMENT`` of its pixels within
    ``tolerance`` of the edge color (the median of the first row), so
    compression noise and a glyph that touches the bar do not end the run.
    The run is a bar only when the strip just inside it carries another
    color: a run that stops at the subject on a plate of the same color is
    the plate itself, which the chroma key handles, and returns 0.
    """
    n_rows = rows.shape[0]
    if n_rows < 2:
        return 0
    edge = np.median(rows[0], axis=0)
    dist = _ycc_distance(rows.reshape(-1, 3), edge).reshape(rows.shape[:2])
    agree = (dist <= tolerance).mean(axis=1)
    ok = (agree >= EDGE_BAND_MIN_AGREEMENT)[:limit]
    run = int(np.argmin(ok)) if not ok.all() else int(len(ok))
    if run == 0 or run >= n_rows:
        return 0
    probe = rows[run:run + EDGE_BAND_PROBE_PX].reshape(-1, 3)
    inner = np.median(probe, axis=0)
    if _ycc_distance(inner.reshape(1, 3), edge)[0] <= tolerance:
        return 0
    return run


def detect_edge_bands(rgb: np.ndarray, *, tolerance: float = 0.2) -> Bands:
    """Uniform bands at the frame edges: (top, bottom, left, right) in pixels.

    A video model can pillarbox a 1:1 clip inside black bars, or letterbox a
    clip inside white. Those bands are background, but not the plate color,
    so the chroma key alone leaves them opaque. A band is a run of rows (or
    columns) from the edge whose pixels are mostly the edge color, followed
    by a strip of another color (the plate). A run that stops at the subject
    on a plate of the same color is plate, not a bar, and counts as 0. A
    band never passes ``EDGE_BAND_MAX_FRACTION`` of the dimension.
    """
    arr = _as_float_rgb(rgb)
    h, w = arr.shape[:2]
    lim_h, lim_w = int(h * EDGE_BAND_MAX_FRACTION), int(w * EDGE_BAND_MAX_FRACTION)
    cols = arr.transpose(1, 0, 2)
    top = _bar_run(arr, lim_h, tolerance)
    bottom = _bar_run(arr[::-1], lim_h, tolerance)
    left = _bar_run(cols, lim_w, tolerance)
    right = _bar_run(cols[::-1], lim_w, tolerance)
    return top, bottom, left, right


def clear_edge_bands(alpha: np.ndarray, bands: Bands) -> np.ndarray:
    """Alpha 0 inside ``bands``. The bands are background by construction."""
    top, bottom, left, right = bands
    if not any(bands):
        return alpha
    out = np.asarray(alpha, dtype=np.float32).copy()
    h, w = out.shape[:2]
    if top:
        out[:top] = 0.0
    if bottom:
        out[h - bottom:] = 0.0
    if left:
        out[:, :left] = 0.0
    if right:
        out[:, w - right:] = 0.0
    return out


def key_distance(a_rgb: Sequence[int], b_rgb: Sequence[int]) -> float:
    """Distance between two colors in the (Cb, Cr) plane, normalized by 255 (same as the keyer)."""
    a = np.array(a_rgb, dtype=np.float32).reshape(1, 3)
    b = np.array(b_rgb, dtype=np.float32).reshape(1, 3)
    acb, acr = _chroma(a)
    bcb, bcr = _chroma(b)
    return float(np.sqrt((acb - bcb) ** 2 + (acr - bcr) ** 2)[0] / 255.0)


def estimate_key_color(image: Image.Image, *, border_px: int = KEY_AUTO_BORDER_PX,
                       tolerance: float = 0.2) -> KeyEstimate:
    """Sample the plate color from the border strip of ``image``.

    The median of the strip is the color. ``uniformity`` is the fraction of
    strip pixels within ``tolerance`` of that median in (Cb, Cr), so a
    luminance gradient counts as uniform and a busy background does not.
    """
    full = np.asarray(image.convert("RGB"))
    bands = detect_edge_bands(full, tolerance=tolerance)
    top, bottom, left, right = bands
    fh, fw = full.shape[:2]
    inner = full[top:fh - bottom, left:fw - right]
    if inner.shape[0] < 4 or inner.shape[1] < 4:
        inner, bands = full, (0, 0, 0, 0)
    edge_color = None
    if any(bands):
        parts = [full[:top], full[fh - bottom:], full[:, :left], full[:, fw - right:]]
        edge = np.concatenate([p.reshape(-1, 3) for p in parts if p.size]).astype(np.float32)
        edge_color = rgb_to_hex(np.median(edge, axis=0))
    rgb = inner
    h, w = rgb.shape[:2]
    b = max(1, min(int(border_px), h // 2, w // 2))
    strip = np.concatenate([
        rgb[:b].reshape(-1, 3), rgb[h - b:].reshape(-1, 3),
        rgb[b:h - b, :b].reshape(-1, 3), rgb[b:h - b, w - b:].reshape(-1, 3),
    ]).astype(np.float32)
    median = np.median(strip, axis=0)
    cb, cr = _chroma(strip)
    kcb, kcr = _chroma(median.reshape(1, 3))
    dist = np.sqrt((cb - kcb) ** 2 + (cr - kcr) ** 2) / 255.0
    uniformity = float((dist <= max(0.0, float(tolerance))).mean())
    return KeyEstimate(rgb_to_hex(median), uniformity, bands, edge_color)


def auto_key_color(image: Image.Image, plate_color: str, *,
                   tolerance: float = 0.2) -> Tuple[str, str, str, bool]:
    """Choose the key color for a clip with no explicit key color.

    Returns ``(key_hex, message, level, sampled)``; ``sampled`` is False when
    the plate color had to stand in. The clip border wins over the
    requested plate color, because the image model and the video model both
    drift from the request. A border that is not one color cannot be
    sampled, so the plate color is used and the message says so.
    """
    plate_hex = rgb_to_hex(parse_key_color(plate_color, context="plate color"))
    est = estimate_key_color(image, tolerance=tolerance)
    if est.uniformity < KEY_AUTO_MIN_UNIFORMITY:
        return plate_hex, (
            f"The clip border is not one color ({est.uniformity:.0%} agrees with {est.color}), "
            f"so the key uses the plate color {plate_hex}. If the key removes nothing, set the "
            f"key color in Keying settings."), "warning", False
    bars = ""
    if est.edge_color and key_distance(hex_to_rgb(est.edge_color), hex_to_rgb(est.color)) > tolerance:
        t, b, l, r = est.bands
        bars = (f" Uniform {est.edge_color} bars at the edges (top {t}, bottom {b}, left {l}, "
                f"right {r} px) are removed.")
    drift = key_distance(hex_to_rgb(est.color), hex_to_rgb(plate_hex))
    if drift > max(0.0, float(tolerance)):
        return est.color, (
            f"Key color sampled from the clip: {est.color}. The plate color {plate_hex} is not "
            f"in the clip (the plate or the video drifted from the request).{bars}"), "warning", True
    return est.color, f"Key color sampled from the clip: {est.color}.{bars}", "info", True


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
    r, g, b = parse_key_color(key_color, context="chromakey preview")
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
