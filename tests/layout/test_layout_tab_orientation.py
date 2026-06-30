# tests/layout/test_layout_tab_orientation.py
from PySide6.QtCore import Qt

from core.layout.models import PageSize
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def test_default_is_portrait_side_by_side(qapp):
    tab = LayoutTab(config=FakeConfig())
    assert not tab.orient_split_btn.isChecked()
    assert tab._main_split.orientation() == Qt.Horizontal


def test_landscape_page_activates_render_on_top(qapp):
    tab = LayoutTab(config=FakeConfig())
    tab.page_setup.set_page_size(PageSize(11, 8.5, "in", "landscape", 300))
    assert tab.orient_split_btn.isChecked()
    assert tab._main_split.orientation() == Qt.Vertical


def test_portrait_reverts_to_side_by_side(qapp):
    tab = LayoutTab(config=FakeConfig())
    tab.page_setup.set_page_size(PageSize(11, 8.5, "in", "landscape", 300))
    tab.page_setup.set_page_size(PageSize(8.5, 11, "in", "portrait", 300))
    assert not tab.orient_split_btn.isChecked()
    assert tab._main_split.orientation() == Qt.Horizontal


def test_manual_toggle_flips_orientation(qapp):
    tab = LayoutTab(config=FakeConfig())
    tab.orient_split_btn.setChecked(True)
    assert tab._main_split.orientation() == Qt.Vertical
    tab.orient_split_btn.setChecked(False)
    assert tab._main_split.orientation() == Qt.Horizontal


def test_manual_override_persists_per_project(qapp, tmp_path):
    # Manually force render-on-top on a PORTRAIT page (against the auto rule),
    # save, reopen — the stored per-project choice wins over orientation.
    from core.layout import project_io

    tab = LayoutTab(config=FakeConfig())  # portrait default, beside
    tab.orient_split_btn.setChecked(True)  # manual override → on top
    assert tab.document.render_on_top is True
    p = tmp_path / "portrait_ontop.iaiproj.json"
    project_io.save_project(tab.document, str(p))

    tab2 = LayoutTab(config=FakeConfig())
    tab2.open_project_from(str(p))
    assert not tab2.page_setup.landscape_btn.isChecked()  # still portrait
    assert tab2.orient_split_btn.isChecked()  # but stored override wins
    assert tab2._main_split.orientation() == Qt.Vertical


def test_manual_override_survives_same_orientation_edit(qapp):
    # A manual choice must survive a non-orientation change (e.g. DPI/size edit).
    tab = LayoutTab(config=FakeConfig())  # portrait, beside
    tab.orient_split_btn.setChecked(True)  # manual → on top
    tab.page_setup.set_page_size(PageSize(8.5, 11, "in", "portrait", 150))  # DPI edit
    assert tab.orient_split_btn.isChecked()  # survived


def test_orientation_flip_overrides_manual_choice(qapp):
    # A real portrait<->landscape flip re-applies the auto rule, overriding manual.
    tab = LayoutTab(config=FakeConfig())  # portrait, beside
    tab.orient_split_btn.setChecked(True)  # manual → on top (portrait)
    tab.page_setup.set_page_size(PageSize(11, 8.5, "in", "landscape", 300))
    assert tab.orient_split_btn.isChecked()  # landscape → on top
    tab.page_setup.set_page_size(PageSize(8.5, 11, "in", "portrait", 300))
    assert not tab.orient_split_btn.isChecked()  # flip reverted to beside


def test_opening_landscape_project_activates_render_on_top(qapp, tmp_path):
    # Build + save a landscape project, then open it and confirm the page-setup
    # orientation buttons and the render-on-top toggle both reflect it.
    from core.layout import project_io

    tab = LayoutTab(config=FakeConfig())
    tab.page_setup.set_page_size(PageSize(11, 8.5, "in", "landscape", 300))
    p = tmp_path / "land.iaiproj.json"
    project_io.save_project(tab.document, str(p))

    tab2 = LayoutTab(config=FakeConfig())  # opens portrait by default
    assert not tab2.orient_split_btn.isChecked()
    tab2.open_project_from(str(p))
    assert tab2.page_setup.landscape_btn.isChecked()
    assert tab2.orient_split_btn.isChecked()
    assert tab2._main_split.orientation() == Qt.Vertical
