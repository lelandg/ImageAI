"""Construction + CRUD smoke tests (offscreen)."""
import pytest

pytest.importorskip("PySide6")

from core.styles.models import Style
from core.styles.store import StyleStore


class FakeConfig(dict):
    def get(self, k, d=None):
        return dict.get(self, k, d)
    def set(self, k, v):
        self[k] = v
    def save(self):
        pass
    def get_api_key(self, provider):
        return None


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def store(tmp_path):
    s = StyleStore(base_dir=tmp_path / "styles")
    s.save(Style(id="water", name="Water", prompt_text="washes",
                 description="soft"))
    return s


def _dialog(store):
    from gui.styles.style_manager_dialog import StyleManagerDialog
    return StyleManagerDialog(FakeConfig(), store=store)


def test_dialog_constructs_and_lists(qapp, store):
    dlg = _dialog(store)
    assert dlg.style_list.count() == 1
    assert dlg.style_list.item(0).text() == "Water"


def test_selecting_populates_fields(qapp, store):
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(0)
    assert dlg.name_edit.text() == "Water"
    assert dlg.prompt_text_edit.toPlainText() == "washes"
    assert dlg.placement_combo.currentText() == "suffix"


def test_save_writes_edits_back(qapp, store):
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(0)
    dlg.prompt_text_edit.setPlainText("new text")
    dlg.placement_combo.setCurrentText("prefix")
    dlg._save_current()
    s = store.get("water")
    assert s.prompt_text == "new text" and s.placement == "prefix"


def test_new_and_delete(qapp, store, monkeypatch):
    dlg = _dialog(store)
    monkeypatch.setattr(
        "gui.styles.style_manager_dialog.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("Fresh", True)))
    dlg._on_new()
    assert store.get_by_name("Fresh") is not None
    assert dlg.style_list.count() == 2
    monkeypatch.setattr(
        "gui.styles.style_manager_dialog.show_question",
        lambda *a, **k: True)
    dlg.style_list.setCurrentRow([dlg.style_list.item(i).text()
                                  for i in range(dlg.style_list.count())].index("Fresh"))
    dlg._on_delete()
    assert store.get_by_name("Fresh") is None


def test_save_auto_selects_exemplars_when_none_starred(qapp, store, tmp_path):
    from PIL import Image
    s = store.get("water")
    imgs = []
    for i, color in enumerate([(255, 0, 0), (0, 255, 0)]):
        p = tmp_path / f"a{i}.png"
        Image.new("RGB", (16, 16), color).save(p)
        imgs.append(p)
    store.add_reference_images(s, imgs)
    store.save(s)
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(0)
    # Nothing checked in refs_list — Save should auto-select the first N.
    dlg._save_current()
    saved = store.get("water")
    assert saved.exemplars == saved.reference_images[:2]


def test_duplicate_preserves_exemplar_identity(qapp, store, tmp_path):
    from PIL import Image
    s = store.get("water")
    imgs = []
    for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255)]):
        p = tmp_path / f"c{i}.png"
        Image.new("RGB", (16, 16), color).save(p)
        imgs.append(p)
    store.add_reference_images(s, imgs)
    s.exemplars = [s.reference_images[2]]  # star the LAST ref only
    store.save(s)
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(0)
    dlg._on_duplicate()
    dup = store.get_by_name("Water copy")
    assert len(dup.exemplars) == 1
    src_pixel = Image.open(store.style_dir(s.id) / s.reference_images[2]).convert("RGB").getpixel((0, 0))
    dup_pixel = Image.open(store.style_dir(dup.id) / dup.exemplars[0]).convert("RGB").getpixel((0, 0))
    # Compare pixel data, not raw bytes: add_reference_images re-encodes to
    # JPEG on every copy (double re-encode here — the fixture's own copy,
    # then this duplicate's copy), and byte-for-byte JPEG re-encoding isn't
    # guaranteed stable. A small tolerance absorbs that lossy rounding while
    # still failing hard if duplicate() ever copies the wrong (red/green)
    # source image for this exemplar — the starred IMAGE, not the starred
    # POSITION, is what must survive.
    assert all(abs(a - b) <= 2 for a, b in zip(src_pixel, dup_pixel)), (src_pixel, dup_pixel)
    assert dup_pixel[2] > 200 and dup_pixel[0] < 50 and dup_pixel[1] < 50  # blue, not red/green


def _row_for(dlg, name):
    return [dlg.style_list.item(i).text()
            for i in range(dlg.style_list.count())].index(name)


def test_pending_descriptor_does_not_leak_across_styles(qapp, store):
    """Analyze A, switch to B without saving, Save must not write A's
    descriptor onto B (regression for PR #35 review item 1)."""
    store.save(Style(id="clay", name="Clay", prompt_text="clay text"))
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(_row_for(dlg, "Water"))
    dlg._on_analysis_done({"descriptor": {"summary": "A-derived"},
                           "prompt_text": "A text"})
    dlg.style_list.setCurrentRow(_row_for(dlg, "Clay"))
    dlg._save_current()
    saved_clay = store.get("clay")
    assert saved_clay.descriptor.summary == ""
    assert saved_clay.prompt_text == "clay text"


def test_pending_descriptor_persists_when_saved_on_same_style(qapp, store):
    """Positive path: analyze-then-save on the SAME style still persists."""
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(_row_for(dlg, "Water"))
    dlg._on_analysis_done({"descriptor": {"summary": "Water-derived"},
                           "prompt_text": "watery text"})
    dlg._save_current()
    saved = store.get("water")
    assert saved.descriptor.summary == "Water-derived"
    assert saved.prompt_text == "watery text"
