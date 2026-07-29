from core.layout.models import Overlay, PageSpec, PathSegment
from gui.layout.overlay_editor import OverlayEditor


class _FakeCanvas:
    def __init__(self, scene):
        self._scene = scene

    def scene(self):
        return self._scene


class _FakeTab:
    def __init__(self, page):
        self._page = page
        self.suspended = None
        self.refreshed = []

    def _current_page(self):
        return self._page

    def set_refresh_suspended(self, on):
        self.suspended = on

    def snapshot_and_refresh(self, prompt):
        self.refreshed.append(prompt)


def _tp():
    return [PathSegment(type="move", pts=[(100.0, 200.0)]),
            PathSegment(type="quad", pts=[(200.0, 120.0), (300.0, 200.0)])]


def _setup(qapp, overlay):
    from PySide6.QtWidgets import QGraphicsScene
    page = PageSpec(page_size_px=(400, 400), regions=[], overlays=[overlay])
    scene = QGraphicsScene(0, 0, 400, 400)
    tab = _FakeTab(page)
    ed = OverlayEditor(_FakeCanvas(scene), tab)
    ed.set_edit_overlay(overlay.id)
    return ed, tab


def test_curved_overlay_gets_five_handle_kinds_worth(qapp):
    ov = Overlay(id="c", kind="caption", text="T", anchor=(200.0, 200.0),
                 text_path=_tp())
    ed, _tab = _setup(qapp, ov)
    kinds = sorted(h._kind for h in ed._handles)
    assert kinds == ["body", "tp0", "tp1", "tpc"]


def test_straight_overlay_unchanged(qapp):
    ov = Overlay(id="c", kind="caption", text="T", anchor=(200.0, 200.0))
    ed, _tab = _setup(qapp, ov)
    assert sorted(h._kind for h in ed._handles) == ["body"]


def test_drag_control_writes_back(qapp):
    ov = Overlay(id="c", kind="caption", text="T", anchor=(200.0, 200.0),
                 text_path=_tp())
    ed, tab = _setup(qapp, ov)
    ed.begin_edit()
    ed.move_handle("tpc", 210.0, 90.0)
    assert ov.text_path[1].pts[0] == (210.0, 90.0)
    ed.move_handle("tp0", 90.0, 210.0)
    assert ov.text_path[0].pts[0] == (90.0, 210.0)
    ed.move_handle("tp1", 310.0, 190.0)
    assert ov.text_path[1].pts[1] == (310.0, 190.0)
    ed.commit()
    assert tab.refreshed  # snapshot taken


def test_commit_restores_on_invalid_geometry(qapp):
    ov = Overlay(id="c", kind="caption", text="T", anchor=(200.0, 200.0),
                 text_path=_tp())
    ed, _tab = _setup(qapp, ov)
    ed.begin_edit()
    ov.text_path[1].pts[0] = (float("nan"), 90.0)  # corrupt mid-drag
    ed.commit()
    assert ov.text_path[1].pts[0] == (200.0, 120.0)  # pre-drag restored
