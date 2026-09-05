"""Chroma-prompt injection for the sprite video route (design §4.2).

The suffixes tell the video model to render on a flat chroma plate. The
prompt text never contains an aspect ratio, a pixel size, or the words in
``FORBIDDEN_WORDS`` — Gemini renders such words literally.
"""
import colorsys
import re
from typing import Tuple

CHROMA_SUFFIX = ("solid chroma {color_name} background {hex}, flat even lighting, "
                 "no shadows on the background, no camera movement, character stays centered")
LOOP_SUFFIX = "seamless loop, ends in the same pose it starts"
FORBIDDEN_WORDS: Tuple[str, ...] = ("transparent", "checkerboard", "alpha")

_ASPECT_RE = re.compile(r"(?<!\d)(?:1\s*:\s*1|3\s*:\s*2|2\s*:\s*3|3\s*:\s*4|4\s*:\s*3|4\s*:\s*5|5\s*:\s*4|9\s*:\s*16|16\s*:\s*9|21\s*:\s*9|16\s*:\s*10|10\s*:\s*16|2\s*:\s*1|1\s*:\s*2|5\s*:\s*3|3\s*:\s*5)(?!\d)")
_PIXELS_RE = re.compile(r"\b\d{2,5}\s*[x×]\s*\d{2,5}\b|\b\d{1,5}\s*px\b", re.IGNORECASE)
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(FORBIDDEN_WORDS) + r")\b", re.IGNORECASE)
_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _parse_hex(hex_color: str) -> Tuple[int, int, int]:
    match = _HEX_RE.match(hex_color.strip())
    if not match:
        raise ValueError(f"plate color must be #RRGGBB, got {hex_color!r}")
    value = match.group(1)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def normalize_hex(hex_color: str) -> str:
    """Return the color as upper-case ``#RRGGBB``."""
    r, g, b = _parse_hex(hex_color)
    return f"#{r:02X}{g:02X}{b:02X}"


def color_name(hex_color: str) -> str:
    """Basic English name for a plate color: green, blue, magenta, red, …"""
    r, g, b = _parse_hex(hex_color)
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    if v < 0.15:
        return "black"
    if s < 0.2:
        return "white" if v > 0.85 else "gray"
    hue = h * 360.0
    if hue < 15 or hue >= 345:
        return "red"
    if hue < 45:
        return "orange"
    if hue < 75:
        return "yellow"
    if hue < 165:
        return "green"
    if hue < 195:
        return "cyan"
    if hue < 255:
        return "blue"
    if hue < 285:
        return "purple"
    return "magenta"


def strip_render_terms(prompt: str) -> str:
    """Remove forbidden words, aspect ratios, and pixel sizes; tidy punctuation."""
    text = _FORBIDDEN_RE.sub(" ", prompt)
    text = _ASPECT_RE.sub(" ", text)
    text = _PIXELS_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;])", r"\1", text)
    text = re.sub(r"([,.;])(?:\s*[,.;])+", r"\1", text)
    text = text.strip().strip(",.; ").strip()
    return text


def inject_chroma(prompt: str, plate_color: str, *, loop: bool) -> str:
    """Append the chroma suffix (and the loop suffix) to a cleaned prompt."""
    hex_color = normalize_hex(plate_color)
    body = strip_render_terms(prompt)
    parts = [body] if body else []
    parts.append(CHROMA_SUFFIX.format(color_name=color_name(hex_color), hex=hex_color))
    if loop:
        parts.append(LOOP_SUFFIX)
    return ", ".join(parts)


def background_prompt(prompt: str, plate_color: str, *, loop: bool,
                      background_mode: str = "transparent") -> str:
    """Keep source scenery when requested; otherwise prepare a removable plate."""
    if background_mode != "original":
        return inject_chroma(prompt, plate_color, loop=loop)
    parts = [strip_render_terms(prompt),
             "Preserve the original reference image background, including its colors and scenery. "
             "Keep the camera fixed and the framing unchanged"]
    if loop:
        parts.append(LOOP_SUFFIX)
    return ", ".join(part for part in parts if part)
