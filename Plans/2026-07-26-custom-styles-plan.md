# Custom Styles Implementation Plan

> **Status: EXECUTED 2026-07-26** — all 17 tasks complete via subagent-driven development; final review + fix wave clean; suite 587 green; shipped as PR #35 / v0.41.0. Fix-round history lived in .superpowers/sdd/ (ephemeral); the durable record is git history + the PR body.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `Plans/2026-07-26-custom-styles-design.md` (approved 2026-07-26). Read it first.

**Goal:** Derive reusable named styles from N reference images via LLM vision and apply them to every generation surface (image GUI/CLI, video, layout) across all providers.

**Architecture:** New self-contained `core/styles/` package (models / store / analyzer / applicator) with LLM calls injected as callables for testability; GUI adds `gui/styles/` (manager dialog + reusable picker); CLI adds a `styles` argument group + `cli/commands/style.py`. Styling is applied at four seams via one `apply_style()` function.

**Tech Stack:** Python 3.12 (`.venv_linux`), PySide6, LiteLLM via `UnifiedLLMProvider`, PIL, pytest.

## Global Constraints

- **Branch:** all work on `feat/custom-styles`, cut with `git -C /mnt/d/Documents/Code/GitHub/ImageAI fetch && git -C /mnt/d/Documents/Code/GitHub/ImageAI checkout -b feat/custom-styles origin/main` before Task 1. One PR for the whole feature at the end — never per task.
- **No `cd`:** absolute paths everywhere; `git -C /mnt/d/Documents/Code/GitHub/ImageAI …` for git.
- **Python:** `PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python` — every test run uses `$PY -m pytest`.
- **GUI tests:** prefix with `QT_QPA_PLATFORM=offscreen` (headless WSL).
- **No hardcoded cloud LLM model IDs** — use `resolve_model()` (`core/llm_models.py:63`); static defaults only as the `static_default=` argument.
- **No dimensions/aspect-ratio strings in any prompt text** (Google renders them literally); the derivation and merge prompts must forbid them.
- **All LLM requests/responses logged** to file log + status console (AGENTS.md §8).
- **Sidecars/history keep the un-styled prompt**; style provenance goes in a separate `style_applied` key.
- **Commits:** Conventional Commits (`feat:`, `test:`, `docs:`); commit at the end of every task.
- **User-data paths:** styles live under `get_user_data_dir() / "styles"` (`core/constants.py:140`), never in the repo.

## File Structure

| Path | Responsibility |
|---|---|
| `core/styles/__init__.py` | Public API re-exports: `Style`, `StyleDescriptor`, `StyleStore`, `apply_style`, `StyledRequest`, `StyleAnalysisError` |
| `core/styles/models.py` | `StyleDescriptor` + `Style` dataclasses, dict round-trip |
| `core/styles/store.py` | `StyleStore`: CRUD, slugs, image copy+downscale, zip export/import |
| `core/styles/analyzer.py` | Chunking, vision message building, descriptor parse/flatten/merge, `derive_style_data()` (pure), `StyleAnalysisService` + `build_completion_fn()` (transport) |
| `core/styles/applicator.py` | `apply_style()`, `StyledRequest`, `style_ref_limit()`, smart-merge prompt |
| `cli/parser.py` | new `styles` argument group |
| `cli/commands/style.py` | management verbs (`run_style_cmd`), `_collect_images` |
| `cli/runner.py` | dispatch to `run_style_cmd`; `--style` on the `--prompt` path |
| `gui/styles/__init__.py`, `style_picker.py` | `StylePickerWidget` (combo + Manage… + Smart merge) |
| `gui/styles/style_manager_dialog.py` | manager dialog + `StyleAnalysisWorker(QThread)` |
| `gui/main_window.py` | picker row in Generate tab; `_generate()` seam; sidecar key |
| `gui/video/workspace_widget.py` | picker + stored-style scene injection |
| `core/layout/batch_fill.py`, `cli/commands/layout.py` | optional style on batch requests / fill loop |
| `tests/styles/…` | all new tests (`__init__.py` not needed; pytest rootdir config exists) |

Interfaces used from the existing codebase (verified 2026-07-26):

- `UnifiedLLMProvider(config: dict)` with keys `openai_api_key` / `anthropic_api_key` / `google_api_key`; `analyze_image(messages, model=None, temperature=0.7, max_tokens=1000, response_format=None, console_callback=None) -> str` (`core/video/prompt_engine.py:70,939`) — works for text-only messages too.
- `LLMResponseParser.parse_json_response(content, expected_type=dict)` (`gui/llm_utils.py:19`).
- `resolve_model(provider_id, family, static_default=None)` (`core/llm_models.py:63`); `get_provider_prefix(provider_id)` (`core/llm_models.py:238`) returns LiteLLM prefixes (`''`, `anthropic/`, `gemini/`).
- `get_user_data_dir()` (`core/constants.py:140`).
- `ConfigManager.get_api_key(provider)` (`core/config.py:121`); `config.get(key, default)` / `config.set(key, value)` / `config.save()`.
- Dialog conventions: `gui/common/dialog_conventions.py` (`standard_splitter`, `persist_splitter`, `restore_splitter`, `bind_primary_action`, `set_default_button`, `DialogCleanupMixin`), `gui/dialog_utils.py` (`show_error`, `show_warning`, `OperationGuardMixin`), `gui/llm_utils.py` (`DialogStatusConsole`).

---

### Task 1: Style dataclasses (`core/styles/models.py`)

**Files:**
- Create: `core/styles/__init__.py`, `core/styles/models.py`
- Test: `tests/styles/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `DESCRIPTOR_KEYS: tuple[str, ...]`; `StyleDescriptor` (fields = the 9 keys, `to_dict() -> dict`, `from_dict(data) -> StyleDescriptor`); `Style(id, name, description="", descriptor=StyleDescriptor(), prompt_text="", placement="suffix", reference_images=[], exemplars=[], source={}, version=1, is_builtin=False)` with `to_dict()` / `from_dict(data)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/styles/test_models.py
"""Tests for core/styles/models.py — Style record dataclasses."""
from core.styles.models import DESCRIPTOR_KEYS, Style, StyleDescriptor


def test_descriptor_keys():
    assert DESCRIPTOR_KEYS == (
        "summary", "medium", "palette", "lighting", "composition",
        "texture", "line_work", "mood", "negative",
    )


def test_descriptor_round_trip():
    d = StyleDescriptor(summary="Watercolor wash", palette="warm pastels")
    data = d.to_dict()
    assert set(data.keys()) == set(DESCRIPTOR_KEYS)
    assert data["summary"] == "Watercolor wash"
    assert StyleDescriptor.from_dict(data) == d


def test_descriptor_from_dict_tolerates_missing_and_extra():
    d = StyleDescriptor.from_dict({"summary": "x", "bogus": "y", "mood": None})
    assert d.summary == "x"
    assert d.mood == ""


def test_style_round_trip():
    s = Style(id="water", name="Water", prompt_text="soft washes",
              reference_images=["refs/0001.jpg"], exemplars=["refs/0001.jpg"],
              source={"provider": "openai", "image_count": 2})
    data = s.to_dict()
    s2 = Style.from_dict(data)
    assert s2 == s
    assert s2.placement == "suffix"
    assert s2.descriptor == StyleDescriptor()


def test_style_from_dict_defaults():
    s = Style.from_dict({"id": "a", "name": "A"})
    assert s.placement == "suffix"
    assert s.reference_images == [] and s.exemplars == []
    assert s.version == 1 and s.is_builtin is False
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest tests/styles/test_models.py -v` (from repo root; `$PY` per Global Constraints)
Expected: FAIL — `ModuleNotFoundError: No module named 'core.styles'`

- [ ] **Step 3: Implement**

```python
# core/styles/models.py
"""Style record dataclasses for the Custom Styles feature.

A Style is a hybrid object: an AI-derived structured descriptor plus a
flattened, user-editable prompt_text, plus copied reference images with a
starred exemplar subset. See Plans/2026-07-26-custom-styles-design.md §3.
"""
from dataclasses import dataclass, field
from typing import Dict, List

DESCRIPTOR_KEYS = (
    "summary", "medium", "palette", "lighting", "composition",
    "texture", "line_work", "mood", "negative",
)


@dataclass
class StyleDescriptor:
    summary: str = ""
    medium: str = ""
    palette: str = ""
    lighting: str = ""
    composition: str = ""
    texture: str = ""
    line_work: str = ""
    mood: str = ""
    negative: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {k: getattr(self, k) for k in DESCRIPTOR_KEYS}

    @classmethod
    def from_dict(cls, data) -> "StyleDescriptor":
        data = data or {}
        return cls(**{k: str(data.get(k) or "") for k in DESCRIPTOR_KEYS})


@dataclass
class Style:
    id: str
    name: str
    description: str = ""
    descriptor: StyleDescriptor = field(default_factory=StyleDescriptor)
    prompt_text: str = ""
    placement: str = "suffix"  # "prefix" | "suffix"
    reference_images: List[str] = field(default_factory=list)  # relative to style dir
    exemplars: List[str] = field(default_factory=list)  # subset of reference_images
    source: Dict = field(default_factory=dict)
    version: int = 1
    is_builtin: bool = False

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "descriptor": self.descriptor.to_dict(),
            "prompt_text": self.prompt_text,
            "placement": self.placement,
            "reference_images": list(self.reference_images),
            "exemplars": list(self.exemplars),
            "source": dict(self.source),
            "version": self.version,
            "is_builtin": self.is_builtin,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Style":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            descriptor=StyleDescriptor.from_dict(data.get("descriptor")),
            prompt_text=data.get("prompt_text", ""),
            placement=data.get("placement", "suffix"),
            reference_images=list(data.get("reference_images") or []),
            exemplars=list(data.get("exemplars") or []),
            source=dict(data.get("source") or {}),
            version=int(data.get("version", 1)),
            is_builtin=bool(data.get("is_builtin", False)),
        )
```

```python
# core/styles/__init__.py
"""Custom Styles: derive reusable styles from reference images, apply anywhere."""
from core.styles.models import DESCRIPTOR_KEYS, Style, StyleDescriptor

__all__ = ["DESCRIPTOR_KEYS", "Style", "StyleDescriptor"]
```

(Later tasks extend `__init__.py` — Task 2 adds `StyleStore`, Task 4 adds `StyleAnalysisError`, Task 6 adds `apply_style` / `StyledRequest`.)

- [ ] **Step 4: Run to verify pass**

Run: `$PY -m pytest tests/styles/test_models.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/styles tests/styles
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): add Style and StyleDescriptor dataclasses"
```

---

### Task 2: StyleStore CRUD + image import (`core/styles/store.py`)

**Files:**
- Create: `core/styles/store.py`
- Modify: `core/styles/__init__.py` (add `StyleStore` to imports/`__all__`)
- Test: `tests/styles/test_store.py`

**Interfaces:**
- Consumes: `Style` / `StyleDescriptor` (Task 1); `get_user_data_dir()` from `core.constants`; PIL.
- Produces: `StyleStore(base_dir=None)` with `list_styles() -> List[Style]`, `get(style_id) -> Optional[Style]`, `get_by_name(name) -> Optional[Style]` (case-insensitive on name or id), `new_id(name) -> str`, `save(style) -> None`, `delete(style_id) -> bool`, `style_dir(style_id) -> Path`, `add_reference_images(style, paths) -> List[str]`, `remove_reference_image(style, rel_path) -> None`, `resolve_refs(style, exemplars_only=False) -> List[Path]`. Module constants `MAX_IMPORT_DIM = 2048`, `JPEG_QUALITY = 90`, `EXEMPLAR_DEFAULT_CAP = 3`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/styles/test_store.py
"""Tests for core/styles/store.py — persistence, slugs, image import."""
from pathlib import Path

from PIL import Image

from core.styles.models import Style
from core.styles.store import (
    EXEMPLAR_DEFAULT_CAP, JPEG_QUALITY, MAX_IMPORT_DIM, StyleStore,
)


def _make_image(path: Path, size=(64, 64), color=(200, 30, 30)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def test_store_starts_empty(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    assert store.list_styles() == []
    assert store.get("nope") is None


def test_save_get_delete_round_trip(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id("Watercolor Storybook"), name="Watercolor Storybook",
              prompt_text="soft washes")
    store.save(s)
    assert s.id == "watercolor-storybook"
    got = store.get("watercolor-storybook")
    assert got is not None and got.name == "Watercolor Storybook"
    # fresh instance reads the same file
    assert StyleStore(base_dir=tmp_path / "styles").get_by_name("watercolor storybook").id == s.id
    assert store.get_by_name("WATERCOLOR-STORYBOOK").id == s.id  # id match too
    assert store.delete(s.id) is True
    assert store.get(s.id) is None
    assert store.delete(s.id) is False


def test_new_id_collision_gets_suffix(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    store.save(Style(id=store.new_id("Neon!"), name="Neon!"))
    second = store.new_id("Neon!")
    assert second == "neon-2"


def test_add_reference_images_copies_and_downscales(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id("Big"), name="Big")
    store.save(s)
    src = _make_image(tmp_path / "src" / "huge.png", size=(4096, 1024))
    added = store.add_reference_images(s, [src])
    assert added == ["refs/0001.jpg"]
    assert s.reference_images == ["refs/0001.jpg"]
    copied = store.style_dir(s.id) / "refs" / "0001.jpg"
    assert copied.exists()
    with Image.open(copied) as img:
        assert max(img.size) <= MAX_IMPORT_DIM
    assert src.exists()  # original untouched


def test_resolve_refs_filters_missing_and_exemplars(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id("R"), name="R")
    store.save(s)
    imgs = [_make_image(tmp_path / f"i{n}.png") for n in range(3)]
    store.add_reference_images(s, imgs)
    s.exemplars = [s.reference_images[0], s.reference_images[2]]
    store.save(s)
    assert len(store.resolve_refs(s)) == 3
    assert len(store.resolve_refs(s, exemplars_only=True)) == 2
    (store.style_dir(s.id) / "refs" / "0001.jpg").unlink()
    assert len(store.resolve_refs(s)) == 2  # missing file silently dropped


def test_remove_reference_image(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id("Rm"), name="Rm")
    store.save(s)
    store.add_reference_images(s, [_make_image(tmp_path / "a.png")])
    rel = s.reference_images[0]
    s.exemplars = [rel]
    store.remove_reference_image(s, rel)
    assert s.reference_images == [] and s.exemplars == []
    assert not (store.style_dir(s.id) / "refs" / "0001.jpg").exists()


def test_delete_removes_style_dir(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id("Gone"), name="Gone")
    store.save(s)
    store.add_reference_images(s, [_make_image(tmp_path / "g.png")])
    d = store.style_dir(s.id)
    assert d.exists()
    store.delete(s.id)
    assert not d.exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest tests/styles/test_store.py -v`
Expected: FAIL — `ImportError: cannot import name 'StyleStore'`

- [ ] **Step 3: Implement**

```python
# core/styles/store.py
"""Persistence for custom styles.

Layout (per Plans/2026-07-26-custom-styles-design.md §3):
    <base_dir>/styles.json      index: {"styles": [record, ...]}
    <base_dir>/<id>/refs/*.jpg  copied, downscaled source images
base_dir defaults to get_user_data_dir()/"styles" — personal artifacts never
live in the repo (unlike data/prompts/custom_presets.json).
"""
import json
import logging
import re
import shutil
from pathlib import Path
from typing import List, Optional

from core.styles.models import Style

logger = logging.getLogger(__name__)

MAX_IMPORT_DIM = 2048
JPEG_QUALITY = 90
EXEMPLAR_DEFAULT_CAP = 3


class StyleStore:
    """CRUD + reference-image management for styles (PresetLoader-shaped)."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            from core.constants import get_user_data_dir
            base_dir = get_user_data_dir() / "styles"
        self.base_dir = Path(base_dir)
        self.index_path = self.base_dir / "styles.json"

    # ---- index I/O -------------------------------------------------------

    def _read_index(self) -> List[dict]:
        if not self.index_path.exists():
            return []
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f).get("styles", [])
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read style index {self.index_path}: {e}")
            return []

    def _write_index(self, records: List[dict]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump({"styles": records}, f, indent=2, ensure_ascii=False)

    # ---- CRUD ------------------------------------------------------------

    def list_styles(self) -> List[Style]:
        out = []
        for rec in self._read_index():
            try:
                out.append(Style.from_dict(rec))
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed style record: {e}")
        return out

    def get(self, style_id: str) -> Optional[Style]:
        for s in self.list_styles():
            if s.id == style_id:
                return s
        return None

    def get_by_name(self, name: str) -> Optional[Style]:
        """Match by display name or id, case-insensitively."""
        needle = (name or "").strip().lower()
        for s in self.list_styles():
            if s.name.lower() == needle or s.id.lower() == needle:
                return s
        return None

    def new_id(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", (name or "style").lower()).strip("-") or "style"
        existing = {s.id for s in self.list_styles()}
        if slug not in existing:
            return slug
        n = 2
        while f"{slug}-{n}" in existing:
            n += 1
        return f"{slug}-{n}"

    def save(self, style: Style) -> None:
        records = self._read_index()
        rec = style.to_dict()
        for i, existing in enumerate(records):
            if existing.get("id") == style.id:
                records[i] = rec
                break
        else:
            records.append(rec)
        self._write_index(records)
        logger.info(f"Saved style '{style.name}' ({style.id})")

    def delete(self, style_id: str) -> bool:
        records = self._read_index()
        kept = [r for r in records if r.get("id") != style_id]
        if len(kept) == len(records):
            return False
        self._write_index(kept)
        d = self.style_dir(style_id)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        logger.info(f"Deleted style {style_id}")
        return True

    # ---- reference images ------------------------------------------------

    def style_dir(self, style_id: str) -> Path:
        return self.base_dir / style_id

    def add_reference_images(self, style: Style, paths: List[Path]) -> List[str]:
        """Copy images into <style>/refs/ downscaled to MAX_IMPORT_DIM JPEG.

        Appends relative paths to style.reference_images and returns them.
        Caller must save() afterwards. Unreadable files are skipped with a
        logged warning, never fatal.
        """
        from PIL import Image
        refs_dir = self.style_dir(style.id) / "refs"
        refs_dir.mkdir(parents=True, exist_ok=True)
        seq = len(style.reference_images)
        added: List[str] = []
        for src in paths:
            src = Path(src)
            try:
                with Image.open(src) as img:
                    img = img.convert("RGB")
                    img.thumbnail((MAX_IMPORT_DIM, MAX_IMPORT_DIM))
                    seq += 1
                    rel = f"refs/{seq:04d}.jpg"
                    img.save(refs_dir / f"{seq:04d}.jpg", "JPEG", quality=JPEG_QUALITY)
            except (OSError, ValueError) as e:
                logger.warning(f"Skipping unreadable image {src}: {e}")
                continue
            style.reference_images.append(rel)
            added.append(rel)
        logger.info(f"Added {len(added)} reference image(s) to style {style.id}")
        return added

    def remove_reference_image(self, style: Style, rel_path: str) -> None:
        p = self.style_dir(style.id) / rel_path
        if p.exists():
            p.unlink()
        style.reference_images = [r for r in style.reference_images if r != rel_path]
        style.exemplars = [r for r in style.exemplars if r != rel_path]

    def resolve_refs(self, style: Style, exemplars_only: bool = False) -> List[Path]:
        """Absolute paths of (existing) reference images, in stored order."""
        rels = style.exemplars if exemplars_only else style.reference_images
        base = self.style_dir(style.id)
        out = []
        for rel in rels:
            p = base / rel
            if p.exists():
                out.append(p)
            else:
                logger.warning(f"Style {style.id}: missing reference file {rel}")
        return out
```

Also update `core/styles/__init__.py`:

```python
"""Custom Styles: derive reusable styles from reference images, apply anywhere."""
from core.styles.models import DESCRIPTOR_KEYS, Style, StyleDescriptor
from core.styles.store import StyleStore

__all__ = ["DESCRIPTOR_KEYS", "Style", "StyleDescriptor", "StyleStore"]
```

- [ ] **Step 4: Run to verify pass**

Run: `$PY -m pytest tests/styles/test_store.py tests/styles/test_models.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/styles tests/styles
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): StyleStore CRUD with copied, downscaled reference images"
```

---

### Task 3: StyleStore zip export/import

**Files:**
- Modify: `core/styles/store.py`
- Test: `tests/styles/test_store_zip.py`

**Interfaces:**
- Consumes: Task 2's `StyleStore`.
- Produces: `StyleStore.export_zip(style_id, out_path) -> bool`; `StyleStore.import_zip(zip_path) -> Optional[Style]` (new id on collision; returns the imported `Style`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/styles/test_store_zip.py
"""Zip export/import round-trip for StyleStore."""
from pathlib import Path

from PIL import Image

from core.styles.models import Style
from core.styles.store import StyleStore


def _store_with_style(tmp_path, name="Zippy"):
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id(name), name=name, prompt_text="zip style")
    store.save(s)
    img = tmp_path / "img.png"
    Image.new("RGB", (32, 32), (0, 128, 0)).save(img)
    store.add_reference_images(s, [img])
    s.exemplars = list(s.reference_images)
    store.save(s)
    return store, s


def test_export_import_round_trip(tmp_path):
    store, s = _store_with_style(tmp_path)
    zip_path = tmp_path / "zippy.zip"
    assert store.export_zip(s.id, zip_path) is True
    assert zip_path.exists()

    other = StyleStore(base_dir=tmp_path / "other")
    imported = other.import_zip(zip_path)
    assert imported is not None
    assert imported.name == "Zippy"
    assert imported.prompt_text == "zip style"
    assert len(other.resolve_refs(imported)) == 1
    assert imported.exemplars == imported.reference_images


def test_import_collision_gets_new_id(tmp_path):
    store, s = _store_with_style(tmp_path)
    zip_path = tmp_path / "z.zip"
    store.export_zip(s.id, zip_path)
    imported = store.import_zip(zip_path)  # same store -> id collision
    assert imported.id == "zippy-2"
    assert store.get("zippy") is not None and store.get("zippy-2") is not None


def test_export_unknown_style_returns_false(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    assert store.export_zip("missing", tmp_path / "x.zip") is False


def test_import_bad_zip_returns_none(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    assert store.import_zip(bad) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest tests/styles/test_store_zip.py -v`
Expected: FAIL — `AttributeError: 'StyleStore' object has no attribute 'export_zip'`

- [ ] **Step 3: Implement** — append to `core/styles/store.py` (inside `StyleStore`):

```python
    # ---- zip export / import --------------------------------------------

    def export_zip(self, style_id: str, out_path: Path) -> bool:
        """Write <out_path> as a zip: style.json + refs/*. Shareable bundle."""
        import zipfile
        style = self.get(style_id)
        if style is None:
            logger.error(f"Cannot export unknown style: {style_id}")
            return False
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("style.json", json.dumps(style.to_dict(), indent=2,
                                                 ensure_ascii=False))
            for p in self.resolve_refs(style):
                zf.write(p, f"refs/{p.name}")
        logger.info(f"Exported style {style_id} to {out_path}")
        return True

    def import_zip(self, zip_path: Path) -> Optional[Style]:
        """Import a style zip; assigns a fresh id on collision."""
        import zipfile
        try:
            with zipfile.ZipFile(zip_path) as zf:
                data = json.loads(zf.read("style.json").decode("utf-8"))
                style = Style.from_dict(data)
                style.id = self.new_id(style.name)
                style.is_builtin = False
                refs_dir = self.style_dir(style.id) / "refs"
                refs_dir.mkdir(parents=True, exist_ok=True)
                for info in zf.infolist():
                    name = Path(info.filename).name
                    if info.filename.startswith("refs/") and name:
                        (refs_dir / name).write_bytes(zf.read(info))
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to import style zip {zip_path}: {e}")
            return None
        self.save(style)
        logger.info(f"Imported style '{style.name}' as {style.id}")
        return style
```

(Note the flattened `refs/{p.name}` in export matches `Path(info.filename).name` in import, so relative paths in the record — all `refs/NNNN.jpg` — stay valid.)

- [ ] **Step 4: Run to verify pass**

Run: `$PY -m pytest tests/styles/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/styles/store.py tests/styles/test_store_zip.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): zip export/import for sharing styles between machines"
```

### Task 4: Analyzer pure pipeline (`core/styles/analyzer.py`)

**Files:**
- Create: `core/styles/analyzer.py`
- Modify: `core/styles/__init__.py` (add `StyleAnalysisError`)
- Test: `tests/styles/test_analyzer.py`

**Interfaces:**
- Consumes: `DESCRIPTOR_KEYS` (Task 1); `LLMResponseParser` from `gui.llm_utils`; PIL.
- Produces: `ANALYZE_CHUNK_SIZE = 8`; `MAX_LLM_IMAGE_DIM = 1568`; `StyleAnalysisError(Exception)`; `chunk_paths(paths, size=ANALYZE_CHUNK_SIZE) -> List[List[Path]]`; `encode_image_for_llm(path) -> Tuple[str, str]` (mime, base64 — downscaled ≤ `MAX_LLM_IMAGE_DIM`); `build_chunk_messages(paths) -> List[dict]` (OpenAI content-parts, data-URI images); `parse_descriptor(content) -> Optional[dict]`; `flatten_descriptor(desc) -> str` (deterministic, ≤ 80 words); `merge_descriptors(descs, completion_fn) -> dict` (returned dict = descriptor keys + `"prompt_text"`); `derive_style_data(paths, vision_fn, completion_fn, progress_cb=None) -> dict` returning `{"descriptor": {...9 keys...}, "prompt_text": str}`. `vision_fn(messages) -> str` and `completion_fn(messages) -> str` are injected callables (Task 5 provides real ones).

- [ ] **Step 1: Write the failing tests**

```python
# tests/styles/test_analyzer.py
"""Tests for the pure (LLM-injected) style derivation pipeline."""
import json
from pathlib import Path

import pytest
from PIL import Image

from core.styles.analyzer import (
    ANALYZE_CHUNK_SIZE, MAX_LLM_IMAGE_DIM, StyleAnalysisError,
    build_chunk_messages, chunk_paths, derive_style_data,
    encode_image_for_llm, flatten_descriptor, merge_descriptors,
    parse_descriptor,
)
from core.styles.models import DESCRIPTOR_KEYS

DESC = {k: f"{k} value" for k in DESCRIPTOR_KEYS}


def _imgs(tmp_path, n, size=(64, 64)):
    out = []
    for i in range(n):
        p = tmp_path / f"img{i}.png"
        Image.new("RGB", size, (i * 10 % 255, 80, 80)).save(p)
        out.append(p)
    return out


def test_chunk_paths():
    paths = [Path(f"{i}.png") for i in range(20)]
    chunks = chunk_paths(paths)
    assert [len(c) for c in chunks] == [8, 8, 4]
    assert chunk_paths(paths[:8]) == [paths[:8]]
    assert chunk_paths([]) == []


def test_encode_image_downscales(tmp_path):
    (p,) = _imgs(tmp_path, 1, size=(4000, 500))
    mime, b64 = encode_image_for_llm(p)
    assert mime == "image/jpeg"
    import base64, io
    with Image.open(io.BytesIO(base64.b64decode(b64))) as img:
        assert max(img.size) <= MAX_LLM_IMAGE_DIM


def test_build_chunk_messages_shape(tmp_path):
    paths = _imgs(tmp_path, 2)
    messages = build_chunk_messages(paths)
    assert len(messages) == 1 and messages[0]["role"] == "user"
    parts = messages[0]["content"]
    assert parts[0]["type"] == "text"
    assert "JSON" in parts[0]["text"]
    assert "aspect" in parts[0]["text"].lower()  # forbids ratio tokens
    images = [p for p in parts if p.get("type") == "image_url"]
    assert len(images) == 2
    assert images[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_parse_descriptor_fenced_and_filtered():
    fenced = "```json\n" + json.dumps({**DESC, "extra": "x"}) + "\n```"
    d = parse_descriptor(fenced)
    assert d is not None and set(d.keys()) == set(DESCRIPTOR_KEYS)
    assert parse_descriptor("not json at all") is None
    assert parse_descriptor("") is None


def test_flatten_descriptor_caps_words():
    desc = dict(DESC)
    desc["summary"] = "word " * 200
    text = flatten_descriptor(desc)
    assert 0 < len(text.split()) <= 80
    assert "negative value" not in text  # negative excluded from prompt text


def test_merge_single_descriptor_skips_llm():
    calls = []
    def completion_fn(messages):
        calls.append(messages)
        return "{}"
    merged = merge_descriptors([DESC], completion_fn)
    assert calls == []  # single chunk: no reduce call
    assert merged["summary"] == DESC["summary"]
    assert merged["prompt_text"] == flatten_descriptor(DESC)


def test_merge_multiple_uses_llm():
    reply = json.dumps({**DESC, "prompt_text": "merged style text"})
    merged = merge_descriptors([DESC, DESC], lambda m: reply)
    assert merged["prompt_text"] == "merged style text"


def test_merge_multiple_llm_garbage_falls_back():
    merged = merge_descriptors([DESC, dict(DESC)], lambda m: "garbage")
    # fallback: first descriptor + deterministic flatten
    assert merged["summary"] == DESC["summary"]
    assert merged["prompt_text"] == flatten_descriptor(DESC)


def test_derive_style_data_two_chunks(tmp_path):
    paths = _imgs(tmp_path, ANALYZE_CHUNK_SIZE + 1)  # -> 2 chunks
    vision_calls = []
    def vision_fn(messages):
        vision_calls.append(messages)
        return json.dumps(DESC)
    def completion_fn(messages):
        return json.dumps({**DESC, "prompt_text": "final text"})
    progress = []
    result = derive_style_data(paths, vision_fn, completion_fn,
                               progress_cb=progress.append)
    assert len(vision_calls) == 2
    assert result["prompt_text"] == "final text"
    assert set(result["descriptor"].keys()) == set(DESCRIPTOR_KEYS)
    assert any("chunk" in p.lower() for p in progress)


def test_derive_style_data_unparseable_chunk_raises(tmp_path):
    paths = _imgs(tmp_path, 2)
    with pytest.raises(StyleAnalysisError):
        derive_style_data(paths, lambda m: "not json", lambda m: "{}")


def test_derive_style_data_no_paths_raises(tmp_path):
    with pytest.raises(StyleAnalysisError):
        derive_style_data([], lambda m: "{}", lambda m: "{}")
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest tests/styles/test_analyzer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.styles.analyzer'`

- [ ] **Step 3: Implement**

```python
# core/styles/analyzer.py
"""Derive a style from N reference images (map-reduce over vision LLM calls).

Pure pipeline: derive_style_data() takes injected callables so tests and the
GUI/CLI transports share one code path. Real transports live in Task 5's
StyleAnalysisService/build_completion_fn below.
Extraction prompt extends core/video/style_analyzer.py:71-89 (style, NOT
content) to N images + structured JSON.
"""
import base64
import io
import json
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core.styles.models import DESCRIPTOR_KEYS

logger = logging.getLogger(__name__)

ANALYZE_CHUNK_SIZE = 8
MAX_LLM_IMAGE_DIM = 1568  # Anthropic's hard cap; safe for all providers

_JSON_SHAPE = ", ".join(f'"{k}": "..."' for k in DESCRIPTOR_KEYS)

CHUNK_PROMPT = f"""Analyze these images TOGETHER and extract ONLY the visual style they SHARE, for replicating in new scenes.

CRITICAL - Identify the rendering/artistic style FIRST:
- Is it: photorealistic, 3D render, cartoon/animated, anime, hand-drawn, painterly, sketch, etc.?
- If animated/cartoon: what animation style? (Disney, anime, flat colors, cel-shaded, etc.)

Then describe the shared style elements:
- Lighting: direction, quality, color temperature, shadows
- Color palette: dominant colors, saturation level, contrast
- Composition: framing, camera angle, perspective tendencies
- Texture/detail level: smooth, detailed, stylized, etc.
- Line work: bold outlines, soft edges, clean lines, sketchy, etc.
- Mood and atmosphere
- Negative: anything to AVOID to stay on-style (or "")

Do NOT describe the content/subjects of the images, only the style.
Do NOT mention image dimensions, pixel sizes, or aspect ratios anywhere.

Return ONLY a JSON object (no prose, no markdown) with exactly these keys:
{{{_JSON_SHAPE}}}"""

MERGE_PROMPT = """You are merging style analyses of several batches of images from ONE visual style.

<chunk_descriptors>
{chunks_json}
</chunk_descriptors>

<instructions>
Merge them into one canonical style description. Resolve disagreements toward
the majority; keep only what the batches share. Do NOT mention image
dimensions, pixel sizes, or aspect ratios. Also write "prompt_text": a single
60-80 word style instruction (no subject/content words) suitable for appending
to any image prompt.
Return ONLY a JSON object with exactly these keys:
{{{json_shape}, "prompt_text": "..."}}
</instructions>"""

SMART_MERGE_NOTE = None  # smart merge lives in applicator.py (Task 6)


class StyleAnalysisError(Exception):
    """Style derivation failed; message is user-facing."""


def chunk_paths(paths: List[Path], size: int = ANALYZE_CHUNK_SIZE) -> List[List[Path]]:
    paths = list(paths)
    return [paths[i:i + size] for i in range(0, len(paths), size)]


def encode_image_for_llm(path: Path) -> Tuple[str, str]:
    """Downscale to MAX_LLM_IMAGE_DIM and return ("image/jpeg", base64 str)."""
    from PIL import Image
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_LLM_IMAGE_DIM, MAX_LLM_IMAGE_DIM))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
    return "image/jpeg", base64.b64encode(buf.getvalue()).decode("utf-8")


def build_chunk_messages(paths: List[Path]) -> List[Dict]:
    """One user message: CHUNK_PROMPT + each image as a data-URI part."""
    parts: List[Dict] = [{"type": "text", "text": CHUNK_PROMPT}]
    for p in paths:
        mime, b64 = encode_image_for_llm(p)
        parts.append({"type": "image_url",
                      "image_url": {"url": f"data:{mime};base64,{b64}"}})
    return [{"role": "user", "content": parts}]


def parse_descriptor(content: str) -> Optional[Dict[str, str]]:
    """Parse an LLM reply into a descriptor dict (keys filtered/defaulted)."""
    from gui.llm_utils import LLMResponseParser
    data = LLMResponseParser.parse_json_response(content or "", expected_type=dict)
    if not isinstance(data, dict):
        return None
    return {k: str(data.get(k) or "") for k in DESCRIPTOR_KEYS}


def flatten_descriptor(desc: Dict[str, str], max_words: int = 80) -> str:
    """Deterministic prompt_text: summary + non-empty fields (negative excluded)."""
    parts = [desc.get("summary", "").strip()]
    for k in ("medium", "palette", "lighting", "composition", "texture",
              "line_work", "mood"):
        v = (desc.get(k) or "").strip()
        if v:
            parts.append(v)
    words = " ".join(p.rstrip(".") + "." for p in parts if p).split()
    return " ".join(words[:max_words])


def merge_descriptors(descs: List[Dict[str, str]],
                      completion_fn: Callable[[List[Dict]], str]) -> Dict[str, str]:
    """Reduce chunk descriptors to one descriptor + prompt_text.

    Single chunk: no LLM call — flatten deterministically (spec §4 step 3).
    Multi chunk: one text-only LLM call; on unparseable reply fall back to the
    first descriptor + deterministic flatten (logged).
    """
    if not descs:
        raise StyleAnalysisError("No descriptors to merge")
    if len(descs) == 1:
        return {**descs[0], "prompt_text": flatten_descriptor(descs[0])}

    prompt = MERGE_PROMPT.format(chunks_json=json.dumps(descs, indent=2),
                                 json_shape=_JSON_SHAPE)
    logger.info(f"Style merge request over {len(descs)} chunk descriptors")
    try:
        reply = completion_fn([{"role": "user", "content": prompt}])
        logger.info(f"Style merge response ({len(reply or '')} chars): {reply}")
        from gui.llm_utils import LLMResponseParser
        data = LLMResponseParser.parse_json_response(reply or "", expected_type=dict)
    except Exception as e:  # noqa: BLE001 - fall back, never crash the reduce
        logger.warning(f"Style merge LLM call failed: {e}")
        data = None
    if isinstance(data, dict):
        merged = {k: str(data.get(k) or "") for k in DESCRIPTOR_KEYS}
        pt = str(data.get("prompt_text") or "").strip()
        merged["prompt_text"] = pt or flatten_descriptor(merged)
        return merged
    logger.warning("Style merge reply unparseable; using first chunk + flatten")
    return {**descs[0], "prompt_text": flatten_descriptor(descs[0])}


def derive_style_data(paths: List[Path],
                      vision_fn: Callable[[List[Dict]], str],
                      completion_fn: Callable[[List[Dict]], str],
                      progress_cb: Optional[Callable[[str], None]] = None) -> Dict:
    """Map-reduce: chunks of images -> descriptors -> one merged style.

    Returns {"descriptor": {<9 keys>}, "prompt_text": str}.
    Raises StyleAnalysisError on empty input or an unparseable chunk (no
    half-derived styles — spec §8).
    """
    def emit(msg: str) -> None:
        logger.info(msg)
        if progress_cb:
            progress_cb(msg)

    paths = [Path(p) for p in paths]
    if not paths:
        raise StyleAnalysisError("No images supplied for style analysis")

    chunks = chunk_paths(paths)
    descs: List[Dict[str, str]] = []
    for i, chunk in enumerate(chunks, start=1):
        emit(f"Analyzing chunk {i}/{len(chunks)} ({len(chunk)} image(s))...")
        messages = build_chunk_messages(chunk)
        reply = vision_fn(messages)
        logger.info(f"Style chunk {i} response ({len(reply or '')} chars): {reply}")
        desc = parse_descriptor(reply)
        if desc is None:
            raise StyleAnalysisError(
                f"Could not parse style analysis for chunk {i}/{len(chunks)}; "
                f"no style was saved. Raw reply logged.")
        descs.append(desc)

    if len(descs) > 1:
        emit(f"Merging {len(descs)} chunk analyses...")
    merged = merge_descriptors(descs, completion_fn)
    prompt_text = merged.pop("prompt_text")
    emit("Style analysis complete.")
    return {"descriptor": merged, "prompt_text": prompt_text}
```

Update `core/styles/__init__.py` imports:

```python
from core.styles.analyzer import StyleAnalysisError
```
and add `"StyleAnalysisError"` to `__all__`.

- [ ] **Step 4: Run to verify pass**

Run: `$PY -m pytest tests/styles/test_analyzer.py -v`
Expected: 11 PASS (note: `gui.llm_utils` imports PySide6 — available in `.venv_linux`; no display needed for these imports)

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/styles tests/styles/test_analyzer.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): map-reduce style derivation pipeline (LLM-injected, pure)"
```

---

### Task 5: Analyzer transport (`StyleAnalysisService`, `build_completion_fn`)

**Files:**
- Modify: `core/styles/analyzer.py` (append)
- Test: `tests/styles/test_analyzer_service.py`

**Interfaces:**
- Consumes: Task 4's pure pipeline; `UnifiedLLMProvider` (`core/video/prompt_engine.py:62`); `resolve_model` / `get_provider_prefix` (`core/llm_models.py`); `ConfigManager.get_api_key`.
- Produces:
  - `normalize_llm_provider(provider) -> str` — maps `google|gemini -> "google"`, `anthropic|claude -> "anthropic"`, else `"openai"`.
  - `default_vision_model(provider) -> str` — registry-resolved (same spec table as `core/video/style_analyzer.py:41`).
  - `build_completion_fn(config, provider=None, model=None) -> Tuple[Callable, str, str]` — returns `(fn, provider, full_model)`; `fn(messages) -> str` goes through `UnifiedLLMProvider.analyze_image`. Raises `StyleAnalysisError` with an actionable message when no API key is configured. `config` is a `ConfigManager`.
  - `StyleAnalysisService(config, provider=None, model=None)` with `.provider`, `.model`, and `derive(paths, progress_cb=None) -> dict` (wires `derive_style_data`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/styles/test_analyzer_service.py
"""Transport-layer tests with UnifiedLLMProvider mocked out."""
import json
from unittest.mock import patch

import pytest
from PIL import Image

from core.styles.analyzer import (
    StyleAnalysisError, StyleAnalysisService, build_completion_fn,
    default_vision_model, normalize_llm_provider,
)
from core.styles.models import DESCRIPTOR_KEYS

DESC_JSON = json.dumps({k: "v" for k in DESCRIPTOR_KEYS})


class FakeConfig:
    def __init__(self, keys=None):
        self._keys = keys or {}
    def get_api_key(self, provider):
        return self._keys.get(provider)
    def get(self, key, default=None):
        return default


def test_normalize_llm_provider():
    assert normalize_llm_provider("gemini") == "google"
    assert normalize_llm_provider("claude") == "anthropic"
    assert normalize_llm_provider("OpenAI") == "openai"
    assert normalize_llm_provider(None) == "openai"


def test_default_vision_model_uses_registry():
    with patch("core.llm_models.resolve_model", return_value="resolved-x") as rm:
        assert default_vision_model("openai") == "resolved-x"
        assert rm.call_args.args[0] == "openai"


def test_build_completion_fn_requires_key():
    with pytest.raises(StyleAnalysisError, match="API key"):
        build_completion_fn(FakeConfig(), provider="openai")


def test_build_completion_fn_calls_unified_provider():
    cfg = FakeConfig({"openai": "sk-test"})
    with patch("core.video.prompt_engine.UnifiedLLMProvider") as MockLLM:
        MockLLM.return_value.analyze_image.return_value = "reply"
        fn, provider, model = build_completion_fn(cfg, provider="openai",
                                                  model="test-model")
        out = fn([{"role": "user", "content": "hi"}])
    assert out == "reply"
    assert provider == "openai"
    assert model == "test-model"  # openai prefix is ''
    assert MockLLM.call_args.args[0] == {"openai_api_key": "sk-test"}


def test_service_derive_end_to_end(tmp_path):
    img = tmp_path / "a.png"
    Image.new("RGB", (32, 32), (10, 10, 10)).save(img)
    cfg = FakeConfig({"openai": "sk-test"})
    with patch("core.video.prompt_engine.UnifiedLLMProvider") as MockLLM:
        MockLLM.return_value.analyze_image.return_value = DESC_JSON
        svc = StyleAnalysisService(cfg, provider="openai", model="test-model")
        result = svc.derive([img])
    assert result["prompt_text"]  # deterministic flatten of the single chunk
    assert set(result["descriptor"].keys()) == set(DESCRIPTOR_KEYS)
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest tests/styles/test_analyzer_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'StyleAnalysisService'`

- [ ] **Step 3: Implement** — append to `core/styles/analyzer.py`:

```python
# ---- transport (real LLM wiring) ----------------------------------------

_PROVIDER_SPECS = {
    # app provider -> (registry provider, family, static fallback, config-key name)
    "google": ("gemini", "pro", "gemini-2.5-pro", "google_api_key"),
    "openai": ("openai", "gpt", "gpt-4o", "openai_api_key"),
    "anthropic": ("anthropic", "sonnet", "claude-sonnet-4-6", "anthropic_api_key"),
}


def normalize_llm_provider(provider) -> str:
    p = (provider or "").strip().lower()
    if p in ("google", "gemini"):
        return "google"
    if p in ("anthropic", "claude"):
        return "anthropic"
    return "openai"


def default_vision_model(provider: str) -> str:
    from core.llm_models import resolve_model
    reg, family, static, _ = _PROVIDER_SPECS[normalize_llm_provider(provider)]
    return resolve_model(reg, family, static_default=static)


def build_completion_fn(config, provider=None, model=None):
    """Build an LLM callable over UnifiedLLMProvider.

    Args:
        config: ConfigManager (uses get_api_key / get).
        provider: openai|anthropic|google (default: config 'llm_provider',
            else openai).
        model: bare model id (default: registry vision default).

    Returns:
        (fn, provider, full_model) where fn(messages) -> str.

    Raises:
        StyleAnalysisError: when no API key is configured for the provider.
    """
    provider = normalize_llm_provider(provider or config.get("llm_provider", None))
    reg, _family, _static, cfg_key = _PROVIDER_SPECS[provider]
    api_key = config.get_api_key(provider)
    if not api_key:
        raise StyleAnalysisError(
            f"No {provider} API key configured. Set one in Settings (GUI) or "
            f"with --set-key --provider {provider} (CLI) before creating a style.")
    model = model or default_vision_model(provider)
    from core.llm_models import get_provider_prefix
    prefix = get_provider_prefix(reg) or ""
    full_model = model if model.startswith(prefix) else f"{prefix}{model}"

    from core.video.prompt_engine import UnifiedLLMProvider
    llm = UnifiedLLMProvider({cfg_key: api_key})

    def fn(messages):
        logger.info(f"Style LLM request -> {full_model} "
                    f"({sum(len(str(m)) for m in messages)} chars)")
        return llm.analyze_image(messages=messages, model=full_model,
                                 max_tokens=1500)

    return fn, provider, full_model


class StyleAnalysisService:
    """Real-transport wrapper: derive a style from image paths."""

    def __init__(self, config, provider=None, model=None):
        self._fn, self.provider, self.model = build_completion_fn(
            config, provider=provider, model=model)

    def derive(self, paths, progress_cb=None) -> Dict:
        """Run the map-reduce; both map (vision) and reduce (text) share
        the same UnifiedLLMProvider callable (it accepts either message
        shape). Raises StyleAnalysisError per derive_style_data."""
        return derive_style_data(paths, vision_fn=self._fn,
                                 completion_fn=self._fn,
                                 progress_cb=progress_cb)
```

- [ ] **Step 4: Run to verify pass**

Run: `$PY -m pytest tests/styles/test_analyzer_service.py tests/styles/test_analyzer.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/styles/analyzer.py tests/styles/test_analyzer_service.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): LLM transport for style derivation via UnifiedLLMProvider"
```

---

### Task 6: Applicator (`core/styles/applicator.py`)

**Files:**
- Create: `core/styles/applicator.py`
- Modify: `core/styles/__init__.py` (add `apply_style`, `StyledRequest`, `style_ref_limit`)
- Test: `tests/styles/test_applicator.py`

**Interfaces:**
- Consumes: `Style` (Task 1); `LLMResponseParser`.
- Produces:
  - `StyledRequest` dataclass: `prompt: str`, `extra_kwargs: dict`, `meta: dict` (meta keys: `style_id`, `style_name`, `smart_merge_used: bool`, `exemplars_attached: int`, `exemplars_dropped: int`).
  - `style_ref_limit(provider, model) -> int` — Google image models per `MODEL_REF_LIMITS` (`gui/imagen_reference_widget.py:449`; numbers duplicated here because core must not import gui), OpenAI gpt-image family 10, everything else 0.
  - `apply_style(prompt, style, provider, model, *, smart=False, completion_fn=None, exemplar_paths=None, existing_references=None) -> StyledRequest`. Callers in Tasks 10/14/15/16 use exactly this signature.

- [ ] **Step 1: Write the failing tests**

```python
# tests/styles/test_applicator.py
"""Application matrix: placement x smart x provider ref limits."""
import json

from core.styles.applicator import StyledRequest, apply_style, style_ref_limit
from core.styles.models import Style, StyleDescriptor


def _style(**over):
    base = dict(id="s1", name="S1", prompt_text="bold watercolor washes",
                descriptor=StyleDescriptor(summary="watercolor"))
    base.update(over)
    return Style(**base)


def _exemplars(tmp_path, n):
    out = []
    for i in range(n):
        p = tmp_path / f"e{i}.jpg"
        p.write_bytes(b"JPEGDATA" + bytes([i]))
        out.append(p)
    return out


def test_ref_limits():
    assert style_ref_limit("google", "gemini-2.5-flash-image") == 5
    assert style_ref_limit("google", "gemini-3.1-flash-image-preview") == 8
    assert style_ref_limit("google", "gemini-3-pro-image-preview") == 14
    assert style_ref_limit("google", "imagen-4") == 3          # google default
    assert style_ref_limit("openai", "gpt-image-2") == 10
    assert style_ref_limit("openai", "gpt-image-1.5") == 10
    assert style_ref_limit("openai", "dall-e-3") == 0
    assert style_ref_limit("stability", "sd3") == 0
    assert style_ref_limit("local_sd", "any") == 0
    assert style_ref_limit("", "") == 0


def test_plain_suffix_default():
    res = apply_style("a red fox", _style(), "stability", "sd3")
    assert isinstance(res, StyledRequest)
    assert res.prompt == "a red fox. In this style: bold watercolor washes"
    assert res.extra_kwargs == {}
    assert res.meta["smart_merge_used"] is False
    assert res.meta["style_id"] == "s1"


def test_plain_prefix():
    res = apply_style("a red fox", _style(placement="prefix"), "stability", "sd3")
    assert res.prompt == "In this style: bold watercolor washes. a red fox"


def test_empty_prompt_text_leaves_prompt_alone():
    res = apply_style("a red fox", _style(prompt_text="  "), "openai", "dall-e-3")
    assert res.prompt == "a red fox"


def test_smart_merge_success():
    reply = json.dumps({"prompt": "a red fox rendered in bold watercolor"})
    res = apply_style("a red fox", _style(), "openai", "dall-e-3",
                      smart=True, completion_fn=lambda m: reply)
    assert res.prompt == "a red fox rendered in bold watercolor"
    assert res.meta["smart_merge_used"] is True


def test_smart_merge_failure_falls_back_to_plain():
    def boom(messages):
        raise RuntimeError("llm down")
    res = apply_style("a red fox", _style(), "openai", "dall-e-3",
                      smart=True, completion_fn=boom)
    assert res.prompt == "a red fox. In this style: bold watercolor washes"
    assert res.meta["smart_merge_used"] is False


def test_smart_without_completion_fn_is_plain():
    res = apply_style("a red fox", _style(), "openai", "dall-e-3", smart=True)
    assert res.meta["smart_merge_used"] is False


def test_exemplars_attached_within_limit(tmp_path):
    ex = _exemplars(tmp_path, 3)
    res = apply_style("a red fox", _style(), "google", "gemini-2.5-flash-image",
                      exemplar_paths=ex)
    assert res.meta["exemplars_attached"] == 3
    assert len(res.extra_kwargs["reference_images"]) == 3
    assert res.extra_kwargs["reference_images"][0] == ex[0].read_bytes()


def test_user_references_take_priority(tmp_path):
    ex = _exemplars(tmp_path, 3)
    user_refs = [b"USER1", b"USER2", b"USER3", b"USER4"]  # limit 5 -> 1 slot
    res = apply_style("a red fox", _style(), "google", "gemini-2.5-flash-image",
                      exemplar_paths=ex, existing_references=user_refs)
    refs = res.extra_kwargs["reference_images"]
    assert refs[:4] == user_refs
    assert len(refs) == 5
    assert res.meta["exemplars_attached"] == 1
    assert res.meta["exemplars_dropped"] == 2


def test_no_slots_no_extra_kwargs(tmp_path):
    ex = _exemplars(tmp_path, 2)
    user_refs = [b"U"] * 5
    res = apply_style("a red fox", _style(), "google", "gemini-2.5-flash-image",
                      exemplar_paths=ex, existing_references=user_refs)
    assert "reference_images" not in res.extra_kwargs
    assert res.meta["exemplars_attached"] == 0
    assert res.meta["exemplars_dropped"] == 2


def test_missing_exemplar_files_degrade_to_text(tmp_path):
    ghost = tmp_path / "gone.jpg"  # never created
    res = apply_style("a red fox", _style(), "google", "gemini-2.5-flash-image",
                      exemplar_paths=[ghost])
    assert "reference_images" not in res.extra_kwargs
    assert res.meta["exemplars_attached"] == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest tests/styles/test_applicator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.styles.applicator'`

- [ ] **Step 3: Implement**

```python
# core/styles/applicator.py
"""Apply a saved style to a generation request.

One function, four seams (GUI image gen, CLI image gen, video scenes, layout
fill). Plain concat is the default; smart merge is opt-in and can never fail
a generation (falls back to plain with a logged warning). Providers that
accept multiple reference images additionally get the style's exemplars,
user references first. Spec: Plans/2026-07-26-custom-styles-design.md §5.
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.styles.models import Style

logger = logging.getLogger(__name__)

# Mirrors gui/imagen_reference_widget.py:449 MODEL_REF_LIMITS (core must not
# import gui). Update both together if a model's limit changes.
GOOGLE_REF_LIMITS = {
    "gemini-2.5-flash-image": 5,
    "gemini-3.1-flash-image-preview": 8,
    "gemini-3-pro-image-preview": 14,
}
GOOGLE_DEFAULT_REF_LIMIT = 3
OPENAI_REF_LIMIT = 10
_OPENAI_IMAGE_MODEL_PREFIXES = ("gpt-image-",)  # gpt-image-1/1.5/1-mini/2

SMART_MERGE_PROMPT = """<user_prompt>
{prompt}
</user_prompt>

<style>
{descriptor_json}
</style>

<instructions>
Rewrite the user prompt as ONE image-generation prompt that fully adopts the
style above. Keep every subject/content element of the user prompt; express
the style through concrete visual language; resolve conflicts in favor of the
style (e.g. "photograph" becomes the style's rendering instead). 2-4
sentences. Do NOT mention image dimensions, pixel sizes, or aspect ratios.
Return JSON: {{"prompt": "..."}}
</instructions>"""


@dataclass
class StyledRequest:
    prompt: str
    extra_kwargs: Dict = field(default_factory=dict)
    meta: Dict = field(default_factory=dict)


def style_ref_limit(provider: str, model: str) -> int:
    """How many total reference images this provider/model accepts (0 = none)."""
    provider = (provider or "").strip().lower()
    model = (model or "").strip()
    if provider == "google":
        return GOOGLE_REF_LIMITS.get(model, GOOGLE_DEFAULT_REF_LIMIT)
    if provider == "openai":
        if any(model.startswith(p) for p in _OPENAI_IMAGE_MODEL_PREFIXES):
            return OPENAI_REF_LIMIT
        return 0
    return 0  # stability (img2img only), local_sd, video, layout, unknown


def _plain_apply(prompt: str, style: Style) -> str:
    text = (style.prompt_text or "").strip()
    if not text:
        return prompt
    if style.placement == "prefix":
        return f"In this style: {text}. {prompt}"
    return f"{prompt}. In this style: {text}"


def _smart_merge(prompt: str, style: Style,
                 completion_fn: Callable[[List[Dict]], str]) -> Optional[str]:
    """One LLM call to fuse prompt + descriptor. None on any failure."""
    payload = SMART_MERGE_PROMPT.format(
        prompt=prompt,
        descriptor_json=json.dumps(
            {**style.descriptor.to_dict(), "prompt_text": style.prompt_text},
            indent=2))
    try:
        logger.info(f"Smart-merge request for style '{style.name}'")
        reply = completion_fn([{"role": "user", "content": payload}])
        logger.info(f"Smart-merge response ({len(reply or '')} chars): {reply}")
        from gui.llm_utils import LLMResponseParser
        data = LLMResponseParser.parse_json_response(reply or "", expected_type=dict)
        if isinstance(data, dict):
            merged = str(data.get("prompt") or "").strip()
            if merged:
                return merged
    except Exception as e:  # noqa: BLE001 - smart merge must never block generation
        logger.warning(f"Smart merge failed ({e}); falling back to plain concat")
        return None
    logger.warning("Smart merge reply unusable; falling back to plain concat")
    return None


def apply_style(prompt: str, style: Style, provider: str, model: str, *,
                smart: bool = False,
                completion_fn: Optional[Callable[[List[Dict]], str]] = None,
                exemplar_paths: Optional[List[Path]] = None,
                existing_references: Optional[List[bytes]] = None) -> StyledRequest:
    """Apply `style` to `prompt` for the given provider/model.

    Returns StyledRequest(prompt, extra_kwargs, meta). extra_kwargs contains a
    merged "reference_images" list (existing user refs first, then exemplar
    bytes) ONLY when at least one exemplar was attached — callers replace
    their kwargs entry with it in that case and leave kwargs untouched
    otherwise.
    """
    meta = {"style_id": style.id, "style_name": style.name,
            "smart_merge_used": False, "exemplars_attached": 0,
            "exemplars_dropped": 0}

    styled = None
    if smart and completion_fn is not None:
        styled = _smart_merge(prompt, style, completion_fn)
        meta["smart_merge_used"] = styled is not None
    if styled is None:
        styled = _plain_apply(prompt, style)

    extra: Dict = {}
    wanted = [Path(p) for p in (exemplar_paths or [])]
    available = [p for p in wanted if p.exists()]
    for p in set(wanted) - set(available):
        logger.warning(f"Style '{style.name}': exemplar missing on disk: {p}")
    limit = style_ref_limit(provider, model)
    if limit and available:
        existing = list(existing_references or [])
        slots = max(0, limit - len(existing))
        attach = available[:slots]
        meta["exemplars_attached"] = len(attach)
        meta["exemplars_dropped"] = len(available) - len(attach)
        if meta["exemplars_dropped"]:
            logger.warning(
                f"Style '{style.name}': dropped {meta['exemplars_dropped']} "
                f"exemplar(s) over the {provider}/{model} limit of {limit}")
        if attach:
            extra["reference_images"] = existing + [p.read_bytes() for p in attach]
    elif available:
        logger.info(f"Style '{style.name}': {provider}/{model} takes no style "
                    f"references; applying text only")

    return StyledRequest(prompt=styled, extra_kwargs=extra, meta=meta)
```

Update `core/styles/__init__.py` (final form):

```python
"""Custom Styles: derive reusable styles from reference images, apply anywhere."""
from core.styles.models import DESCRIPTOR_KEYS, Style, StyleDescriptor
from core.styles.store import StyleStore
from core.styles.analyzer import StyleAnalysisError
from core.styles.applicator import StyledRequest, apply_style, style_ref_limit

__all__ = ["DESCRIPTOR_KEYS", "Style", "StyleDescriptor", "StyleStore",
           "StyleAnalysisError", "StyledRequest", "apply_style",
           "style_ref_limit"]
```

- [ ] **Step 4: Run to verify pass**

Run: `$PY -m pytest tests/styles/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/styles tests/styles/test_applicator.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): apply_style with smart-merge fallback and exemplar ref merging"
```

### Task 7: CLI parser group + dispatch + list/show/delete

**Files:**
- Modify: `cli/parser.py` (new group after the "video generation" group, before "help"), `cli/runner.py` (dispatch after the `--video` block at `cli/runner.py:230-232`)
- Create: `cli/commands/style.py`
- Test: `tests/styles/test_cli_style_parser.py`, `tests/styles/test_cli_style_dispatch.py`

**Interfaces:**
- Consumes: `StyleStore`, `Style` (Tasks 1–2); house CLI pattern from `cli/commands/video.py:12-24`.
- Produces: `run_style_cmd(args, config) -> int` in `cli/commands/style.py` (exit 0 ok, 2 user error, 3 runtime failure); `StyleCliError`; `_emit(msg)`; parser flags `--style`, `--style-smart`, `--style-create`, `--style-images`, `--style-llm-provider`, `--style-llm-model`, `--style-list`, `--style-show`, `--style-delete`, `--style-export`, `--style-import`. Tasks 8–9 extend `run_style_cmd`; Task 10 uses `--style`/`--style-smart`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/styles/test_cli_style_parser.py
"""Parser accepts the styles argument group."""
from cli.parser import build_arg_parser


def test_style_flags_parse():
    p = build_arg_parser()
    args = p.parse_args([
        "--style-create", "Water", "--style-images", "a.png", "imgs/",
        "--style-llm-provider", "openai", "--style-llm-model", "m",
    ])
    assert args.style_create == "Water"
    assert args.style_images == ["a.png", "imgs/"]
    assert args.style_llm_provider == "openai"
    assert args.style_llm_model == "m"


def test_style_use_flags_parse():
    p = build_arg_parser()
    args = p.parse_args(["-p", "a fox", "--style", "Water", "--style-smart"])
    assert args.style == "Water" and args.style_smart is True


def test_style_management_flags_parse():
    p = build_arg_parser()
    assert p.parse_args(["--style-list"]).style_list is True
    assert p.parse_args(["--style-show", "w"]).style_show == "w"
    assert p.parse_args(["--style-delete", "w"]).style_delete == "w"
    assert p.parse_args(["--style-export", "w", "-o", "w.zip"]).style_export == "w"
    assert p.parse_args(["--style-import", "w.zip"]).style_import == "w.zip"


def test_style_defaults_are_none_or_false():
    args = build_arg_parser().parse_args(["-p", "x"])
    assert args.style is None and args.style_smart is False
    assert args.style_create is None and args.style_list is False
```

```python
# tests/styles/test_cli_style_dispatch.py
"""run_cli routes style verbs to run_style_cmd; verbs work against a real store."""
from types import SimpleNamespace
from unittest.mock import patch

from cli.parser import build_arg_parser
from cli.runner import run_cli
from core.styles.models import Style
from core.styles.store import StyleStore


def _args(*argv):
    return build_arg_parser().parse_args(list(argv))


def test_run_cli_dispatches_to_style_cmd():
    with patch("cli.commands.style.run_style_cmd", return_value=0) as cmd:
        assert run_cli(_args("--style-list")) == 0
    cmd.assert_called_once()


def test_list_show_delete(tmp_path, capsys):
    from cli.commands.style import run_style_cmd
    store = StyleStore(base_dir=tmp_path / "styles")
    store.save(Style(id="water", name="Water", prompt_text="washes"))
    config = SimpleNamespace()  # unused by these verbs

    with patch("cli.commands.style.StyleStore", return_value=store):
        assert run_style_cmd(_args("--style-list"), config) == 0
        out = capsys.readouterr().out
        assert "water" in out and "Water" in out

        assert run_style_cmd(_args("--style-show", "Water"), config) == 0
        assert "washes" in capsys.readouterr().out

        assert run_style_cmd(_args("--style-show", "nope"), config) == 2
        assert run_style_cmd(_args("--style-delete", "water"), config) == 0
        assert store.get("water") is None
        assert run_style_cmd(_args("--style-delete", "water"), config) == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest tests/styles/test_cli_style_parser.py tests/styles/test_cli_style_dispatch.py -v`
Expected: FAIL — `unrecognized arguments: --style-create` etc.

- [ ] **Step 3: Implement**

In `cli/parser.py`, after the video group (`:231-289`) and before the "help" group, add:

```python
    # Styles (custom styles derived from reference images)
    g_styles = p.add_argument_group("styles")
    g_styles.add_argument("--style", metavar="NAME", default=None,
                          help="Apply a saved style to this generation "
                               "(works with -p, --video, --layout-fill)")
    g_styles.add_argument("--style-smart", action="store_true",
                          help="Fuse prompt and style with the configured LLM "
                               "(falls back to plain concat on failure)")
    g_styles.add_argument("--style-create", metavar="NAME", default=None,
                          help="Create a style from images (needs --style-images)")
    g_styles.add_argument("--style-images", nargs="+", metavar="PATH", default=None,
                          help="Images for --style-create: files, dirs, or globs")
    g_styles.add_argument("--style-llm-provider", default=None,
                          choices=["openai", "anthropic", "google"],
                          help="Vision LLM for --style-create (default: configured LLM)")
    g_styles.add_argument("--style-llm-model", default=None,
                          help="Vision model id for --style-create (default: registry)")
    g_styles.add_argument("--style-list", action="store_true",
                          help="List saved styles")
    g_styles.add_argument("--style-show", metavar="NAME", default=None,
                          help="Show one style's full record")
    g_styles.add_argument("--style-delete", metavar="NAME", default=None,
                          help="Delete a style")
    g_styles.add_argument("--style-export", metavar="NAME", default=None,
                          help="Export a style to a zip (use -o FILE.zip)")
    g_styles.add_argument("--style-import", metavar="FILE", default=None,
                          help="Import a style zip")
```

In `cli/runner.py`, directly after the `--video` block (`:230-232`), add:

```python
    # Handle style management verbs
    if (getattr(args, "style_create", None) or getattr(args, "style_list", False)
            or getattr(args, "style_show", None)
            or getattr(args, "style_delete", None)
            or getattr(args, "style_export", None)
            or getattr(args, "style_import", None)):
        from cli.commands.style import run_style_cmd
        return run_style_cmd(args, ConfigManager())
```

Create `cli/commands/style.py`:

```python
"""CLI handler for custom-style management verbs."""
import json
import logging
import sys
from pathlib import Path

from core.styles.models import Style
from core.styles.store import StyleStore

logger = logging.getLogger("imageai.cli.style")


class StyleCliError(Exception):
    """User-facing CLI validation error (maps to exit code 2)."""


def _emit(msg: str) -> None:
    """Human-facing progress line -> stderr (keeps stdout pure for data)."""
    print(msg, file=sys.stderr)


def _require(store: StyleStore, name: str) -> Style:
    style = store.get_by_name(name)
    if style is None:
        names = ", ".join(s.name for s in store.list_styles()) or "(none)"
        raise StyleCliError(f"Style not found: {name}. Available: {names}")
    return style


def run_style_cmd(args, config) -> int:
    """Route style management verbs. Returns 0 ok / 2 user error / 3 failure."""
    store = StyleStore()
    try:
        if getattr(args, "style_list", False):
            styles = store.list_styles()
            if not styles:
                print("No styles saved. Create one with --style-create NAME "
                      "--style-images PATH...")
                return 0
            for s in styles:
                refs = len(s.reference_images)
                text = (s.prompt_text or "")[:60].replace("\n", " ")
                print(f"{s.id:24}  {s.name:24}  {refs:3} ref(s)  {text}")
            return 0

        if getattr(args, "style_show", None):
            style = _require(store, args.style_show)
            print(json.dumps(style.to_dict(), indent=2, ensure_ascii=False))
            return 0

        if getattr(args, "style_delete", None):
            style = _require(store, args.style_delete)
            store.delete(style.id)
            _emit(f"Deleted style '{style.name}' ({style.id})")
            return 0

        # Tasks 8-9 extend this router: --style-create, --style-export/import.
        raise StyleCliError("No style verb matched")
    except StyleCliError as e:
        logger.warning(str(e))
        print(f"Error: {e}")
        return 2
    except Exception as e:  # noqa: BLE001 - CLI boundary
        logger.error(f"Style command failed: {e}", exc_info=True)
        print(f"Error: {e}")
        return 3
```

- [ ] **Step 4: Run to verify pass**

Run: `$PY -m pytest tests/styles/test_cli_style_parser.py tests/styles/test_cli_style_dispatch.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli tests/styles
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): CLI styles argument group + list/show/delete verbs"
```

---

### Task 8: CLI `--style-create`

**Files:**
- Modify: `cli/commands/style.py`
- Test: `tests/styles/test_cli_style_create.py`

**Interfaces:**
- Consumes: `StyleAnalysisService` (Task 5), `StyleStore.add_reference_images` (Task 2), `EXEMPLAR_DEFAULT_CAP`.
- Produces: `_collect_images(specs) -> List[Path]` (files, dirs — non-recursive `*.png|jpg|jpeg|webp|bmp` — and glob patterns; sorted, de-duplicated; raises `StyleCliError` if none found); `_handle_create(args, config, store) -> int` wired into `run_style_cmd`'s router (replaces the "No style verb matched" fallthrough for `--style-create`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/styles/test_cli_style_create.py
"""--style-create: image collection, derivation, persistence."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PIL import Image

from cli.parser import build_arg_parser
from cli.commands.style import StyleCliError, _collect_images, run_style_cmd
from core.styles.models import DESCRIPTOR_KEYS
from core.styles.store import StyleStore


def _args(*argv):
    return build_arg_parser().parse_args(list(argv))


def _mk(path, size=(32, 32)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (5, 5, 5)).save(path)
    return path


def test_collect_images_files_dirs_globs(tmp_path):
    a = _mk(tmp_path / "a.png")
    _mk(tmp_path / "d" / "b.jpg")
    _mk(tmp_path / "d" / "c.webp")
    (tmp_path / "d" / "notes.txt").write_text("x")
    got = _collect_images([str(a), str(tmp_path / "d"),
                           str(tmp_path / "d" / "*.jpg")])  # glob dupes b.jpg
    assert [p.name for p in got] == ["a.png", "b.jpg", "c.webp"]


def test_collect_images_none_raises(tmp_path):
    with pytest.raises(StyleCliError):
        _collect_images([str(tmp_path / "empty-dir")])


def test_create_derives_and_saves(tmp_path):
    imgs = [_mk(tmp_path / f"i{n}.png") for n in range(4)]
    store = StyleStore(base_dir=tmp_path / "styles")
    derived = {"descriptor": {k: "v" for k in DESCRIPTOR_KEYS},
               "prompt_text": "derived text"}
    svc = SimpleNamespace(provider="openai", model="m",
                          derive=lambda paths, progress_cb=None: derived)
    with patch("cli.commands.style.StyleStore", return_value=store), \
         patch("cli.commands.style.StyleAnalysisService", return_value=svc):
        rc = run_style_cmd(
            _args("--style-create", "Water", "--style-images", str(tmp_path)),
            SimpleNamespace())
    assert rc == 0
    saved = store.get_by_name("Water")
    assert saved is not None
    assert saved.prompt_text == "derived text"
    assert len(saved.reference_images) == 4
    assert saved.exemplars == saved.reference_images[:3]  # auto-pick first 3
    assert saved.source["image_count"] == 4


def test_create_requires_images_flag(tmp_path, capsys):
    rc = run_style_cmd(_args("--style-create", "W"), SimpleNamespace())
    assert rc == 2
    assert "--style-images" in capsys.readouterr().out


def test_create_analysis_failure_saves_nothing(tmp_path):
    _mk(tmp_path / "i.png")
    store = StyleStore(base_dir=tmp_path / "styles")
    from core.styles.analyzer import StyleAnalysisError
    with patch("cli.commands.style.StyleStore", return_value=store), \
         patch("cli.commands.style.StyleAnalysisService",
               side_effect=StyleAnalysisError("No openai API key configured")):
        rc = run_style_cmd(
            _args("--style-create", "W", "--style-images", str(tmp_path)),
            SimpleNamespace())
    assert rc == 2
    assert store.list_styles() == []
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest tests/styles/test_cli_style_create.py -v`
Expected: FAIL — `ImportError: cannot import name '_collect_images'`

- [ ] **Step 3: Implement** — in `cli/commands/style.py` add imports and handlers:

```python
from datetime import datetime

from core.styles.analyzer import StyleAnalysisError, StyleAnalysisService
from core.styles.store import EXEMPLAR_DEFAULT_CAP

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _collect_images(specs) -> list:
    """Resolve --style-images specs (files, dirs, globs) to sorted unique paths."""
    import glob as globmod
    found = []
    for spec in specs or []:
        p = Path(spec).expanduser()
        if p.is_dir():
            found.extend(c for c in p.iterdir()
                         if c.suffix.lower() in IMAGE_EXTS)
        elif p.is_file():
            found.append(p)
        else:
            found.extend(Path(m) for m in globmod.glob(str(p))
                         if Path(m).suffix.lower() in IMAGE_EXTS)
    unique = sorted(set(p.resolve() for p in found))
    if not unique:
        raise StyleCliError(
            f"No images found in: {', '.join(specs or ['(nothing)'])}")
    return unique


def _handle_create(args, config, store: StyleStore) -> int:
    if not getattr(args, "style_images", None):
        raise StyleCliError("--style-create requires --style-images PATH ...")
    paths = _collect_images(args.style_images)
    _emit(f"Deriving style '{args.style_create}' from {len(paths)} image(s)...")

    service = StyleAnalysisService(config,
                                   provider=getattr(args, "style_llm_provider", None),
                                   model=getattr(args, "style_llm_model", None))
    data = service.derive(paths, progress_cb=_emit)

    from core.styles.models import Style, StyleDescriptor
    style = Style(id=store.new_id(args.style_create), name=args.style_create,
                  descriptor=StyleDescriptor.from_dict(data["descriptor"]),
                  prompt_text=data["prompt_text"],
                  source={"provider": service.provider, "model": service.model,
                          "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                          "image_count": len(paths)})
    store.save(style)
    store.add_reference_images(style, paths)
    style.exemplars = style.reference_images[:EXEMPLAR_DEFAULT_CAP]
    store.save(style)
    _emit(f"Created style '{style.name}' ({style.id}) with "
          f"{len(style.reference_images)} reference image(s)")
    print(style.id)  # stdout: the id, scripting-friendly
    return 0
```

In `run_style_cmd`'s router (before the `raise StyleCliError("No style verb matched")` line) add:

```python
        if getattr(args, "style_create", None):
            return _handle_create(args, config, store)
```

and extend the `except StyleCliError` clause to also catch `StyleAnalysisError` (both are user-facing, exit 2):

```python
    except (StyleCliError, StyleAnalysisError) as e:
```

- [ ] **Step 4: Run to verify pass**

Run: `$PY -m pytest tests/styles/test_cli_style_create.py tests/styles/test_cli_style_dispatch.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli/commands/style.py tests/styles/test_cli_style_create.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): --style-create derives a style from files/dirs/globs"
```

---

### Task 9: CLI export/import verbs

**Files:**
- Modify: `cli/commands/style.py`
- Test: `tests/styles/test_cli_style_zip.py`

**Interfaces:**
- Consumes: `StyleStore.export_zip` / `import_zip` (Task 3).
- Produces: router entries for `--style-export` (requires `-o/--out` ending `.zip`) and `--style-import`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/styles/test_cli_style_zip.py
"""--style-export / --style-import round trip through the CLI."""
from types import SimpleNamespace
from unittest.mock import patch

from cli.parser import build_arg_parser
from cli.commands.style import run_style_cmd
from core.styles.models import Style
from core.styles.store import StyleStore


def _args(*argv):
    return build_arg_parser().parse_args(list(argv))


def test_export_then_import(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    store.save(Style(id="water", name="Water", prompt_text="washes"))
    zip_path = tmp_path / "water.zip"
    with patch("cli.commands.style.StyleStore", return_value=store):
        assert run_style_cmd(
            _args("--style-export", "Water", "-o", str(zip_path)),
            SimpleNamespace()) == 0
        assert zip_path.exists()
        assert run_style_cmd(
            _args("--style-import", str(zip_path)), SimpleNamespace()) == 0
    assert store.get("water-2") is not None


def test_export_requires_out(tmp_path, capsys):
    store = StyleStore(base_dir=tmp_path / "styles")
    store.save(Style(id="water", name="Water"))
    with patch("cli.commands.style.StyleStore", return_value=store):
        assert run_style_cmd(_args("--style-export", "Water"),
                             SimpleNamespace()) == 2
    assert "-o" in capsys.readouterr().out


def test_import_missing_file(tmp_path):
    with patch("cli.commands.style.StyleStore",
               return_value=StyleStore(base_dir=tmp_path / "s")):
        assert run_style_cmd(_args("--style-import", str(tmp_path / "no.zip")),
                             SimpleNamespace()) == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest tests/styles/test_cli_style_zip.py -v`
Expected: FAIL — exits 2 with "No style verb matched" on export

- [ ] **Step 3: Implement** — add to `run_style_cmd`'s router (before the fallthrough raise):

```python
        if getattr(args, "style_export", None):
            style = _require(store, args.style_export)
            out = getattr(args, "out", None)
            if not out:
                raise StyleCliError(
                    "--style-export needs -o FILE.zip for the output path")
            out_path = Path(out).expanduser()
            if out_path.suffix.lower() != ".zip":
                out_path = out_path.with_suffix(".zip")
            if not store.export_zip(style.id, out_path):
                raise StyleCliError(f"Export failed for {style.id}")
            _emit(f"Exported '{style.name}' to {out_path}")
            return 0

        if getattr(args, "style_import", None):
            zip_path = Path(args.style_import).expanduser()
            if not zip_path.exists():
                raise StyleCliError(f"File not found: {zip_path}")
            imported = store.import_zip(zip_path)
            if imported is None:
                raise StyleCliError(f"Not a valid style zip: {zip_path}")
            _emit(f"Imported '{imported.name}' as {imported.id}")
            print(imported.id)
            return 0
```

- [ ] **Step 4: Run to verify pass**

Run: `$PY -m pytest tests/styles/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli/commands/style.py tests/styles/test_cli_style_zip.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): --style-export/--style-import zip verbs"
```

---

### Task 10: CLI `--style` on image generation

**Files:**
- Modify: `cli/runner.py` (the `--prompt` branch, after model resolution at `:339` and before the dispatch at `:370`; plus the sidecar meta at `:480-496`)
- Test: `tests/styles/test_cli_style_generation.py`

**Interfaces:**
- Consumes: `apply_style`, `StyleStore` (Tasks 2/6); `build_completion_fn` (Task 5).
- Produces: styled generation with `style_applied` sidecar key; sidecar `prompt` stays the ORIGINAL un-styled prompt.

- [ ] **Step 1: Write the failing tests**

```python
# tests/styles/test_cli_style_generation.py
"""--style NAME on the -p generation path."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cli.parser import build_arg_parser
from cli.runner import run_cli
from core.styles.models import Style
from core.styles.store import StyleStore


def _args(*argv):
    return build_arg_parser().parse_args(list(argv))


def _fake_provider():
    prov = MagicMock()
    prov.get_default_model.return_value = "fake-model"
    prov.generate.return_value = (["ok"], [b"PNGDATA"])
    return prov


def _run(tmp_path, *argv):
    store = StyleStore(base_dir=tmp_path / "styles")
    store.save(Style(id="water", name="Water", prompt_text="washes"))
    prov = _fake_provider()
    cfg = MagicMock()
    cfg.get_images_dir.return_value = tmp_path / "out"
    (tmp_path / "out").mkdir(exist_ok=True)
    with patch("cli.runner.get_provider", return_value=prov), \
         patch("cli.runner.resolve_api_key", return_value=("k", "test")), \
         patch("cli.runner.ConfigManager", return_value=cfg), \
         patch("core.styles.store.StyleStore.__init__",
               lambda self, base_dir=None: StyleStore.__init__(
                   self, base_dir=tmp_path / "styles")):
        rc = run_cli(_args(*argv))
    return rc, prov, tmp_path / "out"


def test_style_applied_to_generation_prompt(tmp_path):
    rc, prov, out_dir = _run(tmp_path, "-p", "a fox", "--style", "Water")
    assert rc == 0
    sent = prov.generate.call_args.kwargs["prompt"]
    assert sent == "a fox. In this style: washes"


def test_sidecar_keeps_original_prompt_and_provenance(tmp_path):
    rc, prov, out_dir = _run(tmp_path, "-p", "a fox", "--style", "Water")
    sidecars = list(out_dir.glob("*.png.json"))
    assert len(sidecars) == 1
    meta = json.loads(sidecars[0].read_text())
    assert meta["prompt"] == "a fox"  # un-styled
    assert meta["style_applied"]["style_id"] == "water"
    assert meta["style_applied"]["smart_merge_used"] is False


def test_unknown_style_exits_2(tmp_path, capsys):
    rc, _prov, _ = _run(tmp_path, "-p", "a fox", "--style", "Nope")
    assert rc == 2
    assert "Nope" in capsys.readouterr().out
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest tests/styles/test_cli_style_generation.py -v`
Expected: FAIL — style not applied (`sent == "a fox"`), no `style_applied` key

- [ ] **Step 3: Implement** — in `cli/runner.py`, inside the `--prompt` branch. After `model = args.model or provider_instance.get_default_model()` (`:339`) insert:

```python
            # Apply a saved style (Plans/2026-07-26-custom-styles-design.md §5)
            original_prompt = args.prompt
            style_meta = None
            if getattr(args, "style", None):
                from core.styles import StyleStore, apply_style
                _store = StyleStore()
                _style = _store.get_by_name(args.style)
                if _style is None:
                    names = ", ".join(s.name for s in _store.list_styles()) or "(none)"
                    print(f"Error: style not found: {args.style}. Available: {names}")
                    return 2
                completion_fn = None
                if getattr(args, "style_smart", False):
                    try:
                        from core.styles.analyzer import build_completion_fn
                        completion_fn, _p, _m = build_completion_fn(ConfigManager())
                    except Exception as e:  # noqa: BLE001 - degrade to plain
                        print(f"Smart merge unavailable ({e}); using plain concat.",
                              file=sys.stderr)
                styled = apply_style(
                    args.prompt, _style, provider, model,
                    smart=bool(getattr(args, "style_smart", False)),
                    completion_fn=completion_fn,
                    exemplar_paths=_store.resolve_refs(_style, exemplars_only=True))
                args.prompt = styled.prompt
                if "reference_images" in styled.extra_kwargs:
                    kwargs["reference_images"] = styled.extra_kwargs["reference_images"]
                style_meta = styled.meta
                print(f"Applied style '{_style.name}'"
                      + (" (smart merge)" if styled.meta["smart_merge_used"] else ""),
                      file=sys.stderr)
```

NOTE: the kwargs dict is built at `:343-353` — this block must go AFTER kwargs exists; place it immediately after the `if getattr(args, "num_images", 1) > 1:` block (`:352-353`).

Then in the sidecar meta dict (`:480-483`), change `"prompt": args.prompt,` to:

```python
                            "prompt": original_prompt,
```

and after the `if mask_path:` block (`:492-493`) add:

```python
                        if style_meta:
                            meta["style_applied"] = style_meta
```

(`original_prompt` is always bound in this branch — it is set unconditionally at the top of the inserted block.)

- [ ] **Step 4: Run to verify pass**

Run: `$PY -m pytest tests/styles/ tests/layout/ -v` (layout tests guard against runner regressions)
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli/runner.py tests/styles/test_cli_style_generation.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): --style/--style-smart on CLI image generation with sidecar provenance"
```

### Task 11: `StylePickerWidget` (`gui/styles/style_picker.py`)

**Files:**
- Create: `gui/styles/__init__.py`, `gui/styles/style_picker.py`
- Test: `tests/styles/test_style_picker.py`

**Interfaces:**
- Consumes: `StyleStore` (Task 2); `ConfigManager.get/set/save`.
- Produces: `StylePickerWidget(config, surface, parent=None, show_smart=True)` with signal `style_changed = Signal(str)` (style id or `""`), methods `refresh()`, `current_style() -> Optional[Style]`, `smart_merge_enabled() -> bool`, `set_store(store)` (test injection). Persists selection under config keys `style_selected_<surface>` / `style_smart_<surface>`. Tasks 14/15 embed it with surfaces `"image"` / `"video"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/styles/test_style_picker.py
"""Headless smoke tests for StylePickerWidget (QT_QPA_PLATFORM=offscreen)."""
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


@pytest.fixture
def store(tmp_path):
    s = StyleStore(base_dir=tmp_path / "styles")
    s.save(Style(id="water", name="Water", prompt_text="washes"))
    s.save(Style(id="neon", name="Neon", prompt_text="glow"))
    return s


def _picker(qapp, store, config=None, **kw):
    from gui.styles.style_picker import StylePickerWidget
    w = StylePickerWidget(config or FakeConfig(), "image", **kw)
    w.set_store(store)
    w.refresh()
    return w


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_picker_lists_styles_with_none_first(qapp, store):
    w = _picker(qapp, store)
    labels = [w.combo.itemText(i) for i in range(w.combo.count())]
    assert labels[0] == "None"
    assert "Water" in labels and "Neon" in labels
    assert w.current_style() is None


def test_selection_returns_style_and_persists(qapp, store):
    cfg = FakeConfig()
    w = _picker(qapp, store, config=cfg)
    w.combo.setCurrentText("Water")
    assert w.current_style().id == "water"
    assert cfg["style_selected_image"] == "water"
    # a new picker restores the selection
    w2 = _picker(qapp, store, config=cfg)
    assert w2.current_style().id == "water"


def test_smart_checkbox_persists(qapp, store):
    cfg = FakeConfig()
    w = _picker(qapp, store, config=cfg)
    w.smart_check.setChecked(True)
    assert w.smart_merge_enabled() is True
    assert cfg["style_smart_image"] is True


def test_hide_smart(qapp, store):
    w = _picker(qapp, store, show_smart=False)
    assert w.smart_check is None
    assert w.smart_merge_enabled() is False


def test_refresh_keeps_selection_when_possible(qapp, store):
    w = _picker(qapp, store)
    w.combo.setCurrentText("Neon")
    store.save(Style(id="extra", name="Extra"))
    w.refresh()
    assert w.current_style().id == "neon"
```

- [ ] **Step 2: Run to verify failure**

Run: `QT_QPA_PLATFORM=offscreen $PY -m pytest tests/styles/test_style_picker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gui.styles'`

- [ ] **Step 3: Implement**

```python
# gui/styles/__init__.py
"""GUI for the Custom Styles feature."""
```

```python
# gui/styles/style_picker.py
"""Compact reusable style picker: Style: [None v] [Manage...] [ ] Smart merge.

Dropped into the Generate tab, video workspace, and (via the Generate tab)
layout fill. Selection and smart-merge state persist per surface.
"""
import logging
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel,
                               QPushButton, QWidget)

from core.styles.models import Style
from core.styles.store import StyleStore

logger = logging.getLogger(__name__)


class StylePickerWidget(QWidget):
    style_changed = Signal(str)  # style id or "" for None

    def __init__(self, config, surface: str, parent=None, show_smart: bool = True):
        super().__init__(parent)
        self.config = config
        self.surface = surface
        self._store = StyleStore()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Style:"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(160)
        layout.addWidget(self.combo)
        self.manage_btn = QPushButton("Manage…")
        layout.addWidget(self.manage_btn)
        self.smart_check: Optional[QCheckBox] = None
        if show_smart:
            self.smart_check = QCheckBox("Smart merge")
            self.smart_check.setToolTip(
                "Fuse prompt and style with the configured LLM "
                "(falls back to plain concat on failure)")
            self.smart_check.setChecked(
                bool(self.config.get(f"style_smart_{surface}", False)))
            self.smart_check.toggled.connect(self._on_smart_toggled)
            layout.addWidget(self.smart_check)
        layout.addStretch()

        self.manage_btn.clicked.connect(self._open_manager)
        self.combo.currentIndexChanged.connect(self._on_changed)
        self.refresh()

    # -- store injection for tests / shared instances ----------------------
    def set_store(self, store: StyleStore) -> None:
        self._store = store

    def refresh(self) -> None:
        """Reload styles; keep the current selection when it still exists."""
        wanted = (self.combo.currentData()
                  or self.config.get(f"style_selected_{self.surface}", ""))
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("None", "")
        for s in self._store.list_styles():
            self.combo.addItem(s.name, s.id)
            idx = self.combo.count() - 1
            tip = s.description or (s.prompt_text or "")[:120]
            if tip:
                self.combo.setItemData(idx, tip, role=3)  # Qt.ToolTipRole
        pos = self.combo.findData(wanted) if wanted else 0
        self.combo.setCurrentIndex(pos if pos >= 0 else 0)
        self.combo.blockSignals(False)

    def current_style(self) -> Optional[Style]:
        sid = self.combo.currentData()
        return self._store.get(sid) if sid else None

    def smart_merge_enabled(self) -> bool:
        return bool(self.smart_check and self.smart_check.isChecked())

    # -- slots -------------------------------------------------------------
    def _on_changed(self, _idx: int) -> None:
        sid = self.combo.currentData() or ""
        self.config.set(f"style_selected_{self.surface}", sid)
        self.config.save()
        self.style_changed.emit(sid)

    def _on_smart_toggled(self, checked: bool) -> None:
        self.config.set(f"style_smart_{self.surface}", bool(checked))
        self.config.save()

    def _open_manager(self) -> None:
        from gui.styles.style_manager_dialog import StyleManagerDialog
        dlg = StyleManagerDialog(self.config, store=self._store, parent=self)
        dlg.exec()
        self.refresh()
```

NOTE: until Task 12 exists, `_open_manager`'s import would fail at click time only — tests don't click it, so Task 11 stays green. Use `role=3` literal or `from PySide6.QtCore import Qt` + `Qt.ToolTipRole` (prefer the latter; shown condensed here).

- [ ] **Step 4: Run to verify pass**

Run: `QT_QPA_PLATFORM=offscreen $PY -m pytest tests/styles/test_style_picker.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/styles tests/styles/test_style_picker.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): reusable StylePickerWidget with per-surface persistence"
```

---

### Task 12: Style Manager dialog — structure + CRUD

**Files:**
- Create: `gui/styles/style_manager_dialog.py`
- Test: `tests/styles/test_style_manager_dialog.py`

**Interfaces:**
- Consumes: `StyleStore` (Tasks 2–3); dialog conventions (`DialogCleanupMixin`, `OperationGuardMixin`, `bind_primary_action`, `set_default_button`, `standard_splitter`, `persist_splitter`, `restore_splitter`); `DialogStatusConsole`; `show_error`/`show_warning`; `get_provider_models` (`core/llm_models.py:186`); `EXEMPLAR_DEFAULT_CAP`.
- Produces: `StyleManagerDialog(config, store=None, parent=None)`. Widgets (exact attribute names — Task 13 wires the worker to them): `style_list` (QListWidget), `name_edit`, `desc_edit` (QLineEdit), `refs_list` (QListWidget, IconMode, checkable items = exemplar stars, itemData = rel path), `add_files_btn`, `add_folder_btn`, `remove_ref_btn`, `llm_provider_combo`, `llm_model_combo`, `analyze_btn`, `prompt_text_edit` (QTextEdit), `placement_combo` ("suffix"/"prefix"), `descriptor_view` (read-only QTextEdit), `new_btn`, `duplicate_btn`, `delete_btn`, `import_btn`, `export_btn`, `save_btn`, `console` (DialogStatusConsole). Methods: `_load_styles()`, `_current_style() -> Optional[Style]`, `_save_current()`, `_collect_exemplars() -> List[str]`.

- [ ] **Step 1: Write the failing smoke tests**

```python
# tests/styles/test_style_manager_dialog.py
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
```

- [ ] **Step 2: Run to verify failure**

Run: `QT_QPA_PLATFORM=offscreen $PY -m pytest tests/styles/test_style_manager_dialog.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement** — `gui/styles/style_manager_dialog.py`. Full structure (the analysis worker arrives in Task 13; `_on_analyze` shows a "not wired yet" warning for now):

```python
"""Style Manager dialog: create, edit, analyze, import/export custom styles."""
import json
import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QListView, QPushButton,
    QSplitter, QTextEdit, QVBoxLayout, QWidget)

from core.styles.models import Style, StyleDescriptor
from core.styles.store import EXEMPLAR_DEFAULT_CAP, StyleStore
from gui.common.dialog_conventions import (
    DialogCleanupMixin, bind_primary_action, persist_splitter,
    restore_splitter, set_default_button, standard_splitter)
from gui.dialog_utils import OperationGuardMixin, show_error, show_question, show_warning
from gui.llm_utils import DialogStatusConsole

logger = logging.getLogger(__name__)


class StyleManagerDialog(QDialog, OperationGuardMixin, DialogCleanupMixin):
    """Left: style list. Right: details + refs grid + analyze. Bottom: console."""

    def __init__(self, config, store: Optional[StyleStore] = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.store = store or StyleStore()
        self._worker = None  # Task 13
        self.setWindowTitle("Style Manager")
        self.resize(980, 680)
        self.init_operation_guard()
        self._build_ui()
        self._load_styles()

    # ---- UI construction -------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        self.v_splitter = standard_splitter(Qt.Vertical, self)
        outer.addWidget(self.v_splitter)

        top = QWidget()
        top_layout = QHBoxLayout(top)

        # Left pane: list + list-level buttons
        left = QWidget()
        left_l = QVBoxLayout(left)
        self.style_list = QListWidget()
        left_l.addWidget(self.style_list)
        row1 = QHBoxLayout()
        self.new_btn = QPushButton("New")
        self.duplicate_btn = QPushButton("Duplicate")
        self.delete_btn = QPushButton("Delete")
        for b in (self.new_btn, self.duplicate_btn, self.delete_btn):
            row1.addWidget(b)
        left_l.addLayout(row1)
        row2 = QHBoxLayout()
        self.import_btn = QPushButton("Import…")
        self.export_btn = QPushButton("Export…")
        row2.addWidget(self.import_btn)
        row2.addWidget(self.export_btn)
        left_l.addLayout(row2)
        top_layout.addWidget(left, stretch=1)

        # Right pane: details
        right = QWidget()
        right_l = QVBoxLayout(right)
        form_row = QHBoxLayout()
        form_row.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        form_row.addWidget(self.name_edit, stretch=1)
        form_row.addWidget(QLabel("Description:"))
        self.desc_edit = QLineEdit()
        form_row.addWidget(self.desc_edit, stretch=2)
        right_l.addLayout(form_row)

        right_l.addWidget(QLabel(
            f"Reference images (check up to {EXEMPLAR_DEFAULT_CAP} as exemplars "
            f"sent to image-capable providers):"))
        self.refs_list = QListWidget()
        self.refs_list.setViewMode(QListView.IconMode)
        self.refs_list.setIconSize(QPixmap(96, 96).size())
        self.refs_list.setResizeMode(QListView.Adjust)
        right_l.addWidget(self.refs_list, stretch=2)
        ref_row = QHBoxLayout()
        self.add_files_btn = QPushButton("Add Files…")
        self.add_folder_btn = QPushButton("Add Folder…")
        self.remove_ref_btn = QPushButton("Remove Selected")
        for b in (self.add_files_btn, self.add_folder_btn, self.remove_ref_btn):
            ref_row.addWidget(b)
        ref_row.addStretch()
        right_l.addLayout(ref_row)

        llm_row = QHBoxLayout()
        llm_row.addWidget(QLabel("Vision LLM:"))
        self.llm_provider_combo = QComboBox()
        self.llm_provider_combo.addItems(["openai", "anthropic", "google"])
        llm_row.addWidget(self.llm_provider_combo)
        self.llm_model_combo = QComboBox()
        self.llm_model_combo.setEditable(True)
        llm_row.addWidget(self.llm_model_combo, stretch=1)
        self.analyze_btn = QPushButton("Analyze Images")
        llm_row.addWidget(self.analyze_btn)
        right_l.addLayout(llm_row)

        right_l.addWidget(QLabel("Style prompt text (editable — this is what "
                                 "gets injected):"))
        self.prompt_text_edit = QTextEdit()
        self.prompt_text_edit.setMaximumHeight(90)
        right_l.addWidget(self.prompt_text_edit)
        place_row = QHBoxLayout()
        place_row.addWidget(QLabel("Placement:"))
        self.placement_combo = QComboBox()
        self.placement_combo.addItems(["suffix", "prefix"])
        place_row.addWidget(self.placement_combo)
        place_row.addStretch()
        self.save_btn = QPushButton("&Save Style")
        place_row.addWidget(self.save_btn)
        right_l.addLayout(place_row)
        right_l.addWidget(QLabel("Derived descriptor (read-only):"))
        self.descriptor_view = QTextEdit()
        self.descriptor_view.setReadOnly(True)
        self.descriptor_view.setMaximumHeight(110)
        right_l.addWidget(self.descriptor_view)
        top_layout.addWidget(right, stretch=3)

        self.v_splitter.addWidget(top)
        self.console = DialogStatusConsole("Analysis Console", self)
        self.v_splitter.addWidget(self.console)
        restore_splitter(self.v_splitter, "style_manager/splitter")

        set_default_button(self, self.save_btn)
        bind_primary_action(self, self._save_current)

        # wiring
        self.style_list.currentRowChanged.connect(self._on_selected)
        self.new_btn.clicked.connect(self._on_new)
        self.duplicate_btn.clicked.connect(self._on_duplicate)
        self.delete_btn.clicked.connect(self._on_delete)
        self.import_btn.clicked.connect(self._on_import)
        self.export_btn.clicked.connect(self._on_export)
        self.add_files_btn.clicked.connect(self._on_add_files)
        self.add_folder_btn.clicked.connect(self._on_add_folder)
        self.remove_ref_btn.clicked.connect(self._on_remove_ref)
        self.save_btn.clicked.connect(self._save_current)
        self.analyze_btn.clicked.connect(self._on_analyze)

    # ---- data <-> widgets ------------------------------------------------

    def _load_styles(self, select_id: Optional[str] = None):
        self.style_list.clear()
        for s in self.store.list_styles():
            item = QListWidgetItem(s.name)
            item.setData(Qt.UserRole, s.id)
            self.style_list.addItem(item)
            if select_id and s.id == select_id:
                self.style_list.setCurrentItem(item)
        if self.style_list.currentRow() < 0 and self.style_list.count():
            self.style_list.setCurrentRow(0)

    def _current_style(self) -> Optional[Style]:
        item = self.style_list.currentItem()
        if item is None:
            return None
        return self.store.get(item.data(Qt.UserRole))

    def _on_selected(self, _row: int):
        s = self._current_style()
        if s is None:
            return
        self.name_edit.setText(s.name)
        self.desc_edit.setText(s.description)
        self.prompt_text_edit.setPlainText(s.prompt_text)
        self.placement_combo.setCurrentText(s.placement)
        self.descriptor_view.setPlainText(
            json.dumps(s.descriptor.to_dict(), indent=2, ensure_ascii=False))
        self.refs_list.clear()
        base = self.store.style_dir(s.id)
        for rel in s.reference_images:
            item = QListWidgetItem(Path(rel).name)
            item.setData(Qt.UserRole, rel)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if rel in s.exemplars else Qt.Unchecked)
            p = base / rel
            if p.exists():
                item.setIcon(QIcon(QPixmap(str(p)).scaled(
                    96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
            self.refs_list.addItem(item)

    def _collect_exemplars(self) -> List[str]:
        out = []
        for i in range(self.refs_list.count()):
            item = self.refs_list.item(i)
            if item.checkState() == Qt.Checked:
                out.append(item.data(Qt.UserRole))
        return out

    def _save_current(self):
        s = self._current_style()
        if s is None:
            return
        s.name = self.name_edit.text().strip() or s.name
        s.description = self.desc_edit.text().strip()
        s.prompt_text = self.prompt_text_edit.toPlainText().strip()
        s.placement = self.placement_combo.currentText()
        exemplars = self._collect_exemplars()
        if len(exemplars) > EXEMPLAR_DEFAULT_CAP:
            show_warning(self, "Style Manager",
                         f"Only the first {EXEMPLAR_DEFAULT_CAP} checked images "
                         f"are used as exemplars.")
            exemplars = exemplars[:EXEMPLAR_DEFAULT_CAP]
        s.exemplars = exemplars
        self.store.save(s)
        self.console.log(f"Saved style '{s.name}'", "SUCCESS")
        self._load_styles(select_id=s.id)

    # ---- list-level actions ---------------------------------------------

    def _on_new(self):
        name, ok = QInputDialog.getText(self, "New Style", "Style name:")
        if not ok or not name.strip():
            return
        s = Style(id=self.store.new_id(name.strip()), name=name.strip())
        self.store.save(s)
        self._load_styles(select_id=s.id)

    def _on_duplicate(self):
        s = self._current_style()
        if s is None:
            return
        import copy
        dup = copy.deepcopy(s)
        dup.id = self.store.new_id(s.name)
        dup.name = f"{s.name} copy"
        self.store.save(dup)
        src_refs = self.store.resolve_refs(s)
        dup.reference_images, dup.exemplars = [], []
        self.store.add_reference_images(dup, src_refs)
        dup.exemplars = dup.reference_images[:len(s.exemplars)]
        self.store.save(dup)
        self._load_styles(select_id=dup.id)

    def _on_delete(self):
        s = self._current_style()
        if s is None:
            return
        if not show_question(self, "Delete Style",
                             f"Delete style '{s.name}' and its images?"):
            return
        self.store.delete(s.id)
        self._load_styles()

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Style", "",
                                              "Style zip (*.zip)")
        if not path:
            return
        imported = self.store.import_zip(Path(path))
        if imported is None:
            show_error(self, "Style Manager", f"Not a valid style zip: {path}")
            return
        self.console.log(f"Imported '{imported.name}'", "SUCCESS")
        self._load_styles(select_id=imported.id)

    def _on_export(self):
        s = self._current_style()
        if s is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Style",
                                              f"{s.id}.zip", "Style zip (*.zip)")
        if not path:
            return
        if self.store.export_zip(s.id, Path(path)):
            self.console.log(f"Exported to {path}", "SUCCESS")

    # ---- reference images ------------------------------------------------

    def _on_add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Reference Images", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        self._add_paths([Path(p) for p in paths])

    def _on_add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Add Folder of Images")
        if not d:
            return
        exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        self._add_paths([p for p in sorted(Path(d).iterdir())
                         if p.suffix.lower() in exts])

    def _add_paths(self, paths):
        s = self._current_style()
        if s is None or not paths:
            return
        added = self.store.add_reference_images(s, paths)
        self.store.save(s)
        self.console.log(f"Added {len(added)} image(s)", "INFO")
        self._on_selected(self.style_list.currentRow())

    def _on_remove_ref(self):
        s = self._current_style()
        item = self.refs_list.currentItem()
        if s is None or item is None:
            return
        self.store.remove_reference_image(s, item.data(Qt.UserRole))
        self.store.save(s)
        self._on_selected(self.style_list.currentRow())

    # ---- analysis (wired in Task 13) ------------------------------------

    def _on_analyze(self):
        show_warning(self, "Style Manager", "Analysis wiring lands in Task 13.")

    # ---- lifecycle -------------------------------------------------------

    def on_dialog_close(self):
        persist_splitter(self.v_splitter, "style_manager/splitter")
```

NOTE for the implementer: check the actual signatures in `gui/common/dialog_conventions.py` and `gui/dialog_utils.py` before wiring (`standard_splitter:22`, `persist_splitter:30`, `restore_splitter:35`, `bind_primary_action:77`, `set_default_button:82`, `show_question` at `gui/dialog_utils.py:61` — adjust argument order to match the real helpers; the smoke tests don't depend on them beyond construction).

- [ ] **Step 4: Run to verify pass**

Run: `QT_QPA_PLATFORM=offscreen $PY -m pytest tests/styles/test_style_manager_dialog.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/styles tests/styles/test_style_manager_dialog.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): Style Manager dialog with CRUD, refs grid, import/export"
```

---

### Task 13: Analysis worker + dialog wiring

**Files:**
- Modify: `gui/styles/style_manager_dialog.py`
- Test: `tests/styles/test_style_analysis_worker.py`

**Interfaces:**
- Consumes: `StyleAnalysisService` (Task 5), `OperationGuardMixin` (`start_operation`/`end_operation`), `DialogStatusConsole.log`.
- Produces: `StyleAnalysisWorker(QThread)` with signals `progress(str)`, `finished_ok(dict)`, `failed(str)`; real `_on_analyze` + `_on_analysis_done` / `_on_analysis_failed` in the dialog. Re-analysis shows results in the fields but does NOT save until the user clicks Save (spec §4: non-destructive until saved).

- [ ] **Step 1: Write the failing tests**

```python
# tests/styles/test_style_analysis_worker.py
"""Worker thread emits progress/finished/failed correctly (offscreen)."""
import pytest

pytest.importorskip("PySide6")

from types import SimpleNamespace


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def _run_worker(qapp, service, paths):
    from gui.styles.style_manager_dialog import StyleAnalysisWorker
    worker = StyleAnalysisWorker(service, paths)
    got = {"progress": [], "ok": None, "fail": None}
    worker.progress.connect(got["progress"].append)
    worker.finished_ok.connect(lambda d: got.__setitem__("ok", d))
    worker.failed.connect(lambda m: got.__setitem__("fail", m))
    worker.run()  # synchronous call: same code path, no thread flakiness
    return got


def test_worker_success(qapp):
    derived = {"descriptor": {"summary": "s"}, "prompt_text": "t"}
    svc = SimpleNamespace(derive=lambda paths, progress_cb=None: (
        progress_cb and progress_cb("chunk 1/1"), derived)[1])
    got = _run_worker(qapp, svc, ["a.png"])
    assert got["ok"] == derived
    assert got["fail"] is None
    assert "chunk 1/1" in got["progress"]


def test_worker_failure(qapp):
    def boom(paths, progress_cb=None):
        raise RuntimeError("no key")
    got = _run_worker(qapp, SimpleNamespace(derive=boom), ["a.png"])
    assert got["ok"] is None
    assert "no key" in got["fail"]
```

- [ ] **Step 2: Run to verify failure**

Run: `QT_QPA_PLATFORM=offscreen $PY -m pytest tests/styles/test_style_analysis_worker.py -v`
Expected: FAIL — `ImportError: cannot import name 'StyleAnalysisWorker'`

- [ ] **Step 3: Implement** — add to `gui/styles/style_manager_dialog.py` (top-level, above the dialog class):

```python
from PySide6.QtCore import QThread, Signal


class StyleAnalysisWorker(QThread):
    """Runs StyleAnalysisService.derive off the UI thread."""
    progress = Signal(str)
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, service, paths, parent=None):
        super().__init__(parent)
        self._service = service
        self._paths = list(paths)

    def run(self):
        try:
            data = self._service.derive(self._paths,
                                        progress_cb=self.progress.emit)
            self.finished_ok.emit(data)
        except Exception as e:  # noqa: BLE001 - report to UI, never crash thread
            self.failed.emit(str(e))
```

Replace the placeholder `_on_analyze` and add the two handlers:

```python
    def _on_analyze(self):
        s = self._current_style()
        if s is None:
            return
        paths = self.store.resolve_refs(s)
        if not paths:
            show_warning(self, "Style Manager",
                         "Add reference images before analyzing.")
            return
        from core.styles.analyzer import StyleAnalysisError, StyleAnalysisService
        try:
            service = StyleAnalysisService(
                self.config,
                provider=self.llm_provider_combo.currentText(),
                model=self.llm_model_combo.currentText().strip() or None)
        except StyleAnalysisError as e:
            show_error(self, "Style Manager", str(e))
            return
        if not self.start_operation("analyze"):
            return
        self.analyze_btn.setEnabled(False)
        self.console.separator()
        self.console.log(
            f"Analyzing {len(paths)} image(s) with {service.model}...", "INFO")
        self._worker = StyleAnalysisWorker(service, paths, parent=self)
        self._worker.progress.connect(lambda m: self.console.log(m, "INFO"))
        self._worker.finished_ok.connect(self._on_analysis_done)
        self._worker.failed.connect(self._on_analysis_failed)
        self._worker.start()

    def _on_analysis_done(self, data: dict):
        self.end_operation("analyze")
        self.analyze_btn.setEnabled(True)
        # Non-destructive: show in the editable fields; user must Save.
        self.prompt_text_edit.setPlainText(data.get("prompt_text", ""))
        self.descriptor_view.setPlainText(
            json.dumps(data.get("descriptor", {}), indent=2, ensure_ascii=False))
        self._pending_descriptor = data.get("descriptor", {})
        self.console.log("Analysis complete — review, then Save Style.", "SUCCESS")

    def _on_analysis_failed(self, message: str):
        self.end_operation("analyze")
        self.analyze_btn.setEnabled(True)
        self.console.log(f"Analysis failed: {message}", "ERROR")
        show_error(self, "Style Manager", f"Style analysis failed:\n{message}")
```

And in `_save_current()`, persist the pending descriptor (insert before `self.store.save(s)`):

```python
        pending = getattr(self, "_pending_descriptor", None)
        if pending:
            s.descriptor = StyleDescriptor.from_dict(pending)
            self._pending_descriptor = None
```

Also in `on_dialog_close()`, guard the worker:

```python
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(2000)
```

(Check `OperationGuardMixin.start_operation`/`end_operation` signatures at `gui/dialog_utils.py:197,224` and adapt the operation-name argument to the real API.)

- [ ] **Step 4: Run to verify pass**

Run: `QT_QPA_PLATFORM=offscreen $PY -m pytest tests/styles/test_style_analysis_worker.py tests/styles/test_style_manager_dialog.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/styles tests/styles/test_style_analysis_worker.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): QThread analysis worker with live console progress"
```

### Task 14: Generate tab integration

**Files:**
- Modify: `gui/main_window.py` — three edits: picker row in `_init_generate_tab` (after the prompt header block ending ~`:857`), style application in `_generate()` (immediately before the worker creation at ~`:5780`), sidecar key in `_on_generation_finished` (the `meta = {` dict at ~`:6444`, written by `write_image_sidecar` at `:6469`)
- Test: `tests/styles/test_generate_tab_integration.py`

**Interfaces:**
- Consumes: `StylePickerWidget` (Task 11), `apply_style` (Task 6), `build_completion_fn` (Task 5).
- Produces: `self.style_picker` on `MainWindow`; `self.last_style_meta` (dict or None) consumed by the sidecar writer. GUI layout fill ("Fill All") inherits this automatically — it routes each region through `_generate()` (see `_on_layout_fill_all` at `gui/main_window.py:6184` / `_begin_layout_fill:6200`).

- [ ] **Step 1: Write the failing test** (logic-level: the seam helper, not the full window — `MainWindow` construction is too heavy for unit tests; the house pattern for main-window logic is extracting a testable helper)

Add a small free function to `gui/main_window.py`'s seam instead of inlining everything — create it in `core/styles/applicator.py` so it's testable headless:

```python
# appended to tests/styles/test_applicator.py
from core.styles.applicator import apply_style_for_surface


def test_apply_style_for_surface_none_style_is_identity():
    prompt, kwargs, meta = apply_style_for_surface(
        "a fox", None, "google", "m", smart=False, config=None,
        store=None, existing_references=None)
    assert prompt == "a fox" and kwargs == {} and meta is None


def test_apply_style_for_surface_full_path(tmp_path):
    from core.styles.models import Style
    from core.styles.store import StyleStore
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id="w", name="W", prompt_text="washes")
    store.save(s)
    prompt, kwargs, meta = apply_style_for_surface(
        "a fox", s, "stability", "sd3", smart=False, config=None,
        store=store, existing_references=None)
    assert prompt == "a fox. In this style: washes"
    assert meta["style_id"] == "w"


def test_apply_style_for_surface_smart_without_key_degrades(tmp_path):
    from core.styles.models import Style
    from core.styles.store import StyleStore

    class NoKeyConfig:
        def get_api_key(self, provider):
            return None
        def get(self, k, d=None):
            return d

    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id="w", name="W", prompt_text="washes")
    store.save(s)
    prompt, kwargs, meta = apply_style_for_surface(
        "a fox", s, "stability", "sd3", smart=True, config=NoKeyConfig(),
        store=store, existing_references=None)
    assert prompt == "a fox. In this style: washes"  # plain fallback
    assert meta["smart_merge_used"] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest tests/styles/test_applicator.py -v`
Expected: FAIL — `ImportError: cannot import name 'apply_style_for_surface'`

- [ ] **Step 3: Implement the helper** — append to `core/styles/applicator.py`:

```python
def apply_style_for_surface(prompt, style, provider, model, *, smart,
                            config, store, existing_references):
    """Convenience seam used by GUI surfaces.

    Returns (styled_prompt, extra_kwargs, meta_or_None). style=None is a
    no-op. Builds the smart-merge completion_fn from config, degrading to
    plain concat (logged) when the LLM is unavailable.
    """
    if style is None:
        return prompt, {}, None
    completion_fn = None
    if smart and config is not None:
        try:
            from core.styles.analyzer import build_completion_fn
            completion_fn, _p, _m = build_completion_fn(config)
        except Exception as e:  # noqa: BLE001 - degrade, never block generation
            logger.warning(f"Smart merge unavailable ({e}); plain concat")
    exemplars = store.resolve_refs(style, exemplars_only=True) if store else []
    res = apply_style(prompt, style, provider, model, smart=smart,
                      completion_fn=completion_fn, exemplar_paths=exemplars,
                      existing_references=existing_references)
    return res.prompt, res.extra_kwargs, res.meta
```

Export it from `core/styles/__init__.py` (add to imports + `__all__`).

- [ ] **Step 4: Wire the GUI** (no automated test — verified via existing suite + manual note below):

(a) `_init_generate_tab`, after the prompt-header block (~`:857`):

```python
        # Style picker row (Custom Styles feature)
        try:
            from gui.styles.style_picker import StylePickerWidget
            self.style_picker = StylePickerWidget(self.config, "image")
            layout.addWidget(self.style_picker)
        except Exception as e:  # noqa: BLE001 - picker must never break the tab
            logger.warning(f"Style picker unavailable: {e}")
```
(match the local layout variable name used in that block of `_init_generate_tab` — it is the layout the prompt header row was added to.)

(b) `_generate()`, immediately before the `StreamingGenWorker`/`GenWorker` creation (~`:5780`):

```python
        # Apply selected custom style (spec §5: after original_prompt capture,
        # so history/sidecars keep the clean prompt).
        self.last_style_meta = None
        _picker = getattr(self, "style_picker", None)
        _style = _picker.current_style() if _picker else None
        if _style is not None:
            from core.styles import StyleStore, apply_style_for_surface
            prompt, _style_kwargs, self.last_style_meta = apply_style_for_surface(
                prompt, _style, self.current_provider, self.current_model,
                smart=_picker.smart_merge_enabled(), config=self.config,
                store=StyleStore(),
                existing_references=kwargs.get("reference_images"))
            if "reference_images" in _style_kwargs:
                kwargs["reference_images"] = _style_kwargs["reference_images"]
            self._append_to_console(
                f"Style applied: {_style.name}"
                + (" (smart merge)" if self.last_style_meta["smart_merge_used"] else "")
                + (f", {self.last_style_meta['exemplars_attached']} exemplar ref(s)"
                   if self.last_style_meta["exemplars_attached"] else ""),
                "#66ccff")
```

(c) `_on_generation_finished`, inside the `meta = {` sidecar dict block (~`:6444-6469`), after the existing optional keys:

```python
                if getattr(self, "last_style_meta", None):
                    meta["style_applied"] = self.last_style_meta
```

- [ ] **Step 5: Run the full test suite to catch regressions**

Run: `QT_QPA_PLATFORM=offscreen $PY -m pytest -x -q`
Expected: full suite PASS (472+ tests as of v0.40.0, plus the new styles tests)

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/styles gui/main_window.py tests/styles
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): style picker + application in the Generate tab"
```

Manual verification note for Leland (PowerShell, `.venv`): create a style from a few images in the Style Manager, select it, generate with Google and with OpenAI; confirm console shows "Style applied", the sidecar `.json` carries `style_applied`, and history shows the un-styled prompt.

---

### Task 15: Video workspace integration

**Files:**
- Modify: `gui/video/workspace_widget.py` — picker beside the existing style row (built ~`:1137-1160`), and the scene-styling block at `:2859-2878`
- Test: `tests/styles/test_video_style_integration.py`

**Interfaces:**
- Consumes: `StylePickerWidget` (surface `"video"`, `show_smart=False` — scene batches already go through LLM enhancement; per-scene smart merge would multiply calls), `apply_style` (Task 6).
- Produces: `apply_stored_style_to_scenes(scenes, style) -> int` module-level function in `gui/video/workspace_widget.py` (count of scenes styled; skips `[Section]` markers; provider `""` so it is always text-only per spec §5).

- [ ] **Step 1: Write the failing test**

```python
# tests/styles/test_video_style_integration.py
"""Stored-style injection into video scene prompts (pure function)."""
import pytest

pytest.importorskip("PySide6")

from types import SimpleNamespace

from core.styles.models import Style


def _scenes(*prompts):
    return [SimpleNamespace(prompt=p) for p in prompts]


def test_apply_stored_style_to_scenes():
    from gui.video.workspace_widget import apply_stored_style_to_scenes
    style = Style(id="w", name="W", prompt_text="washes")
    scenes = _scenes("a fox", "[Chorus]", "a river")
    n = apply_stored_style_to_scenes(scenes, style)
    assert n == 2
    assert scenes[0].prompt == "a fox. In this style: washes"
    assert scenes[1].prompt == "[Chorus]"  # section marker untouched
    assert scenes[2].prompt == "a river. In this style: washes"


def test_apply_stored_style_none_is_noop():
    from gui.video.workspace_widget import apply_stored_style_to_scenes
    scenes = _scenes("a fox")
    assert apply_stored_style_to_scenes(scenes, None) == 0
    assert scenes[0].prompt == "a fox"
```

- [ ] **Step 2: Run to verify failure**

Run: `QT_QPA_PLATFORM=offscreen $PY -m pytest tests/styles/test_video_style_integration.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement**

Module-level function in `gui/video/workspace_widget.py` (near the top, after imports):

```python
def apply_stored_style_to_scenes(scenes, style) -> int:
    """Apply a stored custom style to scene prompts (text-only; spec §5).

    Skips [Section] markers. Returns the number of scenes styled.
    """
    if style is None:
        return 0
    from core.styles import apply_style
    count = 0
    for scene in scenes:
        p = getattr(scene, "prompt", None)
        if not p:
            continue
        stripped = p.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            continue
        scene.prompt = apply_style(p, style, "", "").prompt
        count += 1
    return count
```

Picker: in the style-row construction area (`:1137-1160`, next to `prompt_style_input` / `manage_styles_btn`), add:

```python
        try:
            from gui.styles.style_picker import StylePickerWidget
            self.style_picker = StylePickerWidget(self.config, "video",
                                                  show_smart=False)
            style_row_layout.addWidget(self.style_picker)
        except Exception as e:
            self.logger.warning(f"Style picker unavailable: {e}")
```
(match the actual layout variable that `prompt_style_input` is added to; the legacy name-only combo stays untouched — spec §10.)

Scene styling: in the block at `:2859-2878`, before the legacy `prompt_style` branch:

```python
        stored_style = (self.style_picker.current_style()
                        if hasattr(self, "style_picker") else None)
        if stored_style is not None:
            n = apply_stored_style_to_scenes(scenes, stored_style)
            self.logger.info(f"🎨 Applied stored style '{stored_style.name}' "
                             f"to {n} scene prompt(s)")
            self._log_to_console(f"🎨 Style '{stored_style.name}' applied to "
                                 f"{n} scene(s)", "INFO")
        elif prompt_style and prompt_style.lower() != 'none':
            ... existing naive-prefix block unchanged ...
```
(i.e. convert the existing `if prompt_style and ...:` to `elif`.)

- [ ] **Step 4: Run to verify pass**

Run: `QT_QPA_PLATFORM=offscreen $PY -m pytest tests/styles/test_video_style_integration.py -v && QT_QPA_PLATFORM=offscreen $PY -m pytest tests/ -q -k "video"`
Expected: PASS, no video-test regressions

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/video/workspace_widget.py tests/styles/test_video_style_integration.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): stored styles on video scene prompts (text-only)"
```

---

### Task 16: Layout fill integration (CLI + batch requests)

**Files:**
- Modify: `core/layout/batch_fill.py` (`build_requests` at `:39`), `cli/commands/layout.py` (`run_fill_cmd` region loop at `:131-137`)
- Test: `tests/styles/test_layout_style_integration.py`

**Interfaces:**
- Consumes: `apply_style` (Task 6); `--style`/`--style-smart` flags (Task 7).
- Produces: `build_requests(document, model, only_empty=False, style=None)` — styled region prompts (text-only, provider `""`); `run_fill_cmd` resolves `--style` by name (exit 2 with available names if unknown) and styles each region prompt before generation. GUI "Fill All" needs nothing: it routes regions through the Generate tab (Task 14).

- [ ] **Step 1: Write the failing test**

```python
# tests/styles/test_layout_style_integration.py
"""Styled prompts in layout batch requests."""
from core.styles.models import Style


def test_build_requests_applies_style():
    from core.layout.batch_fill import build_requests
    from core.layout.models import DocumentSpec, PageSpec, Region
    region = Region(id="r1", kind="image", bbox=(0, 0, 100, 100),
                    prompt="a fox")
    doc = DocumentSpec(title="T", content_kind="storybook",
                       pages=[PageSpec(regions=[region])])
    style = Style(id="w", name="W", prompt_text="washes")
    reqs_plain = build_requests(doc, "m")
    reqs_styled = build_requests(doc, "m", style=style)
    assert reqs_plain[0].prompt == "a fox"
    assert reqs_styled[0].prompt == "a fox. In this style: washes"
```

NOTE: check the real constructor signatures of `DocumentSpec` / `PageSpec` / `Region` in `core/layout/models.py` before writing this test — the shapes above are illustrative; use the minimal valid constructors the existing `tests/layout/` files use (copy their fixture helpers).

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest tests/styles/test_layout_style_integration.py -v`
Expected: FAIL — `TypeError: build_requests() got an unexpected keyword argument 'style'`

- [ ] **Step 3: Implement**

`core/layout/batch_fill.py` — extend `build_requests` (`:39`): add the parameter `style=None`, and where the request is built with `prompt=r.prompt` (`:61`), use:

```python
            prompt = r.prompt
            if style is not None:
                from core.styles import apply_style
                prompt = apply_style(prompt, style, "", "").prompt
```
and pass `prompt=prompt` into the request constructor.

`cli/commands/layout.py` — in `run_fill_cmd`, after `model = ...` (`:125`), resolve the style once:

```python
    fill_style = None
    if getattr(args, "style", None):
        from core.styles import StyleStore
        _store = StyleStore()
        fill_style = _store.get_by_name(args.style)
        if fill_style is None:
            names = ", ".join(s.name for s in _store.list_styles()) or "(none)"
            print(f"Error: style not found: {args.style}. Available: {names}")
            return 2
        print(f"Applying style '{fill_style.name}' to region prompts",
              file=sys.stderr)
```
and in the region loop (`:131-137`), where the region's prompt is used for generation, wrap it:

```python
            region_prompt = r.prompt
            if fill_style is not None:
                from core.styles import apply_style
                region_prompt = apply_style(region_prompt, fill_style, "", "").prompt
```
(use `region_prompt` at the generation call; add `import sys` at the top of the file if not present).

- [ ] **Step 4: Run to verify pass**

Run: `$PY -m pytest tests/styles/test_layout_style_integration.py tests/layout/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/layout/batch_fill.py cli/commands/layout.py tests/styles/test_layout_style_integration.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(styles): --style on layout fill and batch requests"
```

---

### Task 17: Docs, full suite, wrap-up

**Files:**
- Modify: `README.md` (feature blurb in the features section), `.claude/skills/imageai-cli/SKILL.md` if present in-repo (the CLI skill — add the style verbs), `AGENTS.md` §11 optional pointer
- Create: `Docs/CustomStyles.md`

- [ ] **Step 1: Write `Docs/CustomStyles.md`** — user-facing doc covering: what a style is (hybrid text + exemplars), creating one in the GUI (Style Manager walkthrough), creating via CLI (`--style-create "Name" --style-images ./refs/`), applying (`--style`, Smart merge checkbox, per-provider behavior table: Google/OpenAI get exemplar refs, Stability/Local SD/video/layout text-only), sharing (`--style-export`/`--style-import`), storage location per platform, and troubleshooting (no API key, missing refs). Follow the tone/structure of existing `Docs/` feature pages.

- [ ] **Step 2: README** — add one feature bullet ("Custom Styles: derive a reusable style from your own images and apply it across providers") in the features list; do NOT touch version numbers (the version-manager tool owns them).

- [ ] **Step 3: CLI skill** — update the in-repo `imageai-cli` skill's flag reference with the styles group (it documents all CLI surfaces; keep format consistent).

- [ ] **Step 4: Full verification**

```bash
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest -q
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -c "import cli.parser, cli.runner, core.styles, gui.styles"
```
Expected: full suite PASS; imports clean.

- [ ] **Step 5: Commit docs**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add Docs/CustomStyles.md README.md AGENTS.md .claude/skills/imageai-cli 2>/dev/null
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "docs(styles): Custom Styles user guide + README/CLI-skill updates"
```

- [ ] **Step 6: Version bump + PR (Leland's house rules)**

Per AGENTS.md: run the version-manager tool (dry-run, then `release minor --notes FILE --apply` with prose notes — this is a feature ⇒ **minor**), in the same commit as the changelog entry; then push the branch and open ONE PR for the whole feature. Update the plan file's task checkboxes and Plans/ status lines as you go (AGENTS.md §5).

---

## Plan Self-Review (done at write time)

- **Spec coverage:** data model §3 → Tasks 1–3; derivation §4 → Tasks 4–5; application §5 → Tasks 6, 10, 14, 15, 16 (all four seams); UI §6 → Tasks 11–13 + 14; CLI §7 → Tasks 7–10; error handling §8 → covered in Tasks 5 (key check), 4 (chunk failure aborts save), 6 (smart fallback, missing refs, ref-limit drops), 7/10 (unknown style exit 2); testing §9 → every task carries its tests. Out-of-scope §10 respected (no LoRA, no negative-prompt consumption, no video refs, legacy video combo untouched).
- **Deviations from spec (deliberate, small):** (1) `--json` output for style verbs deferred — `--style-show` already prints raw JSON and `--style-create` prints the bare id on stdout; a `--json` envelope adds nothing yet. (2) Drag-and-drop onto the refs grid deferred to polish — Add Files/Add Folder covers the flow (spec lists DnD; note it in the PR as a follow-up). (3) Smart merge hidden on the video picker (`show_smart=False`) — scene enhancement already runs per-scene LLM calls.
- **Type consistency check:** `apply_style` signature identical across Tasks 6/10/14/15/16; `StyledRequest.meta` keys consistent (`style_id`, `style_name`, `smart_merge_used`, `exemplars_attached`, `exemplars_dropped`); `derive(paths, progress_cb=None) -> {"descriptor", "prompt_text"}` consistent across Tasks 5/8/13; picker attribute names (`combo`, `smart_check`, `manage_btn`) consistent between Tasks 11 and 12–14.
- **Known line-number drift risk:** anchors like `:5780`, `:6444`, `:1137` are as of 2026-07-26; implementers must re-locate by the quoted surrounding code, not blindly by number.




