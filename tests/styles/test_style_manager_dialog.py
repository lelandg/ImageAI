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
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    import gc
    app = QApplication.instance() or QApplication([])
    yield app
    # Collect this test's abandoned dialog at a safe point. Every dialog is
    # a reference cycle (child QObjects/slots hold the dialog), and letting
    # the cyclic GC free one mid-event-pump in a LATER test destroys a
    # QDialog from inside Qt event delivery — an intermittent segfault.
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    gc.collect()


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


def test_unsafe_ref_entries_are_skipped_in_ui(qapp, store):
    """Hostile/malformed reference_images entries must not crash the
    thumbnail or duplicate paths (issue #37)."""
    s = store.get("water")
    s.reference_images = ["../../evil.jpg", 7]
    store.save(s)
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(0)          # must not raise
    assert dlg.refs_list.count() == 0        # unsafe entries never listed
    dlg._on_duplicate()                      # must not raise / copy them
    dup = store.get_by_name("Water copy")
    assert dup.reference_images == []


def test_style_list_shows_exemplar_thumbnail(qapp, store, tmp_path):
    from PIL import Image
    s = store.get("water")
    p = tmp_path / "t.png"
    Image.new("RGB", (16, 16), (255, 0, 0)).save(p)
    store.add_reference_images(s, [p])
    s.exemplars = list(s.reference_images)
    store.save(s)
    dlg = _dialog(store)
    assert not dlg.style_list.item(0).icon().isNull()


def test_style_list_thumbnail_falls_back_past_missing_ref(qapp, store, tmp_path):
    """First ref missing on disk -> icon comes from the next existing one."""
    from PIL import Image
    s = store.get("water")
    imgs = []
    for i in range(2):
        p = tmp_path / f"f{i}.png"
        Image.new("RGB", (16, 16), (0, 255, 0)).save(p)
        imgs.append(p)
    store.add_reference_images(s, imgs)
    store.save(s)
    (store.style_dir(s.id) / s.reference_images[0]).unlink()
    dlg = _dialog(store)
    assert not dlg.style_list.item(0).icon().isNull()


def test_llm_combo_and_geometry_persist(qapp, store):
    dlg = _dialog(store)
    dlg.llm_provider_combo.setCurrentText("anthropic")
    dlg.llm_model_combo.setCurrentText("claude-test")
    dlg.reject()                       # real exit path -> on_dialog_close
    dlg2 = _dialog(store)
    assert dlg2.llm_provider_combo.currentText() == "anthropic"
    assert dlg2.llm_model_combo.currentText() == "claude-test"


def test_gui_analysis_populates_source_on_save(qapp, store):
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(0)
    dlg._analysis_source = {"provider": "openai", "model": "gpt-test",
                            "image_count": 2}
    dlg._on_analysis_done({"descriptor": {"summary": "x"}, "prompt_text": "t"})
    dlg._save_current()
    src = store.get("water").source
    assert src["provider"] == "openai" and src["model"] == "gpt-test"
    assert src["image_count"] == 2 and src["created"]


def test_image_paths_from_mime_filters_to_local_images(qapp, tmp_path):
    from PySide6.QtCore import QMimeData, QUrl
    from gui.styles.style_manager_dialog import _image_paths_from_mime
    (tmp_path / "a.png").write_bytes(b"x")
    (tmp_path / "b.txt").write_bytes(b"x")
    (tmp_path / "dir.png").mkdir()          # directory with image-like name
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path / "a.png")),
                  QUrl.fromLocalFile(str(tmp_path / "b.txt")),
                  QUrl.fromLocalFile(str(tmp_path / "dir.png")),
                  QUrl("https://example.com/c.jpg")])
    assert _image_paths_from_mime(mime) == [tmp_path / "a.png"]


def test_refs_grid_accepts_drops_and_adds(qapp, store, tmp_path):
    from PIL import Image
    p = tmp_path / "d.png"
    Image.new("RGB", (16, 16), (0, 0, 255)).save(p)
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(0)
    assert dlg.refs_list.acceptDrops()
    dlg.refs_list.files_dropped.emit([p])   # wiring under test
    assert store.get("water").reference_images  # image landed in the store


# ---- issue #37 coverage: live Analyze flow + orphan-worker detach ----------

class _FakeService:
    provider = "openai"
    model = "gpt-test"

    def __init__(self, config, provider=None, model=None):
        pass

    def derive(self, paths, progress_cb=None):
        if progress_cb:
            progress_cb("chunk 1/1")
        return {"descriptor": {"summary": "derived"},
                "prompt_text": "derived text"}


def _wait_until(qapp, predicate, timeout_s=8.0):
    import time
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _seed_ref(store, tmp_path, color=(255, 0, 0)):
    from PIL import Image
    s = store.get("water")
    p = tmp_path / "ref.png"
    Image.new("RGB", (16, 16), color).save(p)
    store.add_reference_images(s, [p])
    store.save(s)


def _dispose(qapp, dlg):
    """Deterministically destroy a dialog + its worker inside the test.

    The Analyze path connects worker signals to lambdas that close over the
    dialog (dlg -> worker -> lambda -> dlg cycle). Left to the cyclic GC,
    that cycle can be collected mid-event-pump in a LATER test, destroying
    the QDialog from inside Qt event delivery — an intermittent segfault.
    Dispose at a safe point instead: flush pending queued signals, run the
    deferred deletes (processEvents alone never handles DeferredDelete),
    then collect the cycle."""
    import gc
    from PySide6.QtCore import QCoreApplication, QEvent
    dlg.close()
    dlg.deleteLater()
    qapp.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    qapp.processEvents()
    gc.collect()


def test_analyze_click_end_to_end(qapp, store, tmp_path, monkeypatch):
    """Real button click -> real QThread worker -> UI updated on completion."""
    _seed_ref(store, tmp_path)
    monkeypatch.setattr("core.styles.analyzer.StyleAnalysisService", _FakeService)
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(0)
    dlg.analyze_btn.click()
    w = dlg._worker
    assert _wait_until(qapp, lambda: getattr(dlg, "_pending_descriptor", None))
    assert dlg.prompt_text_edit.toPlainText() == "derived text"
    assert dlg.analyze_btn.isEnabled()
    assert dlg._analysis_source["model"] == "gpt-test"
    assert dlg._pending_source["provider"] == "openai"
    assert w.wait(8000)
    _dispose(qapp, dlg)


def test_dialog_close_detaches_running_worker(qapp, store, tmp_path, monkeypatch):
    """Real close with an in-flight analysis exercises the _ORPHAN_WORKERS
    detach branch (issue #37 coverage item)."""
    import time
    from gui.styles import style_manager_dialog as smd

    class _SlowService(_FakeService):
        def derive(self, paths, progress_cb=None):
            time.sleep(3.0)      # outlives on_dialog_close's 2s wait
            return {"descriptor": {}, "prompt_text": ""}

    _seed_ref(store, tmp_path, color=(0, 255, 0))
    monkeypatch.setattr("core.styles.analyzer.StyleAnalysisService", _SlowService)
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(0)
    dlg.analyze_btn.click()
    w = dlg._worker
    assert w is not None and w.isRunning()
    dlg.reject()                             # DialogCleanupMixin -> on_dialog_close
    assert w in smd._ORPHAN_WORKERS          # detached, kept alive
    assert dlg._worker is None
    # The app-level input blocker must be gone: leaving it installed after
    # the dialog dies filters every event through a dead dialog (crash).
    assert dlg._input_blocker is None
    assert not dlg.is_operation_running()
    assert w.wait(8000)                      # worker finishes on its own
    assert _wait_until(qapp, lambda: w not in smd._ORPHAN_WORKERS)
    _dispose(qapp, dlg)
