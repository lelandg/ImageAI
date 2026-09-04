"""Synthetic sprite frames drawn with numpy (design section 5, G16).

A red square moves right across a canvas: ``alpha=True`` puts it on
transparency, ``alpha=False`` on an opaque chroma-green plate. Frame
``index`` has its square at ``x = 8 + index * STEP``; with twelve frames the
last square (x = 74..98) still fits inside the 112 px canvas, so the union
bounding box of all frames is ``(8, 20, 90, 24)``.
"""
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image

FRAME_SIZE = (112, 64)  # w, h
SQUARE = 24
STEP = 6
FRAME_COUNT = 12
RED = (200, 40, 40, 255)


def draw_frame(index: int, *, alpha: bool, size: Tuple[int, int] = FRAME_SIZE,
               square: int = SQUARE, step: int = STEP) -> Image.Image:
    """Frame ``index``: a red square at x = 8 + index*step on green or on transparency."""
    w, h = size
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    if not alpha:
        arr[..., 1] = 255
        arr[..., 3] = 255
    x = 8 + index * step
    y = (h - square) // 2
    arr[y:y + square, x:x + square] = RED
    return Image.fromarray(arr)


def write_frames(directory: Path, count: int = FRAME_COUNT, *, alpha: bool = True,
                 size: Tuple[int, int] = FRAME_SIZE) -> List[Path]:
    """Write ``count`` frames as 0001.png... and return their paths."""
    directory.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    for index in range(count):
        path = directory / f"{index + 1:04d}.png"
        draw_frame(index, alpha=alpha, size=size).save(path, format="PNG")
        paths.append(path)
    return paths
