from gui.layout.layout_tab import LayoutTab
from core.layout.models import Region, Overlay


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tab(overlays, regions=None):
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = regions or []
    tab.document.pages[0].overlays = overlays
    tab._refresh()
    return tab


def test_body_handle_only_when_no_tail(qapp):
    tab = _tab([Overlay(id="o", kind="caption", text="x", anchor=(50.0, 50.0))])
    tab.overlay_editor.set_edit_overlay("o")
    kinds = sorted(h._kind for h in tab.overlay_editor._handles)
    assert kinds == ["body"]


def test_body_and_tail_handles_when_tail(qapp):
    tab = _tab([Overlay(id="o", kind="speech", text="x", anchor=(50.0, 50.0),
                        tail_target=(80.0, 90.0))])
    tab.overlay_editor.set_edit_overlay("o")
    kinds = sorted(h._kind for h in tab.overlay_editor._handles)
    assert kinds == ["body", "tail"]


def test_move_body_commits_anchor(qapp):
    tab = _tab([Overlay(id="o", kind="caption", text="x", anchor=(50.0, 50.0))])
    tab.overlay_editor.set_edit_overlay("o")
    before = len(tab.history.snapshots())
    tab.overlay_editor.begin_edit()
    tab.overlay_editor.move_handle("body", 120.0, 130.0)
    tab.overlay_editor.commit()
    assert tab.document.pages[0].overlays[0].anchor == (120.0, 130.0)
    assert len(tab.history.snapshots()) == before + 1


def test_tail_commit_snaps_to_region_center(qapp):
    tab = _tab(
        [Overlay(id="o", kind="speech", text="x", anchor=(50.0, 50.0), tail_target=(60.0, 60.0))],
        regions=[Region(id="r", kind="image", shape="rect", bbox=(200, 200, 100, 100))],
    )
    tab.overlay_editor.set_edit_overlay("o")
    tab.overlay_editor.begin_edit()
    tab.overlay_editor.move_handle("tail", 248.0, 248.0)  # near region center (250,250)
    tab.overlay_editor.commit()
    assert tab.document.pages[0].overlays[0].tail_target == (250.0, 250.0)


def test_edit_off_clears_handles(qapp):
    tab = _tab([Overlay(id="o", kind="caption", text="x", anchor=(50.0, 50.0))])
    tab.overlay_editor.set_edit_overlay("o")
    tab.overlay_editor.set_edit_overlay(None)
    assert tab.overlay_editor._handles == []
