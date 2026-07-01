# Gemini Omni Flash Docs Parity Implementation Plan

> **Status: ✅ COMPLETE (2026-07-01)** — all 8 tasks implemented and reviewed; suite 472 green; shipped as PR #33. Execution ledger: `.superpowers/sdd/progress.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring ImageAI's Gemini Omni video integration to full parity with the official docs (https://ai.google.dev/gemini-api/docs/omni): multiple reference images, uploaded-video editing, explicit `video_config.task`, `delivery="uri"`, CLI conversational refinement, and prompt-feature documentation.

**Architecture:** All API-shape changes land in `core/video/omni_client.py` (`OmniGenerationConfig` builds the `interactions.create` kwargs; `OmniClient` handles upload/poll/download). The CLI layer (`cli/parser.py`, `cli/commands/video.py`) maps new flags onto the config. Existing GUI callers keep working unchanged via back-compat (`reference_image` folds into the new `reference_images` list).

**Tech Stack:** Python 3.12 (`.venv_linux`), `google-genai>=2.9.0` Interactions API, pytest (all tests mock the SDK — no network).

## Global Constraints

- Python interpreter for all test runs: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python` (never `.venv` from WSL).
- Never `cd`; use absolute paths (`git -C /mnt/d/Documents/Code/GitHub/ImageAI ...`).
- Aspect ratio and task are NEVER embedded in prompt text (AGENTS.md §9).
- Model IDs are resolved via `resolve_model()` — never hardcode new ones (AGENTS.md §8).
- Log every request detail sent to the LLM (AGENTS.md §8).
- Conventional Commits; suite must be green before every commit.
- Existing tests in `tests/video/` must keep passing — the documented request shape asserted there (dict `response_format`, content-list input) is load-bearing.
- Full suite gate: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests -q` (440+ tests; must be green).

## Documented API shapes being implemented (from the official docs, verbatim patterns)

```python
# Multi-reference (reference_to_video): several image items, then text
input=[
    {"type": "image", "data": cat_b64, "mime_type": "image/png"},
    {"type": "image", "data": yarn_b64, "mime_type": "image/png"},
    {"type": "text", "text": "A cat playfully batting at a ball of yarn."},
]

# Edit an uploaded video: Files API upload -> document item by URI
video_file = client.files.upload(file="Video.mp4")   # poll PROCESSING -> ACTIVE
input=[
    {"type": "document", "uri": video_file.uri},
    {"type": "text", "text": "make the mirror ripple like liquid"},
]

# Explicit task
generation_config={"video_config": {"task": "image_to_video"}}

# URI delivery
response_format={"type": "video", "delivery": "uri"}
```

---

### Task 1: Multiple reference images (`reference_images`) with task inference

**Files:**
- Modify: `core/video/omni_client.py` (dataclass `OmniGenerationConfig`, ~lines 74–137; `OmniClient.MODEL_CONSTRAINTS` ~line 156; `OmniClient.validate_config` ~line 187)
- Test: `tests/video/test_omni_client.py`

**Interfaces:**
- Consumes: existing `OmniGenerationConfig` fields.
- Produces: `OmniGenerationConfig.reference_images: List[Path]` (canonical), `reference_image: Optional[Path]` kept as back-compat input that folds into the list; task auto-inferred when `task=""` (new default): `previous_interaction_id → "edit"`, `≥2 refs → "reference_to_video"`, `1 ref → "image_to_video"`, else `"text_to_video"`. `MODEL_CONSTRAINTS["max_reference_images"] == 3`.

- [ ] **Step 1: Write the failing tests** — append to `tests/video/test_omni_client.py`:

```python
# --- Multi-reference images (reference_to_video) -----------------------------

def _write_png(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"\x89PNG\r\n\x1a\nfakepng-" + name.encode())
    return p


def test_multiple_reference_images_build_content_list(tmp_path):
    cat = _write_png(tmp_path, "cat.png")
    yarn = _write_png(tmp_path, "yarn.png")
    cfg = OmniGenerationConfig(prompt="A cat playfully batting at a ball of yarn.",
                               reference_images=[cat, yarn])
    kw = cfg.to_interaction_kwargs()
    # Documented shape: N image items followed by exactly one text item.
    assert [item["type"] for item in kw["input"]] == ["image", "image", "text"]
    assert kw["input"][2]["text"] == "A cat playfully batting at a ball of yarn."
    # Two subject references => reference_to_video (inferred).
    assert cfg.task == "reference_to_video"


def test_single_reference_image_infers_image_to_video(tmp_path):
    ref = _write_png(tmp_path, "ref.png")
    cfg = OmniGenerationConfig(prompt="make it move", reference_images=[ref])
    assert cfg.task == "image_to_video"


def test_legacy_reference_image_folds_into_list(tmp_path):
    ref = _write_png(tmp_path, "ref.png")
    cfg = OmniGenerationConfig(prompt="go", task="image_to_video", reference_image=ref)
    assert cfg.reference_images == [ref]
    kw = cfg.to_interaction_kwargs()
    assert [item["type"] for item in kw["input"]] == ["image", "text"]


def test_too_many_reference_images_rejected(tmp_path):
    refs = [_write_png(tmp_path, f"r{i}.png") for i in range(4)]
    with pytest.raises(ValueError, match="reference image"):
        OmniGenerationConfig(prompt="x", reference_images=refs)


def test_previous_interaction_id_infers_edit_task():
    cfg = OmniGenerationConfig(prompt="make the violin invisible",
                               previous_interaction_id="int_prev")
    assert cfg.task == "edit"


def test_validate_config_checks_all_reference_images_exist(tmp_path):
    ok = _write_png(tmp_path, "ok.png")
    missing = tmp_path / "missing.png"
    cfg = OmniGenerationConfig(prompt="x", reference_images=[ok])
    cfg.reference_images.append(missing)  # bypass __post_init__ to hit validate_config
    client = OmniClient(api_key="test-key")
    is_valid, error = client.validate_config(cfg)
    assert is_valid is False
    assert "missing.png" in error
```

- [ ] **Step 2: Run to verify they fail**

Run: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/test_omni_client.py -v -k "reference_images or infers or too_many or folds"`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'reference_images'` (and similar).

- [ ] **Step 3: Implement** — in `core/video/omni_client.py`:

Add `List` to the typing import:

```python
from typing import Any, Dict, List, Optional, Tuple
```

Replace the `OmniGenerationConfig` dataclass fields and `__post_init__` (keep `to_interaction_kwargs` mostly, shown fully in this step so the file is consistent):

```python
@dataclass
class OmniGenerationConfig:
    """Configuration for a Gemini Omni video generation/edit request."""

    prompt: str = ""
    model: str = ""  # Resolved Omni model ID; defaults via __post_init__.
    aspect_ratio: str = "16:9"  # "16:9" (landscape) or "9:16" (portrait).
    reference_image: Optional[Path] = None  # Back-compat single ref; folds into reference_images.
    reference_images: List[Path] = field(default_factory=list)  # Subject/first-frame refs.
    previous_interaction_id: Optional[str] = None  # Chain a conversational edit.
    # Task sent as generation_config.video_config.task; inferred when left "".
    task: str = ""

    def __post_init__(self):
        if not self.model:
            self.model = OmniModel.default_id()

        if self.reference_image is not None and not self.reference_images:
            self.reference_images = [Path(self.reference_image)]
        self.reference_images = [Path(p) for p in self.reference_images]

        max_refs = OmniClient.MODEL_CONSTRAINTS["max_reference_images"]
        if len(self.reference_images) > max_refs:
            raise ValueError(
                f"Gemini Omni supports at most {max_refs} reference image(s); "
                f"got {len(self.reference_images)}."
            )

        if not self.task:
            self.task = self._infer_task()

        if self.aspect_ratio not in OmniClient.MODEL_CONSTRAINTS["aspect_ratios"]:
            raise ValueError(
                f"aspect_ratio {self.aspect_ratio!r} not supported by Gemini Omni. "
                f"Use one of {OmniClient.MODEL_CONSTRAINTS['aspect_ratios']}."
            )

        valid_tasks = OmniClient.MODEL_CONSTRAINTS["tasks"]
        if self.task not in valid_tasks:
            raise ValueError(f"task {self.task!r} invalid. Use one of {valid_tasks}.")

        # image_to_video / reference_to_video require a reference image.
        if self.task in ("image_to_video", "reference_to_video") and not self.reference_images:
            raise ValueError(
                f"task {self.task!r} requires a reference_image, but none was provided."
            )

    def _infer_task(self) -> str:
        """Infer the video_config task from the input shape (docs task enum)."""
        if self.previous_interaction_id:
            return "edit"
        if len(self.reference_images) >= 2:
            return "reference_to_video"
        if self.reference_images:
            return "image_to_video"
        return "text_to_video"

    def to_interaction_kwargs(self) -> Dict[str, Any]:
        """Build the kwargs for ``client.interactions.create(**kwargs)``.

        Matches the documented Gemini Omni request shape: video output and
        aspect ratio are requested via ``response_format={"type": "video",
        "aspect_ratio": ...}`` (a dict). The aspect ratio is never placed in the
        prompt text (AGENTS.md §9). With reference images, ``input`` is a content
        list ``[{image}, ..., {text}]``; otherwise it is the plain prompt string.
        """
        content: List[Dict[str, Any]] = []
        for ref in self.reference_images:
            image_bytes = Path(ref).read_bytes()
            b64 = base64.b64encode(image_bytes).decode("ascii")
            mime = _IMAGE_MIME_BY_SUFFIX.get(Path(ref).suffix.lower(), "image/png")
            content.append({"type": "image", "data": b64, "mime_type": mime})

        if content:
            content.append({"type": "text", "text": self.prompt})
            input_payload: Any = content
        else:
            input_payload = self.prompt

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "input": input_payload,
            "response_format": {"type": "video", "aspect_ratio": self.aspect_ratio},
        }
        if self.previous_interaction_id:
            kwargs["previous_interaction_id"] = self.previous_interaction_id
        return kwargs
```

Add to `OmniClient.MODEL_CONSTRAINTS` (after `"tasks"`):

```python
        "max_reference_images": 3,  # Docs show multi-subject refs (<IMAGE_REF_N>, N=0..2).
```

Update `validate_config`'s reference-image check to cover the list:

```python
        for ref in (config.reference_images or []):
            if not Path(ref).exists():
                return False, f"Reference image not found: {ref}"
```

(replace the old single `config.reference_image` check).

- [ ] **Step 4: Run the Omni test file — all tests pass (old + new)**

Run: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/test_omni_client.py -v`
Expected: PASS (all, including pre-existing `test_image_to_video_builds_content_list`).

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/video/omni_client.py tests/video/test_omni_client.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(video): support multiple Omni reference images (reference_to_video)"
```

---

### Task 2: Explicit `generation_config.video_config.task`

**Files:**
- Modify: `core/video/omni_client.py` (`to_interaction_kwargs`)
- Test: `tests/video/test_omni_client.py`

**Interfaces:**
- Consumes: `OmniGenerationConfig.task` (Task 1 inference).
- Produces: every `interactions.create` call includes `generation_config={"video_config": {"task": <task>}}`.

- [ ] **Step 1: Write the failing tests** — append:

```python
# --- Explicit generation_config.video_config.task ----------------------------

def test_task_sent_in_generation_config_text_to_video():
    cfg = OmniGenerationConfig(prompt="a sunset")
    kw = cfg.to_interaction_kwargs()
    assert kw["generation_config"] == {"video_config": {"task": "text_to_video"}}


def test_task_sent_in_generation_config_reference_to_video(tmp_path):
    refs = [_write_png(tmp_path, f"s{i}.png") for i in range(2)]
    cfg = OmniGenerationConfig(prompt="together in a park", reference_images=refs)
    kw = cfg.to_interaction_kwargs()
    # Disambiguates subject references from a first-frame image (identical
    # input shapes otherwise).
    assert kw["generation_config"]["video_config"]["task"] == "reference_to_video"
```

- [ ] **Step 2: Run to verify they fail**

Run: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/test_omni_client.py -v -k generation_config`
Expected: FAIL with `KeyError: 'generation_config'`.

- [ ] **Step 3: Implement** — in `to_interaction_kwargs`, add to the `kwargs` dict right after `"response_format"`:

```python
            "generation_config": {"video_config": {"task": self.task}},
```

- [ ] **Step 4: Run the Omni test file**

Run: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/test_omni_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/video/omni_client.py tests/video/test_omni_client.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(video): send explicit video_config.task in Omni requests"
```

---

### Task 3: `delivery="uri"` request option

**Files:**
- Modify: `core/video/omni_client.py` (`OmniGenerationConfig` field + validation + `to_interaction_kwargs`; `MODEL_CONSTRAINTS`)
- Test: `tests/video/test_omni_client.py`

**Interfaces:**
- Consumes: existing URI-download path (`_download_uri`) — already handles a returned URI.
- Produces: `OmniGenerationConfig.delivery: Optional[str]` (`None`/`"inline"`/`"uri"`); when `"uri"`, `response_format` gains `"delivery": "uri"`. `MODEL_CONSTRAINTS["deliveries"] == ["inline", "uri"]`.

- [ ] **Step 1: Write the failing tests** — append:

```python
# --- delivery="uri" -----------------------------------------------------------

def test_delivery_uri_in_response_format():
    cfg = OmniGenerationConfig(prompt="a sunset", delivery="uri")
    kw = cfg.to_interaction_kwargs()
    assert kw["response_format"] == {
        "type": "video", "aspect_ratio": "16:9", "delivery": "uri"
    }


def test_delivery_default_omits_key():
    cfg = OmniGenerationConfig(prompt="a sunset")
    assert "delivery" not in cfg.to_interaction_kwargs()["response_format"]


def test_delivery_inline_omits_key():
    cfg = OmniGenerationConfig(prompt="a sunset", delivery="inline")
    assert "delivery" not in cfg.to_interaction_kwargs()["response_format"]


def test_invalid_delivery_rejected():
    with pytest.raises(ValueError, match="delivery"):
        OmniGenerationConfig(prompt="x", delivery="carrier-pigeon")
```

- [ ] **Step 2: Run to verify they fail**

Run: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/test_omni_client.py -v -k delivery`
Expected: FAIL — unexpected keyword argument `delivery`.

- [ ] **Step 3: Implement**

Add the field to `OmniGenerationConfig` (after `previous_interaction_id`):

```python
    delivery: Optional[str] = None  # None/"inline" (base64) or "uri" (Files API; big clips).
```

Add validation at the end of `__post_init__`:

```python
        if self.delivery not in (None, "inline", "uri"):
            raise ValueError(
                f"delivery {self.delivery!r} invalid. Use 'inline' or 'uri'."
            )
```

In `to_interaction_kwargs`, build `response_format` as a variable:

```python
        response_format: Dict[str, Any] = {
            "type": "video", "aspect_ratio": self.aspect_ratio
        }
        if self.delivery == "uri":
            # Docs recommend URI delivery for clips over ~4MB / higher res.
            response_format["delivery"] = "uri"
```

and use it in `kwargs` (`"response_format": response_format,`).

Add to `MODEL_CONSTRAINTS` after `"max_reference_images"`:

```python
        "deliveries": ["inline", "uri"],
```

- [ ] **Step 4: Run the Omni test file**

Run: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/test_omni_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/video/omni_client.py tests/video/test_omni_client.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(video): support Omni delivery=uri response format"
```

---

### Task 4: Edit uploaded videos (Files API `document` input)

**Files:**
- Modify: `core/video/omni_client.py` (`OmniGenerationConfig` field/validation, `to_interaction_kwargs(video_uri=...)`, `OmniClient.generate_video_async`, new `OmniClient._upload_video`, `validate_config`)
- Test: `tests/video/test_omni_client.py`

**Interfaces:**
- Consumes: Task 1's content-list builder.
- Produces: `OmniGenerationConfig.input_video: Optional[Path]`; `to_interaction_kwargs(video_uri: Optional[str] = None)` (document item first, then images, then text); `OmniClient._upload_video(path: Path) -> str` (async; uploads, polls `PROCESSING`→`ACTIVE`, returns `file.uri`, raises `RuntimeError` on `FAILED`/timeout). `input_video` implies task `"edit"`.

- [ ] **Step 1: Write the failing tests** — append:

```python
# --- Edit uploaded videos (Files API document input) --------------------------

def test_input_video_infers_edit_task(tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(MP4_BYTES)
    cfg = OmniGenerationConfig(prompt="make the mirror ripple", input_video=vid)
    assert cfg.task == "edit"


def test_document_uri_first_in_content_list(tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(MP4_BYTES)
    cfg = OmniGenerationConfig(prompt="make the mirror ripple", input_video=vid)
    kw = cfg.to_interaction_kwargs(video_uri="https://files.example/files/abc123")
    assert kw["input"][0] == {"type": "document",
                              "uri": "https://files.example/files/abc123"}
    assert kw["input"][-1] == {"type": "text", "text": "make the mirror ripple"}
    assert kw["generation_config"]["video_config"]["task"] == "edit"


def test_generate_uploads_input_video_then_creates(tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(MP4_BYTES)
    b64 = base64.b64encode(MP4_BYTES).decode("ascii")
    interaction = _FakeInteraction(output_video=_FakeVideoContent(data=b64))
    client = _make_client(interaction)

    uploaded = pytypes.SimpleNamespace(
        name="files/upload1", uri="https://files.example/files/upload1",
        state=pytypes.SimpleNamespace(name="ACTIVE"),
    )
    upload_calls = []

    def _upload(file):
        upload_calls.append(file)
        return uploaded

    client.client.files = pytypes.SimpleNamespace(
        upload=_upload, get=lambda name: uploaded, download=lambda file: MP4_BYTES,
    )
    client.polling_interval = 0

    out = tmp_path / "out.mp4"
    cfg = OmniGenerationConfig(prompt="ripple the mirror", input_video=vid)
    result = client.generate_video(cfg, out)

    assert result.success is True
    assert upload_calls == [str(vid)]
    sent = client.client.interactions.create_calls[0]
    assert sent["input"][0] == {"type": "document",
                                "uri": "https://files.example/files/upload1"}


def test_generate_fails_cleanly_if_upload_fails(tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(MP4_BYTES)
    interaction = _FakeInteraction()
    client = _make_client(interaction)
    failed = pytypes.SimpleNamespace(
        name="files/upload1", uri=None, state=pytypes.SimpleNamespace(name="FAILED"),
    )
    client.client.files = pytypes.SimpleNamespace(
        upload=lambda file: failed, get=lambda name: failed,
        download=lambda file: MP4_BYTES,
    )
    client.polling_interval = 0

    cfg = OmniGenerationConfig(prompt="ripple", input_video=vid)
    result = client.generate_video(cfg, tmp_path / "out.mp4")

    assert result.success is False
    assert "upload" in result.error.lower() or "failed" in result.error.lower()
    assert client.client.interactions.create_calls == []  # never created


def test_validate_config_checks_input_video_exists(tmp_path):
    cfg = OmniGenerationConfig(prompt="x")
    cfg.input_video = tmp_path / "missing.mp4"  # bypass __post_init__
    client = OmniClient(api_key="test-key")
    is_valid, error = client.validate_config(cfg)
    assert is_valid is False
    assert "missing.mp4" in error
```

- [ ] **Step 2: Run to verify they fail**

Run: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/test_omni_client.py -v -k "input_video or document_uri or upload"`
Expected: FAIL — unexpected keyword argument `input_video`.

- [ ] **Step 3: Implement**

Field (after `reference_images`):

```python
    input_video: Optional[Path] = None  # Existing video to edit (uploaded via Files API).
```

`_infer_task` gains the video branch (before the `previous_interaction_id` check order doesn't matter — both mean edit):

```python
        if self.input_video is not None or self.previous_interaction_id:
            return "edit"
```

Validation in `__post_init__` (after the task checks):

```python
        if self.task == "edit" and not (self.previous_interaction_id or self.input_video):
            raise ValueError(
                "task 'edit' requires previous_interaction_id or input_video."
            )
```

`to_interaction_kwargs` signature and content list:

```python
    def to_interaction_kwargs(self, video_uri: Optional[str] = None) -> Dict[str, Any]:
```

and at the top of the content build (before the reference-image loop):

```python
        content: List[Dict[str, Any]] = []
        if video_uri:
            # Uploaded video to edit — documented as a "document" item by URI.
            content.append({"type": "document", "uri": video_uri})
```

New helper on `OmniClient` (place after `_await_terminal`); module-level state reader next to `_IMAGE_MIME_BY_SUFFIX`:

```python
def _file_state(f: Any) -> Optional[str]:
    """Files-API state as a string ('PROCESSING'/'ACTIVE'/'FAILED')."""
    state = getattr(f, "state", None)
    return getattr(state, "name", None) or (str(state) if state else None)
```

```python
    async def _upload_video(self, path: Path) -> str:
        """Upload a video via the Files API and wait until it is ACTIVE.

        Returns the file URI to reference as a ``document`` input item.
        Raises RuntimeError if processing fails or times out.
        """
        self.logger.info(f"Uploading video for Omni edit: {path}")
        video_file = await asyncio.to_thread(self.client.files.upload, file=str(path))
        deadline = time.time() + self.timeout
        while _file_state(video_file) == "PROCESSING" and time.time() < deadline:
            await asyncio.sleep(self.polling_interval)
            video_file = await asyncio.to_thread(
                self.client.files.get, name=video_file.name
            )
        state = _file_state(video_file)
        if state != "ACTIVE":
            raise RuntimeError(
                f"Files API upload of {path} did not become ACTIVE (state={state})."
            )
        self.logger.info(f"Omni edit video uploaded: {video_file.uri}")
        return video_file.uri
```

In `generate_video_async`, replace `kwargs = config.to_interaction_kwargs()` with:

```python
            video_uri = None
            if config.input_video is not None:
                video_uri = await self._upload_video(Path(config.input_video))
            kwargs = config.to_interaction_kwargs(video_uri=video_uri)
```

(the surrounding `try` already converts the `RuntimeError` into a failed result; log line for the request should also mention `input_video={config.input_video}`).

`validate_config` addition:

```python
        if config.input_video is not None and not Path(config.input_video).exists():
            return False, f"Input video not found: {config.input_video}"
```

- [ ] **Step 4: Run the Omni test file**

Run: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/test_omni_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/video/omni_client.py tests/video/test_omni_client.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(video): edit uploaded videos with Omni via Files API document input"
```

---

### Task 5: CLI — multi-ref cap and `--delivery` for Omni

**Files:**
- Modify: `cli/parser.py` (video group, ~line 230–271), `cli/commands/video.py` (`OMNI_MAX_REFS`, `build_omni_config`, `build_veo_config`)
- Test: `tests/video/test_cli_video_config.py`, `tests/video/test_cli_video_parser.py`

**Interfaces:**
- Consumes: Task 1's `reference_images`, Task 3's `delivery`.
- Produces: `--ref-image` accepted up to 3 for Omni; new arg `--delivery {inline,uri}` (dest `delivery`, Omni-only — Veo rejects it).

- [ ] **Step 1: Write the failing tests**

Append to `tests/video/test_cli_video_config.py` (this file uses a `_ns(**kw)` / namespace helper — match its existing style; check the top of the file and reuse its args factory):

```python
def test_omni_accepts_three_refs(tmp_path):
    refs = []
    for i in range(3):
        p = tmp_path / f"r{i}.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        refs.append(str(p))
    cfg = build_omni_config(_ns(prompt="together", ref_image=refs))
    assert len(cfg.reference_images) == 3
    assert cfg.task == "reference_to_video"


def test_omni_rejects_four_refs(tmp_path):
    refs = [str(tmp_path / f"r{i}.png") for i in range(4)]
    with pytest.raises(VideoCliError, match="3"):
        build_omni_config(_ns(prompt="x", ref_image=refs))


def test_omni_delivery_uri_passthrough():
    cfg = build_omni_config(_ns(prompt="a sunset", delivery="uri"))
    assert cfg.delivery == "uri"


def test_veo_rejects_delivery():
    with pytest.raises(VideoCliError, match="omni"):
        build_veo_config(_ns(prompt="x", delivery="uri"))
```

(Adjust the old `test_omni_rejects_two_refs` — it asserted the 1-ref cap that this task removes: replace it with the 3-ref cap tests above, i.e. delete `test_omni_rejects_two_refs`.)

Append to `tests/video/test_cli_video_parser.py` inside/alongside `test_video_flags_parse` style:

```python
def test_delivery_flag_parses():
    from cli.parser import build_parser
    args = build_parser().parse_args(
        ["--video", "-p", "x", "--video-provider", "omni", "--delivery", "uri"]
    )
    assert args.delivery == "uri"
```

- [ ] **Step 2: Run to verify they fail**

Run: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/test_cli_video_config.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/test_cli_video_parser.py -v`
Expected: new tests FAIL (old 1-ref cap message / unknown `--delivery`).

- [ ] **Step 3: Implement**

`cli/parser.py` — update the `--ref-image` help and add `--delivery` after `--extend`:

```python
    video_group.add_argument(
        "--ref-image",
        action="append",
        metavar="PATH",
        help="Reference image (repeatable; omni: up to 3, veo: up to 3)",
    )
```

```python
    video_group.add_argument(
        "--delivery",
        choices=["inline", "uri"],
        help="Omni only: video delivery ('uri' recommended for large/720p clips)",
    )
```

`cli/commands/video.py`:

```python
OMNI_MAX_REFS = 3
```

`build_omni_config` — replace the single-ref mapping:

```python
    kwargs = dict(
        prompt=getattr(args, "prompt", None) or "",
        aspect_ratio=getattr(args, "aspect", None) or "16:9",
    )
    if getattr(args, "video_model", None):
        kwargs["model"] = args.video_model
    if refs:
        kwargs["reference_images"] = refs
    if getattr(args, "delivery", None):
        kwargs["delivery"] = args.delivery
```

(the explicit `task=` mapping is dropped — `OmniGenerationConfig` now infers it).

`build_veo_config` — add the guard at the top (with the existing ones — mirror how `build_omni_config` rejects `--extend`):

```python
    if getattr(args, "delivery", None):
        raise VideoCliError("--delivery is only supported with --video-provider omni.")
```

- [ ] **Step 4: Run the CLI video tests**

Run: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli/parser.py cli/commands/video.py tests/video/test_cli_video_config.py tests/video/test_cli_video_parser.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(cli): omni multi-ref images (up to 3) and --delivery flag"
```

---

### Task 6: CLI — `--refine-from` and `--edit-video` (Omni conversational edit)

**Files:**
- Modify: `cli/parser.py` (video group), `cli/commands/video.py` (`build_omni_config`, `build_veo_config`)
- Test: `tests/video/test_cli_video_config.py`, `tests/video/test_cli_video_parser.py`

**Interfaces:**
- Consumes: Task 1/4 config fields (`previous_interaction_id`, `input_video`).
- Produces: `--refine-from INTERACTION_ID` (dest `refine_from`) → `previous_interaction_id`; `--edit-video PATH` (dest `edit_video`) → `input_video`. Both Omni-only. The interaction id needed by `--refine-from` is already emitted as `operation_id` in the CLI's JSON output/sidecar.

- [ ] **Step 1: Write the failing tests**

Append to `tests/video/test_cli_video_config.py`:

```python
def test_omni_refine_from_maps_to_previous_interaction():
    cfg = build_omni_config(_ns(prompt="make the violin invisible",
                                refine_from="int_abc123"))
    assert cfg.previous_interaction_id == "int_abc123"
    assert cfg.task == "edit"


def test_omni_edit_video_maps_to_input_video(tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
    cfg = build_omni_config(_ns(prompt="ripple the mirror", edit_video=str(vid)))
    assert cfg.input_video == vid
    assert cfg.task == "edit"


def test_omni_edit_video_missing_file_errors(tmp_path):
    with pytest.raises(VideoCliError, match="not found"):
        build_omni_config(_ns(prompt="x", edit_video=str(tmp_path / "nope.mp4")))


def test_veo_rejects_refine_from():
    with pytest.raises(VideoCliError, match="omni"):
        build_veo_config(_ns(prompt="x", refine_from="int_abc"))


def test_veo_rejects_edit_video():
    with pytest.raises(VideoCliError, match="omni"):
        build_veo_config(_ns(prompt="x", edit_video="clip.mp4"))
```

Append to `tests/video/test_cli_video_parser.py`:

```python
def test_refine_and_edit_video_flags_parse():
    from cli.parser import build_parser
    args = build_parser().parse_args(
        ["--video", "-p", "x", "--video-provider", "omni",
         "--refine-from", "int_1", "--edit-video", "clip.mp4"]
    )
    assert args.refine_from == "int_1"
    assert args.edit_video == "clip.mp4"
```

- [ ] **Step 2: Run to verify they fail**

Run: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video -v -k "refine or edit_video"`
Expected: FAIL (unknown args / missing mapping).

- [ ] **Step 3: Implement**

`cli/parser.py` — add after `--delivery`:

```python
    video_group.add_argument(
        "--refine-from",
        metavar="INTERACTION_ID",
        help="Omni only: conversationally refine a previous generation "
             "(interaction id = 'operation_id' in the JSON sidecar)",
    )
    video_group.add_argument(
        "--edit-video",
        metavar="PATH",
        help="Omni only: upload this video and edit it with the prompt",
    )
```

`cli/commands/video.py` — in `build_omni_config` after the `delivery` mapping:

```python
    if getattr(args, "refine_from", None):
        kwargs["previous_interaction_id"] = args.refine_from
    if getattr(args, "edit_video", None):
        vid = Path(args.edit_video).expanduser()
        if not vid.exists():
            raise VideoCliError(f"--edit-video video not found: {vid}")
        kwargs["input_video"] = vid
```

`build_veo_config` — guards next to the `--delivery` one:

```python
    if getattr(args, "refine_from", None):
        raise VideoCliError("--refine-from is only supported with --video-provider omni.")
    if getattr(args, "edit_video", None):
        raise VideoCliError("--edit-video is only supported with --video-provider omni.")
```

- [ ] **Step 4: Run the video test directory**

Run: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli/parser.py cli/commands/video.py tests/video/test_cli_video_config.py tests/video/test_cli_video_parser.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(cli): omni --refine-from and --edit-video conversational editing"
```

---

### Task 7: Documentation — prompt-level Omni features + new flags

**Files:**
- Modify: `.claude/skills/imageai-cli/SKILL.md` (add a Video section — it currently covers images only)
- Modify: `Docs/ImageAI-CLI-Guide.md` (video section ~lines 260–310 and flag table ~line 459; update ref cap, add new flags, add prompt-features subsection)

**Interfaces:**
- Consumes: flags from Tasks 5–6.
- Produces: docs only; no code.

- [ ] **Step 1: Add a "Video generation" section to `.claude/skills/imageai-cli/SKILL.md`** (before any closing/keys section, matching the file's tone):

```markdown
## Video generation (`--video`)

Two providers: `--video-provider omni` (Gemini Omni, conversational, audio
baked in) and `veo` (default). Reuses `-p/--prompt` and `-o/--out`.

```bash
# Omni text-to-video (16:9 default; audio auto-generated)
python main.py --video --video-provider omni -p "a marble run, smooth shot" -o marble.mp4

# Subject references (up to 3 images; Omni infers reference_to_video)
python main.py --video --video-provider omni -p "the cat bats the yarn ball" \
    --ref-image cat.png --ref-image yarn.png -o cat.mp4

# Conversationally refine the previous clip (id = operation_id in the sidecar)
python main.py --video --video-provider omni --refine-from int_abc123 \
    -p "make the violin invisible" -o v2.mp4

# Edit your own footage (uploads via the Files API first)
python main.py --video --video-provider omni --edit-video input.mp4 \
    -p "make the mirror ripple like liquid" -o edited.mp4

# Large/720p clips: ask for URI delivery
python main.py --video --video-provider omni --delivery uri -p "city timelapse" -o city.mp4
```

### Omni prompt superpowers (in the prompt text, not flags)

- **Image roles**: `<FIRST_FRAME>` (start frame) vs `<IMAGE_REF_N>` (subject refs,
  N=0,1,2); declare with `[# Sources <FIRST_FRAME>@Image1]`.
- **Timing**: natural language ("after 3 seconds, ...") or timecodes
  (`[0-3s] a woman enters`, "every 2s cut to a new angle").
- **Audio direction**: describe music/sound design in the prompt — Omni
  soundtracks every clip by default.
- **On-screen text**: Omni renders readable/animated text ("a neon sign that
  reads OPEN").
- Aspect ratio goes in `--aspect` (16:9 or 9:16), **never** in the prompt.

Omni does **not** support: video extension (`--extend` is Veo-only), video
references > 3s, negative-prompt configs, temperature/system instructions.
```

- [ ] **Step 2: Update `Docs/ImageAI-CLI-Guide.md`**

- In the video examples (~line 275): change `# Reference images (Veo up to 3; Omni 1)` to `# Reference images (up to 3 for both providers; 2+ on Omni = subject references)`.
- Add the four new example commands (refine, edit-video, delivery) mirroring the SKILL.md block above.
- In the capability table (~line 292): update the Omni column — reference images `up to 3`, add rows `Conversational refine (--refine-from)` = Omni only, `Edit uploaded video (--edit-video)` = Omni only, `URI delivery (--delivery uri)` = Omni only.
- In the flag table (~line 459): add `--refine-from`, `--edit-video`, `--delivery` rows with the same one-line help as the parser.
- Add the same "Omni prompt superpowers" subsection (role tags, timecodes, audio, text rendering, limitations).

- [ ] **Step 3: Verify docs render and no code changed**

Run: `git -C /mnt/d/Documents/Code/GitHub/ImageAI diff --stat`
Expected: only `.claude/skills/imageai-cli/SKILL.md` and `Docs/ImageAI-CLI-Guide.md`.

- [ ] **Step 4: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add .claude/skills/imageai-cli/SKILL.md Docs/ImageAI-CLI-Guide.md
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "docs(video): document Omni prompt features and new CLI flags"
```

Note: `Docs/ImageAI-CLI-Guide.md` is currently untracked — this commit tracks it. If that's undesired, flag it to Leland instead of committing it silently... it documents shipped CLI features, so tracking it is the expected outcome.

---

### Task 8: Version bump + full-suite gate

**Files:**
- Modify: `core/constants.py:9` (`VERSION = "0.39.0"` → `"0.40.0"`), `README.md` (version display + changelog entry — see `.claude/VERSION_LOCATIONS.md` for the authoritative list)

- [ ] **Step 1: Bump version per `.claude/VERSION_LOCATIONS.md`**

`core/constants.py`:

```python
VERSION = "0.40.0"
```

`README.md`: update the displayed version and add a changelog entry:

```markdown
### v0.40.0 (2026-07-01)
- Gemini Omni docs parity: multiple reference images (reference_to_video),
  edit uploaded videos (Files API), explicit video_config.task, delivery=uri.
- CLI: `--refine-from` (conversational refine), `--edit-video`, `--delivery`;
  `--ref-image` now up to 3 for Omni.
```

(Read `.claude/VERSION_LOCATIONS.md` first and update every listed location.)

- [ ] **Step 2: Run the FULL suite**

Run: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests -q`
Expected: all pass (440 baseline + ~20 new), 0 failures.

- [ ] **Step 3: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/constants.py README.md
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "chore: bump version to 0.40.0 (Omni docs parity)"
```

---

## Out of scope (deliberate)

- **GUI multi-ref / edit-video pickers** — GUI keeps its current single seed-frame flow; it works unchanged through the `reference_image` back-compat field. A follow-up issue can add multi-ref pickers and an "edit this clip file" action.
- **`store`/`background`/`stream` flags** — docs list them as perf tweaks; `store=false` would break the Refine flow, so defaults stay. Not exposed.
- **Video extension** — unsupported by Omni per docs; CLI already rejects `--extend` for Omni.

## Self-review notes

- Spec coverage: gap 1 → Task 1, gap 2 → Task 4, gap 3 → Task 2, gap 4 → Task 3, gap 5 → Task 6 (+5 for flags), gap 6 → Task 7. Version/housekeeping → Task 8.
- Type consistency: `reference_images: List[Path]`, `input_video: Optional[Path]`, `delivery: Optional[str]`, `to_interaction_kwargs(video_uri: Optional[str] = None)` used consistently across Tasks 1–6.
- Existing-test compatibility checked against `tests/video/test_omni_client.py`: old assertions don't pin the absence of `generation_config`; single-ref content list shape unchanged; `test_omni_rejects_two_refs` is explicitly replaced in Task 5.
