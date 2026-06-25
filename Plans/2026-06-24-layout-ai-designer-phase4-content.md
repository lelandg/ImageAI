# Phase 4 — Content MVP (F-MVP) ⏳ 0%
**Last Updated:** 2026-06-24 17:05

Part of the AI Layout Designer redesign (whole-vision spec:
`Plans/2026-06-24-layout-ai-designer-design.md`, §9 Subsystem F). Phases 1–3 are
done and PR'd (#18 merged, #19/#20 open). This branch
(`feat/layout-ai-designer-phase4`, stacked on `feat/layout-ai-designer-phase3`)
implements **F-MVP**: fill the placeholders the designer/canvas already produce.

## Goal (spec §9 F-MVP)
> Select an image region → **import an image file** *or* pick from the existing
> generated-image history (`ImageHistoryDialog`) → fills the placeholder. Select a
> text region → **edit text**. This alone yields a finished, exportable page.

**Acceptance:** a user fills every region of an AI-designed page with imported
images and typed text and exports a correct PDF — **no** AI content features
required.

## Design decisions (from exploration)
- **Reuse `gui/layout/image_history_dialog.py`** as-is: `ImageHistoryDialog(config,
  parent)` browses generated images via sidecar metadata; `get_selected_image()`
  returns the chosen path. API fits the "From history…" picker exactly.
- **Build a NEW `gui/layout/content_inspector.py`**; do **not** revive the retired
  `gui/layout/inspector_widget.py` (template-era, uses the legacy `TextBlock`/
  `ImageBlock` model; confirmed: zero live references).
- **Single-mutator pattern:** the inspector never mutates the document. It displays
  the selected `Region` and emits `regionContentChanged(region_id, value)`.
  `LayoutTab` owns all document mutation (consistent with `apply_style` /
  `apply_designer_result`): it looks up the region by id and sets `image_ref`
  (image kind) or `text` (text kind), then `_refresh()`. The renderer already draws
  `image_ref` scaled-to-fit and resolves text styles, so a content change is just
  "set attribute → re-render".

## Architecture touch-points (already built)
- `core/layout/qt_renderer.py::_add_image_region` draws a placeholder rect (with
  selectable flags) then, if `image_ref` loads, a pixmap on top. **Bug:** the
  pixmap gets `setData(0, r.id)` but **not** the selectable flags, so a *filled*
  image region can't be re-selected by clicking it (the non-selectable pixmap on
  top swallows the click). Fixed in Task 1.
- `gui/layout/canvas_widget.py` emits `regionSelected(str)` ("" on deselect);
  `selected_region_id()` reads `item.data(0)`.
- `gui/layout/layout_tab.py`: `_adopt_document` centralizes load paths; `_refresh`
  → `canvas.load_page(page, style)`. Add inspector here.

---

## Task 1 — Renderer: filled image regions are selectable ⏳
**File:** `core/layout/qt_renderer.py` · **Test:** `tests/layout/test_qt_renderer.py`

Apply the selectable flags to the loaded-image pixmap so clicking a filled image
selects its region (prerequisite for editing already-filled regions).

### Test (add to `tests/layout/test_qt_renderer.py`)
```python
def test_filled_image_region_is_selectable(qapp, tmp_path):
    from PySide6.QtWidgets import QGraphicsItem
    from PySide6.QtGui import QImage
    from PySide6.QtCore import Qt
    img_path = tmp_path / "ref.png"
    im = QImage(20, 20, QImage.Format_RGB32)
    im.fill(Qt.white)
    assert im.save(str(img_path))
    page = PageSpec(page_size_px=(200, 150), background="#FFFFFF", regions=[
        Region(id="img1", kind="image", bbox=(10, 10, 80, 80), image_ref=str(img_path))])
    scene = qt_renderer.build_scene(page, selectable=True)
    sel = [it for it in scene.items()
           if (it.flags() & QGraphicsItem.ItemIsSelectable) and it.data(0) == "img1"]
    assert sel, "a filled image region must expose a selectable item carrying its id"
```

### Change (`_add_image_region`)
Replace the pixmap's `pi.setData(0, r.id)` with `_apply_flags(pi, selectable, r.id)`:
```python
    if r.image_ref:
        pix = QPixmap(r.image_ref)
        if not pix.isNull():
            scaled = pix.scaled(int(w), int(h), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pi = QGraphicsPixmapItem(scaled)
            pi.setPos(x, y)
            _apply_flags(pi, selectable, r.id)
            scene.addItem(pi)
            return
```

---

## Task 2 — `ContentInspector` widget ⏳
**File:** `gui/layout/content_inspector.py` (new) ·
**Test:** `tests/layout/test_content_inspector.py` (new)

A compact editor for the selected region. Image kind → "Import image…" /
"From history…" buttons + a ref label. Text kind → `QPlainTextEdit` + "Apply text".
Emits `regionContentChanged(region_id, value)`. No-selection → empty page.

### Implementation (`gui/layout/content_inspector.py`)
```python
"""Content inspector: edit the selected region's content (image ref or text)."""
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QLabel, QPushButton,
    QPlainTextEdit, QFileDialog,
)
from PySide6.QtCore import Signal

from core.layout.models import Region


class ContentInspector(QWidget):
    """Edits the content of the currently selected region.

    Emits ``regionContentChanged(region_id, value)``:
      - image region -> ``value`` is the chosen image path (becomes ``image_ref``)
      - text region  -> ``value`` is the new text
    The inspector only *displays* the region; ``LayoutTab`` owns the mutation.
    """

    regionContentChanged = Signal(str, str)  # (region_id, new_value)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._region: Optional[Region] = None
        self._build()
        self.set_region(None)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.header = QLabel("No region selected")
        self.header.setStyleSheet("font-weight: bold;")
        root.addWidget(self.header)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # page 0 — nothing selected
        self.stack.addWidget(QWidget())

        # page 1 — image controls
        img_page = QWidget()
        img_lay = QVBoxLayout(img_page)
        img_lay.setContentsMargins(0, 0, 0, 0)
        btn_row = QHBoxLayout()
        self.import_btn = QPushButton("Import image…")
        self.import_btn.clicked.connect(self._on_import_image)
        self.history_btn = QPushButton("From history…")
        self.history_btn.clicked.connect(self._on_from_history)
        btn_row.addWidget(self.import_btn)
        btn_row.addWidget(self.history_btn)
        btn_row.addStretch(1)
        img_lay.addLayout(btn_row)
        self.image_ref_label = QLabel("(no image)")
        self.image_ref_label.setWordWrap(True)
        self.image_ref_label.setStyleSheet("color: #666; font-size: 11px;")
        img_lay.addWidget(self.image_ref_label)
        img_lay.addStretch(1)
        self.stack.addWidget(img_page)

        # page 2 — text editor
        txt_page = QWidget()
        txt_lay = QVBoxLayout(txt_page)
        txt_lay.setContentsMargins(0, 0, 0, 0)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Type the text for this region…")
        self.text_edit.setFixedHeight(90)
        txt_lay.addWidget(self.text_edit)
        self.apply_text_btn = QPushButton("Apply text")
        self.apply_text_btn.clicked.connect(self._on_apply_text)
        txt_lay.addWidget(self.apply_text_btn)
        self.stack.addWidget(txt_page)

    def set_region(self, region: Optional[Region]):
        """Show the editor for ``region`` (or the empty page when None)."""
        self._region = region
        if region is None:
            self.header.setText("No region selected")
            self.stack.setCurrentIndex(0)
            return
        label = region.name or region.id
        if region.kind == "image":
            self.header.setText(f"Image region: {label}")
            self.image_ref_label.setText(region.image_ref or "(no image)")
            self.stack.setCurrentIndex(1)
        else:
            self.header.setText(f"Text region: {label}")
            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText(region.text or "")
            self.text_edit.blockSignals(False)
            self.stack.setCurrentIndex(2)

    # --- image ---
    def _on_import_image(self):
        if self._region is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if path:
            self._set_image_ref(path)

    def _on_from_history(self):
        if self._region is None:
            return
        from gui.layout.image_history_dialog import ImageHistoryDialog
        dlg = ImageHistoryDialog(self._config, self)
        if dlg.exec():
            path = dlg.get_selected_image()
            if path:
                self._set_image_ref(path)

    def _set_image_ref(self, path: str):
        self.image_ref_label.setText(path)
        self.regionContentChanged.emit(self._region.id, path)

    # --- text ---
    def _on_apply_text(self):
        if self._region is None:
            return
        self.regionContentChanged.emit(self._region.id, self.text_edit.toPlainText())
```

### Tests (`tests/layout/test_content_inspector.py`)
```python
# tests/layout/test_content_inspector.py
from core.layout.models import Region
from gui.layout.content_inspector import ContentInspector


def _img(rid="i", ref=None):
    return Region(id=rid, kind="image", bbox=(0, 0, 10, 10), image_ref=ref)


def _txt(rid="t", text=""):
    return Region(id=rid, kind="text", bbox=(0, 0, 10, 10), text=text)


def test_set_region_switches_editor(qapp):
    insp = ContentInspector()
    insp.set_region(_img(ref="/p.png"))
    assert insp.stack.currentIndex() == 1
    assert "/p.png" in insp.image_ref_label.text()
    insp.set_region(_txt(text="hello"))
    assert insp.stack.currentIndex() == 2
    assert insp.text_edit.toPlainText() == "hello"
    insp.set_region(None)
    assert insp.stack.currentIndex() == 0


def test_import_image_emits(qapp, monkeypatch):
    from gui.layout import content_inspector as ci
    insp = ContentInspector()
    insp.set_region(_img(rid="i1"))
    monkeypatch.setattr(ci.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("/tmp/x.png", "")))
    got = []
    insp.regionContentChanged.connect(lambda rid, v: got.append((rid, v)))
    insp.import_btn.click()
    assert got == [("i1", "/tmp/x.png")]


def test_import_cancelled_emits_nothing(qapp, monkeypatch):
    from gui.layout import content_inspector as ci
    insp = ContentInspector()
    insp.set_region(_img(rid="i1"))
    monkeypatch.setattr(ci.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    got = []
    insp.regionContentChanged.connect(lambda rid, v: got.append((rid, v)))
    insp.import_btn.click()
    assert got == []


def test_from_history_emits(qapp, monkeypatch):
    import gui.layout.image_history_dialog as ihd

    class FakeDlg:
        def __init__(self, config, parent=None):
            pass

        def exec(self):
            return True

        def get_selected_image(self):
            return "/hist/a.png"

    monkeypatch.setattr(ihd, "ImageHistoryDialog", FakeDlg)
    insp = ContentInspector(config=object())
    insp.set_region(_img(rid="i2"))
    got = []
    insp.regionContentChanged.connect(lambda rid, v: got.append((rid, v)))
    insp.history_btn.click()
    assert got == [("i2", "/hist/a.png")]


def test_apply_text_emits(qapp):
    insp = ContentInspector()
    insp.set_region(_txt(rid="t1", text="old"))
    got = []
    insp.regionContentChanged.connect(lambda rid, v: got.append((rid, v)))
    insp.text_edit.setPlainText("new text")
    insp.apply_text_btn.click()
    assert got == [("t1", "new text")]
```

---

## Task 3 — Wire `ContentInspector` into `LayoutTab` ⏳
**File:** `gui/layout/layout_tab.py` ·
**Test:** `tests/layout/test_layout_tab_content.py` (new)

Selection drives the inspector; content edits mutate the document and re-render.
Expose a programmatic `set_region_content(region_id, value)` (used by tests and
re-used by Phase 5's place-by-id). Reset the inspector on every document adopt.

### Changes (`gui/layout/layout_tab.py`)
1. Import: `from gui.layout.content_inspector import ContentInspector`.
2. In `_build()`, after `self.canvas` is added:
```python
        self.inspector = ContentInspector(self.config)
        self.inspector.regionContentChanged.connect(self._on_region_content_changed)
        root.addWidget(self.inspector)
        self.canvas.regionSelected.connect(self._on_region_selected)
```
3. In `_adopt_document()`, after the style-panel reset, reset the inspector too:
```python
        if hasattr(self, "inspector"):
            self.inspector.set_region(None)
```
4. New methods (place after `_refresh`):
```python
    # --- content inspector ---
    def _find_region(self, region_id: str):
        if not region_id or not self.document or not self.document.pages:
            return None
        for r in self.document.pages[0].regions:
            if r.id == region_id:
                return r
        return None

    def _on_region_selected(self, region_id: str):
        self.inspector.set_region(self._find_region(region_id))

    def _on_region_content_changed(self, region_id: str, value: str):
        self.set_region_content(region_id, value)

    def set_region_content(self, region_id: str, value: str):
        """Apply edited content to a region and re-render (programmatic API)."""
        region = self._find_region(region_id)
        if region is None:
            return
        if region.kind == "image":
            region.image_ref = value
        else:
            region.text = value
        self._refresh()
```

### Tests (`tests/layout/test_layout_tab_content.py`)
```python
# tests/layout/test_layout_tab_content.py
from core.layout import designer
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tab_with_regions():
    tab = LayoutTab(config=FakeConfig())
    tab.apply_designer_result(designer.DesignerResult(regions=[
        designer.Region(id="img", kind="image", bbox=(0, 0, 100, 100)),
        designer.Region(id="txt", kind="text", bbox=(0, 110, 100, 40), text="", role="title"),
    ]), user_text="page")
    return tab


def test_selecting_region_populates_inspector(qapp):
    tab = _tab_with_regions()
    tab._on_region_selected("img")
    assert tab.inspector.stack.currentIndex() == 1   # image editor
    tab._on_region_selected("txt")
    assert tab.inspector.stack.currentIndex() == 2   # text editor
    tab._on_region_selected("")                      # deselect
    assert tab.inspector.stack.currentIndex() == 0


def test_image_content_change_sets_image_ref(qapp):
    tab = _tab_with_regions()
    tab._on_region_content_changed("img", "/path/to/pic.png")
    assert tab.document.pages[0].regions[0].image_ref == "/path/to/pic.png"


def test_text_content_change_sets_text(qapp):
    tab = _tab_with_regions()
    tab._on_region_content_changed("txt", "Once upon a time")
    assert tab.document.pages[0].regions[1].text == "Once upon a time"


def test_set_region_content_unknown_id_is_noop(qapp):
    tab = _tab_with_regions()
    tab.set_region_content("nope", "x")  # must not raise
    assert tab.document.pages[0].regions[0].image_ref is None


def test_inspector_resets_on_new_document(qapp):
    tab = _tab_with_regions()
    tab._on_region_selected("img")
    assert tab.inspector.stack.currentIndex() == 1
    tab.new_document()
    assert tab.inspector.stack.currentIndex() == 0
```

---

## Task 4 — End-to-end acceptance ⏳
**File:** `tests/layout/test_layout_tab_content.py` (extend)

Prove the F-MVP acceptance: design a page, fill an image region (real file) and a
text region, export a valid PDF.

```python
def test_fill_image_and_text_then_export_pdf(qapp, tmp_path):
    from PySide6.QtGui import QImage
    from PySide6.QtCore import Qt
    tab = _tab_with_regions()

    img_path = tmp_path / "pic.png"
    im = QImage(40, 40, QImage.Format_RGB32)
    im.fill(Qt.blue)
    assert im.save(str(img_path))

    tab.set_region_content("img", str(img_path))
    tab.set_region_content("txt", "The Title")

    page = tab.document.pages[0]
    assert page.regions[0].image_ref == str(img_path)
    assert page.regions[1].text == "The Title"

    out = tmp_path / "out.pdf"
    tab.export_pdf_to(str(out))
    assert out.exists() and out.read_bytes()[:4] == b"%PDF"
```

---

## Process
- TDD per task: write/extend the test, watch it fail, implement, `QT_QPA_PLATFORM=
  offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` → green, 0 warnings.
- After all 4 tasks: **whole-branch review on opus** over `merge-base..HEAD`, one
  consolidated fix wave, completion summary, push, **stacked PR** (base =
  `feat/layout-ai-designer-phase3`).
- Python: `.venv_linux/bin/python` only. No `cd`. Commit subjects ≤72 chars with the
  Co-Authored-By / Claude-Session trailers.

## Out of scope (deferred to Phase 5 / later)
- Per-region AI prompt help, "Send to Image tab", batch placement, layout-complete
  mode, `.iaibundle` (all F-AI / bundles — Phase 5).
- PNG transparency and image-path page backgrounds (renderer deferrals noted in the
  Phase 1/3 summaries); not required for the F-MVP PDF acceptance.
- Per-region role picker / custom-role editor (Phase 3 deferral).
