"""Lock toggle + session persistence for the Layout tab.

Covers the three requests:
  * generated frames + applied text are locked in place by default,
  * a single toggle unlocks them (and the move is written back so it survives a
    refresh/save),
  * the tab reloads its last layout on startup like the other tabs do.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsPixmapItem,
)

from core.layout.models import Region, PageSpec
from core.layout import qt_renderer
from gui.layout.layout_tab import LayoutTab


def _page():
    return PageSpec(page_size_px=(400, 300), background="#FFFFFF", regions=[
        Region(id="img", kind="image", bbox=(10, 10, 100, 100)),
        Region(id="txt", kind="text", bbox=(10, 200, 300, 60), text="Hi"),
    ])


# --- renderer: lock + content-follows-frame + write-back ---

def test_locked_scene_has_no_movable_items(qapp):
    scene = qt_renderer.build_scene(_page(), selectable=True, locked=True)
    movable = [it for it in scene.items() if it.flags() & QGraphicsItem.ItemIsMovable]
    assert movable == []
    # still selectable so a region can be picked to edit its content
    selectable = [it for it in scene.items() if it.flags() & QGraphicsItem.ItemIsSelectable]
    assert len(selectable) >= 2


def test_only_text_unlocks_frames_stay_locked(qapp):
    # Unlocking moves ONLY text; image frames are always locked in position.
    scene = qt_renderer.build_scene(_page(), selectable=True, locked=False)
    movable_ids = {it.data(0) for it in scene.items()
                   if it.flags() & QGraphicsItem.ItemIsMovable}
    assert movable_ids == {"txt"}


def test_dragging_unlocked_region_writes_back_bbox(qapp):
    page = _page()
    scene = qt_renderer.build_scene(page, selectable=True, locked=False)
    box = next(it for it in scene.items()
               if it.flags() & QGraphicsItem.ItemIsMovable and it.data(0) == "txt")
    box.setPos(25, -40)  # simulate a drag delta
    txt = next(r for r in page.regions if r.id == "txt")
    assert txt.bbox == (35, 160, 300, 60)  # (10+25, 200-40, w, h) — persists on save


def test_applied_text_is_child_of_its_frame_and_moves_with_it(qapp):
    scene = qt_renderer.build_scene(_page(), selectable=True, locked=False)
    box = next(it for it in scene.items()
               if isinstance(it, QGraphicsRectItem) and it.data(0) == "txt")
    # Text is now a grandchild of the box (box -> clip -> text) so that the clip
    # item can enforce the panel-shape boundary.  Walk descendants to find it.
    def _descendants(item):
        for child in item.childItems():
            yield child
            yield from _descendants(child)
    texts = [c for c in _descendants(box) if isinstance(c, QGraphicsSimpleTextItem)]
    assert texts, "applied text must be a descendant of its frame and move with it"
    before = texts[0].scenePos()
    box.setPos(15, 15)
    after = texts[0].scenePos()
    assert (after.x() - before.x(), after.y() - before.y()) == (15, 15)


def test_filled_image_frame_never_movable_even_when_unlocked(qapp, tmp_path):
    from PySide6.QtGui import QImage
    from PySide6.QtCore import Qt
    p = tmp_path / "ref.png"
    im = QImage(20, 20, QImage.Format_RGB32)
    im.fill(Qt.white)
    assert im.save(str(p))
    page = PageSpec(page_size_px=(400, 300), regions=[
        Region(id="i", kind="image", bbox=(10, 10, 100, 100), image_ref=str(p))])
    scene = qt_renderer.build_scene(page, selectable=True, locked=False)
    pi = next(it for it in scene.items()
              if isinstance(it, QGraphicsPixmapItem) and it.data(0) == "i")
    # selectable so the region can be re-picked, but never draggable
    assert pi.flags() & QGraphicsItem.ItemIsSelectable
    assert not (pi.flags() & QGraphicsItem.ItemIsMovable)


# --- LayoutTab: lock toggle persistence + session reload ---

class SessionConfig:
    """Config double with a real on-disk config_dir for session round-trips."""

    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.store = {"layout": {}}

    def get_layout_config(self):
        return dict(self.store["layout"])

    def set_layout_config(self, cfg):
        self.store["layout"] = cfg

    def save(self):
        pass

    def get_layout_llm_provider(self):
        return "google"


def test_lock_toggle_defaults_locked_and_persists(qapp, tmp_path):
    cfg = SessionConfig(tmp_path)
    tab = LayoutTab(config=cfg)
    assert tab._locked is True
    assert tab.lock_btn.isChecked() is True

    tab.lock_btn.setChecked(False)  # user unlocks
    assert tab._locked is False
    assert cfg.store["layout"]["items_locked"] is False

    # a fresh tab on next launch reads the persisted state
    tab2 = LayoutTab(config=cfg)
    assert tab2._locked is False
    assert tab2.lock_btn.isChecked() is False


def test_save_session_then_reload_on_startup(qapp, tmp_path):
    cfg = SessionConfig(tmp_path)
    tab = LayoutTab(config=cfg)
    tab.document.title = "Remembered"
    tab.document.pages[0].regions = [
        Region(id="r", kind="text", bbox=(5, 5, 50, 20), text="hello")]
    tab.save_session()
    assert (tmp_path / "layout" / "last_session.iaiproj.json").exists()

    tab2 = LayoutTab(config=cfg)  # startup restores the saved layout
    assert tab2.document.title == "Remembered"
    assert [r.text for r in tab2.document.pages[0].regions] == ["hello"]


def test_no_config_dir_falls_back_to_new_document(qapp):
    # FakeConfig-style object without config_dir must not crash startup.
    class NoDir:
        def get_layout_config(self):
            return {}
        def set_layout_config(self, cfg):
            pass
        def save(self):
            pass
        def get_layout_llm_provider(self):
            return "google"

    tab = LayoutTab(config=NoDir())
    assert tab.document is not None and len(tab.document.pages) == 1
    assert tab._session_path() is None
