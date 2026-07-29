from core.layout.models import Overlay, PageSpec, PathSegment
from gui.layout.overlay_inspector import OverlayInspector


def _page():
    tp = [PathSegment(type="move", pts=[(0.0, 0.0)]),
          PathSegment(type="quad", pts=[(10.0, -5.0), (20.0, 0.0)])]
    return PageSpec(page_size_px=(400, 400), regions=[], overlays=[
        Overlay(id="cap", kind="caption", text="curved", anchor=(10.0, 10.0),
                text_path=tp),
        Overlay(id="sp", kind="speech", text="talk", anchor=(20.0, 20.0)),
        Overlay(id="fx", kind="sfx", text="POW", anchor=(30.0, 30.0)),
    ])


def test_curve_checkbox_enabled_only_for_caption_sfx(qapp):
    insp = OverlayInspector()
    insp.set_page(_page())
    insp.set_selected("sp")
    assert not insp.curve_chk.isEnabled()
    insp.set_selected("fx")
    assert insp.curve_chk.isEnabled()
    assert not insp.curve_chk.isChecked()
    insp.set_selected("cap")
    assert insp.curve_chk.isEnabled()
    assert insp.curve_chk.isChecked()  # reflects existing text_path


def test_curve_toggle_emits(qapp):
    insp = OverlayInspector()
    insp.set_page(_page())
    insp.set_selected("fx")
    got = []
    insp.curveToggled.connect(lambda oid, on: got.append((oid, on)))
    insp.curve_chk.setChecked(True)
    assert got == [("fx", True)]


def test_outline_change_emits(qapp):
    insp = OverlayInspector()
    insp.set_page(_page())
    insp.set_selected("cap")
    got = []
    insp.outlineChanged.connect(lambda oid, px, col: got.append((oid, px, col)))
    insp.outline_spin.setValue(3.5)
    assert got and got[-1][0] == "cap" and abs(got[-1][1] - 3.5) < 1e-9


def test_layout_tab_curve_handlers(qapp):
    # Pure-logic test of the LayoutTab handler functions via a minimal stub;
    # mirrors how tests/layout/test_overlay_wiring.py exercises handlers.
    from gui.layout.layout_tab import LayoutTab
    page = _page()

    class _Stub:
        document = type("D", (), {"style": None})()
        def _current_page(self):
            return page
        def _find_overlay(self, oid):
            return next((o for o in page.overlays if o.id == oid), None)
        def snapshot_and_refresh(self, prompt):
            self.last = prompt

    stub = _Stub()
    assert LayoutTab._set_overlay_curve(stub, "fx", True) is True
    fx = stub._find_overlay("fx")
    assert fx.text_path is not None and len(fx.text_path) == 2
    assert LayoutTab._set_overlay_curve(stub, "fx", False) is True
    assert fx.text_path is None
    assert LayoutTab._set_overlay_curve(stub, "sp", True) is False  # speech: refused
    assert LayoutTab._set_overlay_outline(stub, "cap", 3.0, "#442200") is True
    cap = stub._find_overlay("cap")
    assert cap.text_style is not None
    assert cap.text_style.outline_px == 3.0
    assert cap.text_style.outline_color == "#442200"
