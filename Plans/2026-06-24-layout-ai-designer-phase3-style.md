# AI Layout Designer — Phase 3 (Style System + Template Sharing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-project **style system** — font roles (whose set varies by content kind) and a color palette — that text regions reference by role name, resolved at render time; plus **layout-template export/import** (`.iailayout.json`: structure + shapes + styles + prompt scaffolding, no content) so layouts can be shared.

**Architecture:** A `ProjectStyle` (role-name → `TextStyle`, plus a color palette) lives on `DocumentSpec`. `core/layout/styles.py` seeds a sensible role set per content kind. The Qt renderer resolves a text region's `role` against the project style when the region has no explicit `text_style`. Template export strips content from a serialized document; import rebuilds an empty-content document with the same structure + style. A GUI `StylePanel` edits roles; the Layout tab seeds the style, renders with it, and gains template export/import.

**Tech Stack:** Python 3.12, PySide6 (`QGraphicsScene`/`QFont`, widgets), dataclasses, `pytest` (headless offscreen Qt). Builds on Phase 1+2 (`core/layout/{models,schema,qt_renderer,project_io}.py`, `gui/layout/{layout_tab,canvas_widget}.py`).

## Global Constraints

- Spec: `Plans/2026-06-24-layout-ai-designer-design.md` (§7 style system, §8 sharing/templates). This plan implements **Phase 3**.
- Python interpreter for all commands: `.venv_linux/bin/python` (never `.venv`). Run from repo root `/mnt/d/Documents/Code/GitHub/ImageAI`. **No `cd`.**
- GUI tests run **headless** under `QT_QPA_PLATFORM=offscreen` (already in `tests/conftest.py`; session `qapp` fixture). No `pytest-qt`.
- Fonts are referenced **by family name** (with fallbacks) — never embedded in templates (the spec defers font-file embedding to Phase 5 bundles).
- Backward compatible: `ProjectStyle` is optional on `DocumentSpec`; documents without a style render exactly as before. Do not break the Phase 1+2 suite (56 tests must stay green).
- Conventional Commits; commit subjects **≤72 chars**; commit after each task. Branch: `feat/layout-ai-designer-phase3`.
- Extend Phase 1/2 modules in place; all new renderer/canvas params default to `None`.

---

## File Structure

**Create:**
- `core/layout/styles.py` — `default_style_for(content_kind) -> ProjectStyle`.
- `core/layout/template_io.py` — `export_template` / `import_template`.
- `gui/layout/style_panel.py` — `StylePanel(QWidget)`.
- Tests: `tests/layout/test_styles.py`, `test_template_io.py`, `test_style_panel.py`, `test_layout_tab_style.py`; renderer-style assertions appended to `test_qt_renderer.py`.

**Modify:**
- `core/layout/models.py` — add `ProjectStyle`; add `style` field to `DocumentSpec`.
- `core/layout/schema.py` — `project_style_to_dict`/`project_style_from_dict`; include `style` in `document_to_dict`/`document_from_dict`.
- `core/layout/qt_renderer.py` — `build_scene`/`render_page_to_image`/`save_page_png` accept a `style`; `export_document_pdf` passes `doc.style`; `_add_text_region` resolves region `role` → project style.
- `gui/layout/canvas_widget.py` — `load_page(page, style=None)`.
- `gui/layout/layout_tab.py` — seed style on `new_document`; pass `self.document.style` when rendering; embed `StylePanel`; add Export/Import Template.

---

### Task 1: ProjectStyle model + content-kind defaults + persistence

**Files:**
- Modify: `core/layout/models.py`, `core/layout/schema.py`
- Create: `core/layout/styles.py`
- Test: `tests/layout/test_styles.py`

**Interfaces:**
- Consumes: Phase-1 `TextStyle`, `DocumentSpec`, `schema.document_to_dict`/`from_dict`.
- Produces:
  - `models.ProjectStyle(font_roles: dict[str, TextStyle] = {}, palette: dict[str, str] = {}, default_text_role: str = "body")`
  - `DocumentSpec.style: ProjectStyle | None = None`
  - `schema.project_style_to_dict(s)`/`project_style_from_dict(d)`; `document_to_dict`/`from_dict` round-trip `style`
  - `styles.default_style_for(content_kind: str) -> ProjectStyle`

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_styles.py
from core.layout.models import ProjectStyle, DocumentSpec, PageSpec, TextStyle
from core.layout import schema, styles


def test_default_style_for_comic_has_dialogue_role():
    st = styles.default_style_for("comic")
    assert "dialogue" in st.font_roles
    assert isinstance(st.font_roles["dialogue"], TextStyle)
    assert st.default_text_role == "dialogue"
    assert st.palette.get("text")


def test_default_style_for_children_has_title_and_narration():
    st = styles.default_style_for("children")
    assert set(["title", "narration"]).issubset(st.font_roles.keys())


def test_default_style_for_unknown_kind_falls_back():
    st = styles.default_style_for("totally-made-up")
    assert "body" in st.font_roles and "title" in st.font_roles


def test_project_style_roundtrip_via_schema():
    doc = DocumentSpec(title="D", pages=[PageSpec(page_size_px=(100, 100))],
                       style=styles.default_style_for("comic"))
    again = schema.document_from_dict(schema.document_to_dict(doc))
    assert again.style is not None
    assert "dialogue" in again.style.font_roles
    assert again.style.font_roles["dialogue"].size_px == doc.style.font_roles["dialogue"].size_px
    assert again.style.default_text_role == "dialogue"


def test_document_without_style_roundtrips_none():
    doc = DocumentSpec(title="D", pages=[PageSpec(page_size_px=(100, 100))])
    again = schema.document_from_dict(schema.document_to_dict(doc))
    assert again.style is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_styles.py -v`
Expected: FAIL (`ImportError`: cannot import `ProjectStyle`/`styles`).

- [ ] **Step 3: Add `ProjectStyle` + `style` to `core/layout/models.py`**

Add after `Snapshot` (before `migrate_legacy_blocks`, or near the other style dataclasses — anywhere after `TextStyle`):

```python
@dataclass
class ProjectStyle:
    """Per-project named font roles + color palette."""

    font_roles: Dict[str, TextStyle] = field(default_factory=dict)
    palette: Dict[str, str] = field(default_factory=dict)  # name -> hex
    default_text_role: str = "body"
```

Extend `DocumentSpec` — add as the LAST field (after `history`):

```python
    style: Optional["ProjectStyle"] = None
```

- [ ] **Step 4: Create `core/layout/styles.py`**

```python
"""Default project style (font roles + palette) seeded by content kind."""
from typing import Dict, List

from core.layout.models import ProjectStyle, TextStyle


def _role(family: List[str], size: int, weight: str = "regular", color: str = "#111111") -> TextStyle:
    return TextStyle(family=list(family), size_px=size, weight=weight, color=color)


_PALETTE = {"background": "#FFFFFF", "text": "#111111", "accent": "#2C7BE5"}

_KIND_ROLES: Dict[str, Dict[str, TextStyle]] = {
    "children": {
        "title": _role(["Georgia", "DejaVu Serif"], 64, "bold"),
        "narration": _role(["Georgia", "DejaVu Serif"], 36),
    },
    "comic": {
        "logo_title": _role(["Impact", "DejaVu Sans"], 72, "black"),
        "dialogue": _role(["Comic Sans MS", "DejaVu Sans"], 28),
        "sfx": _role(["Impact", "DejaVu Sans"], 48, "black", "#D7263D"),
        "caption": _role(["Arial", "DejaVu Sans"], 24),
    },
    "magazine": {
        "masthead": _role(["Georgia", "DejaVu Serif"], 72, "bold"),
        "headline": _role(["Georgia", "DejaVu Serif"], 48, "bold"),
        "body": _role(["Arial", "DejaVu Sans"], 28),
        "caption": _role(["Arial", "DejaVu Sans"], 22),
        "pull_quote": _role(["Georgia", "DejaVu Serif"], 36, "semibold", "#2C7BE5"),
    },
    "scientific": {
        "title": _role(["Times New Roman", "DejaVu Serif"], 56, "bold"),
        "heading": _role(["Times New Roman", "DejaVu Serif"], 36, "bold"),
        "body": _role(["Times New Roman", "DejaVu Serif"], 28),
        "caption": _role(["Arial", "DejaVu Sans"], 22),
    },
}
# aliases
_KIND_ROLES["comic_strip"] = _KIND_ROLES["comic"]
_KIND_ROLES["newspaper"] = _KIND_ROLES["magazine"]

_DEFAULT_ROLE = {
    "children": "narration", "comic": "dialogue", "comic_strip": "dialogue",
    "magazine": "body", "newspaper": "body", "scientific": "body",
}

_FALLBACK_ROLES = {
    "title": _role(["Arial", "DejaVu Sans"], 56, "bold"),
    "body": _role(["Arial", "DejaVu Sans"], 28),
}


def default_style_for(content_kind: str) -> ProjectStyle:
    roles = _KIND_ROLES.get(content_kind, _FALLBACK_ROLES)
    return ProjectStyle(
        font_roles={name: _role(ts.family, ts.size_px, ts.weight, ts.color)
                    for name, ts in roles.items()},
        palette=dict(_PALETTE),
        default_text_role=_DEFAULT_ROLE.get(content_kind, "body"),
    )
```

- [ ] **Step 5: Add style serialization to `core/layout/schema.py`**

Add `ProjectStyle` and `TextStyle` to the `from core.layout.models import (...)` line if not already present. Add:

```python
def project_style_to_dict(s: "ProjectStyle") -> Dict:
    return {
        "font_roles": {name: asdict(ts) for name, ts in s.font_roles.items()},
        "palette": dict(s.palette),
        "default_text_role": s.default_text_role,
    }


def project_style_from_dict(d: Dict) -> "ProjectStyle":
    from core.layout.models import ProjectStyle
    return ProjectStyle(
        font_roles={name: TextStyle(**ts) for name, ts in d.get("font_roles", {}).items()},
        palette=dict(d.get("palette", {})),
        default_text_role=d.get("default_text_role", "body"),
    )
```

In `document_to_dict`, add:

```python
        "style": project_style_to_dict(doc.style) if doc.style else None,
```

In `document_from_dict`, add to the `DocumentSpec(...)` construction:

```python
        style=project_style_from_dict(d["style"]) if d.get("style") else None,
```

- [ ] **Step 6: Run tests + full suite**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_styles.py -v`
Expected: PASS (5 passed).
Run: `.venv_linux/bin/python -m pytest tests/layout/ -q`
Expected: all pass (61 now), 0 warnings.

- [ ] **Step 7: Commit**

```bash
git add core/layout/models.py core/layout/styles.py core/layout/schema.py tests/layout/test_styles.py
git commit -m "feat(layout): add ProjectStyle model, content-kind defaults, persistence"
```

---

### Task 2: Renderer + canvas resolve font roles

**Files:**
- Modify: `core/layout/qt_renderer.py`, `gui/layout/canvas_widget.py`
- Test: `tests/layout/test_qt_renderer.py` (append)

**Interfaces:**
- Consumes: `ProjectStyle`, Phase-1 `build_scene`/render/export, `Region.role`/`text_style`.
- Produces:
  - `qt_renderer.build_scene(page, *, selectable=False, style=None)`
  - `qt_renderer.render_page_to_image(page, *, style=None)`; `save_page_png(page, path, *, style=None)`
  - `export_document_pdf(doc, path, dpi=300)` resolves `doc.style`
  - text regions with a `role` and no `text_style` render using `style.font_roles[role]`
  - `canvas_widget.CanvasWidget.load_page(page, style=None)`

- [ ] **Step 1: Write the failing test (append to `tests/layout/test_qt_renderer.py`)**

```python
def test_text_region_resolves_font_role_from_style(qapp):
    from core.layout.models import Region, PageSpec, ProjectStyle, TextStyle
    from core.layout import qt_renderer
    from PySide6.QtWidgets import QGraphicsSimpleTextItem
    style = ProjectStyle(font_roles={"title": TextStyle(family=["Georgia"], size_px=64, weight="bold")})
    page = PageSpec(page_size_px=(400, 200), regions=[
        Region(id="t", kind="text", bbox=(0, 0, 400, 100), text="Hi", role="title")])
    scene = qt_renderer.build_scene(page, style=style)
    texts = [it for it in scene.items() if isinstance(it, QGraphicsSimpleTextItem)]
    assert texts, "expected a text item"
    f = texts[0].font()
    assert f.pixelSize() == 64
    assert f.bold() is True


def test_explicit_text_style_overrides_role(qapp):
    from core.layout.models import Region, PageSpec, ProjectStyle, TextStyle
    from core.layout import qt_renderer
    from PySide6.QtWidgets import QGraphicsSimpleTextItem
    style = ProjectStyle(font_roles={"title": TextStyle(family=["Georgia"], size_px=64)})
    page = PageSpec(page_size_px=(400, 200), regions=[
        Region(id="t", kind="text", bbox=(0, 0, 400, 100), text="Hi", role="title",
               text_style=TextStyle(family=["Arial"], size_px=20))])
    scene = qt_renderer.build_scene(page, style=style)
    texts = [it for it in scene.items() if isinstance(it, QGraphicsSimpleTextItem)]
    assert texts[0].font().pixelSize() == 20  # explicit style wins
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_qt_renderer.py -k font_role -v`
Expected: FAIL (`build_scene() got an unexpected keyword argument 'style'`).

- [ ] **Step 3: Update `core/layout/qt_renderer.py`**

Replace `_add_text_region` with (rename the local style var to `ts`; add a `project_style` param; resolve role):

```python
def _add_text_region(scene: QGraphicsScene, r: Region, selectable: bool, project_style=None) -> None:
    x, y, w, h = r.bbox
    box = QGraphicsRectItem(QRectF(x, y, w, h))
    box.setBrush(QBrush(Qt.transparent))
    box.setPen(QPen(QColor("#CED4DA"), 1, Qt.DashLine))
    _apply_flags(box, selectable, r.id)
    scene.addItem(box)

    text = QGraphicsSimpleTextItem(r.text or "")
    ts = r.text_style
    if ts is None and project_style is not None and r.role:
        ts = project_style.font_roles.get(r.role)
    font = QFont()
    if ts:
        if ts.family:
            font.setFamily(ts.family[0])
        if ts.size_px:
            font.setPixelSize(ts.size_px)
        font.setBold(ts.weight in ("bold", "black", "semibold"))
        font.setItalic(ts.italic)
        text.setBrush(QBrush(QColor(ts.color)))
    text.setFont(font)
    text.setPos(x + 2, y + 2)
    scene.addItem(text)
```

Update `build_scene` signature + the text-region call:

```python
def build_scene(page: PageSpec, *, selectable: bool = False, style=None) -> QGraphicsScene:
    pw, ph = page.page_size_px
    scene = QGraphicsScene(0, 0, pw, ph)
    scene.setBackgroundBrush(QBrush(QColor(_resolve_bg(page))))
    for r in sorted(page.regions, key=lambda rr: rr.z):
        if r.kind == "image":
            _add_image_region(scene, r, selectable)
        else:
            _add_text_region(scene, r, selectable, project_style=style)
    return scene
```

Update `render_page_to_image` and `save_page_png`:

```python
def render_page_to_image(page: PageSpec, *, style=None) -> QImage:
    pw, ph = page.page_size_px
    scene = build_scene(page, style=style)
    img = QImage(pw, ph, QImage.Format_ARGB32)
    img.fill(QColor(_resolve_bg(page)))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)
    scene.render(painter, QRectF(0, 0, pw, ph), QRectF(0, 0, pw, ph))
    painter.end()
    return img


def save_page_png(page: PageSpec, path: str, *, style=None) -> None:
    render_page_to_image(page, style=style).save(path, "PNG")
```

In `export_document_pdf`, change the scene build inside the loop to pass the document style:

```python
        scene = build_scene(page, style=doc.style)
```

- [ ] **Step 4: Update `gui/layout/canvas_widget.py` `load_page`**

Change the signature and the `build_scene` call:

```python
    def load_page(self, page: PageSpec, style=None) -> None:
        old = self._scene
        if old is not None:
            try:
                old.selectionChanged.disconnect(self._on_selection_changed)
            except (RuntimeError, TypeError):
                pass
        self._page = page
        scene = qt_renderer.build_scene(page, selectable=True, style=style)
        scene.setParent(self)
        scene.selectionChanged.connect(self._on_selection_changed)
        self.setScene(scene)
        self._scene = scene
        self.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)
```

- [ ] **Step 5: Run tests + full suite**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_qt_renderer.py -v`
Expected: PASS (all, incl. 2 new).
Run: `.venv_linux/bin/python -m pytest tests/layout/ -q`
Expected: all pass, 0 warnings.

- [ ] **Step 6: Commit**

```bash
git add core/layout/qt_renderer.py gui/layout/canvas_widget.py tests/layout/test_qt_renderer.py
git commit -m "feat(layout): resolve text-region font roles from project style"
```

---

### Task 3: Template export / import

**Files:**
- Create: `core/layout/template_io.py`
- Test: `tests/layout/test_template_io.py`

**Interfaces:**
- Consumes: `schema.document_to_dict`/`document_from_dict`.
- Produces:
  - `template_io.export_template(doc: DocumentSpec, path: str) -> None` (strips content, keeps geometry/shape/style/prompt/role + ProjectStyle; drops history)
  - `template_io.import_template(path: str) -> DocumentSpec` (structure + style, empty content)

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_template_io.py
from core.layout.models import Region, PageSpec, DocumentSpec
from core.layout import template_io, styles


def _doc():
    page = PageSpec(page_size_px=(500, 500), regions=[
        Region(id="img", kind="image", bbox=(0, 0, 200, 200), image_ref="/a.png",
               prompt="a red car"),
        Region(id="txt", kind="text", bbox=(0, 220, 500, 60), text="My Title", role="title"),
    ])
    doc = DocumentSpec(title="Proj", content_kind="comic", pages=[page],
                       style=styles.default_style_for("comic"))
    return doc


def test_export_strips_content_keeps_structure(tmp_path):
    p = tmp_path / "t.iailayout.json"
    template_io.export_template(_doc(), str(p))
    loaded = template_io.import_template(str(p))
    regions = loaded.pages[0].regions
    # geometry + shape + role + prompt preserved
    assert [r.id for r in regions] == ["img", "txt"]
    assert regions[0].bbox == (0, 0, 200, 200)
    assert regions[0].prompt == "a red car"
    assert regions[1].role == "title"
    # content stripped
    assert regions[0].image_ref is None
    assert regions[1].text == ""
    # style preserved
    assert loaded.style is not None and "dialogue" in loaded.style.font_roles
    # content_kind preserved, history dropped
    assert loaded.content_kind == "comic"
    assert loaded.history == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_template_io.py -v`
Expected: FAIL (`ModuleNotFoundError: core.layout.template_io`).

- [ ] **Step 3: Create `core/layout/template_io.py`**

```python
"""Layout-template export/import: shareable structure + style, no content."""
import json
from pathlib import Path

from core.layout.models import DocumentSpec
from core.layout import schema


def export_template(doc: DocumentSpec, path: str) -> None:
    data = schema.document_to_dict(doc)
    data["history"] = []  # templates carry no iteration history
    for page in data.get("pages", []):
        for region in page.get("regions", []):
            region["text"] = ""        # strip text content
            region["image_ref"] = None  # strip image content
            # keep: id, kind, shape, bbox, points, z, role, prompt, styles
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def import_template(path: str) -> DocumentSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return schema.document_from_dict(data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_template_io.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add core/layout/template_io.py tests/layout/test_template_io.py
git commit -m "feat(layout): add layout-template export/import (.iailayout.json)"
```

---

### Task 4: Style panel (GUI)

**Files:**
- Create: `gui/layout/style_panel.py`
- Test: `tests/layout/test_style_panel.py`

**Interfaces:**
- Consumes: `ProjectStyle`, `TextStyle`.
- Produces:
  - `style_panel.StylePanel(parent=None)` — `QWidget`; signal `styleChanged(object)` (ProjectStyle); methods `set_style(style)`, `style() -> ProjectStyle`.

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_style_panel.py
from core.layout.models import ProjectStyle, TextStyle
from gui.layout.style_panel import StylePanel


def _style():
    return ProjectStyle(font_roles={
        "title": TextStyle(family=["Georgia"], size_px=64, weight="bold"),
        "body": TextStyle(family=["Arial"], size_px=28)},
        palette={"text": "#111111"}, default_text_role="body")


def test_panel_lists_roles(qapp):
    p = StylePanel()
    p.set_style(_style())
    assert p.role_combo.count() == 2


def test_editing_family_updates_style_and_emits(qapp):
    p = StylePanel()
    p.set_style(_style())
    got = []
    p.styleChanged.connect(lambda s: got.append(s))
    p.role_combo.setCurrentText("title")
    p.family_edit.setText("Impact")
    p._on_field_changed()  # internal slot
    assert p.style().font_roles["title"].family[0] == "Impact"
    assert got and got[-1].font_roles["title"].family[0] == "Impact"


def test_editing_size(qapp):
    p = StylePanel()
    p.set_style(_style())
    p.role_combo.setCurrentText("body")
    p.size_spin.setValue(40)
    p._on_field_changed()
    assert p.style().font_roles["body"].size_px == 40
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_style_panel.py -v`
Expected: FAIL (`ModuleNotFoundError: gui.layout.style_panel`).

- [ ] **Step 3: Create `gui/layout/style_panel.py`**

```python
"""Project style editor: per-role font family/size/color + palette."""
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QComboBox, QLineEdit, QSpinBox, QLabel,
)
from PySide6.QtCore import Signal

from core.layout.models import ProjectStyle, TextStyle


class StylePanel(QWidget):
    styleChanged = Signal(object)  # ProjectStyle

    def __init__(self, parent=None):
        super().__init__(parent)
        self._style = ProjectStyle()
        self._build()

    def _build(self):
        form = QFormLayout(self)
        self.role_combo = QComboBox()
        self.role_combo.currentTextChanged.connect(self._on_role_selected)
        form.addRow(QLabel("Role:"), self.role_combo)
        self.family_edit = QLineEdit()
        self.family_edit.editingFinished.connect(self._on_field_changed)
        form.addRow(QLabel("Font family:"), self.family_edit)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 2000)
        self.size_spin.valueChanged.connect(self._on_field_changed)
        form.addRow(QLabel("Size (px):"), self.size_spin)
        self.color_edit = QLineEdit()
        self.color_edit.editingFinished.connect(self._on_field_changed)
        form.addRow(QLabel("Color (hex):"), self.color_edit)

    def set_style(self, style: ProjectStyle):
        self._style = style
        self.role_combo.blockSignals(True)
        self.role_combo.clear()
        self.role_combo.addItems(sorted(style.font_roles.keys()))
        self.role_combo.blockSignals(False)
        if self.role_combo.count():
            self.role_combo.setCurrentIndex(0)
            self._load_role(self.role_combo.currentText())

    def style(self) -> ProjectStyle:
        return self._style

    def _load_role(self, role: str):
        ts = self._style.font_roles.get(role)
        if ts is None:
            return
        for w in (self.family_edit, self.size_spin, self.color_edit):
            w.blockSignals(True)
        self.family_edit.setText(ts.family[0] if ts.family else "")
        self.size_spin.setValue(ts.size_px)
        self.color_edit.setText(ts.color)
        for w in (self.family_edit, self.size_spin, self.color_edit):
            w.blockSignals(False)

    def _on_role_selected(self, role: str):
        if role:
            self._load_role(role)

    def _on_field_changed(self):
        role = self.role_combo.currentText()
        if not role or role not in self._style.font_roles:
            return
        old = self._style.font_roles[role]
        self._style.font_roles[role] = TextStyle(
            family=[self.family_edit.text() or "Arial"],
            weight=old.weight, italic=old.italic,
            size_px=self.size_spin.value(),
            line_height=old.line_height,
            color=self.color_edit.text() or "#111111",
            align=old.align, wrap=old.wrap, letter_spacing=old.letter_spacing,
        )
        self.styleChanged.emit(self._style)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_style_panel.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add gui/layout/style_panel.py tests/layout/test_style_panel.py
git commit -m "feat(layout): add project style panel (font roles editor)"
```

---

### Task 5: Integrate style + templates into the Layout tab

**Files:**
- Modify: `gui/layout/layout_tab.py`
- Test: `tests/layout/test_layout_tab_style.py`

**Interfaces:**
- Consumes: `styles.default_style_for`, `StylePanel`, `template_io`, `qt_renderer` (style-aware).
- Produces (on `LayoutTab`):
  - `new_document` seeds `self.document.style = styles.default_style_for(content_kind)`
  - `_refresh` renders with `self.document.style`
  - `apply_style(style) -> None` (set + re-render)
  - `export_template_to(path)` / `import_template_from(path)`
  - a `StylePanel` (`self.style_panel`) wired so its `styleChanged` calls `apply_style`
  - toolbar "Export Template…" / "Import Template…" entries

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_layout_tab_style.py
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def test_new_document_has_style(qapp):
    tab = LayoutTab(config=FakeConfig())
    assert tab.document.style is not None
    assert tab.document.style.font_roles  # non-empty role set


def test_apply_style_updates_document(qapp):
    from core.layout import styles
    tab = LayoutTab(config=FakeConfig())
    st = styles.default_style_for("comic")
    tab.apply_style(st)
    assert "dialogue" in tab.document.style.font_roles


def test_export_then_import_template_roundtrip(qapp, tmp_path):
    from core.layout import designer
    tab = LayoutTab(config=FakeConfig())
    tab.apply_designer_result(
        designer.DesignerResult(regions=[designer.Region(id="a", kind="text",
                                bbox=(0, 0, 100, 30), text="Hi", role="title")]),
        user_text="v1")
    p = tmp_path / "t.iailayout.json"
    tab.export_template_to(str(p))
    tab2 = LayoutTab(config=FakeConfig())
    tab2.import_template_from(str(p))
    regions = tab2.document.pages[0].regions
    assert [r.id for r in regions] == ["a"]
    assert regions[0].text == ""          # content stripped
    assert regions[0].role == "title"     # structure kept
    assert tab2.document.style is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_layout_tab_style.py -v`
Expected: FAIL (`AttributeError`: `apply_style`/`export_template_to`, or `style is None`).

- [ ] **Step 3: Wire style + templates into `gui/layout/layout_tab.py`**

Add imports near the others:

```python
from core.layout import styles, template_io
from gui.layout.style_panel import StylePanel
```

Extend the toolbar loop list (add two entries):

```python
            ("Export Template…", self._export_template_dialog),
            ("Import Template…", self._import_template_dialog),
```

After embedding the designer panel in `_build`, add the style panel:

```python
        self.style_panel = StylePanel()
        self.style_panel.styleChanged.connect(self.apply_style)
        root.addWidget(self.style_panel)
```

In `new_document`, after building `self.document` and binding history, seed + load the style:

```python
        self.document.style = styles.default_style_for(self.document.content_kind)
        if hasattr(self, "style_panel"):
            self.style_panel.set_style(self.document.style)
```

(Place this BEFORE `self._refresh()`.)

Update `_refresh` to render with the style:

```python
    def _refresh(self):
        if self.document and self.document.pages:
            self.canvas.load_page(self.document.pages[0], self.document.style)
            self.status.setText(f"{self.document.title} — {self.document.pages[0].page_size_px}")
        self.documentChanged.emit()
```

In `open_project_from` and `import_template_from`, after setting `self.document`, refresh the style panel. Add the new methods:

```python
    def apply_style(self, style):
        if self.document is None:
            return
        self.document.style = style
        self._refresh()

    def export_template_to(self, path: str):
        template_io.export_template(self.document, path)
        self.status.setText(f"Exported template {path}")

    def import_template_from(self, path: str):
        self.document = template_io.import_template(path)
        from core.layout.history import History
        self.history = History(self.document)
        if self.document.style is None:
            self.document.style = styles.default_style_for(self.document.content_kind)
        if hasattr(self, "style_panel") and self.document.style:
            self.style_panel.set_style(self.document.style)
        self._refresh()

    def _export_template_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Export Template", "",
                                              "ImageAI Layout Template (*.iailayout.json)")
        if path:
            self.export_template_to(path)

    def _import_template_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Import Template", "",
                                              "ImageAI Layout Template (*.iailayout.json)")
        if path:
            self.import_template_from(path)
```

Also update `open_project_from` to refresh the style panel (add after `self.history = History(self.document)`):

```python
        if hasattr(self, "style_panel") and self.document.style:
            self.style_panel.set_style(self.document.style)
```

- [ ] **Step 4: Run tests + full suite + import smoke**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_layout_tab_style.py -v`
Expected: PASS (3 passed).
Run: `.venv_linux/bin/python -m pytest tests/layout/ -q`
Expected: all pass, 0 warnings.
Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -c "from gui.layout import LayoutTab; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add gui/layout/layout_tab.py tests/layout/test_layout_tab_style.py
git commit -m "feat(layout): wire style panel + template export/import into tab"
```

---

## Self-Review

**Spec coverage (Phase 3):**
- §7 style system: `ProjectStyle` (roles + palette) + per-kind defaults → Task 1; role resolution at render → Task 2; editable roles → Task 4; project-wide application + seeding → Task 5. Font roles whose set varies by kind → `styles.default_style_for`. ✓
- §8 template sharing: `.iailayout.json` structure+style, no content → Task 3; tab export/import → Task 5. ✓
- Fonts by family name (no embedding) — `TextStyle.family` lists; templates carry names only. ✓
- Deferred (later phases): full bundles with embedded fonts (Phase 5); AI font/color suggestions (the designer could propose a `style` — deferred); palette editing UI beyond the per-role color (Phase 3 ships role font + color; palette-name editing is minimal).

**Placeholder scan:** No TBD/TODO; every code step has complete code. The `_doc()` helper's `history.append.__self__` line in Task 3 is explicitly flagged as removable.

**Type consistency:** `ProjectStyle(font_roles, palette, default_text_role)` used identically across Tasks 1/2/4/5; `default_style_for(kind)` consistent 1/5; `build_scene(..., style=)` / `load_page(page, style)` consistent 2/5; `export_template`/`import_template` consistent 3/5; `StylePanel.set_style`/`style`/`styleChanged`/`role_combo`/`family_edit`/`size_spin` consistent 4/5; `apply_style`/`export_template_to`/`import_template_from` consistent in Task 5 test + impl.
