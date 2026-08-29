# core/sprite/ml_install.py
"""Package list for the optional sprite ML backends.

The GUI install dialog (gui/sprite, sub-project 5b) passes ``sprite_ml_packages()``
to ``core.package_installer.PackageInstaller(packages, update_requirements=False)``.
The constants here are the source of truth; ``requirements-sprite-ml.txt`` mirrors
them and a test pins the two together.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

MEDIAPIPE_SPEC = "mediapipe>=0.10.0,<0.10.15"   # legacy mp.solutions API, matches core/character_animator
REMBG_SPEC = "rembg[cpu]>=2.0.60"
REMBG_PYTHON = ((3, 11), (3, 14))                # inclusive floor, exclusive ceiling


def python_supports_rembg() -> bool:
    """rembg pins Python >=3.11,<3.14."""
    version = tuple(sys.version_info[:2])
    return REMBG_PYTHON[0] <= version < REMBG_PYTHON[1]


def sprite_ml_packages() -> Tuple[List[str], str]:
    """(packages, index_url) for PackageInstaller. index_url "" means PyPI."""
    packages = [MEDIAPIPE_SPEC]
    if python_supports_rembg():
        packages.append(REMBG_SPEC)
    return packages, ""


def requirements_file() -> Path:
    """The optional-extras file at the repo root (beside requirements.txt)."""
    return Path(__file__).resolve().parents[2] / "requirements-sprite-ml.txt"


def parse_requirements(text: str) -> List[str]:
    """Non-comment, non-blank requirement specs, inline comments stripped."""
    specs: List[str] = []
    for line in text.splitlines():
        spec = line.split("#", 1)[0].strip()
        if spec:
            specs.append(spec)
    return specs
