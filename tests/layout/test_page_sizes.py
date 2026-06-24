import pytest
from core.layout.models import PageSize
from core.layout import page_sizes as ps


def test_to_pixels_inches_at_300dpi():
    assert PageSize(8.5, 11, "in", "portrait", 300).to_pixels() == (2550, 3300)


def test_to_pixels_mm_a4_at_300dpi():
    # 210mm x 297mm @ 300dpi -> ~2480 x 3508
    assert PageSize(210, 297, "mm", "portrait", 300).to_pixels() == (2480, 3508)


def test_to_pixels_px_ignores_dpi():
    assert PageSize(1080, 1350, "px", "portrait", 72).to_pixels() == (1080, 1350)


def test_swapped_flips_orientation_and_dims():
    sw = PageSize(8.5, 11, "in", "portrait", 300).swapped()
    assert sw.orientation == "landscape"
    assert (sw.width, sw.height) == (11, 8.5)


def test_to_inches_units():
    assert ps.to_inches(72, "pt") == pytest.approx(1.0)
    assert ps.to_inches(25.4, "mm") == pytest.approx(1.0)
    assert ps.to_inches(2, "in") == pytest.approx(2.0)


def test_presets_include_letter_and_a4_and_comic():
    names = {p["name"] for p in ps.PRESETS}
    assert "US Letter" in names
    assert "A4" in names
    assert "US Comic" in names


def test_preset_to_page_size_landscape_swaps():
    letter = next(p for p in ps.PRESETS if p["name"] == "US Letter")
    pgl = ps.preset_to_page_size(letter, "landscape", 300)
    assert pgl.to_pixels() == (3300, 2550)


def test_parse_size_text():
    assert ps.parse_size_text("8.5 x 11") == (8.5, 11.0)
    assert ps.parse_size_text("210X297") == (210.0, 297.0)
    assert ps.parse_size_text("not a size") is None


def test_custom_size_persistence_roundtrip():
    store = {"layout": {}}

    class FakeConfig:
        def get_layout_config(self):
            return dict(store["layout"])
        def set_layout_config(self, cfg):
            store["layout"] = cfg
        def save(self):
            pass

    cfg = FakeConfig()
    assert ps.load_custom_sizes(cfg) == []
    ps.save_custom_size(cfg, {"name": "My Zine", "width": 5.5, "height": 8.5, "unit": "in"})
    loaded = ps.load_custom_sizes(cfg)
    assert loaded == [{"name": "My Zine", "width": 5.5, "height": 8.5, "unit": "in"}]
    # idempotent: saving same name does not duplicate
    ps.save_custom_size(cfg, {"name": "My Zine", "width": 5.5, "height": 8.5, "unit": "in"})
    assert len(ps.load_custom_sizes(cfg)) == 1
