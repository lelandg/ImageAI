"""Shared image-size validation for OpenAI gpt-image-2 and friends.

Both the provider (pre-flight) and the GUI (live red/green label) call
``validate_custom_size`` so the rules can never drift.
"""

from __future__ import annotations

from typing import Mapping, Tuple


def validate_custom_size(width: int, height: int, model_caps: Mapping) -> Tuple[bool, str]:
    """Validate a custom WxH against the model's constraints.

    Args:
        width:  Desired width in pixels.
        height: Desired height in pixels.
        model_caps: A row from ``OpenAIProvider.MODEL_CAPS``. Recognized keys:
            - ``supports_custom_size``: bool, must be True.
            - ``custom_size_min_pixels``: int, default 655_360.
            - ``custom_size_max_pixels``: int, default 8_294_400.
            - ``custom_size_max_edge``: int, default 3840.
            - ``custom_size_edge_multiple``: int, default 16.
            - ``custom_size_max_aspect``: float, default 3.0.

    Returns:
        ``(True, "")`` if valid; ``(False, reason)`` otherwise. ``reason`` is
        a short, human-readable string suitable for showing in a tooltip or
        provider error message.
    """
    if not model_caps.get("supports_custom_size", False):
        return False, "Custom size not supported on this model"

    if width <= 0 or height <= 0:
        return False, "Width and height must be positive"

    multiple = int(model_caps.get("custom_size_edge_multiple", 16))
    if width % multiple or height % multiple:
        return False, f"Both edges must be multiples of {multiple}"

    max_edge = int(model_caps.get("custom_size_max_edge", 3840))
    if width > max_edge or height > max_edge:
        return False, f"Max edge length is {max_edge}px"

    pixels = width * height
    min_px = int(model_caps.get("custom_size_min_pixels", 655_360))
    max_px = int(model_caps.get("custom_size_max_pixels", 8_294_400))
    if pixels < min_px:
        return False, f"Total pixels {pixels:,} below minimum {min_px:,}"
    if pixels > max_px:
        return False, f"Total pixels {pixels:,} above maximum {max_px:,}"

    aspect_max = float(model_caps.get("custom_size_max_aspect", 3.0))
    aspect = max(width, height) / min(width, height)
    if aspect > aspect_max:
        return False, f"Aspect ratio {aspect:.2f}:1 exceeds limit {aspect_max:.0f}:1"

    return True, ""


def parse_size_string(size: str) -> Tuple[int, int]:
    """Parse a 'WxH' string into a (width, height) tuple.

    Accepts ``x`` or ``X`` as the separator. Raises ``ValueError`` on bad input.
    """
    if not isinstance(size, str) or "x" not in size.lower():
        raise ValueError(f"Bad size string: {size!r} (expected 'WxH')")
    w, h = size.lower().split("x", 1)
    return int(w.strip()), int(h.strip())
