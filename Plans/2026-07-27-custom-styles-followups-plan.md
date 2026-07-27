# Custom Styles Follow-ups (Issue #37) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Last Updated:** 2026-07-27 09:20

**Goal:** Close every reviewer-adjudicated follow-up from PR #35 (issue #37): robustness (GUI-thread freeze cap, core/gui decoupling, atomic index write, path-safety guards), consistency (provenance shape, cross-surface picker refresh, dialog polish, drag-and-drop), and the two test-coverage gaps.

**Architecture:** All changes stay inside the existing Custom Styles architecture (`core/styles/` + `gui/styles/` + CLI seams). The one relocation is `LLMResponseParser` moving from `gui/llm_utils.py` to a new `core/llm_parsing.py` (gui re-exports it for back-compat) so no `core/` module imports `gui/`.

**Tech Stack:** Python 3.12 (`.venv_linux`), PySide6 (offscreen in tests), pytest.

## Global Constraints

- No `cd`; absolute paths only (AGENTS.md §6). Repo root: `/mnt/d/Documents/Code/GitHub/ImageAI`.
- Run tests with the Linux venv: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest` (pytest.ini limits collection to `tests/`).
- GUI tests: offscreen — prefix with `QT_QPA_PLATFORM=offscreen`.
- Conventional Commits; never hand-edit version numbers or changelog headings (version-manager tool owns both).
- Branch: `fix/custom-styles-followups` cut from `origin/main`; the plan file is committed in the branch's first commit.
- The `style_applied` sidecar dict shape is: `{"style_id", "style_name", "smart_merge_used", "exemplars_attached", "exemplars_dropped"}` (from `apply_style()` meta, `core/styles/applicator.py:115-117`).

---

### Task 1: Relocate `LLMResponseParser` to core (`core/llm_parsing.py`)

Fixes: PySide6-less CLI `--style-create` fails with misleading `No module named 'PySide6'`. Root cause is `core` importing `gui.llm_utils`; per the systemic-root-cause rule, ALL core importers move over, not just `core/styles`.

**Files:**
- Create: `core/llm_parsing.py`
- Modify: `gui/llm_utils.py` (delete class, re-export from core)
- Modify: `core/styles/analyzer.py:95,133`, `core/styles/applicator.py:89`, `core/prompt_enhancer_llm.py:13`, `core/layout/designer.py:238`, `core/layout/prompt_helper.py:113`
- Test: `tests/styles/test_core_no_gui.py` (new)

**Interfaces:**
- Produces: `core.llm_parsing.LLMResponseParser` — identical static API (`parse_json_response(content, expected_type)`, `extract_text_prompts`, `create_fallback_prompts`). `gui.llm_utils.LLMResponseParser` keeps working as an alias.

- [x] **Step 1: Create `core/llm_parsing.py`** — move the `LLMResponseParser` class verbatim from `gui/llm_utils.py:15-124` with module header:

```python
"""LLM response parsing shared by core pipelines and GUI dialogs.

Lives in core (no Qt imports) so PySide6-less CLI paths — e.g.
--style-create — can use it. gui/llm_utils.py re-exports it for
back-compat with existing dialog imports.
"""
import json
import logging
import re
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class LLMResponseParser:
    ...  # class body verbatim from gui/llm_utils.py:15-124
```

- [x] **Step 2: Slim `gui/llm_utils.py`** — delete the class and the now-unused `import json` / `import re`; add near the top:

```python
from core.llm_parsing import LLMResponseParser  # noqa: F401 — back-compat re-export
```

- [x] **Step 3: Repoint the six core import sites** listed above to `from core.llm_parsing import LLMResponseParser` (they are all function-local imports except `core/prompt_enhancer_llm.py:13`, which is top-level).

- [x] **Step 4: Write the failing test** — `tests/styles/test_core_no_gui.py`:

```python
"""Style pipeline must import and parse without PySide6 (issue #37)."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_style_pipeline_importable_without_pyside6():
    code = (
        "import sys\n"
        "sys.modules['PySide6'] = None\n"  # any 'import PySide6' now raises
        "from core.styles.analyzer import parse_descriptor\n"
        "from core.styles.applicator import apply_style\n"
        "d = parse_descriptor('{\"summary\": \"s\"}')\n"
        "assert d and d['summary'] == 's'\n"
        "print('OK')\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, cwd=REPO)
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout
```

- [x] **Step 5: Run** `.venv_linux/bin/python -m pytest tests/styles/test_core_no_gui.py -v` → PASS (fails before Step 1-3 with ImportError in stderr). Then the full styles dir → PASS.
- [x] **Step 6: Commit** `fix(styles): move LLMResponseParser to core so CLI paths need no PySide6`

### Task 2: StyleStore hardening (atomic index write, `_is_safe_rel` fixes, defensive delete)

**Files:**
- Modify: `core/styles/store.py:29-31` (`_is_safe_rel`), `:56-59` (`_write_index`), `:113-123` (`delete`)
- Test: `tests/styles/test_store.py`

- [x] **Step 1: Write failing tests** (append to `tests/styles/test_store.py`):

```python
def test_write_index_survives_midwrite_failure(tmp_path, monkeypatch):
    store = StyleStore(base_dir=tmp_path)
    store.save(Style(id="a", name="A"))
    original = store.index_path.read_text()
    monkeypatch.setattr("core.styles.store.json.dump",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        store.save(Style(id="b", name="B"))
    assert store.index_path.read_text() == original  # old index intact


def test_is_safe_rel_non_string_entries(tmp_path):
    from core.styles.store import _is_safe_rel
    assert _is_safe_rel(None) is False
    assert _is_safe_rel(7) is False
    assert _is_safe_rel(["refs/a.jpg"]) is False


def test_is_safe_rel_allows_dotdot_inside_filename(tmp_path):
    from core.styles.store import _is_safe_rel
    assert _is_safe_rel("refs/a..b.jpg") is True     # legit filename
    assert _is_safe_rel("refs/..") is False          # traversal
    assert _is_safe_rel("refs/.") is False
    assert _is_safe_rel("refs/../x.jpg") is False    # separator: regex rejects


def test_resolve_refs_skips_non_string_entries(tmp_path):
    store = StyleStore(base_dir=tmp_path)
    s = Style(id="a", name="A", reference_images=[7, "refs/0001.jpg"])
    assert store.resolve_refs(s) == []  # no TypeError; both skipped/missing


def test_delete_unsafe_id_purges_index_without_touching_disk(tmp_path):
    store = StyleStore(base_dir=tmp_path)
    store.save(Style(id="good", name="Good"))
    # inject a malformed record with a traversal id directly into the index
    raw = json.loads(store.index_path.read_text())
    raw["styles"].append({"id": "../evil", "name": "Evil"})
    store.index_path.write_text(json.dumps(raw))
    assert store.delete("../evil") is True        # no ValueError
    assert store.get("good") is not None
    ids = [r["id"] for r in json.loads(store.index_path.read_text())["styles"]]
    assert "../evil" not in ids
```

(`test_store.py` already imports `json`, `pytest`, `Style`, `StyleStore` — verify and add missing imports.)

- [x] **Step 2: Run them** → FAIL (TypeError / corrupted index / ValueError respectively).
- [x] **Step 3: Implement.** In `core/styles/store.py` add `import os` and replace the three functions:

```python
def _is_safe_rel(rel) -> bool:
    """True for 'refs/<plain-basename>' entries — no separators, no traversal.

    Accepts only str (malformed index records may hold ints/lists). '..' is
    fine INSIDE a filename (refs/a..b.jpg); only a whole-segment '.'/'..' is
    traversal, and the regex already rejects further separators.
    """
    if not isinstance(rel, str) or not _SAFE_REL.match(rel):
        return False
    return rel[len("refs/"):] not in (".", "..")
```

```python
    def _write_index(self, records: List[dict]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.index_path.parent / (self.index_path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"styles": records}, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.index_path)  # atomic: never a half-written index
```

```python
    def delete(self, style_id: str) -> bool:
        records = self._read_index()
        kept = [r for r in records if r.get("id") != style_id]
        if len(kept) == len(records):
            return False
        self._write_index(kept)
        if not isinstance(style_id, str) or not _SAFE_ID.match(style_id):
            logger.warning(f"Deleted malformed style record {style_id!r} from "
                           f"index; unsafe id, no directory removed")
            return True
        d = self.style_dir(style_id)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        logger.info(f"Deleted style {style_id}")
        return True
```

- [x] **Step 4: Run** `tests/styles/test_store.py tests/styles/test_store_zip.py -v` → PASS.
- [x] **Step 5: Commit** `fix(styles): atomic styles.json write, non-str/dotdot _is_safe_rel fixes, defensive delete`

### Task 3: Cap smart-merge retries on the GUI seam (UI-freeze fix)

Issue-adjudicated candidate: "cap retries for that one call". The freeze is `analyze_image`'s retry backoff (2s+4s+8s = ~14s worst case, `core/video/prompt_engine.py:1009-1015`). GUI smart merge degrades to plain concat on failure anyway, so the GUI seam gets `max_retries=0`; CLI keeps full retries.

**Files:**
- Modify: `core/video/prompt_engine.py:939-1015` (`analyze_image` gains `max_retries=3` param), `core/styles/analyzer.py:221-257` (`build_completion_fn` gains `max_retries=None`), `core/styles/applicator.py:151-177` (`apply_style_for_surface` passes `max_retries=0`)
- Test: `tests/styles/test_applicator.py`, `tests/styles/test_analyzer_service.py`

**Interfaces:**
- Produces: `build_completion_fn(config, provider=None, model=None, max_retries=None)`; `analyze_image(..., max_retries: int = 3)`. Defaults preserve current behavior everywhere else.

- [x] **Step 1: Write failing tests.** Append to `tests/styles/test_analyzer_service.py`:

```python
def test_analyze_image_forwards_max_retries(monkeypatch):
    from core.video.prompt_engine import UnifiedLLMProvider
    llm = UnifiedLLMProvider({})
    captured = {}

    def fake_retry(func, max_retries=3, **kw):
        captured["max_retries"] = max_retries
        return "ok"

    monkeypatch.setattr(llm, "_retry_with_backoff", fake_retry)
    out = llm.analyze_image(messages=[{"role": "user", "content": "hi"}],
                            model="gpt-4o", max_retries=0)
    assert out == "ok" and captured["max_retries"] == 0
```

Append to `tests/styles/test_applicator.py`:

```python
def test_apply_style_for_surface_caps_smart_merge_retries(monkeypatch):
    from core.styles.applicator import apply_style_for_surface
    captured = {}

    def fake_build(config, provider=None, model=None, max_retries=None):
        captured["max_retries"] = max_retries
        return (lambda messages: '{"prompt": "merged"}'), "openai", "gpt-x"

    monkeypatch.setattr("core.styles.analyzer.build_completion_fn", fake_build)
    style = _style()  # reuse this file's existing Style factory/fixture
    prompt, extra, meta = apply_style_for_surface(
        "a fox", style, "google", "m", smart=True, config=object(),
        store=None, existing_references=None)
    assert captured["max_retries"] == 0
    assert meta["smart_merge_used"] is True and prompt == "merged"
```

(Adapt `_style()` to however `test_applicator.py` builds a Style; keep its conventions.)

- [x] **Step 2: Run** → FAIL (unexpected kwarg `max_retries`).
- [x] **Step 3: Implement.** `analyze_image`: add `max_retries: int = 3` to the signature and pass `max_retries=max_retries` in the `_retry_with_backoff(...)` call (replacing the literal `3`). `build_completion_fn`: add `max_retries=None` param; inside `fn`:

```python
    def fn(messages):
        logger.info(f"Style LLM request -> {full_model} "
                    f"({sum(len(str(m)) for m in messages)} chars)")
        call_kwargs = {"messages": messages, "model": full_model,
                       "max_tokens": 1500}
        if max_retries is not None:
            call_kwargs["max_retries"] = max_retries
        return llm.analyze_image(**call_kwargs)
```

`apply_style_for_surface`: change the build call to
`build_completion_fn(config, max_retries=0)` with a comment: runs on the GUI thread — one transient failure degrades to plain concat instead of freezing the UI for the ~14s retry backoff.

- [x] **Step 4: Run** `tests/styles/ -v` → PASS.
- [x] **Step 5: Commit** `fix(styles): cap GUI smart-merge to a single LLM attempt (no 14s backoff freeze)`

### Task 4: Unify `style_applied` provenance shape (video CLI → dict)

**Files:**
- Modify: `cli/commands/video.py:259-282`
- Modify: `Docs/CustomStyles.md:181` area
- Test: `tests/styles/test_cli_style_video.py:109-126`

- [x] **Step 1: Update the two tests** — in `test_run_video_cmd_adds_style_applied_to_payload` replace the assert with:

```python
    assert data["style_applied"]["style_id"] == "water"
    assert data["style_applied"]["smart_merge_used"] is False
    assert data["style_applied"]["exemplars_attached"] == 0
```

(`test_run_video_cmd_no_style_omits_style_applied` stays as-is.) Run → FAIL (payload is the bare string `"water"`).

- [x] **Step 2: Implement** in `cli/commands/video.py`: initialize `style_meta = None` next to `style = None`; in the style branch capture the full result:

```python
        style = _resolve_style(args)
        if style is not None:
            from core.styles import apply_style
            styled = apply_style(
                getattr(args, "prompt", None) or "", style, "", "")
            args.prompt = styled.prompt
            style_meta = styled.meta
            _emit(f"Applying style '{style.name}' to prompt (text only)")
```

and at payload time replace `payload["style_applied"] = style.id` with `payload["style_applied"] = style_meta` (guard stays `if style is not None:`).

- [x] **Step 3: Update `Docs/CustomStyles.md`** provenance paragraph: state that image sidecars **and** `--video` CLI sidecars record the same `style_applied` block (id/name, smart-merge flag, exemplar counts).
- [x] **Step 4: Run** `tests/styles/test_cli_style_video.py -v` → PASS.
- [x] **Step 5: Commit** `fix(cli): video sidecar style_applied uses the same dict shape as image sidecars`

### Task 5: `_is_safe_rel` guards in Style Manager thumbnail + duplicate paths

**Files:**
- Modify: `gui/styles/style_manager_dialog.py:222-233` (`_on_selected`), `:293-299` (`_on_duplicate`)
- Test: `tests/styles/test_style_manager_dialog.py`

- [x] **Step 1: Write failing test:**

```python
def test_unsafe_ref_entries_are_skipped_in_ui(qapp, store):
    s = store.get("water")
    s.reference_images = ["../../evil.jpg", 7]
    store.save(s)
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(0)          # must not raise
    assert dlg.refs_list.count() == 0        # unsafe entries never listed
    dlg._on_duplicate()                      # must not raise / copy them
    dup = store.get_by_name("Water copy")
    assert dup.reference_images == []
```

- [x] **Step 2: Run** → FAIL (`TypeError` from `base / 7` or the unsafe item appears).
- [x] **Step 3: Implement.** Add `_is_safe_rel` to the `from core.styles.store import ...` line. In `_on_selected`'s loop over `s.reference_images` insert first:

```python
        for rel in s.reference_images:
            if not _is_safe_rel(rel):
                logger.warning(f"Style {s.id}: skipping unsafe reference "
                               f"path {rel!r} in UI")
                continue
```

In `_on_duplicate`'s loop, same guard before `src = self.store.style_dir(s.id) / rel`.

- [x] **Step 4: Run dialog tests** → PASS. **Step 5: Commit** `fix(gui): style manager skips unsafe reference paths in thumbnail/duplicate paths`

### Task 6: Cross-surface picker refresh when the Style Manager closes

**Files:**
- Modify: `gui/styles/style_picker.py`
- Test: `tests/styles/test_style_picker.py`

- [x] **Step 1: Write failing test** (reuse the file's `FakeConfig`; import `Style`, `StyleStore`):

```python
def test_manager_close_refreshes_all_pickers(qapp, tmp_path, monkeypatch):
    from gui.styles.style_picker import StylePickerWidget
    store = StyleStore(base_dir=tmp_path / "styles")
    a = StylePickerWidget(FakeConfig(), "image"); a.set_store(store); a.refresh()
    b = StylePickerWidget(FakeConfig(), "video"); b.set_store(store); b.refresh()

    class FakeDlg:
        def __init__(self, config, store=None, parent=None):
            self._s = store
        def exec(self):
            self._s.save(Style(id="fresh", name="Fresh"))

    monkeypatch.setattr(
        "gui.styles.style_manager_dialog.StyleManagerDialog", FakeDlg)
    a._open_manager()
    assert a.combo.findData("fresh") >= 0
    assert b.combo.findData("fresh") >= 0   # the OTHER picker refreshed too
```

- [x] **Step 2: Run** → FAIL (`b` still lacks "fresh").
- [x] **Step 3: Implement** in `style_picker.py`: add `import weakref`; module-level `_PICKERS = weakref.WeakSet()`; in `__init__` (before the final `self.refresh()`): `_PICKERS.add(self)`; replace `_open_manager`'s tail:

```python
    def _open_manager(self) -> None:
        from gui.styles.style_manager_dialog import StyleManagerDialog
        dlg = StyleManagerDialog(self.config, store=self._store, parent=self)
        dlg.exec()
        for w in list(_PICKERS):
            try:
                w.refresh()   # every surface's picker, not just the opener
            except RuntimeError:
                pass          # underlying C++ widget already deleted
```

- [x] **Step 4: Run** `tests/styles/test_style_picker.py -v` → PASS. **Step 5: Commit** `feat(gui): refresh style pickers on every surface when the Style Manager closes`

### Task 7: Dialog polish (design §6): list thumbnails, geometry + LLM-combo persistence, GUI `source` provenance

**Files:**
- Modify: `gui/styles/style_manager_dialog.py` (`__init__`, `_build_ui`, `_load_styles`, `_on_selected`, `_on_analyze`, `_on_analysis_done`, `_save_current`, `on_dialog_close`)
- Test: `tests/styles/test_style_manager_dialog.py`

- [x] **Step 1: Write failing tests:**

```python
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
```

- [x] **Step 2: Run** → FAIL.
- [x] **Step 3: Implement:**
  - Imports: add `QSize` to the `PySide6.QtCore` import; add `from datetime import datetime`.
  - `_build_ui`: after creating `self.style_list` add `self.style_list.setIconSize(QSize(48, 48))`.
  - `_load_styles` loop, after `item = QListWidgetItem(s.name)`:

```python
            rels = s.exemplars or s.reference_images
            if rels and _is_safe_rel(rels[0]):
                p = self.store.style_dir(s.id) / rels[0]
                if p.exists():
                    item.setIcon(QIcon(QPixmap(str(p)).scaled(
                        48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
```

  - `__init__` after `self._build_ui()`: restore geometry + combos:

```python
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        saved_provider = self.settings.value("llm_provider")
        if saved_provider:
            idx = self.llm_provider_combo.findText(saved_provider)
            if idx >= 0:
                self.llm_provider_combo.setCurrentIndex(idx)
        saved_model = self.settings.value("llm_model")
        if saved_model:
            self.llm_model_combo.setCurrentText(saved_model)
```

  - `on_dialog_close` (end): `self.settings.setValue("geometry", self.saveGeometry())`, `self.settings.setValue("llm_provider", self.llm_provider_combo.currentText())`, `self.settings.setValue("llm_model", self.llm_model_combo.currentText())`.
  - Provenance: `_on_selected` and `_on_analyze` clear `self._pending_source = None` right where `_pending_descriptor` is cleared. `_on_analyze` after the service is constructed: `self._analysis_source = {"provider": service.provider, "model": service.model, "image_count": len(paths)}`. `_on_analysis_done`:

```python
        src = getattr(self, "_analysis_source", None)
        self._pending_source = (
            {**src, "created": datetime.now().strftime("%Y-%m-%d %H:%M")}
            if src else None)
```

  - `_save_current`, inside `if pending:`: also

```python
            if getattr(self, "_pending_source", None):
                s.source = self._pending_source
                self._pending_source = None
```

- [x] **Step 4: Run dialog tests** → PASS. **Step 5: Commit** `feat(gui): style manager polish — list thumbnails, geometry/LLM persistence, source provenance`

### Task 8: Drag-and-drop onto the refs grid

**Files:**
- Modify: `gui/styles/style_manager_dialog.py` (new `_RefsListWidget` + helper; `_build_ui` uses it; `_on_add_folder` reuses the ext set)
- Test: `tests/styles/test_style_manager_dialog.py`

- [x] **Step 1: Write failing tests:**

```python
def test_image_paths_from_mime_filters_to_local_images(qapp, tmp_path):
    from PySide6.QtCore import QMimeData, QUrl
    from gui.styles.style_manager_dialog import _image_paths_from_mime
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path / "a.png")),
                  QUrl.fromLocalFile(str(tmp_path / "b.txt")),
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
```

- [x] **Step 2: Run** → FAIL (no `_image_paths_from_mime` / `files_dropped`).
- [x] **Step 3: Implement.** Module-level, above the dialog class:

```python
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _image_paths_from_mime(mime) -> List[Path]:
    """Local image files in a drag payload, order preserved."""
    if not mime.hasUrls():
        return []
    out = []
    for url in mime.urls():
        if not url.isLocalFile():
            continue
        p = Path(url.toLocalFile())
        if p.suffix.lower() in _IMAGE_EXTS:
            out.append(p)
    return out


class _RefsListWidget(QListWidget):
    """Refs grid that accepts image-file drops from the OS file manager."""
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if _image_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if _image_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        paths = _image_paths_from_mime(event.mimeData())
        if paths:
            event.acceptProposedAction()
            self.files_dropped.emit(paths)
        else:
            super().dropEvent(event)
```

In `_build_ui`: `self.refs_list = _RefsListWidget()`; in the wiring block: `self.refs_list.files_dropped.connect(self._add_paths)`. `_on_add_folder`: replace its inline `exts = {...}` with `_IMAGE_EXTS`.

- [x] **Step 4: Run dialog tests** → PASS. **Step 5: Commit** `feat(gui): drag-and-drop image files onto the Style Manager refs grid`

### Task 9: Coverage gaps — `--batch --style`, live Analyze click, orphan detach on real close

**Files:**
- Test: `tests/styles/test_cli_style_generation.py`, `tests/styles/test_style_manager_dialog.py`

- [x] **Step 1: `--batch` + `--style` test.** In `_fake_provider()` add `prov.submit_batch_job.return_value = "job-123"`. Append:

```python
def test_batch_with_style_is_text_only(tmp_path, capsys):
    """--batch submits the STYLED prompt; exemplars are dropped with a notice."""
    def _add_exemplar(store):
        ex_dir = store.style_dir("water") / "refs"
        ex_dir.mkdir(parents=True)
        (ex_dir / "0001.jpg").write_bytes(b"X")
        s = store.get("water")
        s.reference_images = ["refs/0001.jpg"]
        s.exemplars = ["refs/0001.jpg"]
        store.save(s)

    rc, prov, _ = _run(tmp_path, "--provider", "openai", "-p", "a fox",
                       "--style", "Water", "--batch", setup=_add_exemplar)
    assert rc == 0
    (reqs,) = prov.submit_batch_job.call_args.args
    assert reqs[0]["prompt"] == "a fox. In this style: washes"
    assert "reference_images" not in reqs[0]
    assert "text only" in capsys.readouterr().err
```

- [x] **Step 2: Live Analyze-click + orphan tests.** Append to `test_style_manager_dialog.py`:

```python
class _FakeService:
    provider = "openai"
    model = "gpt-test"

    def __init__(self, config, provider=None, model=None):
        pass

    def derive(self, paths, progress_cb=None):
        if progress_cb:
            progress_cb("chunk 1/1")
        return {"descriptor": {"summary": "derived"}, "prompt_text": "derived text"}


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


def test_analyze_click_end_to_end(qapp, store, tmp_path, monkeypatch):
    """Real button click -> real QThread worker -> UI updated on completion."""
    _seed_ref(store, tmp_path)
    monkeypatch.setattr("core.styles.analyzer.StyleAnalysisService", _FakeService)
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(0)
    dlg.analyze_btn.click()
    assert _wait_until(qapp, lambda: getattr(dlg, "_pending_descriptor", None))
    assert dlg.prompt_text_edit.toPlainText() == "derived text"
    assert dlg.analyze_btn.isEnabled()
    assert dlg._analysis_source["model"] == "gpt-test"


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
    assert w.wait(8000)                      # worker finishes on its own
    assert _wait_until(qapp, lambda: w not in smd._ORPHAN_WORKERS)
```

- [x] **Step 3: Run** the two files → PASS (Task 7 must land first for `_analysis_source`).
- [x] **Step 4: Commit** `test(styles): cover --batch --style, live Analyze flow, and orphan-worker detach`

### Task 10: Full suite, version bump, PR, issue bookkeeping

- [x] **Step 1:** Full suite: `QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest` → must be all green.
- [x] **Step 2:** Version bump via the tool (never hand-edit): dry-run `python3 ~/.claude/skills/version-manager/version_tool.py --repo /mnt/d/Documents/Code/GitHub/ImageAI release minor`, write prose notes to a temp file, then `release minor --notes FILE --apply`; commit as the tool directs.
- [x] **Step 3:** Update this plan file's checkboxes + push branch; open PR titled `fix: Custom Styles post-merge follow-ups (issue #37)` with a body mapping each issue checkbox to its commit; `Closes #37` deliberately omitted — label `test` and comment instead (close after verification per house rules).
- [x] **Step 4:** Comment on issue #37 summarizing what shipped (note the smart-merge fix took the adjudicated "cap retries" candidate; full GenWorker move remains possible later), add label `test`, credit Claude Fable 5.

## Self-Review Notes

- All 13 issue checkboxes are covered: Tasks 3 (freeze), 1 (parser relocation), 2 (atomic write, isinstance, delete, `..` filenames), 5 (thumbnail/duplicate guards), 4 (provenance), 6 (picker refresh), 7 (dialog polish §6), 8 (drag-and-drop), 9 (batch+style, Analyze E2E, orphan detach).
- Type consistency: `_is_safe_rel` stays a module function of `core/styles/store.py`, imported by the dialog (Tasks 5, 7). `build_completion_fn`'s new kwarg is keyword-only-by-convention with default `None` (CLI call sites unchanged).
- Deliberate scope choice: the UI-freeze item takes the issue's "cap retries" candidate rather than the GenWorker relocation — the generation seam (streaming + non-streaming workers) is the riskiest code in the app, and the adjudicated pain is specifically the retry backoff.
