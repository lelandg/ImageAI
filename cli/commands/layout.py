"""CLI handlers for the publication layout engine (design / fill / export)."""
import logging
from pathlib import Path

from core.layout import designer, styles
from core.layout.models import DocumentSpec, PageSpec, Region
from core.layout.page_sizes import PRESETS, preset_to_page_size

logger = logging.getLogger("imageai.cli.layout")


def _resolve_preset(name: str) -> dict:
    """Match a user page-size name to a PRESETS entry (case-insensitive, substring)."""
    n = (name or "").strip().lower()
    for p in PRESETS:
        if p["name"].lower() == n:
            return p
    for p in PRESETS:
        if n and n in p["name"].lower():
            return p
    choices = ", ".join(p["name"] for p in PRESETS)
    raise ValueError(f"Unknown page size {name!r}. Choices: {choices}")


def _page_px(page_size: str, orientation: str, dpi: int) -> tuple:
    """Resolve (width_px, height_px) for a named page size at an orientation/DPI."""
    ps = preset_to_page_size(_resolve_preset(page_size), orientation, dpi)
    return ps.to_pixels()


def _export_format(out_path: str) -> str:
    """Return 'pdf' or 'png' from the output extension, else raise ValueError."""
    suffix = Path(out_path).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".png":
        return "png"
    raise ValueError(f"--layout-export -o must end in .pdf or .png (got {out_path!r})")


def _region_size_str(region: Region, cap: int = 1024) -> str:
    """'WxH' for a region's bbox, scaled so the long edge is <= cap (aspect kept)."""
    _, _, w, h = region.bbox
    w, h = int(w), int(h)
    longest = max(w, h, 1)
    if longest > cap:
        scale = cap / longest
        w = max(1, round(w * scale))
        h = max(1, round(h * scale))
    return f"{w}x{h}"


def _assemble_document(result, page_size: str, orientation: str, dpi: int,
                       content_kind: str, title: str) -> DocumentSpec:
    """Build a one-page DocumentSpec from a DesignerResult (mirrors GUI new-doc)."""
    ps = preset_to_page_size(_resolve_preset(page_size), orientation, dpi)
    pw, ph = ps.to_pixels()
    regions = (result.regions if result.regions is not None
               else designer.fallback_result((pw, ph)).regions)
    page = PageSpec(
        page_size_px=(pw, ph), page_size=ps, background="#FFFFFF",
        regions=list(regions), overlays=list(result.overlays or []),
    )
    return DocumentSpec(
        title=title or "Untitled", pages=[page],
        content_kind=content_kind, style=styles.default_style_for(content_kind),
    )
