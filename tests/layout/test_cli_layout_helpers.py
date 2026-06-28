import pytest

from cli.commands.layout import (
    _resolve_preset, _page_px, _export_format, _region_size_str,
)
from core.layout.models import Region


def test_resolve_preset_case_insensitive_and_substring():
    assert _resolve_preset("A4")["name"] == "A4"
    assert _resolve_preset("letter")["name"] == "US Letter"
    with pytest.raises(ValueError):
        _resolve_preset("nope")


def test_page_px_letter_portrait_300dpi():
    # US Letter 8.5x11in @300dpi = 2550 x 3300
    assert _page_px("Letter", "portrait", 300) == (2550, 3300)


def test_page_px_landscape_swaps():
    assert _page_px("Letter", "landscape", 300) == (3300, 2550)


def test_export_format_from_extension():
    assert _export_format("a.pdf") == "pdf"
    assert _export_format("a.PNG") == "png"
    with pytest.raises(ValueError):
        _export_format("a.gif")


def test_region_size_str_caps_long_edge():
    r = Region(id="r1", kind="image", bbox=(0, 0, 4000, 2000))
    assert _region_size_str(r, cap=1024) == "1024x512"
    r2 = Region(id="r2", kind="image", bbox=(0, 0, 800, 600))
    assert _region_size_str(r2, cap=1024) == "800x600"
