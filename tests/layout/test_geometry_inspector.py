from gui.layout.geometry_inspector import GeometryInspector
from gui.layout.layout_tab import LayoutTab
from core.layout.models import Region, ImageStyle


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def test_inspector_reflects_region_and_emits(qapp):
    insp = GeometryInspector()
    r = Region(id="p1", kind="image", shape="path", bbox=(0, 0, 100, 100),
               bleed=True, z=3, image_style=ImageStyle(stroke_px=6))
    insp.set_region(r)
    assert insp.bleed_chk.isChecked() is True
    assert insp.borderless_chk.isChecked() is False  # stroke 6 -> not borderless
    assert insp.z_spin.value() == 3

    seen = []
    insp.bleedToggled.connect(lambda rid, b: seen.append(("bleed", rid, b)))
    insp.bleed_chk.setChecked(False)
    assert seen == [("bleed", "p1", False)]


def test_layout_tab_geometry_handlers_write_model(qapp):
    tab = LayoutTab(config=FakeConfig())
    page = tab.document.pages[0]
    page.regions = [Region(id="p1", kind="image", shape="path", bbox=(0, 0, 100, 100),
                           image_style=ImageStyle(stroke_px=6))]

    tab._on_region_bleed_toggled("p1", True)
    assert page.regions[0].bleed is True

    tab._on_region_borderless_toggled("p1", True)
    assert page.regions[0].image_style.stroke_px == 0
    tab._on_region_borderless_toggled("p1", False)
    assert page.regions[0].image_style.stroke_px == 4

    tab._on_region_z_changed("p1", 12)
    assert page.regions[0].z == 12


def test_borderless_creates_image_style_when_absent(qapp):
    tab = LayoutTab(config=FakeConfig())
    page = tab.document.pages[0]
    page.regions = [Region(id="p1", kind="image", shape="path", bbox=(0, 0, 100, 100))]
    tab._on_region_borderless_toggled("p1", False)
    assert page.regions[0].image_style is not None
    assert page.regions[0].image_style.stroke_px == 4
