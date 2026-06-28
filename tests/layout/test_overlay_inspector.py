from PySide6.QtCore import Qt
from gui.layout.overlay_inspector import OverlayInspector
from core.layout.models import PageSpec, Overlay


def _page(overlays):
    return PageSpec(page_size_px=(400, 400), regions=[], overlays=overlays)


def test_set_page_lists_overlays(qapp):
    insp = OverlayInspector()
    insp.set_page(_page([
        Overlay(id="o1", kind="speech", text="hi", anchor=(10.0, 10.0)),
        Overlay(id="o2", kind="sfx", text="POW", anchor=(20.0, 20.0)),
    ]))
    assert insp.overlay_list.count() == 2


def test_add_buttons_emit_kind(qapp):
    insp = OverlayInspector()
    seen = []
    insp.addRequested.connect(lambda k: seen.append(k))
    insp.add_speech_btn.click()
    insp.add_sfx_btn.click()
    assert seen == ["speech", "sfx"]


def test_rotation_and_delete_emit_for_selected(qapp):
    insp = OverlayInspector()
    insp.set_page(_page([Overlay(id="o1", kind="sfx", text="x", anchor=(0.0, 0.0), rotation=10.0)]))
    insp.set_selected("o1")
    assert insp.rotation_spin.value() == 10
    rot, dele = [], []
    insp.rotationChanged.connect(lambda i, d: rot.append((i, d)))
    insp.deleteRequested.connect(lambda i: dele.append(i))
    insp.rotation_spin.setValue(90)
    insp.delete_btn.click()
    assert rot == [("o1", 90)]
    assert dele == ["o1"]
