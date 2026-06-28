# Layout CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three CLI commands — `--layout-design`, `--layout-fill`, `--layout-export` — that drive the existing `core/layout/` engine without launching the GUI.

**Architecture:** New `cli/commands/layout.py` holds pure helpers + three handlers that wire to already-tested `core.layout` functions (`designer`, `project_io`, `qt_renderer`, `styles`, `page_sizes`). `cli/parser.py` gains one argument group; `cli/runner.py` gains three dispatch branches. Design/fill are pure-Python; export bootstraps an offscreen `QApplication`.

**Tech Stack:** Python 3.12 (`.venv_linux`), argparse, pytest, LiteLLM (via `designer.run_completion`), PySide6 (export only).

**Design spec:** `Plans/2026-06-28-layout-cli-design.md`

## Global Constraints

- **No hardcoded LLM model IDs** — design resolves models through `designer.run_completion` → model registry; never hardcode `claude-*`/`gpt-*`/`gemini-*`.
- **All errors logged** — every user-facing error goes through a module logger (`logging.getLogger("imageai.cli.layout")`), platform-independently (AGENTS.md §6/§8).
- **Images scaled, not cropped** — fill saves provider output as-is; the renderer applies `fit="cover"`. Region image size is capped to max edge 1024 px (AGENTS.md §9 Google rule).
- **Content-kind values (exact):** `children`, `comic`, `comic_strip`, `magazine`, `newspaper`, `scientific`, `custom` (must match `gui/layout/designer_panel.py:15` / `core/layout/styles.py` keys).
- **Page-size names** resolve against `core/layout/page_sizes.py:PRESETS` (e.g. `Letter`→`US Letter`, `A4`, `A5`, `Tabloid`, `US Comic`, `Instagram Square`, `Full HD`); case-insensitive, substring fallback.
- **Layout-LLM provider set:** `openai`, `anthropic`, `google`, `ollama`, `lmstudio` (wider than image `--provider`). Default = `config.get_layout_llm_provider()`. There is **no** `get_layout_llm_model()`; default model = `None` → `run_completion` picks the provider's first registry model.
- **No new dependencies** (PySide6 is already a project dependency).
- **Test runner:** `.venv_linux/bin/python -m pytest`.

---

### Task 1: CLI parser — `layout` argument group

**Files:**
- Modify: `cli/parser.py` (add a new argument group before the `help` group, ~line 181)
- Test: `tests/layout/test_cli_layout_parser.py`

**Interfaces:**
- Consumes: `build_arg_parser()` (existing).
- Produces: parsed `args` with attributes `layout_design`, `layout_export`, `layout_fill`, `content_kind`, `page_size`, `orientation`, `dpi`, `layout_llm_provider`, `layout_llm_model` (all default `None` except where noted). Reuses existing `out`, `provider`, `model`, `api_key`, `api_key_file`, `auth_mode`.

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_cli_layout_parser.py
from cli.parser import build_arg_parser


def test_layout_design_flags_parse():
    p = build_arg_parser()
    args = p.parse_args([
        "--layout-design", "a 4-panel comic",
        "--content-kind", "comic",
        "--page-size", "A4",
        "--orientation", "landscape",
        "--dpi", "150",
        "--layout-llm-provider", "anthropic",
        "--layout-llm-model", "some-model",
        "-o", "out.iaiproj.json",
    ])
    assert args.layout_design == "a 4-panel comic"
    assert args.content_kind == "comic"
    assert args.page_size == "A4"
    assert args.orientation == "landscape"
    assert args.dpi == 150
    assert args.layout_llm_provider == "anthropic"
    assert args.layout_llm_model == "some-model"
    assert args.out == "out.iaiproj.json"


def test_layout_export_and_fill_flags_parse():
    p = build_arg_parser()
    a1 = p.parse_args(["--layout-export", "proj.json", "-o", "out.pdf"])
    assert a1.layout_export == "proj.json"
    a2 = p.parse_args(["--layout-fill", "proj.json", "--provider", "google"])
    assert a2.layout_fill == "proj.json"


def test_content_kind_rejects_unknown():
    import pytest
    p = build_arg_parser()
    with pytest.raises(SystemExit):
        p.parse_args(["--layout-design", "x", "--content-kind", "childrens_book"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_parser.py -v`
Expected: FAIL — `AttributeError: 'Namespace' object has no attribute 'layout_design'`.

- [ ] **Step 3: Add the argument group**

In `cli/parser.py`, insert before the `# Help options` group (currently ~line 182):

```python
    # Layout (publication layout engine)
    layout_group = parser.add_argument_group("layout")
    layout_group.add_argument(
        "--layout-design",
        metavar="DESCRIPTION",
        help="Generate a layout project from a text description (requires -o)",
    )
    layout_group.add_argument(
        "--layout-export",
        metavar="PROJECT",
        help="Render a layout project (.iaiproj.json/.layout.json) to PDF/PNG (requires -o)",
    )
    layout_group.add_argument(
        "--layout-fill",
        metavar="PROJECT",
        help="Generate images for all prompted image regions in a layout project",
    )
    layout_group.add_argument(
        "--content-kind",
        choices=["children", "comic", "comic_strip", "magazine",
                 "newspaper", "scientific", "custom"],
        help="Content kind for --layout-design (default: custom)",
    )
    layout_group.add_argument(
        "--page-size",
        help="Page size for --layout-design (e.g. Letter, A4, A5, Tabloid, US Comic; "
             "default: Letter)",
    )
    layout_group.add_argument(
        "--orientation",
        choices=["portrait", "landscape"],
        help="Page orientation for --layout-design (default: portrait)",
    )
    layout_group.add_argument(
        "--dpi",
        type=int,
        help="DPI for --layout-design geometry and --layout-export PDF (default: 300)",
    )
    layout_group.add_argument(
        "--layout-llm-provider",
        choices=["openai", "anthropic", "google", "ollama", "lmstudio"],
        help="Text-LLM provider for --layout-design (default: configured layout provider)",
    )
    layout_group.add_argument(
        "--layout-llm-model",
        help="Text-LLM model for --layout-design (default: provider's first registry model)",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_parser.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add cli/parser.py tests/layout/test_cli_layout_parser.py
git commit -m "feat(layout-cli): add layout argument group to CLI parser"
```

---

### Task 2: Pure helpers — page geometry, format inference, region sizing

**Files:**
- Create: `cli/commands/layout.py`
- Test: `tests/layout/test_cli_layout_helpers.py`

**Interfaces:**
- Consumes: `core.layout.page_sizes` (`PRESETS`, `preset_to_page_size`), `core.layout.models.Region`.
- Produces:
  - `_resolve_preset(name: str) -> dict` (raises `ValueError` on unknown)
  - `_page_px(page_size: str, orientation: str, dpi: int) -> tuple[int, int]`
  - `_export_format(out_path: str) -> str` (returns `"pdf"` or `"png"`; raises `ValueError` otherwise)
  - `_region_size_str(region: Region, cap: int = 1024) -> str` (returns `"WxH"`)

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_cli_layout_helpers.py
import pytest

from cli.commands.layout import (
    _resolve_preset, _page_px, _export_format, _region_size_str,
)
from core.layout.models import Region


def test_resolve_preset_case_insensitive_and_substring():
    assert _resolve_preset("A4")["name"] == "A4"
    assert _resolve_preset("letter")["name"] == "US Letter"
    with pytest.raises(ValueError):
        _resolve_preset("nope")


def test_page_px_letter_portrait_300dpi():
    # US Letter 8.5x11in @300dpi = 2550 x 3300
    assert _page_px("Letter", "portrait", 300) == (2550, 3300)


def test_page_px_landscape_swaps():
    assert _page_px("Letter", "landscape", 300) == (3300, 2550)


def test_export_format_from_extension():
    assert _export_format("a.pdf") == "pdf"
    assert _export_format("a.PNG") == "png"
    with pytest.raises(ValueError):
        _export_format("a.gif")


def test_region_size_str_caps_long_edge():
    r = Region(id="r1", kind="image", bbox=(0, 0, 4000, 2000))
    assert _region_size_str(r, cap=1024) == "1024x512"
    r2 = Region(id="r2", kind="image", bbox=(0, 0, 800, 600))
    assert _region_size_str(r2, cap=1024) == "800x600"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_helpers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cli.commands.layout'`.

- [ ] **Step 3: Create the helpers**

```python
# cli/commands/layout.py
"""CLI handlers for the publication layout engine (design / fill / export)."""
import logging
from pathlib import Path

from core.layout.models import Region
from core.layout.page_sizes import PRESETS, preset_to_page_size

logger = logging.getLogger("imageai.cli.layout")


def _resolve_preset(name: str) -> dict:
    """Match a user page-size name to a PRESETS entry (case-insensitive, substring)."""
    n = (name or "").strip().lower()
    for p in PRESETS:
        if p["name"].lower() == n:
            return p
    for p in PRESETS:
        if n and n in p["name"].lower():
            return p
    choices = ", ".join(p["name"] for p in PRESETS)
    raise ValueError(f"Unknown page size {name!r}. Choices: {choices}")


def _page_px(page_size: str, orientation: str, dpi: int) -> tuple:
    """Resolve (width_px, height_px) for a named page size at an orientation/DPI."""
    ps = preset_to_page_size(_resolve_preset(page_size), orientation, dpi)
    return ps.to_pixels()


def _export_format(out_path: str) -> str:
    """Return 'pdf' or 'png' from the output extension, else raise ValueError."""
    suffix = Path(out_path).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".png":
        return "png"
    raise ValueError(f"--layout-export -o must end in .pdf or .png (got {out_path!r})")


def _region_size_str(region: Region, cap: int = 1024) -> str:
    """'WxH' for a region's bbox, scaled so the long edge is <= cap (aspect kept)."""
    _, _, w, h = region.bbox
    w, h = int(w), int(h)
    longest = max(w, h, 1)
    if longest > cap:
        scale = cap / longest
        w = max(1, round(w * scale))
        h = max(1, round(h * scale))
    return f"{w}x{h}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_helpers.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add cli/commands/layout.py tests/layout/test_cli_layout_helpers.py
git commit -m "feat(layout-cli): add pure helpers (page px, format, region size)"
```

---

### Task 3: `_assemble_document` — DesignerResult → DocumentSpec

**Files:**
- Modify: `cli/commands/layout.py`
- Test: `tests/layout/test_cli_layout_assemble.py`

**Interfaces:**
- Consumes: `_resolve_preset` (Task 2); `core.layout.designer.DesignerResult`/`fallback_result`, `core.layout.styles.default_style_for`, `core.layout.models.{PageSpec,DocumentSpec}`.
- Produces: `_assemble_document(result, page_size: str, orientation: str, dpi: int, content_kind: str, title: str) -> DocumentSpec` — one page sized to `page_size`, carrying `result.regions` (or a full-page fallback when `None`) + `result.overlays`, with content-kind style defaults.

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_cli_layout_assemble.py
from cli.commands.layout import _assemble_document
from core.layout.designer import DesignerResult
from core.layout.models import Region


def test_assemble_builds_single_page_with_regions_and_style():
    regions = [Region(id="r1", kind="image", bbox=(0, 0, 100, 100))]
    result = DesignerResult(questions=[], regions=regions, overlays=[], raw="")
    doc = _assemble_document(result, "Letter", "portrait", 300, "comic", "MyBook")
    assert doc.title == "MyBook"
    assert doc.content_kind == "comic"
    assert len(doc.pages) == 1
    assert doc.pages[0].page_size_px == (2550, 3300)
    assert [r.id for r in doc.pages[0].regions] == ["r1"]
    # comic style provides a "dialogue" role
    assert "dialogue" in doc.style.font_roles


def test_assemble_uses_fallback_region_when_none():
    result = DesignerResult(questions=["need detail"], regions=None, overlays=[], raw="")
    doc = _assemble_document(result, "Letter", "portrait", 300, "custom", "X")
    assert len(doc.pages[0].regions) == 1  # full-page fallback frame
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_assemble.py -v`
Expected: FAIL — `ImportError: cannot import name '_assemble_document'`.

- [ ] **Step 3: Implement `_assemble_document`**

Add to `cli/commands/layout.py` (after the helpers; add imports at top):

```python
from core.layout import designer, styles
from core.layout.models import DocumentSpec, PageSpec


def _assemble_document(result, page_size: str, orientation: str, dpi: int,
                       content_kind: str, title: str) -> DocumentSpec:
    """Build a one-page DocumentSpec from a DesignerResult (mirrors GUI new-doc)."""
    ps = preset_to_page_size(_resolve_preset(page_size), orientation, dpi)
    pw, ph = ps.to_pixels()
    regions = (result.regions if result.regions is not None
               else designer.fallback_result((pw, ph)).regions)
    page = PageSpec(
        page_size_px=(pw, ph), page_size=ps, background="#FFFFFF",
        regions=list(regions), overlays=list(result.overlays or []),
    )
    return DocumentSpec(
        title=title or "Untitled", pages=[page],
        content_kind=content_kind, style=styles.default_style_for(content_kind),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_assemble.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add cli/commands/layout.py tests/layout/test_cli_layout_assemble.py
git commit -m "feat(layout-cli): assemble DocumentSpec from DesignerResult"
```

---

### Task 4: `run_design_cmd` — generate a layout from a description

**Files:**
- Modify: `cli/commands/layout.py`
- Test: `tests/layout/test_cli_layout_design.py`

**Interfaces:**
- Consumes: `_page_px`, `_assemble_document`; `core.layout.designer.{build_messages,run_completion,parse_response}`; `core.layout.project_io.save_project`.
- Produces: `run_design_cmd(args, config) -> int`. Reads `args.layout_design`, `args.out` (required), `args.content_kind`, `args.page_size`, `args.orientation`, `args.dpi`, `args.layout_llm_provider`, `args.layout_llm_model`. Returns `0` ok, `2` bad input, `3` LLM failure.

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_cli_layout_design.py
from argparse import Namespace

import cli.commands.layout as layout_cli
from core.layout import project_io


class _StubConfig:
    def get_layout_llm_provider(self):
        return "google"


def _args(**kw):
    base = dict(layout_design="a comic page", out=None, content_kind="comic",
                page_size="Letter", orientation="portrait", dpi=300,
                layout_llm_provider="google", layout_llm_model=None)
    base.update(kw)
    return Namespace(**base)


def test_design_writes_project(tmp_path, monkeypatch):
    out = tmp_path / "proj.iaiproj.json"
    fake_json = (
        '{"layout": {"regions": ['
        '{"id": "r1", "kind": "image", "bbox": [0,0,500,500]}]}}'
    )
    monkeypatch.setattr(layout_cli.designer, "run_completion",
                        lambda *a, **k: fake_json)
    rc = layout_cli.run_design_cmd(_args(out=str(out)), _StubConfig())
    assert rc == 0
    assert out.exists()
    doc = project_io.load_project(str(out))
    assert doc.content_kind == "comic"
    assert any(r.id == "r1" for r in doc.pages[0].regions)


def test_design_requires_out():
    rc = layout_cli.run_design_cmd(_args(out=None), _StubConfig())
    assert rc == 2


def test_design_llm_failure_returns_3(tmp_path, monkeypatch):
    out = tmp_path / "p.json"
    def _boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(layout_cli.designer, "run_completion", _boom)
    rc = layout_cli.run_design_cmd(_args(out=str(out)), _StubConfig())
    assert rc == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_design.py -v`
Expected: FAIL — `AttributeError: module 'cli.commands.layout' has no attribute 'run_design_cmd'`.

- [ ] **Step 3: Implement `run_design_cmd`**

Add to `cli/commands/layout.py` (add `from core.layout import project_io` to imports):

```python
def run_design_cmd(args, config) -> int:
    """Generate a layout project from a text description via the layout LLM."""
    text = args.layout_design
    out = getattr(args, "out", None)
    if not out:
        print("Error: --layout-design requires -o/--out (project .json path)")
        return 2
    content_kind = getattr(args, "content_kind", None) or "custom"
    page_size = getattr(args, "page_size", None) or "Letter"
    orientation = getattr(args, "orientation", None) or "portrait"
    dpi = int(getattr(args, "dpi", None) or 300)
    llm_provider = getattr(args, "layout_llm_provider", None) or config.get_layout_llm_provider()
    llm_model = getattr(args, "layout_llm_model", None)
    try:
        page_px = _page_px(page_size, orientation, dpi)
    except ValueError as e:
        print(f"Error: {e}")
        return 2

    messages = designer.build_messages(content_kind, page_px, text)
    try:
        content = designer.run_completion(config, llm_provider, llm_model, messages)
    except Exception as e:  # noqa: BLE001 - surface + log any LLM/runtime failure
        logger.error("Layout design LLM call failed: %s", e)
        print(f"Error: layout design failed: {e}")
        return 3

    result = designer.parse_response(content or "", page_px)
    for q in result.questions:
        print(f"[designer] {q}")
    title = Path(out).stem or "Untitled"
    doc = _assemble_document(result, page_size, orientation, dpi, content_kind, title)
    project_io.save_project(doc, str(Path(out).expanduser()))
    page0 = doc.pages[0]
    print(f"Saved layout project to {out} "
          f"({len(page0.regions)} regions, {len(page0.overlays)} overlays)")
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_design.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add cli/commands/layout.py tests/layout/test_cli_layout_design.py
git commit -m "feat(layout-cli): --layout-design handler"
```

---

### Task 5: `run_fill_cmd` — generate images for prompted regions

**Files:**
- Modify: `cli/commands/layout.py`
- Test: `tests/layout/test_cli_layout_fill.py`

**Interfaces:**
- Consumes: `_region_size_str`; `core.layout.project_io.{load_project,save_project}`; `cli.runner.resolve_api_key`; `providers.get_provider`.
- Produces: `run_fill_cmd(args, config) -> int`. Reads `args.layout_fill` (project path), `args.out` (optional; in-place when absent), `args.provider`, `args.model`, `args.api_key`, `args.api_key_file`, `args.auth_mode`. Uses `config.get_images_dir()`. Returns `0` ok, `2` bad input/no key, `4` if any region failed.

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_cli_layout_fill.py
from argparse import Namespace

import cli.commands.layout as layout_cli
from core.layout import project_io
from core.layout.models import DocumentSpec, PageSpec, Region


class _StubConfig:
    def __init__(self, images_dir):
        self._d = images_dir
    def get_images_dir(self):
        return self._d


class _FakeProvider:
    def get_default_model(self):
        return "fake-model"
    def generate(self, prompt, model=None, **kwargs):
        return ([], [b"PNGBYTES"])


def _project(tmp_path):
    doc = DocumentSpec(title="t", pages=[PageSpec(
        page_size_px=(500, 500),
        regions=[
            Region(id="r1", kind="image", bbox=(0, 0, 200, 200), prompt="a cat"),
            Region(id="r2", kind="image", bbox=(0, 0, 200, 200), prompt=""),  # skipped
            Region(id="t1", kind="text", bbox=(0, 0, 200, 50), text="hi"),    # ignored
        ])])
    p = tmp_path / "proj.json"
    project_io.save_project(doc, str(p))
    return p


def _args(path, **kw):
    base = dict(layout_fill=str(path), out=None, provider="google", model=None,
                api_key="dummy", api_key_file=None, auth_mode="api-key")
    base.update(kw)
    return Namespace(**base)


def test_fill_sets_image_ref_and_saves(tmp_path, monkeypatch):
    images = tmp_path / "images"; images.mkdir()
    p = _project(tmp_path)
    monkeypatch.setattr(layout_cli, "get_provider", lambda prov, cfg: _FakeProvider())
    rc = layout_cli.run_fill_cmd(_args(p), _StubConfig(images))
    assert rc == 0
    doc = project_io.load_project(str(p))  # saved in-place
    r1 = next(r for r in doc.pages[0].regions if r.id == "r1")
    r2 = next(r for r in doc.pages[0].regions if r.id == "r2")
    assert r1.image_ref and Path(r1.image_ref).exists()
    assert not r2.image_ref  # no prompt -> skipped


def test_fill_failure_returns_4(tmp_path, monkeypatch):
    images = tmp_path / "images"; images.mkdir()
    p = _project(tmp_path)
    class _Boom(_FakeProvider):
        def generate(self, prompt, model=None, **kwargs):
            raise RuntimeError("api error")
    monkeypatch.setattr(layout_cli, "get_provider", lambda prov, cfg: _Boom())
    rc = layout_cli.run_fill_cmd(_args(p), _StubConfig(images))
    assert rc == 4


from pathlib import Path  # noqa: E402  (placed after to keep test code grouped)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_fill.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'run_fill_cmd'`.

- [ ] **Step 3: Implement `run_fill_cmd`**

Add to `cli/commands/layout.py`. Add module-level imports `from cli.runner import resolve_api_key` and `from providers import get_provider` at the top (so tests can monkeypatch `layout_cli.get_provider`):

```python
def run_fill_cmd(args, config) -> int:
    """Generate images for every prompted image region, in-place (or to -o)."""
    src = Path(getattr(args, "layout_fill")).expanduser()
    if not src.exists():
        print(f"Error: project file not found: {src}")
        return 2
    try:
        doc = project_io.load_project(str(src))
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to load project %s: %s", src, e)
        print(f"Error: failed to load project: {e}")
        return 2

    provider = (getattr(args, "provider", None) or "google").strip().lower()
    key, _ = resolve_api_key(getattr(args, "api_key", None),
                             getattr(args, "api_key_file", None), provider)
    if not key and provider != "local_sd":
        print("No API key. Use --api-key/--api-key-file or --set-key.")
        return 2
    provider_config = {"api_key": key, "auth_mode": getattr(args, "auth_mode", "api-key")}
    try:
        provider_instance = get_provider(provider, provider_config)
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to init provider %s: %s", provider, e)
        print(f"Error: {e}")
        return 2
    model = getattr(args, "model", None) or provider_instance.get_default_model()
    images_dir = Path(config.get_images_dir())
    images_dir.mkdir(parents=True, exist_ok=True)
    stem = src.stem

    filled, skipped, failed = 0, [], []
    for page in doc.pages:
        for r in page.regions:
            if r.kind != "image":
                continue
            if not (r.prompt or "").strip():
                skipped.append(r.id)
                continue
            try:
                _texts, images = provider_instance.generate(
                    prompt=r.prompt, model=model,
                    size=_region_size_str(r), n=1)
                if not images:
                    logger.error("Fill: no image returned for region %s", r.id)
                    failed.append(r.id)
                    continue
                img_path = images_dir / f"{stem}_{r.id}.png"
                img_path.write_bytes(images[0])
                r.image_ref = str(img_path)
                filled += 1
                print(f"Filled region {r.id} -> {img_path}")
            except Exception as e:  # noqa: BLE001 - log, continue, report
                logger.error("Fill failed for region %s: %s", r.id, e)
                print(f"Failed region {r.id}: {e}")
                failed.append(r.id)

    out = Path(getattr(args, "out", None) or src).expanduser()
    project_io.save_project(doc, str(out))
    print(f"Saved project to {out}. "
          f"Filled {filled}, skipped {len(skipped)}, failed {len(failed)}.")
    return 0 if not failed else 4
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_fill.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add cli/commands/layout.py tests/layout/test_cli_layout_fill.py
git commit -m "feat(layout-cli): --layout-fill handler (sync per-region)"
```

---

### Task 6: `run_export_cmd` — render a project to PDF/PNG (offscreen Qt)

**Files:**
- Modify: `cli/commands/layout.py`
- Test: `tests/layout/test_cli_layout_export.py`

**Interfaces:**
- Consumes: `_export_format`; `core.layout.project_io.load_project`; `core.layout.qt_renderer.{export_document_pdf,save_page_png}`; `config.get_layout_export_dpi()`.
- Produces:
  - `_with_offscreen_qapp(fn)` — ensures a `QApplication` exists under `QT_QPA_PLATFORM=offscreen`; raises `RuntimeError` with an install hint if PySide6 is missing; returns `fn()`.
  - `run_export_cmd(args, config) -> int`. Reads `args.layout_export` (path), `args.out` (required, `.pdf`/`.png`), `args.dpi`. PDF is one document; multi-page PNG writes `out-001.png …`. PNG renders at the project's native pixel size. Returns `0` ok, `2` bad input / PySide6 missing.

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_cli_layout_export.py
from argparse import Namespace

import pytest

pytest.importorskip("PySide6")  # export needs Qt; skip in headless-without-Qt envs

import cli.commands.layout as layout_cli
from core.layout import project_io
from core.layout.models import DocumentSpec, PageSpec, Region


class _StubConfig:
    def get_layout_export_dpi(self):
        return 300


def _project(tmp_path):
    doc = DocumentSpec(title="t", pages=[PageSpec(
        page_size_px=(300, 300), background="#FFFFFF",
        regions=[Region(id="r1", kind="image", bbox=(10, 10, 100, 100))])])
    p = tmp_path / "proj.json"
    project_io.save_project(doc, str(p))
    return p


def _args(path, out, dpi=None):
    return Namespace(layout_export=str(path), out=str(out), dpi=dpi)


def test_export_pdf(tmp_path):
    p = _project(tmp_path)
    out = tmp_path / "out.pdf"
    rc = layout_cli.run_export_cmd(_args(p, out), _StubConfig())
    assert rc == 0
    assert out.exists() and out.stat().st_size > 0


def test_export_png(tmp_path):
    p = _project(tmp_path)
    out = tmp_path / "out.png"
    rc = layout_cli.run_export_cmd(_args(p, out), _StubConfig())
    assert rc == 0
    assert out.exists() and out.stat().st_size > 0


def test_export_bad_extension(tmp_path):
    p = _project(tmp_path)
    rc = layout_cli.run_export_cmd(_args(p, tmp_path / "out.gif"), _StubConfig())
    assert rc == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_export.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'run_export_cmd'`.

- [ ] **Step 3: Implement export handler + offscreen bootstrap**

Add to `cli/commands/layout.py` (add `import os` to the top imports):

```python
def _with_offscreen_qapp(fn):
    """Run fn() with a headless QApplication; raise RuntimeError if PySide6 absent."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as e:
        raise RuntimeError(
            "Layout export requires PySide6 — install with: pip install PySide6") from e
    app = QApplication.instance() or QApplication([])  # noqa: F841 - kept alive
    return fn()


def run_export_cmd(args, config) -> int:
    """Render a layout project to PDF or PNG (format inferred from -o)."""
    src = Path(getattr(args, "layout_export")).expanduser()
    out = getattr(args, "out", None)
    if not out:
        print("Error: --layout-export requires -o/--out (.pdf or .png)")
        return 2
    if not src.exists():
        print(f"Error: project file not found: {src}")
        return 2
    try:
        fmt = _export_format(out)
    except ValueError as e:
        print(f"Error: {e}")
        return 2
    try:
        doc = project_io.load_project(str(src))
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to load project %s: %s", src, e)
        print(f"Error: failed to load project: {e}")
        return 2
    dpi = int(getattr(args, "dpi", None) or config.get_layout_export_dpi() or 300)
    out_path = Path(out).expanduser()

    def _do():
        from core.layout import qt_renderer
        if fmt == "pdf":
            qt_renderer.export_document_pdf(doc, str(out_path), dpi=dpi)
            print(f"Exported PDF to {out_path}")
        else:
            pages = doc.pages
            if len(pages) == 1:
                qt_renderer.save_page_png(pages[0], str(out_path), style=doc.style)
                print(f"Exported PNG to {out_path}")
            else:
                for i, page in enumerate(pages, start=1):
                    p = out_path.with_name(f"{out_path.stem}-{i:03d}{out_path.suffix}")
                    qt_renderer.save_page_png(page, str(p), style=doc.style)
                    print(f"Exported PNG to {p}")

    try:
        _with_offscreen_qapp(_do)
    except RuntimeError as e:
        logger.error("Layout export failed: %s", e)
        print(f"Error: {e}")
        return 2
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_export.py -v`
Expected: PASS (3 tests) — or SKIP if PySide6 is unavailable in the environment.

- [ ] **Step 5: Commit**

```bash
git add cli/commands/layout.py tests/layout/test_cli_layout_export.py
git commit -m "feat(layout-cli): --layout-export handler (offscreen Qt PDF/PNG)"
```

---

### Task 7: Wire dispatch into `run_cli`

**Files:**
- Modify: `cli/runner.py` (in `run_cli`, after the `--lyrics-to-prompts` block, ~line 216)
- Test: `tests/layout/test_cli_layout_dispatch.py`

**Interfaces:**
- Consumes: `run_design_cmd`, `run_fill_cmd`, `run_export_cmd` (Tasks 4-6); `ConfigManager` (existing import).
- Produces: `run_cli(args)` routes `--layout-design`/`--layout-fill`/`--layout-export` to their handlers before image-generation/key handling.

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_cli_layout_dispatch.py
from cli.parser import build_arg_parser
from cli.runner import run_cli
import cli.runner as runner


def test_dispatch_routes_design(monkeypatch):
    called = {}
    monkeypatch.setattr("cli.commands.layout.run_design_cmd",
                        lambda args, config: called.setdefault("design", True) or 0)
    args = build_arg_parser().parse_args(
        ["--layout-design", "x", "-o", "p.json"])
    assert run_cli(args) == 0
    assert called.get("design")


def test_dispatch_routes_export(monkeypatch):
    called = {}
    monkeypatch.setattr("cli.commands.layout.run_export_cmd",
                        lambda args, config: called.setdefault("export", True) or 0)
    args = build_arg_parser().parse_args(
        ["--layout-export", "p.json", "-o", "o.pdf"])
    assert run_cli(args) == 0
    assert called.get("export")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_dispatch.py -v`
Expected: FAIL — handlers not routed (`run_cli` falls through to "Nothing to do", returns 0 without setting `called`).

- [ ] **Step 3: Add dispatch branches**

In `cli/runner.py`, immediately after the `--lyrics-to-prompts` block (after line 216 `return handle_lyrics_to_prompts(args)`):

```python
    # Handle layout commands (publication layout engine)
    if getattr(args, "layout_design", None):
        from cli.commands.layout import run_design_cmd
        return run_design_cmd(args, ConfigManager())
    if getattr(args, "layout_fill", None):
        from cli.commands.layout import run_fill_cmd
        return run_fill_cmd(args, ConfigManager())
    if getattr(args, "layout_export", None):
        from cli.commands.layout import run_export_cmd
        return run_export_cmd(args, ConfigManager())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_dispatch.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full layout + CLI suite**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_cli_layout_*.py -v`
Expected: all PASS (export may SKIP without PySide6).

- [ ] **Step 6: Commit**

```bash
git add cli/runner.py tests/layout/test_cli_layout_dispatch.py
git commit -m "feat(layout-cli): route layout commands in run_cli"
```

---

### Task 8: Docs — document the new CLI commands

**Files:**
- Modify: `README.md` (CLI usage section — add layout examples)
- Modify: `Docs/` CLI reference if one exists (grep for an existing CLI doc; otherwise skip)

**Interfaces:** none (documentation only).

- [ ] **Step 1: Add usage examples to README**

Under the existing CLI examples, add:

```markdown
### Layout (publication layout engine)

```bash
# Design a layout from a description (LLM → project JSON)
python main.py --layout-design "4-panel comic about a cat heist" \
    --content-kind comic --page-size Letter -o heist.iaiproj.json

# Generate images for every prompted region (in-place)
python main.py --layout-fill heist.iaiproj.json --provider google

# Render to PDF or PNG
python main.py --layout-export heist.iaiproj.json -o heist.pdf
python main.py --layout-export heist.iaiproj.json -o heist.png
```

Notes:
- `--layout-design` uses the text LLM (`--layout-llm-provider`/`--layout-llm-model`);
  `--layout-fill` uses the image provider (`--provider`/`-m`).
- `--layout-export` requires PySide6 (`pip install PySide6`); design and fill do not.
- PNG export renders at the project's native pixel size; `--dpi` controls PDF
  rendering and design geometry.
```

- [ ] **Step 2: Verify the full suite still passes**

Run: `.venv_linux/bin/python -m pytest tests/layout/ -q`
Expected: PASS (export tests may SKIP without PySide6).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(layout-cli): document --layout-design/--fill/--export"
```

---

## Self-Review

**Spec coverage:**
- §4 CLI surface → Task 1 (flags), Tasks 4-6 (behavior). ✅
- §4 export format inference → Task 2 `_export_format`, Task 6 multi-page PNG. ✅
- §4 separate layout-LLM vs image provider → Task 4 (`layout_llm_provider`) vs Task 5 (`provider`). ✅
- §5 components (`cli/commands/layout.py`, parser group, runner dispatch) → Tasks 1-7. ✅
- §6 data flow (design/fill/export) → Tasks 4/5/6. ✅
- §7 error handling (PySide6 missing, LLM fail, bad inputs, fill partial→non-zero) → Tasks 4-6 return codes + logging. ✅
- §8 DesignerResult→DocumentSpec assembler → Task 3. ✅
- §9 testing (parser, page_px, format, design mock, fill mock, export guarded) → every task's tests. ✅

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✅

**Type consistency:** Handler signatures `(args, config) -> int` consistent across Tasks 4-7. `_assemble_document(result, page_size, orientation, dpi, content_kind, title)` defined in Task 3, called identically in Task 4. `_region_size_str(region, cap=1024)`, `_export_format(out_path)`, `_page_px(page_size, orientation, dpi)` defined in Task 2, used unchanged later. ✅

**Known nuance (documented, not a gap):** PNG export renders at the project's native pixel size (`save_page_png` has no scale param); `--dpi` affects PDF + design geometry. Captured in Task 8 README notes.
