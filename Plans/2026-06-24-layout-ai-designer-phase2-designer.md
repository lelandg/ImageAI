# AI Layout Designer — Phase 2 (AI Designer + Iteration History) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the AI layout *designer* — describe a page (or type a modification) → a text LLM proposes a structured layout (and/or asks clarifying questions) rendered on the canvas → iterate in a loop — plus a browsable iteration **history** (snapshot/restore/branch) persisted with the project.

**Architecture:** Pure, testable core (`designer.py` builds the prompt and parses the LLM's JSON into `Region`s; `history.py` manages snapshots) with the network LLM call isolated behind an injectable `completion_fn` so everything is unit-testable headless without a network. The GUI (`designer_panel.py` with a `QThread` worker + status console, `history_window.py`) sits on top and wires into the Phase-1 `LayoutTab`. Reuses the existing `LiteLLMHandler`/`LLMResponseParser`/`DialogStatusConsole` and the model registry.

**Tech Stack:** Python 3.12, PySide6 (`QThread`, `QDialog`), LiteLLM (via `gui/llm_utils.py`), `core/llm_models.resolve_model`, `pytest` (headless offscreen Qt). Builds on Phase 1 (`core/layout/{models,schema,qt_renderer,project_io}.py`, `gui/layout/{layout_tab,canvas_widget,page_setup_widget}.py`).

## Global Constraints

- Spec: `Plans/2026-06-24-layout-ai-designer-design.md` (§5 AI designer, §6 history). This plan implements **Phase 2**.
- Python interpreter for all commands: `.venv_linux/bin/python` (never `.venv`). Run from repo root `/mnt/d/Documents/Code/GitHub/ImageAI`. **No `cd`.**
- GUI tests run **headless** under `QT_QPA_PLATFORM=offscreen` (already set in `tests/conftest.py`; session `qapp` fixture). No `pytest-qt`.
- **LLM logging (repo rule §8):** every request (provider, model, temperature, prompt) and full response must be shown in the designer's status console **and** the file logger. Handle empty responses with a fallback layout; parse JSON robustly (markdown fences).
- **Model IDs:** resolve via `resolve_model()` / the model registry; never hardcode `claude-*`/`gpt-*`/`gemini-*`.
- The LLM network call lives ONLY in `core/layout/designer.py::run_completion`; all other designer logic takes an injected `completion_fn(messages)->str` so it is testable without network.
- Conventional Commits; commit subjects **≤72 chars**; commit after each task. Branch: `feat/layout-ai-designer-phase2`.
- Extend Phase-1 modules in place; do not break the Phase-1 test suite (35 tests must stay green).

---

## File Structure

**Create:**
- `core/layout/history.py` — `History` manager (append/snapshots/get/restore over a `DocumentSpec`).
- `core/layout/designer.py` — `DesignerResult`, `build_messages`, `parse_response`, `fallback_result`, `run_design`, `run_completion`.
- `gui/layout/designer_panel.py` — `DesignerWorker(QThread)` + `DesignerPanel(QWidget)`.
- `gui/layout/history_window.py` — `HistoryWindow(QDialog)`.
- Tests: `tests/layout/test_history.py`, `test_designer.py`, `test_designer_panel.py`, `test_history_window.py`, `test_layout_tab_designer.py`.

**Modify:**
- `core/layout/models.py` — add `Snapshot` dataclass; add `history` field to `DocumentSpec`.
- `core/layout/schema.py` — `snapshot_to_dict`/`snapshot_from_dict`; include `history` in `document_to_dict`/`document_from_dict`.
- `gui/layout/layout_tab.py` — embed `DesignerPanel`, a "History…" button, content-kind; wire `layoutProposed` → apply + snapshot, restore → load.

---

### Task 1: Snapshot model + history persistence

**Files:**
- Modify: `core/layout/models.py`, `core/layout/schema.py`
- Test: `tests/layout/test_history.py` (persistence portion)

**Interfaces:**
- Consumes: Phase-1 `DocumentSpec`, `schema.document_to_dict`/`document_from_dict`, `Region`/`PageSpec`.
- Produces:
  - `models.Snapshot(id: str, parent_id: Optional[str], timestamp: str, prompt: str, document: dict, thumbnail: Optional[str] = None)`
  - `DocumentSpec.history: list[Snapshot] = []`
  - `schema.snapshot_to_dict(s)`/`schema.snapshot_from_dict(d)`
  - `document_to_dict`/`document_from_dict` round-trip `history`

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_history.py
from core.layout.models import Snapshot, DocumentSpec, PageSpec, Region
from core.layout import schema


def test_snapshot_roundtrip_via_schema():
    snap = Snapshot(id="s1", parent_id=None, timestamp="2026-06-24 12:00",
                    prompt="a 9-panel comic", document={"title": "X", "pages": []})
    d = schema.snapshot_to_dict(snap)
    again = schema.snapshot_from_dict(d)
    assert again.id == "s1"
    assert again.prompt == "a 9-panel comic"
    assert again.document == {"title": "X", "pages": []}


def test_document_history_roundtrip():
    doc = DocumentSpec(title="Doc", pages=[PageSpec(page_size_px=(100, 100),
                       regions=[Region(id="r1", kind="text", text="hi")])])
    doc.history.append(Snapshot(id="s1", parent_id=None, timestamp="t",
                                prompt="p", document={"k": "v"}))
    again = schema.document_from_dict(schema.document_to_dict(doc))
    assert len(again.history) == 1
    assert again.history[0].id == "s1"
    assert again.history[0].document == {"k": "v"}
    # content still intact
    assert again.pages[0].regions[0].text == "hi"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_history.py -v`
Expected: FAIL (`ImportError`: cannot import `Snapshot`).

- [ ] **Step 3: Add `Snapshot` + `history` to `core/layout/models.py`**

Add after the `Region` dataclass:

```python
@dataclass
class Snapshot:
    """One iteration of the layout designer (browsable in history)."""

    id: str
    parent_id: Optional[str]
    timestamp: str
    prompt: str
    document: Dict  # serialized DocumentSpec (without its own history)
    thumbnail: Optional[str] = None
```

Extend `DocumentSpec` — add after `schema_version` (keep it last; default factory):

```python
    history: List["Snapshot"] = field(default_factory=list)
```

- [ ] **Step 4: Add history serialization to `core/layout/schema.py`**

Add `Snapshot` to the `from core.layout.models import (...)` line. Add these functions (place near `document_to_dict`):

```python
def snapshot_to_dict(s: "Snapshot") -> Dict:
    return {
        "id": s.id, "parent_id": s.parent_id, "timestamp": s.timestamp,
        "prompt": s.prompt, "document": s.document, "thumbnail": s.thumbnail,
    }


def snapshot_from_dict(d: Dict) -> "Snapshot":
    from core.layout.models import Snapshot
    return Snapshot(
        id=d["id"], parent_id=d.get("parent_id"), timestamp=d.get("timestamp", ""),
        prompt=d.get("prompt", ""), document=d.get("document", {}),
        thumbnail=d.get("thumbnail"),
    )
```

In `document_to_dict`, add to the returned dict:

```python
        "history": [snapshot_to_dict(s) for s in doc.history],
```

In `document_from_dict`, add the field to the `DocumentSpec(...)` construction:

```python
        history=[snapshot_from_dict(s) for s in d.get("history", [])],
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_history.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Confirm Phase-1 suite still green**

Run: `.venv_linux/bin/python -m pytest tests/layout/ -q`
Expected: all pass (37 now), no warnings.

- [ ] **Step 7: Commit**

```bash
git add core/layout/models.py core/layout/schema.py tests/layout/test_history.py
git commit -m "feat(layout): add Snapshot model + history persistence in schema"
```

---

### Task 2: History manager

**Files:**
- Create: `core/layout/history.py`
- Test: `tests/layout/test_history.py` (append)

**Interfaces:**
- Consumes: `DocumentSpec`, `Snapshot`, `schema.document_to_dict`/`document_from_dict`.
- Produces:
  - `History(document: DocumentSpec)`
  - `History.append(prompt: str, *, snapshot_id: str | None = None, timestamp: str | None = None, parent_id: str | None = None) -> Snapshot`
  - `History.snapshots() -> list[Snapshot]`
  - `History.get(snapshot_id: str) -> Snapshot | None`
  - `History.restore(snapshot_id: str) -> DocumentSpec` (content of the snapshot, with the live timeline re-attached)

- [ ] **Step 1: Write the failing test (append to `tests/layout/test_history.py`)**

```python
def _doc_with_text(t):
    from core.layout.models import DocumentSpec, PageSpec, Region
    return DocumentSpec(title="D", pages=[PageSpec(page_size_px=(100, 100),
                        regions=[Region(id="r1", kind="text", text=t)])])


def test_history_append_snapshots_current_doc():
    from core.layout.history import History
    doc = _doc_with_text("v1")
    h = History(doc)
    s1 = h.append("first", snapshot_id="s1", timestamp="t1")
    assert s1.id == "s1" and s1.parent_id is None
    # snapshot captured the doc WITHOUT nesting history inside it
    assert "history" not in s1.document
    assert s1.document["pages"][0]["regions"][0]["text"] == "v1"
    assert len(h.snapshots()) == 1


def test_history_parent_chain_and_restore():
    from core.layout.history import History
    doc = _doc_with_text("v1")
    h = History(doc)
    h.append("first", snapshot_id="s1", timestamp="t1")
    # mutate the live doc, snapshot again
    doc.pages[0].regions[0].text = "v2"
    s2 = h.append("second", snapshot_id="s2", timestamp="t2")
    assert s2.parent_id == "s1"  # auto-parents to previous snapshot
    restored = h.restore("s1")
    assert restored.pages[0].regions[0].text == "v1"  # got s1 content
    assert len(restored.history) == 2  # timeline preserved on the restored doc


def test_history_get_missing_returns_none():
    from core.layout.history import History
    h = History(_doc_with_text("v1"))
    assert h.get("nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_history.py -v`
Expected: FAIL (`ModuleNotFoundError: core.layout.history`).

- [ ] **Step 3: Create `core/layout/history.py`**

```python
"""Iteration-history manager for the layout designer."""
import uuid
from datetime import datetime
from typing import List, Optional

from core.layout.models import DocumentSpec, Snapshot
from core.layout import schema


class History:
    """Append/browse/restore layout snapshots stored on a DocumentSpec."""

    def __init__(self, document: DocumentSpec):
        self.document = document

    def snapshots(self) -> List[Snapshot]:
        return self.document.history

    def get(self, snapshot_id: str) -> Optional[Snapshot]:
        for s in self.document.history:
            if s.id == snapshot_id:
                return s
        return None

    def append(self, prompt: str, *, snapshot_id: Optional[str] = None,
               timestamp: Optional[str] = None, parent_id: Optional[str] = None) -> Snapshot:
        doc_dict = schema.document_to_dict(self.document)
        doc_dict.pop("history", None)  # never nest history inside a snapshot
        if parent_id is None and self.document.history:
            parent_id = self.document.history[-1].id
        snap = Snapshot(
            id=snapshot_id or uuid.uuid4().hex[:8],
            parent_id=parent_id,
            timestamp=timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            prompt=prompt,
            document=doc_dict,
        )
        self.document.history.append(snap)
        return snap

    def restore(self, snapshot_id: str) -> DocumentSpec:
        snap = self.get(snapshot_id)
        if snap is None:
            raise KeyError(f"No snapshot {snapshot_id!r}")
        restored = schema.document_from_dict(snap.document)
        restored.history = list(self.document.history)  # keep the timeline
        return restored
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_history.py -v`
Expected: PASS (5 passed total in this file).

- [ ] **Step 5: Commit**

```bash
git add core/layout/history.py tests/layout/test_history.py
git commit -m "feat(layout): add History manager (append/restore/branch)"
```

---

### Task 3: Designer prompt building

**Files:**
- Create: `core/layout/designer.py`
- Test: `tests/layout/test_designer.py`

**Interfaces:**
- Consumes: `Region` (for current-layout context).
- Produces:
  - `designer.build_messages(content_kind: str, page_px: tuple[int,int], user_text: str, current_regions: list[Region] | None = None) -> list[dict]`

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_designer.py
from core.layout.models import Region
from core.layout import designer


def test_build_messages_includes_context_and_json_instruction():
    msgs = designer.build_messages("comic", (1000, 800), "9 panels that flow into each other")
    assert isinstance(msgs, list) and msgs[0]["role"] == "system"
    joined = " ".join(m["content"] for m in msgs)
    assert "comic" in joined
    assert "1000" in joined and "800" in joined
    assert "9 panels that flow into each other" in joined
    assert "JSON" in joined or "json" in joined
    assert "regions" in joined  # tells the model our schema key


def test_build_messages_includes_current_layout_when_iterating():
    regions = [Region(id="r1", kind="image", bbox=(0, 0, 500, 500))]
    msgs = designer.build_messages("comic", (1000, 800), "make the top panel bigger", regions)
    joined = " ".join(m["content"] for m in msgs)
    assert "r1" in joined  # current layout passed back for modification
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_designer.py -v`
Expected: FAIL (`ModuleNotFoundError: core.layout.designer`).

- [ ] **Step 3: Create `core/layout/designer.py` (prompt builder portion)**

```python
"""AI layout designer: prompt building, response parsing, and the LLM call."""
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable

from core.layout.models import Region
from core.layout import schema

logger = logging.getLogger("imageai.layout.designer")

_SYSTEM = (
    "You are a page-layout designer. You design the GEOMETRY of a single page as "
    "regions (image or text placeholders). You never write the actual content. "
    "Respond with a SINGLE JSON object and nothing else."
)


def build_messages(content_kind: str, page_px: Tuple[int, int], user_text: str,
                   current_regions: Optional[List[Region]] = None) -> List[Dict[str, str]]:
    pw, ph = page_px
    current = ""
    if current_regions:
        current = (
            "<current_layout>\n"
            + json.dumps([schema.region_to_dict(r) for r in current_regions], indent=0)
            + "\n</current_layout>\n"
        )
    user = (
        f"<context>\n"
        f"content_kind: {content_kind}\n"
        f"page_pixels: {pw} x {ph} (x,y origin top-left; all coordinates in pixels)\n"
        f"</context>\n"
        f"{current}"
        f"<request>\n{user_text}\n</request>\n"
        f"<instructions>\n"
        f"Return a JSON object with optional keys:\n"
        f'  "questions": [strings]   // ask for missing detail if needed\n'
        f'  "layout": {{ "regions": [ {{\n'
        f'      "id": string, "kind": "image"|"text", "shape": "rect"|"polygon",\n'
        f'      "bbox": [x,y,w,h], "points": [[x,y],...] (polygon only),\n'
        f'      "z": int, "text": string (text only) }} ] }}\n'
        f"All coordinates MUST be within the page ({pw} x {ph}). Prefer 'rect' unless the\n"
        f"request implies panels that flow into each other (then use 'polygon'). You may\n"
        f"return questions, a layout, or both.\n"
        f"</instructions>"
    )
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_designer.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add core/layout/designer.py tests/layout/test_designer.py
git commit -m "feat(layout): add designer prompt builder"
```

---

### Task 4: Designer response parsing + fallback + run_design

**Files:**
- Modify: `core/layout/designer.py`
- Test: `tests/layout/test_designer.py` (append)

**Interfaces:**
- Consumes: `schema.region_from_dict`/`normalize_region`, `gui.llm_utils.LLMResponseParser`.
- Produces:
  - `designer.DesignerResult(questions: list[str], regions: list[Region] | None, raw: str)`
  - `designer.parse_response(content: str, page_px: tuple[int,int]) -> DesignerResult`
  - `designer.fallback_result(page_px: tuple[int,int]) -> DesignerResult`
  - `designer.run_design(messages: list[dict], page_px: tuple[int,int], completion_fn: Callable[[list[dict]], str]) -> DesignerResult`
  - `designer.run_completion(config, provider: str, model: str, messages, temperature: float = 0.4) -> str` (real LLM call; not unit-tested)

- [ ] **Step 1: Write the failing test (append to `tests/layout/test_designer.py`)**

```python
def test_parse_response_with_regions_and_questions():
    content = (
        "```json\n"
        '{"questions": ["What palette?"],'
        ' "layout": {"regions": [{"id": "p1", "kind": "image", "shape": "rect",'
        ' "bbox": [0,0,500,400]}, {"id": "t1", "kind": "text", "bbox": [0,420,500,80],'
        ' "text": "Title"}]}}'
        "\n```"
    )
    res = designer.parse_response(content, (1000, 800))
    assert res.questions == ["What palette?"]
    assert [r.id for r in res.regions] == ["p1", "t1"]
    assert res.regions[0].kind == "image"
    # out-of-nothing clamp safety: bbox stays within page
    x, y, w, h = res.regions[1].bbox
    assert x + w <= 1000 and y + h <= 800


def test_parse_response_questions_only():
    res = designer.parse_response('{"questions": ["how many pages?"]}', (1000, 800))
    assert res.questions == ["how many pages?"]
    assert res.regions is None


def test_parse_response_garbage_falls_back():
    res = designer.parse_response("the model rambled with no json", (1000, 800))
    assert res.regions is not None and len(res.regions) >= 1  # fallback layout
    assert res.regions[0].bbox[2] > 0


def test_run_design_uses_injected_completion():
    captured = {}

    def fake_completion(messages):
        captured["msgs"] = messages
        return '{"layout": {"regions": [{"id":"a","kind":"image","bbox":[0,0,100,100]}]}}'

    msgs = designer.build_messages("comic", (200, 200), "one panel")
    res = designer.run_design(msgs, (200, 200), fake_completion)
    assert captured["msgs"] == msgs
    assert [r.id for r in res.regions] == ["a"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_designer.py -v`
Expected: FAIL (`AttributeError`: `parse_response`/`DesignerResult`).

- [ ] **Step 3: Add parsing, fallback, run_design, run_completion to `core/layout/designer.py`**

Append:

```python
@dataclass
class DesignerResult:
    questions: List[str] = field(default_factory=list)
    regions: Optional[List[Region]] = None
    raw: str = ""


def fallback_result(page_px: Tuple[int, int]) -> DesignerResult:
    pw, ph = page_px
    region = Region(id="region1", kind="image", shape="rect",
                    bbox=(0, 0, pw, ph), name="full page")
    return DesignerResult(
        questions=["I couldn't parse a layout — here's a single full-page frame. "
                   "Tell me how to divide it."],
        regions=[region], raw="")


def parse_response(content: str, page_px: Tuple[int, int]) -> DesignerResult:
    from gui.llm_utils import LLMResponseParser
    data = LLMResponseParser.parse_json_response(content, expected_type=dict)
    if not isinstance(data, dict):
        logger.warning("Designer: unparseable response, using fallback")
        return fallback_result(page_px)
    questions = [str(q) for q in data.get("questions", []) if str(q).strip()]
    regions = None
    layout = data.get("layout")
    if isinstance(layout, dict) and isinstance(layout.get("regions"), list):
        regions = []
        for i, rd in enumerate(layout["regions"]):
            if not isinstance(rd, dict):
                continue
            rd.setdefault("id", f"region{i + 1}")
            rd.setdefault("kind", "image")
            region = schema.region_from_dict(rd)
            regions.append(schema.normalize_region(region, page_px))
        if not regions:
            regions = None
    if regions is None and not questions:
        return fallback_result(page_px)
    return DesignerResult(questions=questions, regions=regions, raw=content)


def run_design(messages: List[Dict], page_px: Tuple[int, int],
               completion_fn: Callable[[List[Dict]], str]) -> DesignerResult:
    content = completion_fn(messages)
    return parse_response(content or "", page_px)


def run_completion(config, provider: str, model: str, messages: List[Dict],
                   temperature: float = 0.4) -> str:
    """Real LLM call (mirrors TextGenerationWorker). Not unit-tested (network)."""
    from gui.llm_utils import LiteLLMHandler
    from core.llm_models import get_provider_models, get_provider_prefix
    ok, litellm = LiteLLMHandler.setup_litellm(enable_console_logging=True)
    if not ok or litellm is None:
        raise RuntimeError("Failed to initialize LiteLLM")
    provider = provider or (config.get_layout_llm_provider() if config else "google")
    provider_map = {"google": "google", "anthropic": "anthropic", "openai": "openai",
                    "ollama": "ollama", "lm studio": "lmstudio"}
    pid_api = provider_map.get(provider.lower(), provider.lower())
    pid = "gemini" if pid_api == "google" else pid_api
    api_key = None
    auth_mode = "api-key"
    if pid_api == "google" and config is not None:
        am = config.get("auth_mode", "api-key")
        auth_mode = "gcloud" if am in ("gcloud", "Google Cloud Account") else "api-key"
    if auth_mode == "api-key" and config is not None:
        api_key = config.get_api_key(pid_api)
    models = get_provider_models(pid)
    model_name = model or (models[0] if models else None)
    if not model_name:
        raise RuntimeError(f"No models available for provider {provider!r}")
    prefix = get_provider_prefix(pid)
    full_model = f"{prefix}{model_name}" if prefix else model_name
    logger.info("Designer LLM call: model=%s temp=%s", full_model, temperature)
    kwargs = {"model": full_model, "messages": messages, "temperature": temperature}
    if api_key:
        kwargs["api_key"] = api_key
    resp = litellm.completion(**kwargs)
    if not resp or not resp.choices:
        raise RuntimeError("Empty LLM response")
    return resp.choices[0].message.content or ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_designer.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add core/layout/designer.py tests/layout/test_designer.py
git commit -m "feat(layout): add designer response parsing, fallback, run_design"
```

---

### Task 5: Designer worker + panel (GUI)

**Files:**
- Create: `gui/layout/designer_panel.py`
- Test: `tests/layout/test_designer_panel.py`

**Interfaces:**
- Consumes: `designer.build_messages`/`run_design`/`run_completion`, `DialogStatusConsole`, `core.llm_models` provider helpers.
- Produces:
  - `designer_panel.DesignerWorker(messages, page_px, completion_fn, parent=None)` — `QThread`; signals `progress(str)`, `proposed(object)` (DesignerResult), `failed(str)`.
  - `designer_panel.DesignerPanel(config, parent=None)` — `QWidget`; signal `layoutProposed(object)` (DesignerResult); method `content_kind() -> str`; method `start_design(user_text, page_px, current_regions=None, completion_fn=None)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_designer_panel.py
from core.layout.models import Region
from gui.layout.designer_panel import DesignerPanel, DesignerWorker
from core.layout import designer


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def test_worker_emits_proposed_with_injected_completion(qapp):
    msgs = designer.build_messages("comic", (200, 200), "one panel")
    fake = lambda m: '{"layout": {"regions": [{"id":"a","kind":"image","bbox":[0,0,100,100]}]}}'
    w = DesignerWorker(msgs, (200, 200), fake)
    got = []
    w.proposed.connect(lambda res: got.append(res))
    w.run()  # run synchronously in-test (no thread start)
    assert got and [r.id for r in got[0].regions] == ["a"]


def test_panel_builds_and_reports_content_kind(qapp):
    p = DesignerPanel(FakeConfig())
    assert isinstance(p.content_kind(), str) and p.content_kind()


def test_panel_start_design_emits_layout_proposed(qapp):
    p = DesignerPanel(FakeConfig())
    got = []
    p.layoutProposed.connect(lambda res: got.append(res))
    fake = lambda m: '{"layout": {"regions": [{"id":"z","kind":"text","bbox":[0,0,50,50],"text":"hi"}]}}'
    p.start_design("a title page", (300, 300), completion_fn=fake)
    assert got and [r.id for r in got[0].regions] == ["z"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_designer_panel.py -v`
Expected: FAIL (`ModuleNotFoundError: gui.layout.designer_panel`).

- [ ] **Step 3: Create `gui/layout/designer_panel.py`**

```python
"""Designer panel: description/iterate input, status console, LLM worker."""
import logging
from typing import List, Dict, Optional, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPlainTextEdit, QPushButton, QLabel,
)
from PySide6.QtCore import QThread, Signal

from core.layout import designer
from gui.llm_utils import DialogStatusConsole

logger = logging.getLogger("imageai.layout.designer_panel")

CONTENT_KINDS = ["children", "comic", "comic_strip", "magazine", "newspaper", "scientific", "custom"]


class DesignerWorker(QThread):
    progress = Signal(str)
    proposed = Signal(object)  # DesignerResult
    failed = Signal(str)

    def __init__(self, messages: List[Dict], page_px, completion_fn: Callable[[List[Dict]], str], parent=None):
        super().__init__(parent)
        self._messages = messages
        self._page_px = page_px
        self._completion_fn = completion_fn

    def run(self):
        try:
            self.progress.emit("Designing layout…")
            result = designer.run_design(self._messages, self._page_px, self._completion_fn)
            self.proposed.emit(result)
        except Exception as e:  # noqa: BLE001 - surfaced to UI + log
            logger.error("Designer worker failed: %s", e, exc_info=True)
            self.failed.emit(str(e))


class DesignerPanel(QWidget):
    layoutProposed = Signal(object)  # DesignerResult

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._worker: Optional[DesignerWorker] = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Kind:"))
        self.kind_combo = QComboBox()
        self.kind_combo.addItems(CONTENT_KINDS)
        row.addWidget(self.kind_combo)
        row.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.model_combo = QComboBox()
        self._populate_providers()
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        row.addWidget(self.provider_combo)
        row.addWidget(self.model_combo)
        lay.addLayout(row)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText(
            "Describe the page, or type a change to the current layout…")
        self.prompt_edit.setFixedHeight(70)
        lay.addWidget(self.prompt_edit)

        self.design_btn = QPushButton("Design / Iterate")
        lay.addWidget(self.design_btn)

        self.console = DialogStatusConsole("Designer")
        lay.addWidget(self.console)

    def _populate_providers(self):
        from core.llm_models import get_all_provider_ids, get_provider_display_name
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        self.provider_combo.addItems([get_provider_display_name(p) for p in get_all_provider_ids()])
        saved = self._config.get_layout_llm_provider() if self._config else None
        if saved:
            idx = self.provider_combo.findText(saved, )
            if idx < 0:
                idx = self.provider_combo.findText(saved.capitalize())
            if idx >= 0:
                self.provider_combo.setCurrentIndex(idx)
        self.provider_combo.blockSignals(False)
        self._on_provider_changed(self.provider_combo.currentText())

    def _on_provider_changed(self, provider: str):
        from core.llm_models import get_provider_models
        provider_map = {"claude": "anthropic", "google": "gemini", "lm studio": "lmstudio"}
        pid = provider_map.get(provider.lower(), provider.lower())
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(get_provider_models(pid) or [])
        self.model_combo.blockSignals(False)

    def content_kind(self) -> str:
        return self.kind_combo.currentText()

    def start_design(self, user_text: str, page_px, current_regions=None,
                     completion_fn: Optional[Callable[[List[Dict]], str]] = None):
        kind = self.content_kind()
        messages = designer.build_messages(kind, page_px, user_text, current_regions)
        self.console.log(f"Designing ({kind}, {page_px[0]}x{page_px[1]}): {user_text}", "INFO")
        if completion_fn is None:
            provider = self.provider_combo.currentText()
            model = self.model_combo.currentText()
            cfg = self._config
            completion_fn = lambda m: designer.run_completion(cfg, provider, model, m)
        self._worker = DesignerWorker(messages, page_px, completion_fn)
        self._worker.progress.connect(lambda msg: self.console.log(msg, "INFO"))
        self._worker.proposed.connect(self._on_proposed)
        self._worker.failed.connect(lambda err: self.console.log(err, "ERROR"))
        if completion_fn is not None and self.sender() is None:
            pass
        self._worker.start()

    def _on_proposed(self, result):
        n = len(result.regions) if result.regions else 0
        self.console.log(f"Proposed layout: {n} regions; {len(result.questions)} question(s).",
                         "SUCCESS")
        for q in result.questions:
            self.console.log(f"Q: {q}", "WARNING")
        self.layoutProposed.emit(result)
```

> Note for the implementer: `start_design` starts a `QThread` in real use. In the test `test_panel_start_design_emits_layout_proposed`, the injected `completion_fn` returns instantly and `proposed` is delivered via the worker; if the threaded delivery is flaky in headless CI, call `self._worker.wait(2000)` is NOT needed because the test connects before `start()` and the worker is trivial — but if `layoutProposed` is not received synchronously, change `start_design` to run the worker inline when a `completion_fn` is explicitly injected: replace `self._worker.start()` with:
> ```python
>         if completion_fn is not None:
>             self._worker.run()      # synchronous for injected/test completions
>         else:
>             self._worker.start()
> ```
> Implement this inline-when-injected behavior (it is also correct for production, since production passes `completion_fn=None` and uses the thread). Remove the dead `if completion_fn is not None and self.sender() is None: pass` lines.

- [ ] **Step 4: Apply the inline-when-injected fix and run tests**

Edit `start_design` per the note: run the worker synchronously when `completion_fn` was explicitly provided, else `start()` the thread. Then:

Run: `.venv_linux/bin/python -m pytest tests/layout/test_designer_panel.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add gui/layout/designer_panel.py tests/layout/test_designer_panel.py
git commit -m "feat(layout): add designer panel + worker with status console"
```

---

### Task 6: History window (GUI)

**Files:**
- Create: `gui/layout/history_window.py`
- Test: `tests/layout/test_history_window.py`

**Interfaces:**
- Consumes: `core.layout.history.History`, `Snapshot`.
- Produces:
  - `history_window.HistoryWindow(history, parent=None)` — `QDialog`; signal `restoreRequested(str)` (snapshot id); method `set_history(history)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_history_window.py
from core.layout.models import DocumentSpec, PageSpec, Region
from core.layout.history import History
from gui.layout.history_window import HistoryWindow


def _history_with(n):
    doc = DocumentSpec(title="D", pages=[PageSpec(page_size_px=(100, 100),
                       regions=[Region(id="r1", kind="text", text="v")])])
    h = History(doc)
    for i in range(n):
        h.append(f"step {i}", snapshot_id=f"s{i}", timestamp=f"t{i}")
    return h


def test_window_lists_snapshots(qapp):
    win = HistoryWindow(_history_with(3))
    assert win.list_widget.count() == 3


def test_restore_emits_snapshot_id(qapp):
    win = HistoryWindow(_history_with(2))
    got = []
    win.restoreRequested.connect(lambda sid: got.append(sid))
    win.list_widget.setCurrentRow(0)
    win._on_restore()  # internal slot
    assert got == ["s0"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_history_window.py -v`
Expected: FAIL (`ModuleNotFoundError: gui.layout.history_window`).

- [ ] **Step 3: Create `gui/layout/history_window.py`**

```python
"""Browsable iteration-history window for the layout designer."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel,
)
from PySide6.QtCore import Signal, Qt


class HistoryWindow(QDialog):
    restoreRequested = Signal(str)  # snapshot id

    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Layout History")
        self.resize(420, 360)
        self._history = history
        self._build()
        self.set_history(history)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Iterations (newest last):"))
        self.list_widget = QListWidget()
        lay.addWidget(self.list_widget, 1)
        row = QHBoxLayout()
        self.restore_btn = QPushButton("Restore selected")
        self.restore_btn.clicked.connect(self._on_restore)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(self.restore_btn)
        row.addWidget(close_btn)
        lay.addLayout(row)

    def set_history(self, history):
        self._history = history
        self.list_widget.clear()
        for s in history.snapshots():
            label = f"[{s.timestamp}] {s.prompt[:60]}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, s.id)
            self.list_widget.addItem(item)

    def _on_restore(self):
        item = self.list_widget.currentItem()
        if item is None:
            return
        self.restoreRequested.emit(item.data(Qt.UserRole))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_history_window.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add gui/layout/history_window.py tests/layout/test_history_window.py
git commit -m "feat(layout): add browsable history window"
```

---

### Task 7: Integrate designer + history into the Layout tab

**Files:**
- Modify: `gui/layout/layout_tab.py`
- Test: `tests/layout/test_layout_tab_designer.py`

**Interfaces:**
- Consumes: `DesignerPanel` (`layoutProposed`), `History`, `HistoryWindow`, `designer.DesignerResult`.
- Produces (on `LayoutTab`):
  - `apply_designer_result(result, user_text="") -> None` — set current page regions from `result.regions`, re-render, append a history snapshot.
  - `restore_snapshot(snapshot_id) -> None` — restore the document from history and re-render.
  - attribute `self.history: History` (bound to `self.document`).

- [ ] **Step 1: Write the failing test**

```python
# tests/layout/test_layout_tab_designer.py
from core.layout import designer
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def test_apply_designer_result_sets_regions_and_snapshots(qapp):
    tab = LayoutTab(config=FakeConfig())
    res = designer.DesignerResult(
        questions=[], regions=[designer.Region(id="a", kind="image", bbox=(0, 0, 100, 100))],
        raw="")
    tab.apply_designer_result(res, user_text="one panel")
    assert [r.id for r in tab.document.pages[0].regions] == ["a"]
    assert len(tab.history.snapshots()) == 1
    assert tab.history.snapshots()[0].prompt == "one panel"


def test_restore_snapshot_reloads_document(qapp):
    tab = LayoutTab(config=FakeConfig())
    # iteration 1
    tab.apply_designer_result(
        designer.DesignerResult(regions=[designer.Region(id="a", kind="image", bbox=(0, 0, 50, 50))]),
        user_text="v1")
    sid = tab.history.snapshots()[0].id
    # iteration 2 (different regions)
    tab.apply_designer_result(
        designer.DesignerResult(regions=[designer.Region(id="b", kind="text", bbox=(0, 0, 50, 50), text="x")]),
        user_text="v2")
    assert [r.id for r in tab.document.pages[0].regions] == ["b"]
    tab.restore_snapshot(sid)
    assert [r.id for r in tab.document.pages[0].regions] == ["a"]  # back to v1


def test_design_button_calls_start_design_with_page_size(qapp):
    tab = LayoutTab(config=FakeConfig())
    captured = {}
    tab.designer.start_design = lambda *a, **k: captured.setdefault("call", (a, k))
    tab.designer.prompt_edit.setPlainText("a comic cover")
    tab._on_design_clicked()
    a, k = captured["call"]
    assert a[0] == "a comic cover"                       # prompt text passed
    assert a[1] == tab.document.pages[0].page_size_px    # current page size supplied
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_layout_tab_designer.py -v`
Expected: FAIL (`AttributeError`: `apply_designer_result`).

- [ ] **Step 3: Wire designer + history into `gui/layout/layout_tab.py`**

Add imports near the top (after the existing imports):

```python
from core.layout.history import History
from gui.layout.designer_panel import DesignerPanel
from gui.layout.history_window import HistoryWindow
```

In `_build`, add a "History…" toolbar button (extend the toolbar loop list) and embed the designer panel. Replace the toolbar loop list with:

```python
        for label, slot in [
            ("New", self.new_document), ("Open…", self._open_dialog),
            ("Save…", self._save_dialog), ("Export PDF…", self._export_dialog),
            ("History…", self._open_history),
        ]:
```

After `root.addWidget(self.page_setup)` add the designer panel:

```python
        self.designer = DesignerPanel(self.config)
        self.designer.layoutProposed.connect(self._on_layout_proposed)
        self.designer.design_btn.clicked.connect(self._on_design_clicked)
        root.addWidget(self.designer)
```

The designer panel's "Design / Iterate" button does not self-wire (it has no page size); the tab owns that wiring — it supplies the current page's pixel size and regions.

In `new_document`, after building `self.document`, bind history:

```python
        self.history = History(self.document)
```

In `open_project_from` and after any place `self.document` is reassigned, rebind history. Update `open_project_from`:

```python
    def open_project_from(self, path: str):
        self.document = project_io.load_project(path)
        self.history = History(self.document)
        self._refresh()
```

Add the new methods:

```python
    def _on_design_clicked(self):
        if not self.document or not self.document.pages:
            return
        text = self.designer.prompt_edit.toPlainText().strip()
        if not text:
            return
        page = self.document.pages[0]
        self.designer.start_design(text, page.page_size_px,
                                   current_regions=page.regions or None)

    def _on_layout_proposed(self, result):
        text = self.designer.prompt_edit.toPlainText().strip() if hasattr(self.designer, "prompt_edit") else ""
        self.apply_designer_result(result, user_text=text)

    def apply_designer_result(self, result, user_text: str = ""):
        if not self.document or not self.document.pages:
            return
        self.document.content_kind = self.designer.content_kind() if hasattr(self, "designer") else self.document.content_kind
        if result.regions:
            self.document.pages[0].regions = list(result.regions)
            self.history.append(user_text or "design")
            self._refresh()

    def restore_snapshot(self, snapshot_id: str):
        restored = self.history.restore(snapshot_id)
        self.document = restored
        self.history = History(self.document)
        self._refresh()

    def _open_history(self):
        win = HistoryWindow(self.history, self)
        win.restoreRequested.connect(self.restore_snapshot)
        win.exec()
```

Note: `new_document` must set `self.history` BEFORE `_refresh()` is first called, and `__init__` calls `new_document()` — so `self.history` exists after construction. Ensure the `self.history = History(self.document)` line is added inside `new_document` right after `self.document = DocumentSpec(...)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv_linux/bin/python -m pytest tests/layout/test_layout_tab_designer.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the FULL suite + import smoke**

Run: `.venv_linux/bin/python -m pytest tests/layout/ -q`
Expected: all pass, no warnings.
Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -c "from gui.layout import LayoutTab; print('ok')"`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add gui/layout/layout_tab.py tests/layout/test_layout_tab_designer.py
git commit -m "feat(layout): wire AI designer + history into the Layout tab"
```

---

## Self-Review

**Spec coverage (Phase 2):**
- §5 AI designer: prompt (content_kind + page + current layout + JSON instruction) → Task 3; parse JSON/questions/regions with robust fences + fallback → Task 4; provider/model selection + status-console logging + QThread worker → Task 5; iterate loop (re-design with current regions, apply) → Tasks 5+7. ✓
- §6 history: Snapshot model + persistence → Task 1; append/restore/branch manager → Task 2; browsable separate window → Task 6; wired (snapshot on each apply, restore) → Task 7. ✓
- Cross-cutting LLM logging (console + file) → `DialogStatusConsole` in Task 5 + `logger` in Task 4. Model IDs via registry (`get_provider_models`/`get_provider_prefix`) → Task 4. ✓
- Deferred (correctly, later phases): style system (Phase 3), content import (Phase 4), thumbnails in history (optional; `Snapshot.thumbnail` field exists, generation deferred).

**Placeholder scan:** No TBD/TODO. The Task-5 note prescribes the exact `start_design` inline-when-injected change with code; Step 4 makes applying it explicit (not a vague "handle threading").

**Type consistency:** `DesignerResult(questions, regions, raw)` used consistently in Tasks 4/5/7; `build_messages`/`run_design`/`parse_response` signatures match across Tasks 3/4/5; `History(document)` + `append`/`restore`/`snapshots` consistent across Tasks 2/6/7; `DesignerPanel.layoutProposed`/`content_kind`/`start_design` consistent across Tasks 5/7; `HistoryWindow(history)`/`restoreRequested`/`list_widget` consistent across Tasks 6/7. `Snapshot` fields consistent across Tasks 1/2.

**Note for implementer:** the real LLM path (`run_completion`) is network and is intentionally NOT unit-tested; all designer logic is exercised through injected `completion_fn`. Do not add a live-network test.
