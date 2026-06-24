# AI Layout Designer — Phase 1 (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation of the AI Layout Designer — a structured page/region document model, a native Qt renderer that is the single source of truth for both the live editor and PNG/PDF export, a working page-setup UI (any size/orientation/unit/DPI), and project save/load — so a user can create, edit by hand, save, reopen, and export a page.

**Architecture:** One structured document (`DocumentSpec → PageSpec → Region`, regions are rect or polygon). A `qt_renderer` turns a `PageSpec` into a `QGraphicsScene`; the *same* scene renders to high-res `QImage`/PNG and to PDF via `QPdfWriter` (WYSIWYG, no second renderer). The GUI (`page_setup_widget`, reworked `canvas_widget`, reworked `layout_tab`) sits on top. Phase 1 renders **placeholder** image regions and basic text — content filling is Phase 4.

**Tech Stack:** Python 3.12, PySide6 (QtWidgets/QtGui — `QGraphicsScene`, `QPdfWriter`), dataclasses, `pytest` (headless, offscreen Qt). Reuses existing `core/config.py` `ConfigManager` and `core/layout` package.

## Global Constraints

- Spec: `Plans/2026-06-24-layout-ai-designer-design.md`. This plan implements its **Phase 1** only.
- Python interpreter for all commands (agents run in WSL): `.venv_linux/bin/python`. **Never** use `.venv`.
- **No `cd`** — all commands use repo-root-relative or absolute paths; run from repo root `/mnt/d/Documents/Code/GitHub/ImageAI`.
- GUI tests run **headless**: a session `QApplication` is created under `QT_QPA_PLATFORM=offscreen` (set in `tests/conftest.py`). Do **not** add a `pytest-qt` dependency.
- **Extend & refactor in place** — keep `DocumentSpec`/`PageSpec` lineage; do not delete `engine.py`/`template_manager.py` in Phase 1 (they are demoted, not removed).
- Images are **scaled, not cropped** (honor `ImageStyle.fit`).
- Config access only via `ConfigManager` methods (`get_layout_config`/`set_layout_config`/`save`), never raw dict writes from new code.
- Conventional Commits; commit after each task. Branch is `feat/layout-ai-designer` (already created).
- Canonical units: store physical size + unit + DPI; pixels = `round(inches × dpi)` (px unit stores pixels directly).

---

## File Structure

**Create:**
- `tests/conftest.py` — session offscreen `qapp` fixture.
- `tests/layout/test_page_sizes.py`, `test_models.py`, `test_schema.py`, `test_qt_renderer.py`, `test_project_io.py`, `test_page_setup_widget.py`, `test_canvas_widget.py`, `test_layout_tab.py`.
- `core/layout/page_sizes.py` — presets, unit conversion, custom-preset persistence.
- `core/layout/schema.py` — (de)serialization + validate/normalize + AI JSON schema.
- `core/layout/qt_renderer.py` — scene build + PNG/PDF export (source of truth).
- `core/layout/project_io.py` — `.iaiproj.json` save/load + legacy `.layout.json` migration.
- `gui/layout/page_setup_widget.py` — orientation/size/unit/DPI control.

**Modify:**
- `core/layout/models.py` — add `PageSize`, `Region`, extend `PageSpec`/`DocumentSpec`, `migrate_legacy_blocks`.
- `core/layout/__init__.py` — export new symbols.
- `gui/layout/canvas_widget.py` — rework into a functional `QGraphicsView` over a renderer scene.
- `gui/layout/layout_tab.py` — rework into the Phase-1 orchestration (page setup + canvas + toolbar New/Open/Save/Export); drop dev/info banners.

**Deliberately untouched in Phase 1:** `engine.py`, `template_manager.py`, `text_gen_dialog.py`, `inspector_widget.py` content editing (Phase 4), `designer*`/`history*` (Phase 2).

---

### Task 1: Test harness + PageSize model + units

**Files:**
- Create: `tests/conftest.py`, `tests/layout/test_page_sizes.py`
- Create: `core/layout/page_sizes.py`
- Modify: `core/layout/models.py` (add `PageSize`)

**Interfaces:**
- Produces:
  - `models.PageSize(width: float, height: float, unit: str = "in", orientation: str = "portrait", dpi: int = 300)` with `to_pixels() -> tuple[int, int]` and `swapped() -> PageSize` (orientation flip, swaps width/height).
  - `page_sizes.to_inches(value: float, unit: str) -> float`
  - `page_sizes.PRESETS: list[dict]` (each `{"name","width","height","unit"}`)
  - `page_sizes.preset_to_page_size(preset: dict, orientation: str = "portrait", dpi: int = 300) -> PageSize`
  - `page_sizes.parse_size_text(text: str) -> tuple[float, float] | None`
  - `page_sizes.load_custom_sizes(config) -> list[dict]`
  - `page_sizes.save_custom_size(config, preset: dict) -> None`

- [ ] **Step 1: Write `tests/conftest.py` (shared offscreen QApplication)**

```python
# tests/conftest.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
```

- [ ] **Step 2: Write the failing test**

```python
# tests/layout/test_page_sizes.py
import pytest
from core.layout.models import PageSize
from core.layout import page_sizes as ps


def test_to_pixels_inches_at_300dpi():
    assert PageSize(8.5, 11, "in", "portrait", 300).to_pixels() == (2550, 3300)


def test_to_pixels_mm_a4_at_300dpi():
    # 210mm x 297mm @ 300dpi -> ~2480 x 3508
    assert PageSize(210, 297, "mm", "portrait", 300).to_pixels() == (2480, 3508)


def test_to_pixels_px_ignores_dpi():
    assert PageSize(1080, 1350, "px", "portrait", 72).to_pixels() == (1080, 1350)


def test_swapped_flips_orientation_and_dims():
    sw = PageSize(8.5, 11, "in", "portrait", 300).swapped()
    assert sw.orientation == "landscape"
    assert (sw.width, sw.height) == (11, 8.5)


def test_to_inches_units():
    assert ps.to_inches(72, "pt") == pytest.approx(1.0)
    assert ps.to_inches(25.4, "mm") == pytest.approx(1.0)
    assert ps.to_inches(2, "in") == pytest.approx(2.0)


def test_presets_include_letter_and_a4_and_comic():
    names = {p["name"] for p in ps.PRESETS}
    assert "US Letter" in names
    assert "A4" in names
    assert "US Comic" in names


def test_preset_to_page_size_landscape_swaps():
    letter = next(p for p in ps.PRESETS if p["name"] == "US Letter")
    pgl = ps.preset_to_page_size(letter, "landscape", 300)
    assert pgl.to_pixels() == (3300, 2550)


def test_parse_size_text():
    assert ps.parse_size_text("8.5 x 11") == (8.5, 11.0)
    assert ps.parse_size_text("210X297") == (210.0, 297.0)
    assert ps.parse_size_text("not a size") is None


def test_custom_size_persistence_roundtrip():
    store = {"layout": {}}

    class FakeConfig:
        def get_layout_config(self):
            return dict(store["layout"])
        def set_layout_config(self, cfg):
            store["layout"] = cfg
        def save(self):
            pass

    cfg = FakeConfig()
    assert ps.load_custom_sizes(cfg) == []
    ps.save_custom_size(cfg, {"name": "My Zine", "width": 5.5, "height": 8.5, "unit": "in"})
    loaded = ps.load_custom_sizes(cfg)
    assert loaded == [{"name": "My Zine", "width": 5.5, "height": 8.5, "unit": "in"}]
    # idempotent: saving same name does not duplicate
    ps.save_custom_size(cfg, {"name": "My Zine", "width": 5.5, "height": 8.5, "unit": "in"})
    assert len(ps.load_custom_sizes(cfg)) == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_page_sizes.py -v`
Expected: FAIL (`ImportError`/`AttributeError`: `PageSize`, `page_sizes` not defined).

- [ ] **Step 4: Add `PageSize` to `core/layout/models.py`**

Add after the `Size`/`Rect` aliases (around line 12):

```python
@dataclass
class PageSize:
    """Physical page size with unit + DPI; pixels derived on demand."""

    width: float
    height: float
    unit: Literal["in", "mm", "pt", "px"] = "in"
    orientation: Literal["portrait", "landscape"] = "portrait"
    dpi: int = 300

    def to_pixels(self) -> Tuple[int, int]:
        from core.layout.page_sizes import to_inches
        if self.unit == "px":
            return (round(self.width), round(self.height))
        return (
            round(to_inches(self.width, self.unit) * self.dpi),
            round(to_inches(self.height, self.unit) * self.dpi),
        )

    def swapped(self) -> "PageSize":
        new_orient = "landscape" if self.orientation == "portrait" else "portrait"
        return PageSize(self.height, self.width, self.unit, new_orient, self.dpi)
```

- [ ] **Step 5: Create `core/layout/page_sizes.py`**

```python
"""Page-size presets, unit conversion, and custom-size persistence."""
import re
from typing import List, Dict, Optional, Tuple

from core.layout.models import PageSize

_INCHES_PER = {"in": 1.0, "mm": 1.0 / 25.4, "pt": 1.0 / 72.0, "px": None}

# Seeded from Plans/common-sizes.md
PRESETS: List[Dict] = [
    {"name": "US Letter", "width": 8.5, "height": 11.0, "unit": "in"},
    {"name": "US Legal", "width": 8.5, "height": 14.0, "unit": "in"},
    {"name": "Tabloid", "width": 11.0, "height": 17.0, "unit": "in"},
    {"name": "A4", "width": 210.0, "height": 297.0, "unit": "mm"},
    {"name": "A5", "width": 148.0, "height": 210.0, "unit": "mm"},
    {"name": "US Comic", "width": 6.625, "height": 10.25, "unit": "in"},
    {"name": "Instagram Square", "width": 1080.0, "height": 1080.0, "unit": "px"},
    {"name": "Instagram Portrait", "width": 1080.0, "height": 1350.0, "unit": "px"},
    {"name": "Full HD", "width": 1920.0, "height": 1080.0, "unit": "px"},
]


def to_inches(value: float, unit: str) -> float:
    factor = _INCHES_PER.get(unit)
    if factor is None:
        raise ValueError(f"Cannot convert unit {unit!r} to inches")
    return value * factor


def preset_to_page_size(preset: Dict, orientation: str = "portrait", dpi: int = 300) -> PageSize:
    pg = PageSize(preset["width"], preset["height"], preset["unit"], "portrait", dpi)
    return pg.swapped() if orientation == "landscape" else pg


def parse_size_text(text: str) -> Optional[Tuple[float, float]]:
    m = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*[xX×]\s*([0-9]*\.?[0-9]+)\s*$", text or "")
    if not m:
        return None
    return (float(m.group(1)), float(m.group(2)))


def load_custom_sizes(config) -> List[Dict]:
    return list(config.get_layout_config().get("custom_page_sizes", []))


def save_custom_size(config, preset: Dict) -> None:
    cfg = config.get_layout_config()
    sizes = cfg.get("custom_page_sizes", [])
    sizes = [s for s in sizes if s.get("name") != preset.get("name")]
    sizes.append(preset)
    cfg["custom_page_sizes"] = sizes
    config.set_layout_config(cfg)
    config.save()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_page_sizes.py -v`
Expected: PASS (9 passed).

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py tests/layout/test_page_sizes.py core/layout/page_sizes.py core/layout/models.py
git commit -m "feat(layout): add PageSize model, presets, unit conversion, custom-size persistence"
```

---

### Task 2: Region model + Page/Document extension + legacy migration

**Files:**
- Modify: `core/layout/models.py`
- Test: `tests/layout/test_models.py`

**Interfaces:**
- Consumes: `PageSize` (Task 1), existing `TextStyle`/`ImageStyle`/`TextBlock`/`ImageBlock`/`PageSpec`/`DocumentSpec`.
- Produces:
  - `models.Region(id, kind, shape="rect", bbox=(0,0,100,100), points=[], z=0, name="", text="", role="", image_ref=None, prompt="", gen_settings={}, text_style=None, image_style=None)`
  - `PageSpec` gains `page_size: PageSize | None = None`, `regions: list[Region] = []`
  - `DocumentSpec` gains `content_kind: str = "custom"`, `schema_version: str = "2.0"`
  - `models.migrate_legacy_blocks(blocks: list) -> list[Region]`

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_models.py
from core.layout.models import (
    Region, PageSpec, DocumentSpec, PageSize,
    TextBlock, ImageBlock, TextStyle, ImageStyle, migrate_legacy_blocks,
)


def test_region_defaults():
    r = Region(id="r1", kind="image")
    assert r.shape == "rect"
    assert r.bbox == (0, 0, 100, 100)
    assert r.points == []
    assert r.image_ref is None


def test_pagespec_holds_regions_and_pagesize():
    p = PageSpec(page_size_px=(100, 100), page_size=PageSize(8.5, 11, "in"),
                 regions=[Region(id="r1", kind="text", text="hi")])
    assert p.regions[0].text == "hi"
    assert p.page_size.to_pixels() == (2550, 3300)


def test_documentspec_content_kind_default():
    d = DocumentSpec(title="Doc")
    assert d.content_kind == "custom"
    assert d.schema_version == "2.0"


def test_migrate_legacy_blocks():
    blocks = [
        TextBlock(id="t1", rect=(0, 0, 50, 20), text="Hello", style=TextStyle(family=["Arial"])),
        ImageBlock(id="i1", rect=(0, 30, 80, 80), image_path="/tmp/x.png", style=ImageStyle()),
    ]
    regions = migrate_legacy_blocks(blocks)
    assert [r.kind for r in regions] == ["text", "image"]
    assert regions[0].text == "Hello"
    assert regions[0].bbox == (0, 0, 50, 20)
    assert regions[1].image_ref == "/tmp/x.png"
    assert regions[1].bbox == (0, 30, 80, 80)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_models.py -v`
Expected: FAIL (`ImportError`: cannot import `Region`/`migrate_legacy_blocks`).

- [ ] **Step 3: Add `Region`, extend specs, add migration in `core/layout/models.py`**

Add after `ImageBlock` (after line 66):

```python
@dataclass
class Region:
    """A selectable layout region (rect or polygon), image or text."""

    id: str
    kind: Literal["image", "text"]
    shape: Literal["rect", "polygon"] = "rect"
    bbox: Rect = (0, 0, 100, 100)
    points: List[Tuple[int, int]] = field(default_factory=list)  # polygon vertices, page px
    z: int = 0
    name: str = ""
    # content (text)
    text: str = ""
    role: str = ""  # font-role name resolved via ProjectStyle (Phase 3)
    # content (image)
    image_ref: Optional[str] = None
    prompt: str = ""  # scaffolding for AI content phases
    gen_settings: Dict[str, Union[str, int, float]] = field(default_factory=dict)
    # style
    text_style: Optional[TextStyle] = None
    image_style: Optional[ImageStyle] = None
```

Extend `PageSpec` — add two fields after `variables` (line 78):

```python
    page_size: Optional[PageSize] = None
    regions: List[Region] = field(default_factory=list)
```

Extend `DocumentSpec` — add after `metadata` (line 89):

```python
    content_kind: str = "custom"
    schema_version: str = "2.0"
```

Add the migration helper at end of file:

```python
def migrate_legacy_blocks(blocks: List[Union[TextBlock, ImageBlock]]) -> List[Region]:
    """Convert legacy TextBlock/ImageBlock objects into Region objects."""
    regions: List[Region] = []
    for b in blocks:
        if getattr(b, "type", None) == "image" or isinstance(b, ImageBlock):
            regions.append(Region(
                id=b.id, kind="image", bbox=tuple(b.rect),
                image_ref=getattr(b, "image_path", None),
                image_style=getattr(b, "style", None),
                name=getattr(b, "alt_text", "") or "",
            ))
        else:
            regions.append(Region(
                id=b.id, kind="text", bbox=tuple(b.rect),
                text=getattr(b, "text", "") or "",
                text_style=getattr(b, "style", None),
            ))
    return regions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_models.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Export new symbols from `core/layout/__init__.py`**

In the `from .models import (...)` block add `PageSize`, `Region`, `migrate_legacy_blocks`; add the same three strings to `__all__`.

- [ ] **Step 6: Verify package import still works**

Run: `.venv_linux/bin/python -c "from core.layout import Region, PageSize, migrate_legacy_blocks; print('ok')"`
Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add core/layout/models.py core/layout/__init__.py tests/layout/test_models.py
git commit -m "feat(layout): add Region model, extend Page/Document specs, legacy block migration"
```

---

### Task 3: Schema — (de)serialization, normalize, validate

**Files:**
- Create: `core/layout/schema.py`
- Test: `tests/layout/test_schema.py`

**Interfaces:**
- Consumes: `models` (Tasks 1-2).
- Produces:
  - `schema.document_to_dict(doc: DocumentSpec) -> dict`
  - `schema.document_from_dict(d: dict) -> DocumentSpec`  (handles legacy `blocks` → `regions`)
  - `schema.normalize_region(r: Region, page_px: tuple[int, int]) -> Region` (assign bbox from polygon points; clamp to page)
  - `schema.validate_document(doc: DocumentSpec) -> list[str]`
  - `schema.REGION_JSON_SCHEMA: dict` (JSON Schema for AI output — used in Phase 2)

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_schema.py
from core.layout.models import Region, PageSpec, DocumentSpec, PageSize
from core.layout import schema


def _doc():
    page = PageSpec(page_size_px=(1000, 800), page_size=PageSize(1000, 800, "px"),
                    regions=[
                        Region(id="r1", kind="text", bbox=(10, 10, 200, 50), text="Title"),
                        Region(id="r2", kind="image", shape="polygon",
                               points=[(0, 0), (300, 0), (150, 300)]),
                    ])
    return DocumentSpec(title="T", content_kind="comic", pages=[page])


def test_document_roundtrip():
    doc = _doc()
    again = schema.document_from_dict(schema.document_to_dict(doc))
    assert again.title == "T"
    assert again.content_kind == "comic"
    assert again.pages[0].regions[0].text == "Title"
    assert again.pages[0].regions[1].shape == "polygon"
    assert again.pages[0].regions[1].points == [(0, 0), (300, 0), (150, 300)]


def test_document_from_dict_migrates_legacy_blocks():
    legacy = {
        "title": "Old", "pages": [{
            "page_size_px": [500, 500],
            "blocks": [
                {"type": "text", "id": "t1", "rect": [0, 0, 100, 30], "text": "Hi"},
                {"type": "image", "id": "i1", "rect": [0, 40, 100, 100], "image_path": "/a.png"},
            ],
        }],
    }
    doc = schema.document_from_dict(legacy)
    kinds = [r.kind for r in doc.pages[0].regions]
    assert kinds == ["text", "image"]
    assert doc.pages[0].regions[1].image_ref == "/a.png"


def test_normalize_region_clamps_and_sets_polygon_bbox():
    r = Region(id="r", kind="image", bbox=(900, 700, 500, 500))  # overflows 1000x800
    n = schema.normalize_region(r, (1000, 800))
    x, y, w, h = n.bbox
    assert x + w <= 1000 and y + h <= 800

    poly = Region(id="p", kind="image", shape="polygon", points=[(10, 20), (110, 20), (60, 120)])
    np = schema.normalize_region(poly, (1000, 800))
    assert np.bbox == (10, 20, 100, 100)  # bbox computed from points


def test_validate_document_flags_empty_pages():
    doc = DocumentSpec(title="x", pages=[])
    issues = schema.validate_document(doc)
    assert any("page" in i.lower() for i in issues)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_schema.py -v`
Expected: FAIL (`ModuleNotFoundError: core.layout.schema`).

- [ ] **Step 3: Create `core/layout/schema.py`**

```python
"""Serialization, normalization, and validation for layout documents."""
from dataclasses import asdict
from typing import Dict, List, Tuple

from core.layout.models import (
    Region, PageSpec, DocumentSpec, PageSize, TextStyle, ImageStyle,
    migrate_legacy_blocks, TextBlock, ImageBlock,
)

REGION_JSON_SCHEMA: Dict = {
    "type": "object",
    "required": ["id", "kind"],
    "properties": {
        "id": {"type": "string"},
        "kind": {"enum": ["image", "text"]},
        "shape": {"enum": ["rect", "polygon"]},
        "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
        "points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
        "z": {"type": "integer"},
        "text": {"type": "string"},
        "role": {"type": "string"},
        "image_ref": {"type": ["string", "null"]},
        "prompt": {"type": "string"},
    },
}


def _style_to_dict(style):
    return asdict(style) if style is not None else None


def region_to_dict(r: Region) -> Dict:
    return {
        "id": r.id, "kind": r.kind, "shape": r.shape,
        "bbox": list(r.bbox), "points": [list(p) for p in r.points],
        "z": r.z, "name": r.name, "text": r.text, "role": r.role,
        "image_ref": r.image_ref, "prompt": r.prompt, "gen_settings": dict(r.gen_settings),
        "text_style": _style_to_dict(r.text_style),
        "image_style": _style_to_dict(r.image_style),
    }


def region_from_dict(d: Dict) -> Region:
    ts = d.get("text_style")
    is_ = d.get("image_style")
    return Region(
        id=d["id"], kind=d["kind"], shape=d.get("shape", "rect"),
        bbox=tuple(d.get("bbox", (0, 0, 100, 100))),
        points=[tuple(p) for p in d.get("points", [])],
        z=int(d.get("z", 0)), name=d.get("name", ""),
        text=d.get("text", ""), role=d.get("role", ""),
        image_ref=d.get("image_ref"), prompt=d.get("prompt", ""),
        gen_settings=dict(d.get("gen_settings", {})),
        text_style=TextStyle(**ts) if ts else None,
        image_style=ImageStyle(**is_) if is_ else None,
    )


def _page_size_from_dict(d):
    return PageSize(**d) if d else None


def page_to_dict(p: PageSpec) -> Dict:
    return {
        "page_size_px": list(p.page_size_px),
        "page_size": asdict(p.page_size) if p.page_size else None,
        "margin_px": p.margin_px, "bleed_px": p.bleed_px, "background": p.background,
        "regions": [region_to_dict(r) for r in p.regions],
        "variables": dict(p.variables),
    }


def page_from_dict(d: Dict) -> PageSpec:
    if "regions" in d:
        regions = [region_from_dict(r) for r in d["regions"]]
    else:  # legacy: migrate blocks -> regions
        legacy = []
        for b in d.get("blocks", []):
            if b.get("type") == "image":
                legacy.append(ImageBlock(id=b["id"], rect=tuple(b["rect"]),
                                         image_path=b.get("image_path")))
            else:
                legacy.append(TextBlock(id=b["id"], rect=tuple(b["rect"]),
                                        text=b.get("text", "")))
        regions = migrate_legacy_blocks(legacy)
    return PageSpec(
        page_size_px=tuple(d.get("page_size_px", (1000, 1000))),
        page_size=_page_size_from_dict(d.get("page_size")),
        margin_px=d.get("margin_px", 64), bleed_px=d.get("bleed_px", 0),
        background=d.get("background"), regions=regions,
        variables=dict(d.get("variables", {})),
    )


def document_to_dict(doc: DocumentSpec) -> Dict:
    return {
        "schema_version": doc.schema_version, "title": doc.title, "author": doc.author,
        "content_kind": doc.content_kind, "theme": dict(doc.theme),
        "metadata": dict(doc.metadata), "pages": [page_to_dict(p) for p in doc.pages],
    }


def document_from_dict(d: Dict) -> DocumentSpec:
    return DocumentSpec(
        title=d.get("title", "Untitled"), author=d.get("author"),
        pages=[page_from_dict(p) for p in d.get("pages", [])],
        theme=dict(d.get("theme", {})), metadata=dict(d.get("metadata", {})),
        content_kind=d.get("content_kind", "custom"),
        schema_version=d.get("schema_version", "2.0"),
    )


def normalize_region(r: Region, page_px: Tuple[int, int]) -> Region:
    pw, ph = page_px
    if r.shape == "polygon" and r.points:
        xs = [p[0] for p in r.points]
        ys = [p[1] for p in r.points]
        r.bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    x, y, w, h = r.bbox
    x = max(0, min(x, pw))
    y = max(0, min(y, ph))
    w = max(1, min(w, pw - x))
    h = max(1, min(h, ph - y))
    r.bbox = (x, y, w, h)
    return r


def validate_document(doc: DocumentSpec) -> List[str]:
    issues: List[str] = []
    if not doc.pages:
        issues.append("Document has no pages.")
    for pi, p in enumerate(doc.pages):
        ids = [r.id for r in p.regions]
        if len(ids) != len(set(ids)):
            issues.append(f"Page {pi}: duplicate region ids.")
    return issues
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_schema.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add core/layout/schema.py tests/layout/test_schema.py
git commit -m "feat(layout): add schema (de)serialization, region normalize, document validate"
```

---

### Task 4: Qt renderer — scene build + PNG export

**Files:**
- Create: `core/layout/qt_renderer.py`
- Test: `tests/layout/test_qt_renderer.py`

**Interfaces:**
- Consumes: `models` (Region/PageSpec).
- Produces:
  - `qt_renderer.build_scene(page: PageSpec, *, selectable: bool = False) -> QGraphicsScene`
  - `qt_renderer.render_page_to_image(page: PageSpec) -> QImage`
  - `qt_renderer.save_page_png(page: PageSpec, path: str) -> None`
- Notes: image regions render as a **placeholder** (light-gray fill + region name/`[image]` label) in Phase 1; a real `image_ref` is drawn scaled-to-fit if present. Text regions draw `region.text` with `TextStyle`. Scene rect = page pixels.

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_qt_renderer.py
import pytest
from core.layout.models import Region, PageSpec
from core.layout import qt_renderer


def _page():
    return PageSpec(page_size_px=(200, 150), background="#FFFFFF", regions=[
        Region(id="r1", kind="image", bbox=(10, 10, 80, 80)),
        Region(id="r2", kind="text", bbox=(10, 100, 180, 40), text="Hello"),
        Region(id="r3", kind="image", shape="polygon",
               points=[(100, 10), (190, 10), (145, 90)]),
    ])


def test_build_scene_item_count(qapp):
    scene = qt_renderer.build_scene(_page())
    # at least one graphics item per region
    assert len(scene.items()) >= 3
    assert scene.width() == 200 and scene.height() == 150


def test_build_scene_selectable_flag(qapp):
    from PySide6.QtWidgets import QGraphicsItem
    scene = qt_renderer.build_scene(_page(), selectable=True)
    selectable = [it for it in scene.items()
                  if it.flags() & QGraphicsItem.ItemIsSelectable]
    assert len(selectable) >= 3


def test_render_page_to_image_size(qapp):
    img = qt_renderer.render_page_to_image(_page())
    assert img.width() == 200 and img.height() == 150
    assert not img.isNull()


def test_save_png(qapp, tmp_path):
    out = tmp_path / "page.png"
    qt_renderer.save_page_png(_page(), str(out))
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_qt_renderer.py -v`
Expected: FAIL (`ModuleNotFoundError: core.layout.qt_renderer`).

- [ ] **Step 3: Create `core/layout/qt_renderer.py`**

```python
"""Native Qt renderer: PageSpec -> QGraphicsScene -> QImage/PNG (source of truth)."""
from typing import Optional

from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsRectItem, QGraphicsPolygonItem,
    QGraphicsSimpleTextItem, QGraphicsItem, QGraphicsPixmapItem,
)
from PySide6.QtGui import (
    QColor, QBrush, QPen, QPolygonF, QImage, QPainter, QFont, QPixmap,
)
from PySide6.QtCore import QPointF, QRectF, Qt

from core.layout.models import PageSpec, Region

_PLACEHOLDER_FILL = QColor("#E9ECEF")
_PLACEHOLDER_PEN = QColor("#ADB5BD")


def _apply_flags(item: QGraphicsItem, selectable: bool, region_id: str) -> None:
    item.setData(0, region_id)
    if selectable:
        item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        item.setFlag(QGraphicsItem.ItemIsMovable, True)


def _add_image_region(scene: QGraphicsScene, r: Region, selectable: bool) -> None:
    x, y, w, h = r.bbox
    if r.shape == "polygon" and r.points:
        poly = QPolygonF([QPointF(px, py) for px, py in r.points])
        item = QGraphicsPolygonItem(poly)
    else:
        item = QGraphicsRectItem(QRectF(x, y, w, h))
    item.setBrush(QBrush(_PLACEHOLDER_FILL))
    item.setPen(QPen(_PLACEHOLDER_PEN, 1))
    _apply_flags(item, selectable, r.id)
    scene.addItem(item)

    if r.image_ref:
        pix = QPixmap(r.image_ref)
        if not pix.isNull():
            scaled = pix.scaled(int(w), int(h), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pi = QGraphicsPixmapItem(scaled)
            pi.setPos(x, y)
            pi.setData(0, r.id)
            scene.addItem(pi)
            return

    label = QGraphicsSimpleTextItem(r.name or "[image]")
    label.setPos(x + 4, y + 4)
    label.setBrush(QBrush(QColor("#6C757D")))
    scene.addItem(label)


def _add_text_region(scene: QGraphicsScene, r: Region, selectable: bool) -> None:
    x, y, w, h = r.bbox
    box = QGraphicsRectItem(QRectF(x, y, w, h))
    box.setBrush(QBrush(Qt.transparent))
    box.setPen(QPen(QColor("#CED4DA"), 1, Qt.DashLine))
    _apply_flags(box, selectable, r.id)
    scene.addItem(box)

    text = QGraphicsSimpleTextItem(r.text or "")
    style = r.text_style
    font = QFont()
    if style:
        if style.family:
            font.setFamily(style.family[0])
        font.setPixelSize(style.size_px)
        font.setBold(style.weight in ("bold", "black", "semibold"))
        font.setItalic(style.italic)
        text.setBrush(QBrush(QColor(style.color)))
    text.setFont(font)
    text.setPos(x + 2, y + 2)
    scene.addItem(text)


def build_scene(page: PageSpec, *, selectable: bool = False) -> QGraphicsScene:
    pw, ph = page.page_size_px
    scene = QGraphicsScene(0, 0, pw, ph)
    bg = page.background if (page.background and page.background.startswith("#")) else "#FFFFFF"
    scene.setBackgroundBrush(QBrush(QColor(bg)))
    for r in sorted(page.regions, key=lambda rr: rr.z):
        if r.kind == "image":
            _add_image_region(scene, r, selectable)
        else:
            _add_text_region(scene, r, selectable)
    return scene


def render_page_to_image(page: PageSpec) -> QImage:
    pw, ph = page.page_size_px
    scene = build_scene(page)
    img = QImage(pw, ph, QImage.Format_ARGB32)
    bg = page.background if (page.background and page.background.startswith("#")) else "#FFFFFF"
    img.fill(QColor(bg))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)
    scene.render(painter, QRectF(0, 0, pw, ph), QRectF(0, 0, pw, ph))
    painter.end()
    return img


def save_page_png(page: PageSpec, path: str) -> None:
    render_page_to_image(page).save(path, "PNG")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_qt_renderer.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add core/layout/qt_renderer.py tests/layout/test_qt_renderer.py
git commit -m "feat(layout): add Qt renderer (scene build + PNG export)"
```

---

### Task 5: Qt renderer — PDF export

**Files:**
- Modify: `core/layout/qt_renderer.py`
- Test: `tests/layout/test_qt_renderer.py` (append)

**Interfaces:**
- Consumes: `DocumentSpec`, `build_scene` (Task 4).
- Produces: `qt_renderer.export_document_pdf(doc: DocumentSpec, path: str) -> None`

- [ ] **Step 1: Write the failing test (append to test_qt_renderer.py)**

```python
def test_export_pdf(qapp, tmp_path):
    from core.layout.models import DocumentSpec
    from core.layout import qt_renderer
    doc = DocumentSpec(title="D", pages=[_page(), _page()])
    out = tmp_path / "doc.pdf"
    qt_renderer.export_document_pdf(doc, str(out))
    assert out.exists() and out.stat().st_size > 500
    assert out.read_bytes()[:4] == b"%PDF"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_qt_renderer.py::test_export_pdf -v`
Expected: FAIL (`AttributeError: export_document_pdf`).

- [ ] **Step 3: Add PDF export to `core/layout/qt_renderer.py`**

Add imports at top:

```python
from PySide6.QtGui import QPdfWriter, QPageSize, QPageLayout
from PySide6.QtCore import QSizeF, QMarginsF
```

Append function:

```python
def export_document_pdf(doc: DocumentSpec, path: str, dpi: int = 300) -> None:
    writer = QPdfWriter(path)
    writer.setResolution(dpi)
    painter = QPainter()
    started = False
    for i, page in enumerate(doc.pages):
        pw, ph = page.page_size_px
        size_inches = QSizeF(pw / dpi, ph / dpi)
        writer.setPageSize(QPageSize(size_inches, QPageSize.Inch))
        writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Inch)
        if not started:
            painter.begin(writer)
            started = True
        else:
            writer.newPage()
        scene = build_scene(page)
        target = painter.viewport()
        scene.render(painter, QRectF(target), QRectF(0, 0, pw, ph))
    if started:
        painter.end()
```

Add `DocumentSpec` to the `from core.layout.models import` line at the top of the file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_qt_renderer.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add core/layout/qt_renderer.py tests/layout/test_qt_renderer.py
git commit -m "feat(layout): add WYSIWYG PDF export via QPdfWriter"
```

---

### Task 6: Project save/load + legacy migration

**Files:**
- Create: `core/layout/project_io.py`
- Test: `tests/layout/test_project_io.py`

**Interfaces:**
- Consumes: `schema.document_to_dict`/`document_from_dict`.
- Produces:
  - `project_io.save_project(doc: DocumentSpec, path: str) -> None`
  - `project_io.load_project(path: str) -> DocumentSpec`  (reads `.iaiproj.json` and legacy `.layout.json` shapes)

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_project_io.py
import json
from core.layout.models import Region, PageSpec, DocumentSpec
from core.layout import project_io


def test_save_load_roundtrip(tmp_path):
    doc = DocumentSpec(title="Proj", content_kind="comic", pages=[
        PageSpec(page_size_px=(500, 500),
                 regions=[Region(id="r1", kind="text", text="Hi", bbox=(0, 0, 100, 30))])
    ])
    p = tmp_path / "x.iaiproj.json"
    project_io.save_project(doc, str(p))
    loaded = project_io.load_project(str(p))
    assert loaded.title == "Proj"
    assert loaded.content_kind == "comic"
    assert loaded.pages[0].regions[0].text == "Hi"


def test_load_legacy_layout_json(tmp_path):
    legacy = {"title": "Legacy", "pages": [{
        "page_size_px": [400, 400],
        "blocks": [{"type": "image", "id": "i1", "rect": [0, 0, 100, 100],
                    "image_path": "/p.png"}]}]}
    p = tmp_path / "old.layout.json"
    p.write_text(json.dumps(legacy), encoding="utf-8")
    loaded = project_io.load_project(str(p))
    assert loaded.pages[0].regions[0].kind == "image"
    assert loaded.pages[0].regions[0].image_ref == "/p.png"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_project_io.py -v`
Expected: FAIL (`ModuleNotFoundError: core.layout.project_io`).

- [ ] **Step 3: Create `core/layout/project_io.py`**

```python
"""Project persistence: .iaiproj.json save/load + legacy .layout.json migration."""
import json
from pathlib import Path

from core.layout.models import DocumentSpec
from core.layout import schema


def save_project(doc: DocumentSpec, path: str) -> None:
    data = schema.document_to_dict(doc)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_project(path: str) -> DocumentSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return schema.document_from_dict(data)  # handles both new + legacy shapes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_project_io.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add core/layout/project_io.py tests/layout/test_project_io.py
git commit -m "feat(layout): add project save/load with legacy .layout.json migration"
```

---

### Task 7: Page-setup widget

**Files:**
- Create: `gui/layout/page_setup_widget.py`
- Test: `tests/layout/test_page_setup_widget.py`

**Interfaces:**
- Consumes: `page_sizes` (Task 1), a `ConfigManager`-like object.
- Produces:
  - `page_setup_widget.PageSetupWidget(config, parent=None)` — QWidget
  - signal `pageSizeChanged(object)` (emits a `PageSize`)
  - method `page_size() -> PageSize`
  - method `set_page_size(ps: PageSize) -> None`
  - `add_custom_from_text(text: str) -> bool` (parses "W x H", persists, selects)

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_page_setup_widget.py
from core.layout.models import PageSize
from gui.layout.page_setup_widget import PageSetupWidget


class FakeConfig:
    def __init__(self):
        self.store = {"layout": {}}
    def get_layout_config(self):
        return dict(self.store["layout"])
    def set_layout_config(self, cfg):
        self.store["layout"] = cfg
    def save(self):
        pass


def test_widget_builds_and_default_page_size(qapp):
    w = PageSetupWidget(FakeConfig())
    ps = w.page_size()
    assert isinstance(ps, PageSize)
    assert ps.to_pixels()[0] > 0


def test_orientation_swap_changes_dims(qapp):
    w = PageSetupWidget(FakeConfig())
    w.set_page_size(PageSize(8.5, 11, "in", "portrait", 300))
    before = w.page_size().to_pixels()
    w._on_landscape()  # internal slot
    after = w.page_size().to_pixels()
    assert after == (before[1], before[0])


def test_add_custom_persists(qapp):
    cfg = FakeConfig()
    w = PageSetupWidget(cfg)
    assert w.add_custom_from_text("5.5 x 8.5") is True
    assert any(s["name"].startswith("Custom") for s in cfg.store["layout"]["custom_page_sizes"])


def test_emits_page_size_changed(qapp):
    w = PageSetupWidget(FakeConfig())
    received = []
    w.pageSizeChanged.connect(lambda ps: received.append(ps))
    w.set_page_size(PageSize(4, 6, "in", "portrait", 300))
    assert received and received[-1].to_pixels() == (1200, 1800)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_page_setup_widget.py -v`
Expected: FAIL (`ModuleNotFoundError: gui.layout.page_setup_widget`).

- [ ] **Step 3: Create `gui/layout/page_setup_widget.py`**

```python
"""Page-setup controls: orientation, size (presets + freeform), unit, DPI."""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QSpinBox, QPushButton, QLabel,
)
from PySide6.QtCore import Signal

from core.layout.models import PageSize
from core.layout import page_sizes as ps


class PageSetupWidget(QWidget):
    pageSizeChanged = Signal(object)  # emits PageSize

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._unit = "in"
        self._dpi = config.get_layout_config().get("export_dpi", 300) if config else 300
        self._orientation = "portrait"
        self._build()
        self._reload_presets()
        self._emit_current()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.addWidget(QLabel("Size:"))
        self.size_combo = QComboBox()
        self.size_combo.setEditable(True)
        self.size_combo.activated.connect(lambda *_: self._on_preset_selected())
        self.size_combo.lineEdit().returnPressed.connect(self._on_freeform_entered)
        lay.addWidget(self.size_combo, 2)

        lay.addWidget(QLabel("Unit:"))
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["in", "mm", "pt", "px"])
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)
        lay.addWidget(self.unit_combo)

        lay.addWidget(QLabel("DPI:"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(1, 2400)
        self.dpi_spin.setValue(self._dpi)
        self.dpi_spin.valueChanged.connect(self._on_dpi_changed)
        lay.addWidget(self.dpi_spin)

        self.portrait_btn = QPushButton("Portrait")
        self.portrait_btn.clicked.connect(self._on_portrait)
        self.landscape_btn = QPushButton("Landscape")
        self.landscape_btn.clicked.connect(self._on_landscape)
        lay.addWidget(self.portrait_btn)
        lay.addWidget(self.landscape_btn)

    def _reload_presets(self):
        self.size_combo.blockSignals(True)
        self.size_combo.clear()
        self._presets = list(ps.PRESETS) + ps.load_custom_sizes(self._config)
        for p in self._presets:
            self.size_combo.addItem(f'{p["name"]} ({p["width"]}x{p["height"]} {p["unit"]})')
        self.size_combo.blockSignals(False)

    def _current_preset(self):
        idx = self.size_combo.currentIndex()
        if 0 <= idx < len(self._presets):
            return self._presets[idx]
        return self._presets[0]

    def page_size(self) -> PageSize:
        p = self._current_preset()
        return ps.preset_to_page_size(p, self._orientation, self.dpi_spin.value())

    def set_page_size(self, page: PageSize) -> None:
        self._orientation = page.orientation
        self.unit_combo.setCurrentText(page.unit)
        self.dpi_spin.setValue(page.dpi)
        name = f"Custom {page.width}x{page.height}"
        preset = {"name": name, "width": page.width, "height": page.height, "unit": page.unit}
        self._presets = [preset] + [p for p in self._presets if p.get("name") != name]
        self.size_combo.blockSignals(True)
        self.size_combo.clear()
        for p in self._presets:
            self.size_combo.addItem(f'{p["name"]} ({p["width"]}x{p["height"]} {p["unit"]})')
        self.size_combo.setCurrentIndex(0)
        self.size_combo.blockSignals(False)
        self._emit_current()

    def add_custom_from_text(self, text: str) -> bool:
        parsed = ps.parse_size_text(text)
        if not parsed:
            return False
        w, h = parsed
        preset = {"name": f"Custom {w}x{h}", "width": w, "height": h,
                  "unit": self.unit_combo.currentText()}
        ps.save_custom_size(self._config, preset)
        self._reload_presets()
        for i, p in enumerate(self._presets):
            if p["name"] == preset["name"]:
                self.size_combo.setCurrentIndex(i)
                break
        self._emit_current()
        return True

    # --- slots ---
    def _on_preset_selected(self):
        self._emit_current()

    def _on_freeform_entered(self):
        self.add_custom_from_text(self.size_combo.currentText())

    def _on_unit_changed(self, unit):
        self._unit = unit

    def _on_dpi_changed(self, _):
        self._emit_current()

    def _on_portrait(self):
        self._orientation = "portrait"
        self._emit_current()

    def _on_landscape(self):
        self._orientation = "landscape"
        self._emit_current()

    def _emit_current(self):
        self.pageSizeChanged.emit(self.page_size())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_page_setup_widget.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add gui/layout/page_setup_widget.py tests/layout/test_page_setup_widget.py
git commit -m "feat(layout): add page-setup widget (size/unit/dpi/orientation, custom persistence)"
```

---

### Task 8: Canvas widget rework

**Files:**
- Modify: `gui/layout/canvas_widget.py` (replace contents)
- Test: `tests/layout/test_canvas_widget.py`

**Interfaces:**
- Consumes: `qt_renderer.build_scene`, `PageSpec`/`Region`.
- Produces:
  - `canvas_widget.CanvasWidget(parent=None)` — `QGraphicsView`
  - signal `regionSelected(str)` (region id, or "" when cleared)
  - method `load_page(page: PageSpec) -> None`
  - method `selected_region_id() -> str | None`

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_canvas_widget.py
from core.layout.models import Region, PageSpec
from gui.layout.canvas_widget import CanvasWidget


def _page():
    return PageSpec(page_size_px=(300, 200), regions=[
        Region(id="a", kind="image", bbox=(10, 10, 80, 80)),
        Region(id="b", kind="text", bbox=(10, 100, 200, 40), text="Hi"),
    ])


def test_load_page_builds_selectable_scene(qapp):
    w = CanvasWidget()
    w.load_page(_page())
    from PySide6.QtWidgets import QGraphicsItem
    sel = [it for it in w.scene().items()
           if it.flags() & QGraphicsItem.ItemIsSelectable]
    assert len(sel) >= 2


def test_selection_emits_region_id(qapp):
    w = CanvasWidget()
    w.load_page(_page())
    got = []
    w.regionSelected.connect(lambda rid: got.append(rid))
    # select the first selectable item programmatically
    from PySide6.QtWidgets import QGraphicsItem
    item = next(it for it in w.scene().items()
                if it.flags() & QGraphicsItem.ItemIsSelectable and it.data(0) == "a")
    item.setSelected(True)
    assert got and got[-1] == "a"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_canvas_widget.py -v`
Expected: FAIL (import error or missing `regionSelected`/`load_page`).

- [ ] **Step 3: Replace `gui/layout/canvas_widget.py`**

```python
"""Live editor canvas: a QGraphicsView over a renderer-built scene."""
from typing import Optional

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtGui import QPainter
from PySide6.QtCore import Signal, Qt

from core.layout.models import PageSpec
from core.layout import qt_renderer


class CanvasWidget(QGraphicsView):
    regionSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self._page: Optional[PageSpec] = None
        self.setScene(QGraphicsScene(self))

    def load_page(self, page: PageSpec) -> None:
        self._page = page
        scene = qt_renderer.build_scene(page, selectable=True)
        scene.selectionChanged.connect(self._on_selection_changed)
        self.setScene(scene)
        self.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)

    def selected_region_id(self) -> Optional[str]:
        for it in self.scene().selectedItems():
            rid = it.data(0)
            if rid:
                return rid
        return None

    def _on_selection_changed(self):
        rid = self.selected_region_id()
        self.regionSelected.emit(rid or "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_canvas_widget.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add gui/layout/canvas_widget.py tests/layout/test_canvas_widget.py
git commit -m "feat(layout): rework canvas into functional QGraphicsView with selection"
```

---

### Task 9: Layout tab rework + integration

**Files:**
- Modify: `gui/layout/layout_tab.py` (rework toolbar + wiring; drop dev/info banners)
- Test: `tests/layout/test_layout_tab.py`

**Interfaces:**
- Consumes: `PageSetupWidget` (T7), `CanvasWidget` (T8), `project_io` (T6), `qt_renderer` (T4-5), `models`.
- Produces:
  - `LayoutTab(config=None, parent=None)` keeps its constructor signature (used by `gui/main_window.py:553`).
  - methods: `new_document() -> None`, `save_project_to(path: str) -> None`, `open_project_from(path: str) -> None`, `export_pdf_to(path: str) -> None`
  - attribute `self.document: DocumentSpec`

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_layout_tab.py
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def __init__(self):
        self.store = {"layout": {}}
    def get_layout_config(self):
        return dict(self.store["layout"])
    def set_layout_config(self, cfg):
        self.store["layout"] = cfg
    def save(self):
        pass


def test_new_document_creates_one_page(qapp):
    tab = LayoutTab(config=FakeConfig())
    tab.new_document()
    assert tab.document is not None
    assert len(tab.document.pages) == 1


def test_save_then_open_roundtrip(qapp, tmp_path):
    tab = LayoutTab(config=FakeConfig())
    tab.new_document()
    tab.document.title = "RoundTrip"
    p = tmp_path / "proj.iaiproj.json"
    tab.save_project_to(str(p))
    assert p.exists()

    tab2 = LayoutTab(config=FakeConfig())
    tab2.open_project_from(str(p))
    assert tab2.document.title == "RoundTrip"


def test_export_pdf(qapp, tmp_path):
    tab = LayoutTab(config=FakeConfig())
    tab.new_document()
    out = tmp_path / "out.pdf"
    tab.export_pdf_to(str(out))
    assert out.exists() and out.read_bytes()[:4] == b"%PDF"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_layout_tab.py -v`
Expected: FAIL (missing `new_document`/`save_project_to`/etc., or banner-era construction errors).

- [ ] **Step 3: Rework `gui/layout/layout_tab.py`**

Replace the file with the Phase-1 orchestration below. (This removes the "Development in Progress"/info banners and the template-picker three-panel layout; later phases re-introduce the inspector and designer panels.)

```python
"""Layout tab — Phase 1 foundation: page setup + canvas + New/Open/Save/Export."""
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLabel,
)
from PySide6.QtCore import Signal

from core.layout.models import DocumentSpec, PageSpec, PageSize
from core.layout import project_io, qt_renderer
from gui.layout.page_setup_widget import PageSetupWidget
from gui.layout.canvas_widget import CanvasWidget

logger = logging.getLogger("imageai.layout.tab")


class LayoutTab(QWidget):
    documentChanged = Signal()

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.document: Optional[DocumentSpec] = None
        self._build()
        self.new_document()

    def _build(self):
        root = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        for label, slot in [
            ("New", self.new_document), ("Open…", self._open_dialog),
            ("Save…", self._save_dialog), ("Export PDF…", self._export_dialog),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            toolbar.addWidget(btn)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self.page_setup = PageSetupWidget(self.config)
        self.page_setup.pageSizeChanged.connect(self._on_page_size_changed)
        root.addWidget(self.page_setup)

        self.canvas = CanvasWidget()
        root.addWidget(self.canvas, 1)

        self.status = QLabel("")
        root.addWidget(self.status)

    # --- document lifecycle ---
    def new_document(self):
        ps = self.page_setup.page_size() if hasattr(self, "page_setup") else PageSize(8.5, 11, "in")
        pw, ph = ps.to_pixels()
        page = PageSpec(page_size_px=(pw, ph), page_size=ps, background="#FFFFFF")
        self.document = DocumentSpec(title="Untitled", pages=[page])
        self._refresh()

    def _on_page_size_changed(self, ps: PageSize):
        if not self.document or not self.document.pages:
            return
        page = self.document.pages[0]
        page.page_size = ps
        page.page_size_px = ps.to_pixels()
        self._refresh()

    def _refresh(self):
        if self.document and self.document.pages:
            self.canvas.load_page(self.document.pages[0])
            self.status.setText(f"{self.document.title} — {self.document.pages[0].page_size_px}")
        self.documentChanged.emit()

    # --- programmatic API (tested) ---
    def save_project_to(self, path: str):
        project_io.save_project(self.document, path)
        self.status.setText(f"Saved {path}")

    def open_project_from(self, path: str):
        self.document = project_io.load_project(path)
        self._refresh()

    def export_pdf_to(self, path: str):
        qt_renderer.export_document_pdf(self.document, path)
        self.status.setText(f"Exported {path}")

    # --- dialogs ---
    def _save_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "ImageAI Project (*.iaiproj.json)")
        if path:
            self.save_project_to(path)

    def _open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Project", "",
                                              "ImageAI Project (*.iaiproj.json *.layout.json)")
        if path:
            self.open_project_from(path)

    def _export_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", "", "PDF (*.pdf)")
        if path:
            self.export_pdf_to(path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_layout_tab.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Verify main-window construction still imports**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -c "from gui.layout import LayoutTab; print('LayoutTab import ok')"`
Expected: `LayoutTab import ok`
(If `gui/layout/__init__.py` exports more than `LayoutTab`, ensure it still imports — Phase 1 only changed `LayoutTab` internals.)

- [ ] **Step 6: Run the full Phase-1 suite**

Run: `.venv_linux/bin/python -m pytest tests/layout/ -v`
Expected: PASS (all Phase-1 tests green).

- [ ] **Step 7: Commit**

```bash
git add gui/layout/layout_tab.py tests/layout/test_layout_tab.py
git commit -m "feat(layout): rework Layout tab to AI-designer Phase-1 foundation (setup+canvas+save/export)"
```

---

## Self-Review

**Spec coverage (Phase 1 scope):**
- §3 data model (Region/PageSpec/DocumentSpec, polygon) → Tasks 2-3. ✓
- §4 page setup (size/orientation/unit/DPI, presets + freeform, custom persistence) → Tasks 1, 7. ✓
- §3/§8 Qt render source-of-truth + PNG + PDF (QPdfWriter) → Tasks 4-5. ✓
- §8 project save/load + legacy `.layout.json` migration → Tasks 3, 6. ✓
- functional canvas (rect + polygon, selectable) → Tasks 4, 8. ✓
- retire dev/info banners, keep `LayoutTab(config=...)` signature for `main_window` → Task 9. ✓
- Deferred by design (not Phase 1): AI designer/history (Phase 2), style system/sharing (Phase 3), content import + inspector editing (Phase 4), bundles + AI content (Phase 5). Polygon **vertex editing** deferred to Phase 2 per spec §12 risk note (Phase 1 renders + AI can emit polygons; rect drag only). ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases" — every code step contains complete code. ✓

**Type consistency:** `PageSize.to_pixels()` used identically in Tasks 1/2/4/9; `build_scene(page, selectable=…)` signature consistent across Tasks 4/8; `document_to_dict`/`document_from_dict` names consistent across Tasks 3/6; `regionSelected(str)`/`load_page` consistent across Tasks 8/9; `new_document`/`save_project_to`/`open_project_from`/`export_pdf_to` consistent across Task 9 test + impl. ✓

**Note for implementer:** image regions render as gray placeholders in Phase 1 — that is intentional; real image filling is Phase 4 (F-MVP). Do not add image-import UI here.
