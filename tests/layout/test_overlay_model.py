from core.layout.models import Overlay, OverlayStyle, PageSpec, TextStyle


def test_overlay_style_defaults():
    s = OverlayStyle()
    assert s.fill == "#FFFFFF"
    assert s.stroke_px == 2.0
    assert s.stroke_color == "#000000"
    assert s.padding_px == 10.0
    assert s.radius_px == 16.0
    assert s.max_width_px == 240.0


def test_overlay_defaults_and_fields():
    ov = Overlay(id="o1", kind="speech", text="Hi!", anchor=(50.0, 40.0))
    assert ov.kind == "speech"
    assert ov.anchor == (50.0, 40.0)
    assert ov.anchor_mode == "center"
    assert ov.tail_target is None
    assert ov.z == 0
    assert ov.role == ""
    assert ov.text_style is None
    assert isinstance(ov.style, OverlayStyle)


def test_overlay_independent_style_instances():
    a = Overlay(id="a", kind="caption", text="x", anchor=(0.0, 0.0))
    b = Overlay(id="b", kind="caption", text="y", anchor=(0.0, 0.0))
    a.style.fill = "#FFEE00"
    assert b.style.fill == "#FFFFFF"  # default_factory -> no shared mutable default


def test_overlay_with_tail_and_text_style():
    ts = TextStyle(family=["Arial", "Helvetica"])
    ov = Overlay(id="o2", kind="thought", text="hmm", anchor=(10.0, 10.0),
                 tail_target=(5.0, 30.0), z=3, role="dialogue", text_style=ts)
    assert ov.tail_target == (5.0, 30.0)
    assert ov.z == 3
    assert ov.role == "dialogue"
    assert ov.text_style is ts


def test_pagespec_overlays_default_empty():
    page = PageSpec(page_size_px=(100, 100))
    assert page.overlays == []
    page.overlays.append(Overlay(id="o", kind="sfx", text="BOOM", anchor=(20.0, 20.0)))
    assert len(page.overlays) == 1
