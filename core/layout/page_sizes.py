"""Page-size presets, unit conversion, and custom-size persistence."""
import re
from typing import List, Dict, Optional, Tuple

from core.layout.models import PageSize

_INCHES_PER = {"in": 1.0, "mm": 1.0 / 25.4, "pt": 1.0 / 72.0, "px": None}

# Seeded from Plans/common-sizes.md
PRESETS: List[Dict] = [
    {"name": "US Letter", "width": 8.5, "height": 11.0, "unit": "in"},
    {"name": "US Legal", "width": 8.5, "height": 14.0, "unit": "in"},
    {"name": "Tabloid", "width": 11.0, "height": 17.0, "unit": "in"},
    {"name": "A4", "width": 210.0, "height": 297.0, "unit": "mm"},
    {"name": "A5", "width": 148.0, "height": 210.0, "unit": "mm"},
    {"name": "US Comic", "width": 6.625, "height": 10.25, "unit": "in"},
    {"name": "Instagram Square", "width": 1080.0, "height": 1080.0, "unit": "px"},
    {"name": "Instagram Portrait", "width": 1080.0, "height": 1350.0, "unit": "px"},
    {"name": "Full HD", "width": 1920.0, "height": 1080.0, "unit": "px"},
]


def to_inches(value: float, unit: str) -> float:
    factor = _INCHES_PER.get(unit)
    if factor is None:
        raise ValueError(f"Cannot convert unit {unit!r} to inches")
    return value * factor


def preset_to_page_size(preset: Dict, orientation: str = "portrait", dpi: int = 300) -> PageSize:
    pg = PageSize(preset["width"], preset["height"], preset["unit"], "portrait", dpi)
    return pg.swapped() if orientation == "landscape" else pg


def parse_size_text(text: str) -> Optional[Tuple[float, float]]:
    m = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*[xX×]\s*([0-9]*\.?[0-9]+)\s*$", text or "")
    if not m:
        return None
    return (float(m.group(1)), float(m.group(2)))


def load_custom_sizes(config) -> List[Dict]:
    return list(config.get_layout_config().get("custom_page_sizes", []))


def save_custom_size(config, preset: Dict) -> None:
    cfg = config.get_layout_config()
    sizes = cfg.get("custom_page_sizes", [])
    sizes = [s for s in sizes if s.get("name") != preset.get("name")]
    sizes.append(preset)
    cfg["custom_page_sizes"] = sizes
    config.set_layout_config(cfg)
    config.save()
