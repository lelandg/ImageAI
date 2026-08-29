# Sprite Video Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `Plans/2026-08-29-sprite-tab-design.md` (§1.1, §1.3, §2, §4.2). Read it first.
**Goal:** Turn a character image plus a one-line brief into per-action video clips on a chroma plate, with cost estimates, a retrying queue, and cancel hooks in the two video clients.
**Architecture:** Pure-Python modules under `core/sprite/generation/` (no Qt). Provider calls go through `GoogleProvider.edit_image`, `OmniClient`, `VeoClient`, and LiteLLM. Every module accepts an injected `log` callable and logs every request and response in full. Every artifact gets a `.json` sidecar. Errors are `SpriteGenerationError` subclasses that carry a `user_message`.
**Tech Stack:** Python 3.11+, Pillow, numpy, `google-genai` (Veo/Omni), LiteLLM, ffmpeg via `core/video/ffmpeg_utils.py`, pytest with `MagicMock`.
**Sub-project:** 2 of 8 — depends on sub-project 1 (core spine). Consumed by 5a (GUI) and 7 (CLI).

Sub-project 1 provides these symbols; this plan treats them as present with the design's signatures:

- `core/sprite/models.py`: `Rect`, `Size`, `FrameMeta`, `TagMeta`, `SheetMeta`.
- `core/sprite/project.py`: `GenerationSettings`, `ExtractionSettings`, `ActionCard`, `ClipRecord`, `CostEntry`, `SpriteProject` (with `.save()`).
- `core/sprite/pipeline.py`: `CancelToken`, `Cancelled`, `ProgressFn`, `no_progress`, `run_pipeline(project, action, *, upto, progress, token, force)`.
- `core/sprite/extract.py`: `ExtractResult`, `extract_frames(video, out_dir, settings, *, progress, token)`.

`core/sprite/timing.py` does **not** exist yet. It is part of this plan (Task 4).

## Global Constraints

- Never `cd`. Use absolute paths. Git runs as `git -C /mnt/d/Documents/Code/GitHub/ImageAI …`.
- Python: `PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python`. Tests run as `$PY -m pytest <path> -v`.
- Cloud LLM model IDs come from `resolve_model()` in `core/llm_models.py`. Never hardcode `claude-*`/`gpt-*`/`gemini-*` outside a `static_default=` fallback argument. Chat kwargs come from `core.llm_params.build_completion_kwargs`. Prefer LiteLLM.
- Log every LLM/provider request (provider, model, params, prompt) and the full response to the file logger and to the injected `log` callable. Log every user-facing error.
- Never put "transparent", an aspect ratio, or a pixel size in a Gemini prompt. Aspect goes through `aspect_ratio=` / `image_config` kwargs.
- Every generated artifact gets a `.json` sidecar. Images use `core.utils.write_image_sidecar` (`name.png.json`). Clips use `name.json` beside `name.mp4`, the same shape as `cli/commands/video.py`.
- Provider calls in tests are injected callables or `MagicMock`. Live tests use `@pytest.mark.live` (skipped unless `IMAGEAI_LIVE_TESTS=1`).
- Conventional Commits. Commit at the end of every task. No version bump in this sub-project.
- Prose in Simplified Technical English style: active voice, short sentences.
- Test files use unique basenames. `tests/` has no `__init__.py`, so two files with the same basename collide.

## File Structure

| Path | Responsibility |
|---|---|
| `core/sprite/generation/__init__.py` | Package exports (Task 13). |
| `core/sprite/generation/_common.py` | `emit()` dual logging helper and `now_iso()`. Private. |
| `core/sprite/generation/errors.py` | `SpriteGenerationError`, `SafetyRefusal`, `QuotaExceeded`, `ProviderError`, `classify_provider_error`. |
| `core/sprite/generation/prompts.py` | `CHROMA_SUFFIX`, `LOOP_SUFFIX`, `FORBIDDEN_WORDS`, `inject_chroma`, `color_name`. |
| `core/sprite/source.py` | `SourceAnalysis`, `normalize_source`, `analyze_source`. |
| `core/sprite/timing.py` | `loop_seconds`, `suggest_clip_duration`, `snap_duration`, `legal_durations`, `frames_per_clip`, `ms_to_fps`. |
| `core/sprite/generation/cost.py` | `PRICE_TABLE_VERIFIED`, `OMNI_USD_PER_SECOND`, `price_per_second`, `estimate_action`, `estimate_project`, `record_actual`. |
| `core/sprite/generation/plate.py` | `PLATE_PROMPT`, `make_chroma_plate`. |
| `core/sprite/generation/turnaround.py` | `VIEWS`, `VIEW_PHRASES`, `generate_turnaround`. |
| `core/sprite/generation/action_cards.py` | LLM contract "Sprite Action Cards — Strict v1.0": prompts, schema, `GENRE_CHECKLISTS`, `ActionCardDraft`, `build_messages`, `parse_action_cards`, `generate_action_cards`, `draft_to_card`, `default_chat_model`. |
| `core/video/veo_client.py` | Modify: `VeoPollCancelled`, `cancel_check` on `_poll_for_completion`, `generate_video_async`, `generate_video`. |
| `core/video/omni_client.py` | Modify: `OmniPollCancelled`, `cancel_check` on `_await_terminal`, `generate_video_async`, `generate_video`. |
| `core/sprite/generation/video_route.py` | `RenderRequest`, `build_omni_config`, `build_veo_config`, `render_action`, `refine_action`, `seam_scores`, `find_loop_seam`, `trim_to_loop`. |
| `core/sprite/generation/queue.py` | `ActionQueue` with retries, backoff, cancel, pipeline hand-off, cost rows. |
| `tests/sprite/generation/conftest.py` | Shared fixtures: `png_file`, `make_action`, `make_project`. |
| `tests/sprite/generation/test_gen_*.py` | One test file per generation module. |
| `tests/sprite/test_sprite_source.py`, `tests/sprite/test_sprite_timing.py` | Tests for `source.py` and `timing.py`. |
| `tests/video/test_veo_cancel_hook.py`, `tests/video/test_omni_cancel_hook.py` | Client cancel-hook tests. |

Verified line ranges in files this plan modifies (checked 2026-08-29 on `feat/sprite-tab` at `25788d3`):

- `core/video/veo_client.py`: `VeoGenerationResult` 138–152; `VeoClient.__init__` 183–211; `generate_video_async` 325–610 (`result.operation_id = response.name` at 562; `await self._poll_for_completion(response, max_wait)` at 572; `except Exception` at 606); `generate_video` 612–627; `_poll_for_completion` 793–904 (`await asyncio.sleep(poll_interval)` at 894; `except Exception` at 899).
- `core/video/omni_client.py`: `generate_video_async` 259–366 (`interactions.create` at 305–307; `_await_terminal` call at 309; `except Exception` at 360); `generate_video` 368–376; `_await_terminal` 378–406 (`await asyncio.sleep(self.polling_interval)` at 390).

---

### Task 1: Errors and the shared logging helper

**Files:**
- Create: `core/sprite/generation/__init__.py` (empty docstring only; exports come in Task 13)
- Create: `core/sprite/generation/_common.py`
- Create: `core/sprite/generation/errors.py`
- Create: `tests/sprite/generation/conftest.py`
- Create: `tests/sprite/generation/test_gen_errors.py`

**Interfaces:**
- Consumes: nothing from sub-project 1.
- Produces:
  - `_common.emit(logger: logging.Logger, log: Optional[Callable[[str], None]], message: str, level: str = "info") -> None`
  - `_common.now_iso() -> str`
  - `errors.SpriteGenerationError(user_message: str, *, retryable: Optional[bool] = None, operation_id: Optional[str] = None)` with attributes `user_message`, `retryable`, `operation_id`
  - `errors.SafetyRefusal`, `errors.QuotaExceeded` (`retryable = True`), `errors.ProviderError`
  - `errors.classify_provider_error(exc: BaseException, *, provider: str = "", operation_id: Optional[str] = None) -> SpriteGenerationError`

- [ ] **Step 1: Write the failing tests**

`tests/sprite/generation/conftest.py`:

```python
"""Fixtures for the sprite generation route tests (sub-project 2)."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image


@pytest.fixture
def png_file(tmp_path):
    """Factory: write a small RGBA PNG and return its path."""
    def _make(name="char.png", size=(64, 48), color=(200, 40, 40, 255),
              border=None):
        arr = np.zeros((size[1], size[0], 4), dtype=np.uint8)
        arr[..., :4] = color
        if border is not None:
            arr[:4, :, :] = border
            arr[-4:, :, :] = border
            arr[:, :4, :] = border
            arr[:, -4:, :] = border
        path = tmp_path / name
        Image.fromarray(arr).save(path)  # mode comes from the array shape
        return path
    return _make


@pytest.fixture
def make_action():
    """Factory for an ActionCard with sensible defaults."""
    def _make(**overrides):
        from core.sprite.project import ActionCard
        values = dict(id="a1", name="walk", prompt="the hero walks to the right",
                      duration_s=4, loop=True, target_frames=8, fps=12)
        values.update(overrides)
        return ActionCard(**values)
    return _make


@pytest.fixture
def make_project(tmp_path, png_file):
    """Factory for a SpriteProject with a plate and a project dir.

    This factory is the only place that constructs SpriteProject in these
    tests. If sub-project 1 requires more constructor arguments than
    ``name`` and ``project_dir``, extend this factory. Do not change the
    tests.
    """
    def _make(actions=(), provider="omni", plate=True, turnaround=False):
        from core.sprite.project import SpriteProject, GenerationSettings
        project_dir = tmp_path / "hero"
        project_dir.mkdir(parents=True, exist_ok=True)
        project = SpriteProject(name="hero", project_dir=project_dir)
        project.generation = GenerationSettings(provider=provider)
        project.plate_color = "#00FF00"
        if plate:
            project.plate_path = png_file("plate.png", color=(0, 255, 0, 255))
        else:
            project.plate_path = None
        if turnaround:
            project.turnaround = {
                "front": png_file("front.png"),
                "side": png_file("side.png"),
            }
        else:
            project.turnaround = {}
        project.actions = list(actions)
        return project
    return _make
```

`tests/sprite/generation/test_gen_errors.py`:

```python
"""Tests for core/sprite/generation/errors.py (design §1.3)."""
import logging

import pytest

from core.sprite.generation._common import emit, now_iso
from core.sprite.generation.errors import (
    ProviderError,
    QuotaExceeded,
    SafetyRefusal,
    SpriteGenerationError,
    classify_provider_error,
)


def test_base_error_carries_user_message_and_flags():
    err = SpriteGenerationError("Something failed", operation_id="op-9")
    assert str(err) == "Something failed"
    assert err.user_message == "Something failed"
    assert err.retryable is False
    assert err.operation_id == "op-9"


def test_quota_is_retryable_by_class_and_safety_is_not():
    assert QuotaExceeded("q").retryable is True
    assert SafetyRefusal("s").retryable is False
    assert ProviderError("p").retryable is False
    assert ProviderError("p", retryable=True).retryable is True


@pytest.mark.parametrize("message", [
    "Request blocked by Responsible AI (RAI) filters",
    "person_generation is not allowed for this request",
    "The prompt violates the content policy",
    "Blocked by safety settings: HARM_CATEGORY_DANGEROUS",
])
def test_classify_safety_messages(message):
    err = classify_provider_error(RuntimeError(message), provider="omni")
    assert isinstance(err, SafetyRefusal)
    assert err.retryable is False
    # The message names the other provider as an option.
    assert "Veo" in err.user_message


def test_safety_message_names_omni_when_veo_refused():
    err = classify_provider_error(RuntimeError("RAI filter triggered"), provider="veo")
    assert "Omni" in err.user_message


@pytest.mark.parametrize("message", [
    "429 Too Many Requests",
    "RESOURCE_EXHAUSTED: quota exceeded for this project",
    "Rate limit reached, retry later",
])
def test_classify_quota_messages(message):
    err = classify_provider_error(RuntimeError(message))
    assert isinstance(err, QuotaExceeded)
    assert err.retryable is True


def test_classify_status_code_attribute():
    exc = RuntimeError("boom")
    exc.status_code = 429
    assert isinstance(classify_provider_error(exc), QuotaExceeded)


@pytest.mark.parametrize("message", [
    "503 Service Unavailable",
    "Deadline exceeded: request timed out",
    "The model is overloaded, please try again",
])
def test_transient_provider_errors_are_retryable(message):
    err = classify_provider_error(RuntimeError(message))
    assert isinstance(err, ProviderError)
    assert err.retryable is True


def test_unknown_errors_are_non_retryable_provider_errors():
    err = classify_provider_error(ValueError("bad aspect ratio 4:3"))
    assert isinstance(err, ProviderError)
    assert err.retryable is False
    assert "bad aspect ratio" in err.user_message


def test_classify_passes_through_existing_errors_and_keeps_operation_id():
    original = QuotaExceeded("q", operation_id="op-1")
    assert classify_provider_error(original) is original
    err = classify_provider_error(RuntimeError("x"), operation_id="op-2")
    assert err.operation_id == "op-2"


def test_word_rai_does_not_match_inside_other_words():
    err = classify_provider_error(RuntimeError("terrain generation failed"))
    assert not isinstance(err, SafetyRefusal)


def test_emit_calls_sink_and_skips_duplicate_module_logger(caplog):
    logger = logging.getLogger("core.sprite.generation.test_emit")
    seen = []
    with caplog.at_level(logging.INFO, logger=logger.name):
        emit(logger, seen.append, "hello")
        emit(logger, logger.info, "again")
        emit(logger, None, "silent sink")
    assert seen == ["hello"]
    messages = [r.getMessage() for r in caplog.records]
    assert messages == ["hello", "again", "silent sink"]


def test_now_iso_is_second_precision():
    stamp = now_iso()
    assert "T" in stamp and len(stamp) == 19
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_errors.py -v`
Expected: `ModuleNotFoundError: No module named 'core.sprite.generation'`.

- [ ] **Step 3: Implement the package stub, `_common.py`, and `errors.py`**

`core/sprite/generation/__init__.py`:

```python
"""Sprite generation routes: chroma plate, turnaround, action cards, video clips."""
```

`core/sprite/generation/_common.py`:

```python
"""Small helpers shared by the sprite generation modules. Private."""
import logging
from datetime import datetime
from typing import Callable, Optional

LogFn = Callable[[str], None]


def emit(logger: logging.Logger, log: Optional[LogFn], message: str,
         level: str = "info") -> None:
    """Write ``message`` to the file logger and to the injected sink.

    The sink is skipped when it is a bound method of ``logger`` itself, so a
    module default of ``log=logger.info`` does not write every line twice.
    A sink that raises never breaks generation; the failure goes to DEBUG.
    """
    getattr(logger, level, logger.info)(message)
    if log is None:
        return
    if getattr(log, "__self__", None) is logger:
        return
    try:
        log(message)
    except Exception:  # noqa: BLE001 - a broken console must not stop a render
        logger.debug("log sink raised", exc_info=True)


def now_iso() -> str:
    """Local time as ISO-8601 with second precision (sidecars, ledger rows)."""
    return datetime.now().isoformat(timespec="seconds")
```

`core/sprite/generation/errors.py`:

```python
"""Failure classes for the sprite generation route (design §1.3).

Every error carries a ``user_message`` that the GUI and the CLI show, and a
``retryable`` flag that the queue reads. ``classify_provider_error`` maps a
raw provider exception onto one of these classes by message and status code.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class SpriteGenerationError(Exception):
    """Base class for generation failures with a user-facing message."""

    retryable: bool = False

    def __init__(self, user_message: str, *, retryable: Optional[bool] = None,
                 operation_id: Optional[str] = None) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        if retryable is not None:
            self.retryable = retryable
        self.operation_id = operation_id


class SafetyRefusal(SpriteGenerationError):
    """RAI / safety / person_generation refusal. Never retried."""

    retryable = False


class QuotaExceeded(SpriteGenerationError):
    """429 / RESOURCE_EXHAUSTED / rate limit. Retried with backoff."""

    retryable = True


class ProviderError(SpriteGenerationError):
    """Any other provider failure. ``retryable`` is True for transient codes."""

    retryable = False


_SAFETY_PATTERNS = (
    r"\brai\b", r"responsible ai", r"safety", r"person_generation",
    r"person generation", r"content policy", r"violat", r"harm_category",
    r"usage guidelines", r"prohibited", r"blocked",
)
_QUOTA_PATTERNS = (
    r"\b429\b", r"resource_exhausted", r"resource exhausted", r"quota",
    r"rate limit", r"rate_limit", r"too many requests",
)
_TRANSIENT_PATTERNS = (
    r"\b50[0234]\b", r"\b529\b", r"timeout", r"timed out", r"unavailable",
    r"overloaded", r"connection", r"deadline", r"internal error",
    r"try again", r"temporarily",
)

_OTHER_PROVIDER = {"omni": "Veo", "veo": "Gemini Omni"}


def _status_code(exc: BaseException) -> Optional[int]:
    for attr in ("status_code", "code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def _matches(text: str, patterns) -> bool:
    return any(re.search(p, text) for p in patterns)


def classify_provider_error(exc: BaseException, *, provider: str = "",
                            operation_id: Optional[str] = None) -> SpriteGenerationError:
    """Map a provider exception onto a ``SpriteGenerationError`` subclass.

    Order: an existing ``SpriteGenerationError`` passes through; then safety
    refusal; then quota; then transient provider errors (retryable); then a
    non-retryable ``ProviderError``. The full exception text is logged.
    """
    if isinstance(exc, SpriteGenerationError):
        return exc

    raw = f"{type(exc).__name__}: {exc}"
    text = raw.lower()
    code = _status_code(exc)
    logger.error("Provider error (%s): %s", provider or "unknown", raw)

    if _matches(text, _SAFETY_PATTERNS):
        other = _OTHER_PROVIDER.get(provider.lower(), "the other video provider")
        message = (f"The provider refused this request for safety reasons: {exc}. "
                   f"Try {other}, or change the character image or the prompt.")
        return SafetyRefusal(message, operation_id=operation_id)

    if code == 429 or _matches(text, _QUOTA_PATTERNS):
        message = f"The provider quota or rate limit was reached: {exc}. The queue retries."
        return QuotaExceeded(message, operation_id=operation_id)

    if (code is not None and code >= 500) or _matches(text, _TRANSIENT_PATTERNS):
        message = f"The provider had a temporary failure: {exc}. The queue retries."
        return ProviderError(message, retryable=True, operation_id=operation_id)

    return ProviderError(f"The provider returned an error: {exc}", operation_id=operation_id)
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_errors.py -v`
Expected: 19 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/__init__.py core/sprite/generation/_common.py core/sprite/generation/errors.py tests/sprite/generation/conftest.py tests/sprite/generation/test_gen_errors.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): generation error classes and provider error classifier"
```

---

### Task 2: Chroma prompt injection

**Files:**
- Create: `core/sprite/generation/prompts.py`
- Create: `tests/sprite/generation/test_gen_prompts.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `CHROMA_SUFFIX: str`, `LOOP_SUFFIX: str`, `FORBIDDEN_WORDS: Tuple[str, ...]`
  - `color_name(hex_color: str) -> str`
  - `inject_chroma(prompt: str, plate_color: str, *, loop: bool) -> str`
  - `strip_render_terms(prompt: str) -> str`

- [ ] **Step 1: Write the failing tests**

`tests/sprite/generation/test_gen_prompts.py`:

```python
"""Tests for core/sprite/generation/prompts.py (chroma-prompt-injection)."""
import pytest

from core.sprite.generation.prompts import (
    CHROMA_SUFFIX,
    FORBIDDEN_WORDS,
    LOOP_SUFFIX,
    color_name,
    inject_chroma,
    strip_render_terms,
)


@pytest.mark.parametrize("hex_color,name", [
    ("#00FF00", "green"), ("#00B140", "green"), ("#0000FF", "blue"),
    ("#FF00FF", "magenta"), ("#FF0000", "red"), ("#FFFF00", "yellow"),
    ("#00FFFF", "cyan"), ("#FFFFFF", "white"), ("#000000", "black"),
    ("#808080", "gray"), ("00ff00", "green"),
])
def test_color_name(hex_color, name):
    assert color_name(hex_color) == name


def test_color_name_rejects_bad_hex():
    with pytest.raises(ValueError):
        color_name("#12")


def test_inject_appends_chroma_suffix_with_name_and_hex():
    out = inject_chroma("the hero walks", "#00ff00", loop=False)
    assert out.startswith("the hero walks, ")
    assert CHROMA_SUFFIX.format(color_name="green", hex="#00FF00") in out
    assert LOOP_SUFFIX not in out


def test_inject_appends_loop_suffix_when_looping():
    out = inject_chroma("the hero walks", "#00FF00", loop=True)
    assert out.endswith(", " + LOOP_SUFFIX)


def test_inject_strips_forbidden_words_case_insensitive():
    out = inject_chroma("Transparent background, ALPHA channel, checkerboard behind",
                        "#00FF00", loop=False)
    lowered = out.lower().replace(LOOP_SUFFIX, "")
    for word in FORBIDDEN_WORDS:
        assert word not in lowered.split(CHROMA_SUFFIX[:10].lower())[0]


def test_inject_strips_aspect_ratios_and_pixel_sizes():
    out = inject_chroma("side view 16:9 at 1920x1080, 512 px tall, 4:3 crop",
                        "#00FF00", loop=False)
    body = out.split(", solid chroma")[0]
    assert "16:9" not in body and "4:3" not in body
    assert "1920x1080" not in body and "512 px" not in body.lower()


def test_strip_render_terms_collapses_whitespace_and_punctuation():
    assert strip_render_terms("a  hero ,  transparent , walking ,") == "a hero, walking"


def test_inject_never_emits_aspect_or_pixels():
    out = inject_chroma("jump", "#0000FF", loop=True)
    assert ":" not in out.replace("chroma blue background", "")
    assert "px" not in out.lower()
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_prompts.py -v`
Expected: `ModuleNotFoundError: No module named 'core.sprite.generation.prompts'`.

- [ ] **Step 3: Implement `prompts.py`**

```python
"""Chroma-prompt injection for the sprite video route (design §4.2).

The suffixes tell the video model to render on a flat chroma plate. The
prompt text never contains an aspect ratio, a pixel size, or the words in
``FORBIDDEN_WORDS`` — Gemini renders such words literally.
"""
import colorsys
import re
from typing import Tuple

CHROMA_SUFFIX = ("solid chroma {color_name} background {hex}, flat even lighting, "
                 "no shadows on the background, no camera movement, character stays centered")
LOOP_SUFFIX = "seamless loop, ends in the same pose it starts"
FORBIDDEN_WORDS: Tuple[str, ...] = ("transparent", "checkerboard", "alpha")

_ASPECT_RE = re.compile(r"\b\d{1,2}\s*:\s*\d{1,2}\b")
_PIXELS_RE = re.compile(r"\b\d{2,5}\s*[x×]\s*\d{2,5}\b|\b\d{1,5}\s*px\b", re.IGNORECASE)
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(FORBIDDEN_WORDS) + r")\b", re.IGNORECASE)
_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _parse_hex(hex_color: str) -> Tuple[int, int, int]:
    match = _HEX_RE.match(hex_color.strip())
    if not match:
        raise ValueError(f"plate color must be #RRGGBB, got {hex_color!r}")
    value = match.group(1)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def normalize_hex(hex_color: str) -> str:
    """Return the color as upper-case ``#RRGGBB``."""
    r, g, b = _parse_hex(hex_color)
    return f"#{r:02X}{g:02X}{b:02X}"


def color_name(hex_color: str) -> str:
    """Basic English name for a plate color: green, blue, magenta, red, …"""
    r, g, b = _parse_hex(hex_color)
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    if v < 0.15:
        return "black"
    if s < 0.2:
        return "white" if v > 0.85 else "gray"
    hue = h * 360.0
    if hue < 15 or hue >= 345:
        return "red"
    if hue < 45:
        return "orange"
    if hue < 75:
        return "yellow"
    if hue < 165:
        return "green"
    if hue < 195:
        return "cyan"
    if hue < 255:
        return "blue"
    if hue < 285:
        return "purple"
    return "magenta"


def strip_render_terms(prompt: str) -> str:
    """Remove forbidden words, aspect ratios, and pixel sizes; tidy punctuation."""
    text = _FORBIDDEN_RE.sub(" ", prompt)
    text = _ASPECT_RE.sub(" ", text)
    text = _PIXELS_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;])", r"\1", text)
    text = re.sub(r"([,.;])(?:\s*[,.;])+", r"\1", text)
    text = text.strip().strip(",.; ").strip()
    return text


def inject_chroma(prompt: str, plate_color: str, *, loop: bool) -> str:
    """Append the chroma suffix (and the loop suffix) to a cleaned prompt."""
    hex_color = normalize_hex(plate_color)
    body = strip_render_terms(prompt)
    parts = [body] if body else []
    parts.append(CHROMA_SUFFIX.format(color_name=color_name(hex_color), hex=hex_color))
    if loop:
        parts.append(LOOP_SUFFIX)
    return ", ".join(parts)
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_prompts.py -v`
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/prompts.py tests/sprite/generation/test_gen_prompts.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): chroma prompt injection with forbidden-word and size stripping"
```

---

### Task 3: Character source import (`core/sprite/source.py`)

**Files:**
- Create: `core/sprite/source.py`
- Create: `tests/sprite/test_sprite_source.py`

**Interfaces:**
- Consumes: `core.sprite.models.Size`; `providers.google.apply_transparent_canvas_fix(image_bytes, target_aspect_ratio, logger_instance=None, console_logger=None) -> bytes`; `core.utils.write_image_sidecar(path, meta)`.
- Produces:
  - `SourceAnalysis(has_alpha: bool, border_color: Optional[str], border_uniform: bool, size: Size)`
  - `analyze_source(image: Path) -> SourceAnalysis`
  - `normalize_source(image: Path, out_png: Path, aspect_ratio: str = "16:9") -> Path`

- [ ] **Step 1: Write the failing tests**

`tests/sprite/test_sprite_source.py`:

```python
"""Tests for core/sprite/source.py (character-source-import)."""
import json

import numpy as np
import pytest
from PIL import Image

from core.sprite.source import SourceAnalysis, analyze_source, normalize_source


def _write(tmp_path, name, arr):
    path = tmp_path / name
    Image.fromarray(arr).save(path)  # mode comes from the array shape
    return path


def test_analyze_uniform_green_border_no_alpha(tmp_path):
    arr = np.zeros((60, 80, 3), dtype=np.uint8)
    arr[...] = (0, 255, 0)
    arr[20:40, 30:50] = (200, 30, 30)
    path = _write(tmp_path, "green.png", arr)
    info = analyze_source(path)
    assert isinstance(info, SourceAnalysis)
    assert info.has_alpha is False
    assert info.border_uniform is True
    assert info.border_color == "#00FF00"
    assert info.size == (80, 60)


def test_analyze_detects_alpha(tmp_path):
    arr = np.zeros((32, 32, 4), dtype=np.uint8)
    arr[8:24, 8:24] = (255, 0, 0, 255)
    path = _write(tmp_path, "alpha.png", arr)
    info = analyze_source(path)
    assert info.has_alpha is True
    assert info.size == (32, 32)


def test_analyze_noisy_border_is_not_uniform(tmp_path):
    rng = np.random.default_rng(1)
    arr = rng.integers(0, 255, size=(40, 40, 3), dtype=np.uint8)
    path = _write(tmp_path, "noise.png", arr)
    info = analyze_source(path)
    assert info.border_uniform is False
    assert info.border_color is None


def test_normalize_pads_to_target_aspect_and_writes_sidecar(tmp_path):
    arr = np.zeros((100, 100, 4), dtype=np.uint8)
    arr[...] = (10, 20, 30, 255)
    src = _write(tmp_path, "square.png", arr)
    out = tmp_path / "source" / "character.png"
    result = normalize_source(src, out, aspect_ratio="16:9")
    assert result == out and out.exists()
    with Image.open(out) as img:
        w, h = img.size
        assert img.mode == "RGBA"
        assert abs((w / h) - (16 / 9)) < 0.02
        assert w >= 100 and h >= 100          # never cropped
        assert img.getpixel((0, 0))[3] == 0    # transparent padding
        assert img.getpixel((w // 2, h // 2)) == (10, 20, 30, 255)
    sidecar = out.with_suffix(".png.json")
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    assert meta["aspect_ratio"] == "16:9"
    assert meta["source"] == str(src)
    assert meta["kind"] == "character_source"


def test_normalize_keeps_matching_aspect_unchanged(tmp_path):
    arr = np.zeros((90, 160, 3), dtype=np.uint8)
    arr[...] = (5, 5, 5)
    src = _write(tmp_path, "wide.png", arr)
    out = tmp_path / "character.png"
    normalize_source(src, out, aspect_ratio="16:9")
    with Image.open(out) as img:
        assert img.size == (160, 90)
        assert img.mode == "RGBA"


def test_normalize_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        normalize_source(tmp_path / "nope.png", tmp_path / "out.png")
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_sprite_source.py -v`
Expected: `ModuleNotFoundError: No module named 'core.sprite.source'`.

- [ ] **Step 3: Implement `source.py`**

```python
"""Character source import: analysis and aspect normalization (design §4.2).

``normalize_source`` pads the character onto a transparent canvas of the
target aspect ratio through ``providers.google.apply_transparent_canvas_fix``.
It never crops and never distorts (AGENTS.md hard rule).
"""
import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from core.sprite.models import Size
from core.utils import write_image_sidecar
from core.sprite.generation._common import now_iso

logger = logging.getLogger(__name__)

# A border pixel counts as "the same color" when its RGB distance to the
# median border color is at most this value (0..441).
_BORDER_DISTANCE = 24.0
# The border is uniform when at least this fraction of ring pixels match.
_UNIFORM_FRACTION = 0.95


@dataclass
class SourceAnalysis:
    has_alpha: bool
    border_color: Optional[str]
    border_uniform: bool
    size: Size


def _border_ring(rgb: np.ndarray, width: int) -> np.ndarray:
    top = rgb[:width, :, :].reshape(-1, 3)
    bottom = rgb[-width:, :, :].reshape(-1, 3)
    left = rgb[width:-width, :width, :].reshape(-1, 3)
    right = rgb[width:-width, -width:, :].reshape(-1, 3)
    return np.concatenate([top, bottom, left, right], axis=0)


def analyze_source(image: Path) -> SourceAnalysis:
    """Report alpha presence, the dominant border color, and the size."""
    with Image.open(image) as img:
        rgba = np.asarray(img.convert("RGBA"))
    height, width = rgba.shape[:2]
    alpha = rgba[..., 3]
    has_alpha = bool(alpha.min() < 255)

    ring_width = max(1, min(width, height) // 50)
    ring = _border_ring(rgba[..., :3].astype(np.float32), ring_width)
    median = np.median(ring, axis=0)
    distance = np.linalg.norm(ring - median, axis=1)
    fraction = float((distance <= _BORDER_DISTANCE).mean()) if ring.size else 0.0
    uniform = fraction >= _UNIFORM_FRACTION
    color = None
    if uniform:
        r, g, b = (int(round(c)) for c in median)
        color = f"#{r:02X}{g:02X}{b:02X}"
    logger.info("analyze_source %s: size=%dx%d has_alpha=%s border_uniform=%s (%.0f%%) color=%s",
                image, width, height, has_alpha, uniform, fraction * 100, color)
    return SourceAnalysis(has_alpha=has_alpha, border_color=color,
                          border_uniform=uniform, size=(width, height))


def normalize_source(image: Path, out_png: Path, aspect_ratio: str = "16:9") -> Path:
    """Pad the character onto a transparent canvas of ``aspect_ratio``.

    Writes an RGBA PNG to ``out_png`` plus a ``.json`` sidecar. Raises
    ``FileNotFoundError`` when ``image`` is missing.
    """
    from providers.google import apply_transparent_canvas_fix

    image = Path(image)
    if not image.exists():
        raise FileNotFoundError(f"Character image not found: {image}")
    out_png = Path(out_png)
    raw = image.read_bytes()
    fixed = apply_transparent_canvas_fix(raw, aspect_ratio, logger_instance=logger)

    with Image.open(io.BytesIO(fixed)) as img:
        rgba = img.convert("RGBA")
        out_png.parent.mkdir(parents=True, exist_ok=True)
        rgba.save(out_png, format="PNG")
        width, height = rgba.size

    analysis = analyze_source(image)
    write_image_sidecar(out_png, {
        "kind": "character_source",
        "source": str(image),
        "aspect_ratio": aspect_ratio,
        "padded": fixed is not raw,
        "size": [width, height],
        "source_has_alpha": analysis.has_alpha,
        "source_border_color": analysis.border_color,
        "timestamp": now_iso(),
    })
    logger.info("normalize_source: %s -> %s (%dx%d, aspect %s)",
                image, out_png, width, height, aspect_ratio)
    return out_png
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_sprite_source.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/source.py tests/sprite/test_sprite_source.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): character source analysis and transparent-canvas normalization"
```

---

### Task 4: Clip timing hints (`core/sprite/timing.py`)

**Files:**
- Create: `core/sprite/timing.py`
- Create: `tests/sprite/test_sprite_timing.py`

**Interfaces:**
- Consumes: `core.sprite.project.ExtractionSettings`; `core.video.veo_client.VeoModel` (lazy import); `core.video.omni_client.OmniClient.MODEL_CONSTRAINTS["duration_range"]` (lazy import).
- Produces:
  - `loop_seconds(target_frames: int, fps: int) -> float`
  - `legal_durations(provider: str, model: str) -> Tuple[int, ...]`
  - `suggest_clip_duration(target_frames: int, fps: int, provider: str, model: str) -> int`
  - `snap_duration(duration_s: int, provider: str, model: str, *, loop_conditioning: bool = False) -> int`
  - `frames_per_clip(duration_s: float, source_fps: float, settings: ExtractionSettings) -> int`
  - `ms_to_fps(durations_ms: Sequence[int]) -> Tuple[int, List[float]]`

- [ ] **Step 1: Write the failing tests**

`tests/sprite/test_sprite_timing.py`:

```python
"""Tests for core/sprite/timing.py (clip-timing-hints)."""
import pytest

from core.sprite.project import ExtractionSettings
from core.sprite.timing import (
    frames_per_clip,
    legal_durations,
    loop_seconds,
    ms_to_fps,
    snap_duration,
    suggest_clip_duration,
)

VEO_STD = "veo-3.1-generate-001"
VEO_FAST = "veo-3.1-fast-generate-001"


def test_loop_seconds():
    assert loop_seconds(8, 12) == pytest.approx(8 / 12)
    assert loop_seconds(24, 24) == 1.0


def test_loop_seconds_rejects_zero_fps():
    with pytest.raises(ValueError):
        loop_seconds(8, 0)


def test_legal_durations_per_provider():
    assert legal_durations("veo", VEO_STD) == (8,)
    assert legal_durations("veo", "") == (8,)
    assert legal_durations("veo", VEO_FAST) == (4, 6, 8)
    assert legal_durations("omni", "") == tuple(range(3, 11))
    with pytest.raises(ValueError):
        legal_durations("sora", "")


def test_suggest_duration_gives_at_least_two_loops():
    # 8 frames at 12 fps = 0.67 s per loop -> needs >= 1.33 s -> Omni 3 s.
    assert suggest_clip_duration(8, 12, "omni", "") == 3
    # 24 frames at 8 fps = 3 s per loop -> needs 6 s -> Omni 6 s, Veo fast 6 s.
    assert suggest_clip_duration(24, 8, "omni", "") == 6
    assert suggest_clip_duration(24, 8, "veo", VEO_FAST) == 6
    # Veo standard is always 8.
    assert suggest_clip_duration(8, 12, "veo", VEO_STD) == 8


def test_suggest_duration_caps_at_longest_legal():
    # 60 frames at 8 fps = 7.5 s per loop -> needs 15 s -> longest legal.
    assert suggest_clip_duration(60, 8, "omni", "") == 10
    assert suggest_clip_duration(60, 8, "veo", VEO_FAST) == 8


def test_snap_duration():
    assert snap_duration(5, "veo", VEO_FAST) == 6
    assert snap_duration(4, "veo", VEO_FAST) == 4
    assert snap_duration(4, "veo", VEO_STD) == 8
    assert snap_duration(4, "veo", VEO_FAST, loop_conditioning=True) == 8
    assert snap_duration(12, "omni", "") == 10
    assert snap_duration(1, "omni", "") == 3
    assert snap_duration(7, "omni", "") == 7


def test_frames_per_clip_modes():
    every = ExtractionSettings(mode="every_n", every_n=8)
    assert frames_per_clip(8.0, 24.0, every) == 24
    fps = ExtractionSettings(mode="target_fps", target_fps=12)
    assert frames_per_clip(8.0, 24.0, fps) == 96
    exact = ExtractionSettings(mode="exact_n", exact_n=10)
    assert frames_per_clip(8.0, 24.0, exact) == 10


def test_frames_per_clip_honors_trim():
    every = ExtractionSettings(mode="every_n", every_n=1, trim_start_s=1.0, trim_end_s=1.0)
    assert frames_per_clip(8.0, 24.0, every) == 144
    assert frames_per_clip(1.0, 24.0, every) == 0


def test_ms_to_fps_gcd():
    fps, mult = ms_to_fps([100, 100, 200])
    assert fps == 10
    assert mult == [1.0, 1.0, 2.0]


def test_ms_to_fps_reports_drift_in_multipliers():
    fps, mult = ms_to_fps([83, 83, 83])
    assert fps == 12
    assert all(abs(m - 1.0) < 0.01 for m in mult)
    assert mult[0] != 1.0


def test_ms_to_fps_clamps_to_60_and_handles_empty():
    fps, mult = ms_to_fps([5, 5])
    assert fps == 60
    assert ms_to_fps([]) == (12, [])
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_sprite_timing.py -v`
Expected: `ModuleNotFoundError: No module named 'core.sprite.timing'`.

- [ ] **Step 3: Implement `timing.py`**

```python
"""Clip timing hints for the sprite feature (design §4.2).

Pure arithmetic. Provider duration tables are read from the video clients
at call time so the sprite feature never restates them.
"""
import logging
import math
from functools import reduce
from typing import List, Sequence, Tuple

from core.sprite.project import ExtractionSettings

logger = logging.getLogger(__name__)

DEFAULT_FPS = 12
MAX_FPS = 60


def loop_seconds(target_frames: int, fps: int) -> float:
    """Seconds one loop of ``target_frames`` takes at ``fps``."""
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps}")
    return target_frames / float(fps)


def legal_durations(provider: str, model: str) -> Tuple[int, ...]:
    """Integer clip durations the provider accepts for ``model``."""
    name = (provider or "").strip().lower()
    if name == "veo":
        from core.video.veo_client import VeoModel
        if not model or model == VeoModel.VEO_3_1_GENERATE.value:
            return (8,)
        if model == VeoModel.VEO_3_1_FAST.value:
            return (4, 6, 8)
        return (8,)
    if name == "omni":
        from core.video.omni_client import OmniClient
        low, high = OmniClient.MODEL_CONSTRAINTS["duration_range"]
        return tuple(range(int(low), int(high) + 1))
    raise ValueError(f"Unknown sprite video provider {provider!r}. Use 'omni' or 'veo'.")


def suggest_clip_duration(target_frames: int, fps: int, provider: str, model: str) -> int:
    """Shortest legal duration that holds at least two loops, else the longest."""
    needed = 2.0 * loop_seconds(target_frames, fps)
    legal = legal_durations(provider, model)
    candidates = [d for d in legal if d >= needed]
    chosen = min(candidates) if candidates else max(legal)
    logger.debug("suggest_clip_duration: %d frames @ %d fps needs %.2fs -> %ds (%s/%s)",
                 target_frames, fps, needed, chosen, provider, model)
    return chosen


def snap_duration(duration_s: int, provider: str, model: str, *,
                  loop_conditioning: bool = False) -> int:
    """Nearest legal duration. Veo loop conditioning (first+last frame) forces 8 s."""
    if (provider or "").strip().lower() == "veo" and loop_conditioning:
        return 8
    legal = legal_durations(provider, model)
    return min(legal, key=lambda d: (abs(d - duration_s), -d))


def frames_per_clip(duration_s: float, source_fps: float, settings: ExtractionSettings) -> int:
    """Frames the extractor will produce from a clip of ``duration_s``."""
    effective = max(0.0, float(duration_s) - settings.trim_start_s - settings.trim_end_s)
    total = int(round(effective * source_fps))
    if settings.mode == "every_n":
        step = max(1, int(settings.every_n))
        return int(math.ceil(total / step)) if total else 0
    if settings.mode == "target_fps":
        return int(round(effective * settings.target_fps))
    if settings.mode == "exact_n":
        return int(settings.exact_n)
    raise ValueError(f"Unknown extraction mode {settings.mode!r}")


def ms_to_fps(durations_ms: Sequence[int]) -> Tuple[int, List[float]]:
    """GCD-based frame rate plus per-frame multipliers.

    Returns ``(fps, multipliers)`` where ``multiplier[i] * (1000 / fps)``
    reproduces ``durations_ms[i]``. Multipliers are integers when the
    durations share an exact base; otherwise they carry the rounding drift,
    which is also logged.
    """
    values = [max(1, int(d)) for d in durations_ms]
    if not values:
        return DEFAULT_FPS, []
    base = reduce(math.gcd, values)
    fps = int(round(1000.0 / base))
    fps = max(1, min(MAX_FPS, fps))
    multipliers = [d * fps / 1000.0 for d in values]
    drift = max(abs(m - round(m)) for m in multipliers)
    if drift > 1e-6:
        logger.info("ms_to_fps: base %d ms -> %d fps; rounding drift %.3f frame", base, fps, drift)
    return fps, multipliers
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_sprite_timing.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/timing.py tests/sprite/test_sprite_timing.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): clip timing hints (loop length, duration snapping, GCD fps)"
```

---

### Task 5: Cost estimator and ledger (`core/sprite/generation/cost.py`)

**Files:**
- Create: `core/sprite/generation/cost.py`
- Create: `tests/sprite/generation/test_gen_cost.py`

**Interfaces:**
- Consumes: `core.video.veo_client.VeoClient.estimate_cost`, `VeoGenerationConfig`, `VeoModel`; `core.config.ConfigManager.get`; `core.sprite.timing.snap_duration`; `core.sprite.project.GenerationSettings`, `ActionCard`, `SpriteProject`, `CostEntry`.
- Produces:
  - `PRICE_TABLE_VERIFIED: str` (`"YYYY-MM-DD"` or `"unverified"`)
  - `OMNI_USD_PER_SECOND: Optional[float]`
  - `PRICE_OVERRIDES_KEY = "sprite.price_overrides"`
  - `price_overrides() -> Dict[str, float]`
  - `price_per_second(provider: str, model: str, *, include_audio: bool) -> Optional[float]`
  - `estimate_action(settings: GenerationSettings, action: ActionCard) -> Optional[float]`
  - `estimate_project(project: SpriteProject) -> Tuple[Optional[float], int]`
  - `record_actual(project: SpriteProject, action: ActionCard, usd: Optional[float], note: str = "", *, provider: Optional[str] = None, model: Optional[str] = None, seconds: Optional[float] = None, estimated_usd: Optional[float] = None) -> CostEntry` (overrides let the image route record its own provider/model/unit count)

- [ ] **Step 1: Verify the Omni price on the day of implementation**

Open the Google Gemini API pricing page (https://ai.google.dev/gemini-api/docs/pricing) in a browser. Find the Gemini Omni video output price. Record the per-second video rate in USD and today's date.

- If the page states a per-second video rate: set `OMNI_USD_PER_SECOND` to that number and `PRICE_TABLE_VERIFIED` to today's date as `"YYYY-MM-DD"`.
- If the page states a per-clip or per-token price instead, or the rate cannot be found: leave `OMNI_USD_PER_SECOND = None` and `PRICE_TABLE_VERIFIED = "unverified"`. The estimator then returns `None` for Omni and the UI shows "unknown". Never guess a rate.

The Veo rates are not re-verified here; they come from `VeoClient.estimate_cost` (October 2025 table).

- [ ] **Step 2: Write the failing tests**

`tests/sprite/generation/test_gen_cost.py`:

```python
"""Tests for core/sprite/generation/cost.py (G12 cost source + ledger)."""
import re

import pytest

from core.sprite.generation import cost
from core.sprite.project import CostEntry, GenerationSettings

VEO_STD = "veo-3.1-generate-001"
VEO_FAST = "veo-3.1-fast-generate-001"


@pytest.fixture(autouse=True)
def _no_overrides(monkeypatch):
    monkeypatch.setattr(cost, "price_overrides", lambda: {})


def test_price_table_verified_is_date_or_unverified():
    assert cost.PRICE_TABLE_VERIFIED == "unverified" or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", cost.PRICE_TABLE_VERIFIED)
    if cost.PRICE_TABLE_VERIFIED == "unverified":
        assert cost.OMNI_USD_PER_SECOND is None
    else:
        assert isinstance(cost.OMNI_USD_PER_SECOND, float)


def test_veo_rates_reuse_veo_client_table():
    from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel
    stub = VeoClient.__new__(VeoClient)
    expected = VeoClient.estimate_cost(
        stub, VeoGenerationConfig(model=VeoModel.VEO_3_1_GENERATE, duration=8,
                                  include_audio=False)) / 8
    assert cost.price_per_second("veo", VEO_STD, include_audio=False) == pytest.approx(expected)
    assert cost.price_per_second("veo", "", include_audio=False) == pytest.approx(expected)
    with_audio = cost.price_per_second("veo", VEO_STD, include_audio=True)
    assert with_audio > expected
    fast = cost.price_per_second("veo", VEO_FAST, include_audio=False)
    assert fast < expected


def test_unknown_models_and_providers_return_none():
    assert cost.price_per_second("veo", "veo-9.9-imaginary", include_audio=False) is None
    assert cost.price_per_second("sora", "", include_audio=False) is None


def test_omni_rate_follows_module_constant(monkeypatch):
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", None)
    assert cost.price_per_second("omni", "", include_audio=False) is None
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", 0.05)
    assert cost.price_per_second("omni", "any", include_audio=True) == 0.05


def test_config_override_wins(monkeypatch):
    monkeypatch.setattr(cost, "price_overrides",
                        lambda: {"omni": 0.07, "veo/" + VEO_FAST: 0.01})
    assert cost.price_per_second("omni", "", include_audio=False) == 0.07
    assert cost.price_per_second("veo", VEO_FAST, include_audio=True) == 0.01
    assert cost.price_per_second("veo", VEO_STD, include_audio=False) is not None


def test_price_overrides_reads_both_config_shapes(monkeypatch):
    monkeypatch.undo()  # use the real reader below
    class _Cfg:
        def __init__(self, data): self._d = data
        def get(self, key, default=None): return self._d.get(key, default)
    monkeypatch.setattr(cost, "_config_manager", lambda: _Cfg({"sprite.price_overrides": {"omni": "0.5"}}))
    assert cost.price_overrides() == {"omni": 0.5}
    monkeypatch.setattr(cost, "_config_manager", lambda: _Cfg({"sprite": {"price_overrides": {"veo": 0.2, "bad": "x"}}}))
    assert cost.price_overrides() == {"veo": 0.2}


def test_estimate_action_uses_snapped_duration(make_action, monkeypatch):
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", 0.10)
    action = make_action(duration_s=5)
    omni = GenerationSettings(provider="omni")
    assert cost.estimate_action(omni, action) == pytest.approx(0.5)
    veo = GenerationSettings(provider="veo", model=VEO_STD, include_audio=False,
                             loop_conditioning=True)
    rate = cost.price_per_second("veo", VEO_STD, include_audio=False)
    assert cost.estimate_action(veo, action) == pytest.approx(rate * 8)


def test_estimate_action_unknown_rate_is_none(make_action, monkeypatch):
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", None)
    assert cost.estimate_action(GenerationSettings(provider="omni"), make_action()) is None


def test_estimate_project_sums_and_counts_unknown(make_project, make_action, monkeypatch):
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", 0.10)
    project = make_project(actions=[make_action(id="a", duration_s=4),
                                    make_action(id="b", name="run", duration_s=6)])
    assert cost.estimate_project(project) == (pytest.approx(1.0), 0)
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", None)
    assert cost.estimate_project(project) == (None, 2)
    empty = make_project(actions=[])
    assert cost.estimate_project(empty) == (0.0, 0)


def test_record_actual_appends_ledger_row_and_updates_clip(make_project, make_action, monkeypatch):
    from core.sprite.project import ClipRecord
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", 0.10)
    action = make_action(duration_s=4)
    project = make_project(actions=[action])
    action.clip = ClipRecord(path=project.project_dir / "clips" / "a1.mp4", provider="omni",
                             model="m", operation_id="int-1",
                             params={"duration_s": 4, "aspect_ratio": "16:9"},
                             prompt="p", generated_at="2026-08-29T10:00:00",
                             estimated_usd=0.4, actual_usd=None)
    entry = cost.record_actual(project, action, 0.42, note="billing export")
    assert isinstance(entry, CostEntry)
    assert project.cost_ledger[-1] is entry
    assert entry.action_id == "a1" and entry.action_name == "walk"
    assert entry.provider == "omni" and entry.model == "m"
    assert entry.seconds == 4 and entry.estimated_usd == 0.4 and entry.actual_usd == 0.42
    assert entry.note == "billing export" and "T" in entry.timestamp
    assert action.clip.actual_usd == 0.42


def test_record_actual_without_clip_uses_settings(make_project, make_action, monkeypatch):
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", 0.10)
    action = make_action(duration_s=4)
    project = make_project(actions=[action])
    entry = cost.record_actual(project, action, None)
    assert entry.provider == "omni" and entry.actual_usd is None
    assert entry.estimated_usd == pytest.approx(0.4)


def test_record_actual_overrides_for_other_routes(make_project, make_action, monkeypatch):
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", 0.10)
    action = make_action(duration_s=4)
    project = make_project(actions=[action])
    entry = cost.record_actual(project, action, None, note="image route: 6 edits",
                               provider="google", model="image-model", seconds=6)
    assert entry.provider == "google" and entry.model == "image-model"
    assert entry.seconds == 6.0
    assert entry.estimated_usd is None          # video estimate must not leak in
    assert entry.note == "image route: 6 edits"
    explicit = cost.record_actual(project, action, 0.12, provider="google",
                                  model="image-model", seconds=6, estimated_usd=0.1)
    assert explicit.estimated_usd == 0.1 and explicit.actual_usd == 0.12
    assert len(project.cost_ledger) == 2
```

- [ ] **Step 3: Run the tests and watch them fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_cost.py -v`
Expected: `ImportError: cannot import name 'cost' from 'core.sprite.generation'`.

- [ ] **Step 4: Implement `cost.py`**

Set `PRICE_TABLE_VERIFIED` and `OMNI_USD_PER_SECOND` from Step 1. The code below shows the unverified state.

```python
"""Cost estimates and the per-action cost ledger (design §4.2, G12).

Veo rates reuse ``VeoClient.estimate_cost`` so the sprite feature never
restates them. The Omni rate is a module constant that the implementer
verifies against the Google Gemini API pricing page on the day of
implementation; ``PRICE_TABLE_VERIFIED`` records that date. When no verified
rate exists the estimator returns ``None`` and the UI shows "unknown". The
config key ``sprite.price_overrides`` (config.json) lets the user correct any
rate without a release.
"""
import logging
from typing import Dict, Optional, Tuple

from core.sprite.generation._common import now_iso
from core.sprite.project import ActionCard, CostEntry, GenerationSettings, SpriteProject
from core.sprite.timing import snap_duration

logger = logging.getLogger(__name__)

# Date the implementer verified the Omni rate below ("YYYY-MM-DD"), or
# "unverified" when no per-second rate could be confirmed.
PRICE_TABLE_VERIFIED = "unverified"
# USD per second of Gemini Omni video output. None = unknown; never a guess.
OMNI_USD_PER_SECOND: Optional[float] = None

PRICE_OVERRIDES_KEY = "sprite.price_overrides"


def _config_manager():
    """Late import so tests can substitute a fake reader."""
    from core.config import ConfigManager
    return ConfigManager()


def price_overrides() -> Dict[str, float]:
    """User rate overrides from config.json.

    Accepts a top-level ``"sprite.price_overrides"`` key or a nested
    ``{"sprite": {"price_overrides": {...}}}`` block. Keys are
    ``"<provider>"`` or ``"<provider>/<model>"``; values are USD per second.
    Non-numeric values are dropped with a logged warning.
    """
    try:
        config = _config_manager()
        raw = config.get(PRICE_OVERRIDES_KEY)
        if raw is None:
            sprite_block = config.get("sprite") or {}
            raw = sprite_block.get("price_overrides") if isinstance(sprite_block, dict) else None
    except Exception as exc:  # noqa: BLE001 - a broken config must not break estimates
        logger.warning("price_overrides: could not read config: %s", exc)
        return {}
    result: Dict[str, float] = {}
    for key, value in (raw or {}).items():
        try:
            result[str(key).strip().lower()] = float(value)
        except (TypeError, ValueError):
            logger.warning("price_overrides: ignoring non-numeric rate for %r: %r", key, value)
    return result


def _veo_rate(model: str, include_audio: bool) -> Optional[float]:
    from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel
    try:
        veo_model = VeoModel(model) if model else VeoModel.VEO_3_1_GENERATE
    except ValueError:
        logger.warning("price_per_second: unknown Veo model %r", model)
        return None
    duration = 8  # legal for every Veo 3.1 model
    config = VeoGenerationConfig(model=veo_model, duration=duration, include_audio=include_audio)
    # estimate_cost reads only its config argument; a bare instance is enough.
    stub = VeoClient.__new__(VeoClient)
    return VeoClient.estimate_cost(stub, config) / duration


def price_per_second(provider: str, model: str, *, include_audio: bool) -> Optional[float]:
    """USD per second of generated video, or ``None`` when unknown."""
    name = (provider or "").strip().lower()
    model_id = (model or "").strip()
    overrides = price_overrides()
    for key in (f"{name}/{model_id.lower()}", name):
        if key in overrides:
            return overrides[key]
    if name == "veo":
        return _veo_rate(model_id, include_audio)
    if name == "omni":
        return OMNI_USD_PER_SECOND
    return None


def estimate_action(settings: GenerationSettings, action: ActionCard) -> Optional[float]:
    """Estimated USD for one action under ``settings``; ``None`` when unknown."""
    rate = price_per_second(settings.provider, settings.model, include_audio=settings.include_audio)
    if rate is None:
        return None
    try:
        seconds = snap_duration(action.duration_s, settings.provider, settings.model,
                                loop_conditioning=settings.loop_conditioning)
    except ValueError:
        return None
    return round(rate * seconds, 4)


def estimate_project(project: SpriteProject) -> Tuple[Optional[float], int]:
    """``(usd, unknown_count)`` over every action. ``usd`` is ``None`` when all are unknown."""
    total = 0.0
    unknown = 0
    for action in project.actions:
        value = estimate_action(project.generation, action)
        if value is None:
            unknown += 1
        else:
            total += value
    if project.actions and unknown == len(project.actions):
        return None, unknown
    return round(total, 4), unknown


def record_actual(project: SpriteProject, action: ActionCard, usd: Optional[float],
                  note: str = "", *, provider: Optional[str] = None,
                  model: Optional[str] = None, seconds: Optional[float] = None,
                  estimated_usd: Optional[float] = None) -> CostEntry:
    """Append a ledger row for ``action`` and copy ``usd`` onto its clip.

    Defaults come from ``action.clip`` (video route) or from the project's
    video settings. The keyword overrides let another route (image route,
    retouch) record its own provider, model, unit count, and estimate.
    """
    clip = action.clip
    if clip is not None:
        default_provider, default_model = clip.provider, clip.model
        default_seconds = float(clip.params.get("duration_s", action.duration_s))
        default_estimate = clip.estimated_usd
    else:
        default_provider, default_model = project.generation.provider, project.generation.model
        default_seconds = float(snap_duration(action.duration_s, default_provider, default_model,
                                              loop_conditioning=project.generation.loop_conditioning))
        default_estimate = estimate_action(project.generation, action)
    if provider is None:
        provider = default_provider
    if model is None:
        model = default_model
    if seconds is None:
        seconds = default_seconds
    if estimated_usd is None and provider == default_provider and model == default_model:
        estimated_usd = default_estimate
    entry = CostEntry(action_id=action.id, action_name=action.name, provider=provider,
                      model=model, seconds=float(seconds), estimated_usd=estimated_usd,
                      actual_usd=usd, timestamp=now_iso(), note=note)
    project.cost_ledger.append(entry)
    if clip is not None:
        clip.actual_usd = usd
    logger.info("Cost ledger: %s (%s/%s) %.1fs est=%s actual=%s %s",
                action.name, provider, model, seconds, estimated_usd, usd, note)
    return entry
```

- [ ] **Step 5: Run the tests and watch them pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_cost.py -v`
Expected: 12 passed.

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/cost.py tests/sprite/generation/test_gen_cost.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): cost estimator with verified price table and ledger rows"
```

---

### Task 6: Chroma plate (`core/sprite/generation/plate.py`)

**Files:**
- Create: `core/sprite/generation/plate.py`
- Create: `tests/sprite/generation/test_gen_plate.py`

**Interfaces:**
- Consumes: `providers.base.ImageProvider.edit_image(image, prompt, model, **kwargs) -> Tuple[List[str], List[bytes]]` (Google accepts a `Path` and `aspect_ratio=`), `ImageProvider.get_default_model()`; `core.utils.write_image_sidecar`; `prompts.color_name`, `prompts.normalize_hex`; `errors.classify_provider_error`, `errors.ProviderError`.
- Produces:
  - `PLATE_PROMPT: str`
  - `make_chroma_plate(provider, character: Path, out_png: Path, plate_color: str = "#00FF00", *, model: Optional[str] = None, aspect_ratio: str = "16:9", log: Callable[[str], None] = logger.info) -> Path`

- [ ] **Step 1: Write the failing tests**

`tests/sprite/generation/test_gen_plate.py`:

```python
"""Tests for core/sprite/generation/plate.py (chroma-plate-prep)."""
import io
import json
from unittest.mock import MagicMock

import pytest
from PIL import Image

from core.sprite.generation.errors import ProviderError, SafetyRefusal
from core.sprite.generation.plate import PLATE_PROMPT, make_chroma_plate


def _png_bytes(color=(0, 255, 0)):
    buf = io.BytesIO()
    Image.new("RGB", (16, 9), color).save(buf, format="PNG")
    return buf.getvalue()


def _provider(images=None, texts=None, raises=None):
    provider = MagicMock()
    provider.get_default_model.return_value = "image-model-default"
    if raises is not None:
        provider.edit_image.side_effect = raises
    else:
        provider.edit_image.return_value = (texts or [], images if images is not None else [_png_bytes()])
    return provider


def test_make_plate_calls_edit_image_with_prompt_and_aspect(png_file, tmp_path):
    src = png_file()
    provider = _provider(texts=["done"])
    out = tmp_path / "source" / "plate.png"
    seen = []
    result = make_chroma_plate(provider, src, out, "#00ff00", log=seen.append)
    assert result == out and out.exists()
    args, kwargs = provider.edit_image.call_args
    assert args[0] == src
    assert args[1] == PLATE_PROMPT.format(color_name="green", hex="#00FF00")
    assert args[2] == "image-model-default"
    assert kwargs["aspect_ratio"] == "16:9"
    # Prompt hygiene: no forbidden words, no aspect, no pixels.
    assert "transparent" not in args[1].lower() and "16:9" not in args[1]
    with Image.open(out) as img:
        assert img.mode == "RGBA"
    meta = json.loads(out.with_suffix(".png.json").read_text(encoding="utf-8"))
    assert meta["plate_color"] == "#00FF00"
    assert meta["kind"] == "chroma_plate"
    assert meta["model"] == "image-model-default"
    assert meta["prompt"] == args[1]
    assert meta["response_texts"] == ["done"]
    joined = "\n".join(seen)
    assert "Chroma plate request" in joined and "done" in joined


def test_make_plate_honors_model_and_aspect(png_file, tmp_path):
    provider = _provider()
    make_chroma_plate(provider, png_file(), tmp_path / "p.png", model="custom-image",
                      aspect_ratio="1:1")
    args, kwargs = provider.edit_image.call_args
    assert args[2] == "custom-image" and kwargs["aspect_ratio"] == "1:1"


def test_make_plate_raises_provider_error_when_no_image(png_file, tmp_path):
    provider = _provider(images=[])
    with pytest.raises(ProviderError, match="no image"):
        make_chroma_plate(provider, png_file(), tmp_path / "p.png")
    assert not (tmp_path / "p.png").exists()


def test_make_plate_classifies_provider_exceptions(png_file, tmp_path):
    provider = _provider(raises=RuntimeError("Google image editing failed: blocked by safety"))
    seen = []
    with pytest.raises(SafetyRefusal):
        make_chroma_plate(provider, png_file(), tmp_path / "p.png", log=seen.append)
    assert any("failed" in line.lower() for line in seen)


def test_make_plate_rejects_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        make_chroma_plate(_provider(), tmp_path / "missing.png", tmp_path / "p.png")
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_plate.py -v`
Expected: `ModuleNotFoundError: No module named 'core.sprite.generation.plate'`.

- [ ] **Step 3: Implement `plate.py`**

```python
"""Chroma plate preparation via an image edit (design §4.2).

Places the character on a flat solid plate color so the video model starts
from a keyable frame. Uses ``ImageProvider.edit_image`` (Google Gemini by
default). The prompt never mentions transparency, aspect, or pixel sizes.
"""
import io
import logging
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from core.sprite.generation._common import emit, now_iso
from core.sprite.generation.errors import ProviderError, classify_provider_error
from core.sprite.generation.prompts import color_name, normalize_hex
from core.utils import write_image_sidecar

logger = logging.getLogger(__name__)

PLATE_PROMPT = ("Place this exact character on a flat solid {color_name} background {hex}. "
                "Remove all shadows and reflections. Do not change the character.")


def make_chroma_plate(provider, character: Path, out_png: Path,
                      plate_color: str = "#00FF00", *, model: Optional[str] = None,
                      aspect_ratio: str = "16:9",
                      log: Callable[[str], None] = logger.info) -> Path:
    """Render ``character`` onto a solid ``plate_color`` plate and save ``out_png``."""
    character = Path(character)
    out_png = Path(out_png)
    if not character.exists():
        raise FileNotFoundError(f"Character image not found: {character}")

    hex_color = normalize_hex(plate_color)
    prompt = PLATE_PROMPT.format(color_name=color_name(hex_color), hex=hex_color)
    model_id = model or provider.get_default_model()
    provider_name = type(provider).__name__

    emit(logger, log, "=== Chroma plate request ===")
    emit(logger, log, f"provider={provider_name} model={model_id} aspect_ratio={aspect_ratio} "
                      f"plate_color={hex_color} image={character}")
    emit(logger, log, f"Prompt (FULL, {len(prompt)} chars):\n{prompt}")

    try:
        texts, images = provider.edit_image(character, prompt, model_id, aspect_ratio=aspect_ratio)
    except Exception as exc:  # noqa: BLE001 - classified below
        err = classify_provider_error(exc, provider="gemini")
        emit(logger, log, f"Chroma plate failed: {err.user_message}", level="error")
        raise err from exc

    emit(logger, log, f"=== Chroma plate response: {len(images)} image(s), {len(texts)} text(s) ===")
    for text in texts:
        emit(logger, log, f"Response text (FULL, {len(text)} chars):\n{text}")

    if not images:
        err = ProviderError("The image model returned no image for the chroma plate. "
                            "Try again or use another image model.")
        emit(logger, log, err.user_message, level="error")
        raise err

    with Image.open(io.BytesIO(images[0])) as img:
        rgba = img.convert("RGBA")
        out_png.parent.mkdir(parents=True, exist_ok=True)
        rgba.save(out_png, format="PNG")
        size = list(rgba.size)

    write_image_sidecar(out_png, {
        "kind": "chroma_plate",
        "prompt": prompt,
        "provider": provider_name,
        "model": model_id,
        "aspect_ratio": aspect_ratio,
        "plate_color": hex_color,
        "source": str(character),
        "size": size,
        "response_texts": list(texts),
        "timestamp": now_iso(),
    })
    emit(logger, log, f"Chroma plate saved: {out_png} ({size[0]}x{size[1]})")
    return out_png
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_plate.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/plate.py tests/sprite/generation/test_gen_plate.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): chroma plate generation through ImageProvider.edit_image"
```

---

### Task 7: Turnaround pack (`core/sprite/generation/turnaround.py`)

**Files:**
- Create: `core/sprite/generation/turnaround.py`
- Create: `tests/sprite/generation/test_gen_turnaround.py`

**Interfaces:**
- Consumes: `ImageProvider.edit_image`, `ImageProvider.get_default_model`; `core.sprite.pipeline.CancelToken`, `Cancelled`; `prompts.color_name`, `prompts.normalize_hex`; `errors.classify_provider_error`, `errors.ProviderError`; `core.utils.write_image_sidecar`.
- Produces:
  - `VIEWS = ("front", "side", "back", "three_quarter")`
  - `VIEW_PHRASES: Dict[str, str]`
  - `TURNAROUND_PROMPT: str`
  - `build_view_prompt(view: str, plate_color: str, do_not_change: Sequence[str]) -> str`
  - `generate_turnaround(provider, character: Path, out_dir: Path, views: Sequence[str] = VIEWS, *, plate_color: str, do_not_change: Sequence[str] = ("face", "hair", "proportions", "outfit"), model: Optional[str] = None, aspect_ratio: str = "1:1", log: Callable[[str], None] = logger.info, token: Optional[CancelToken] = None) -> Dict[str, Path]`

- [ ] **Step 1: Write the failing tests**

`tests/sprite/generation/test_gen_turnaround.py`:

```python
"""Tests for core/sprite/generation/turnaround.py (character-turnaround-pack)."""
import io
import json
from unittest.mock import MagicMock

import pytest
from PIL import Image

from core.sprite.generation.errors import QuotaExceeded
from core.sprite.generation.turnaround import (
    VIEW_PHRASES,
    VIEWS,
    build_view_prompt,
    generate_turnaround,
)
from core.sprite.pipeline import CancelToken, Cancelled


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (0, 255, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _provider():
    provider = MagicMock()
    provider.get_default_model.return_value = "img-default"
    provider.edit_image.return_value = (["ok"], [_png_bytes()])
    return provider


def test_views_and_phrases_cover_each_other():
    assert VIEWS == ("front", "side", "back", "three_quarter")
    assert set(VIEW_PHRASES) == set(VIEWS)


def test_build_view_prompt_lists_do_not_change_and_color():
    prompt = build_view_prompt("side", "#00ff00", ("face", "hair", "outfit"))
    assert VIEW_PHRASES["side"] in prompt
    assert "green background #00FF00" in prompt
    assert "Do not change the face, hair, and outfit." in prompt
    assert "transparent" not in prompt.lower() and ":" not in prompt.replace("#00FF00", "")


def test_build_view_prompt_rejects_unknown_view():
    with pytest.raises(ValueError):
        build_view_prompt("top", "#00FF00", ("face",))


def test_generate_turnaround_writes_each_view_with_sidecar(png_file, tmp_path):
    provider = _provider()
    out_dir = tmp_path / "turnaround"
    seen = []
    result = generate_turnaround(provider, png_file(), out_dir, plate_color="#00FF00",
                                 log=seen.append)
    assert list(result) == list(VIEWS)
    for view, path in result.items():
        assert path == out_dir / f"{view}.png" and path.exists()
        meta = json.loads(path.with_suffix(".png.json").read_text(encoding="utf-8"))
        assert meta["view"] == view and meta["kind"] == "turnaround"
        assert meta["plate_color"] == "#00FF00"
        assert meta["prompt"] == build_view_prompt(view, "#00FF00",
                                                   ("face", "hair", "proportions", "outfit"))
    assert provider.edit_image.call_count == 4
    _, kwargs = provider.edit_image.call_args
    assert kwargs["aspect_ratio"] == "1:1"
    assert sum("Turnaround request" in line for line in seen) == 4


def test_generate_turnaround_subset_and_model(png_file, tmp_path):
    provider = _provider()
    result = generate_turnaround(provider, png_file(), tmp_path / "t", views=("front",),
                                 plate_color="#0000FF", model="img-x")
    assert list(result) == ["front"]
    args, _ = provider.edit_image.call_args
    assert args[2] == "img-x" and "blue background #0000FF" in args[1]


def test_generate_turnaround_honors_cancel_token(png_file, tmp_path):
    provider = _provider()
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        generate_turnaround(provider, png_file(), tmp_path / "t", plate_color="#00FF00",
                            token=token)
    provider.edit_image.assert_not_called()


def test_generate_turnaround_classifies_errors_and_stops(png_file, tmp_path):
    provider = _provider()
    provider.edit_image.side_effect = [(["ok"], [_png_bytes()]),
                                       RuntimeError("429 quota exceeded")]
    with pytest.raises(QuotaExceeded):
        generate_turnaround(provider, png_file(), tmp_path / "t", plate_color="#00FF00")
    assert (tmp_path / "t" / "front.png").exists()
    assert not (tmp_path / "t" / "side.png").exists()
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_turnaround.py -v`
Expected: `ModuleNotFoundError: No module named 'core.sprite.generation.turnaround'`.

- [ ] **Step 3: Implement `turnaround.py`**

```python
"""Character turnaround pack: front / side / back / three-quarter (design §4.2).

Each view is an image edit of the character on the plate color. The views
serve as reference images for every video render so the character stays
consistent across clips.
"""
import io
import logging
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence

from PIL import Image

from core.sprite.generation._common import emit, now_iso
from core.sprite.generation.errors import ProviderError, classify_provider_error
from core.sprite.generation.prompts import color_name, normalize_hex
from core.sprite.pipeline import CancelToken
from core.utils import write_image_sidecar

logger = logging.getLogger(__name__)

VIEWS = ("front", "side", "back", "three_quarter")

VIEW_PHRASES: Dict[str, str] = {
    "front": "front view, facing the camera",
    "side": "side profile view, facing right",
    "back": "back view, facing away from the camera",
    "three_quarter": "three-quarter view, turned 45 degrees to the right",
}

TURNAROUND_PROMPT = (
    "Show this exact character from the {view_phrase}, standing in a neutral pose, "
    "on a flat solid {color_name} background {hex}. Do not change the {keep}. "
    "Same art style, same colors, same scale. No shadows, no reflections."
)


def _join_keep(items: Sequence[str]) -> str:
    items = [str(i).strip() for i in items if str(i).strip()]
    if not items:
        return "character"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + ", and " + items[-1]


def build_view_prompt(view: str, plate_color: str, do_not_change: Sequence[str]) -> str:
    """Prompt for one turnaround view. Raises ``ValueError`` on an unknown view."""
    if view not in VIEW_PHRASES:
        raise ValueError(f"Unknown turnaround view {view!r}. Use one of {VIEWS}.")
    hex_color = normalize_hex(plate_color)
    return TURNAROUND_PROMPT.format(view_phrase=VIEW_PHRASES[view],
                                    color_name=color_name(hex_color), hex=hex_color,
                                    keep=_join_keep(do_not_change))


def generate_turnaround(provider, character: Path, out_dir: Path,
                        views: Sequence[str] = VIEWS, *, plate_color: str,
                        do_not_change: Sequence[str] = ("face", "hair", "proportions", "outfit"),
                        model: Optional[str] = None, aspect_ratio: str = "1:1",
                        log: Callable[[str], None] = logger.info,
                        token: Optional[CancelToken] = None) -> Dict[str, Path]:
    """Render each view in ``views`` to ``out_dir/<view>.png`` with a sidecar."""
    character = Path(character)
    out_dir = Path(out_dir)
    if not character.exists():
        raise FileNotFoundError(f"Character image not found: {character}")
    model_id = model or provider.get_default_model()
    provider_name = type(provider).__name__
    hex_color = normalize_hex(plate_color)
    results: Dict[str, Path] = {}

    for view in views:
        if token is not None:
            token.raise_if_cancelled()
        prompt = build_view_prompt(view, hex_color, do_not_change)
        emit(logger, log, f"=== Turnaround request: {view} ===")
        emit(logger, log, f"provider={provider_name} model={model_id} aspect_ratio={aspect_ratio} "
                          f"plate_color={hex_color} image={character}")
        emit(logger, log, f"Prompt (FULL, {len(prompt)} chars):\n{prompt}")
        try:
            texts, images = provider.edit_image(character, prompt, model_id,
                                                aspect_ratio=aspect_ratio)
        except Exception as exc:  # noqa: BLE001 - classified below
            err = classify_provider_error(exc, provider="gemini")
            emit(logger, log, f"Turnaround view '{view}' failed: {err.user_message}", level="error")
            raise err from exc

        emit(logger, log, f"=== Turnaround response ({view}): {len(images)} image(s), "
                          f"{len(texts)} text(s) ===")
        for text in texts:
            emit(logger, log, f"Response text (FULL, {len(text)} chars):\n{text}")
        if not images:
            err = ProviderError(f"The image model returned no image for the '{view}' view.")
            emit(logger, log, err.user_message, level="error")
            raise err

        out_png = out_dir / f"{view}.png"
        with Image.open(io.BytesIO(images[0])) as img:
            rgba = img.convert("RGBA")
            out_dir.mkdir(parents=True, exist_ok=True)
            rgba.save(out_png, format="PNG")
            size = list(rgba.size)
        write_image_sidecar(out_png, {
            "kind": "turnaround",
            "view": view,
            "prompt": prompt,
            "provider": provider_name,
            "model": model_id,
            "aspect_ratio": aspect_ratio,
            "plate_color": hex_color,
            "do_not_change": list(do_not_change),
            "source": str(character),
            "size": size,
            "response_texts": list(texts),
            "timestamp": now_iso(),
        })
        results[view] = out_png
        emit(logger, log, f"Turnaround view saved: {out_png}")
    return results
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_turnaround.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/turnaround.py tests/sprite/generation/test_gen_turnaround.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): turnaround pack with do-not-change prompt and cancel token"
```

---

### Task 8: Action cards LLM contract (`core/sprite/generation/action_cards.py`)

**Files:**
- Create: `core/sprite/generation/action_cards.py`
- Create: `tests/sprite/generation/test_gen_action_cards.py`

**Interfaces:**
- Consumes: `core.llm_params.build_completion_kwargs`, `LLMParams`, `normalize_provider`; `core.llm_models.resolve_model`; `core.llm_parsing.LLMResponseParser.parse_json_response`; `core.sprite.project.ActionCard`; `errors.classify_provider_error`, `ProviderError`.
- Produces:
  - `CONTRACT_NAME = "Sprite Action Cards — Strict v1.0"`, `CONTRACT_VERSION = "1.0"`
  - `SYSTEM_PROMPT: str`, `USER_PROMPT_TEMPLATE: str`, `ACTION_CARDS_SCHEMA: dict`
  - `GENRE_CHECKLISTS: Dict[str, List[str]]` for `sidescroller`, `top_down`, `fighting`
  - `ActionCardDraft(name: str, prompt: str, duration_s: int, loop: bool, target_frames: int, fps: int)`
  - `build_messages(brief: str, genre: str, plate_color: str, character_notes: str) -> List[Dict[str, str]]`
  - `parse_action_cards(text: str) -> List[ActionCardDraft]`
  - `default_chat_model(provider: str) -> str`
  - `generate_action_cards(brief: str, genre: str, *, provider: str, model: Optional[str], api_key: Optional[str], plate_color: str, character_notes: str = "", auth_mode: Optional[str] = None, completion_fn: Optional[Callable[..., Any]] = None, log: Callable[[str], None] = logger.info) -> List[ActionCardDraft]`
  - `draft_to_card(draft: ActionCardDraft) -> ActionCard`

- [ ] **Step 1: Write the failing tests**

`tests/sprite/generation/test_gen_action_cards.py`:

```python
"""Tests for the 'Sprite Action Cards — Strict v1.0' LLM contract."""
import json
from types import SimpleNamespace

import pytest

from core.sprite.generation.action_cards import (
    ACTION_CARDS_SCHEMA,
    CONTRACT_NAME,
    GENRE_CHECKLISTS,
    SYSTEM_PROMPT,
    ActionCardDraft,
    build_messages,
    default_chat_model,
    draft_to_card,
    generate_action_cards,
    parse_action_cards,
)
from core.sprite.generation.errors import ProviderError, QuotaExceeded

VALID = {
    "version": "1.0",
    "cards": [
        {"name": "idle", "prompt": "the hero breathes slowly", "duration_s": 4,
         "loop": True, "target_frames": 6, "fps": 12},
        {"name": "attack", "prompt": "the hero swings a sword", "duration_s": 3,
         "loop": False, "target_frames": 8, "fps": 12},
    ],
}


def _response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_contract_text_and_schema():
    assert "Sprite Action Cards — Strict v1.0" in SYSTEM_PROMPT
    assert CONTRACT_NAME in SYSTEM_PROMPT
    assert "code fences" in SYSTEM_PROMPT
    assert ACTION_CARDS_SCHEMA["properties"]["cards"]["items"]["required"] == [
        "name", "prompt", "duration_s", "loop", "target_frames", "fps"]
    assert ACTION_CARDS_SCHEMA["properties"]["cards"]["items"]["properties"]["duration_s"] == {
        "type": "integer", "minimum": 1, "maximum": 15}


def test_genre_checklists():
    assert set(GENRE_CHECKLISTS) == {"sidescroller", "top_down", "fighting"}
    assert GENRE_CHECKLISTS["sidescroller"] == [
        "idle", "walk", "run", "jump", "fall", "attack", "hurt", "death"]
    for names in GENRE_CHECKLISTS.values():
        assert names[0] == "idle" and len(names) == len(set(names))


def test_build_messages_shape_and_hygiene():
    messages = build_messages("a knight with a red cape", "sidescroller", "#00FF00", "cape flows")
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[0]["content"] == SYSTEM_PROMPT
    user = messages[1]["content"]
    assert "BRIEF: a knight with a red cape" in user
    assert "idle, walk, run, jump, fall, attack, hurt, death" in user
    assert "CHARACTER NOTES: cape flows" in user
    assert "green" in user
    assert "16:9" not in user and "transparent" not in user.lower().replace('"transparent"', "")


def test_build_messages_rejects_unknown_genre():
    with pytest.raises(ValueError):
        build_messages("x", "rts", "#00FF00", "")


def test_parse_plain_json():
    cards = parse_action_cards(json.dumps(VALID))
    assert [c.name for c in cards] == ["idle", "attack"]
    assert cards[0] == ActionCardDraft("idle", "the hero breathes slowly", 4, True, 6, 12)


def test_parse_tolerates_fences_and_prose():
    fence = "`" * 3  # built at runtime so the Markdown plan file keeps its own fence intact
    text = f"Here you go:\n{fence}json\n" + json.dumps(VALID) + f"\n{fence}\nEnjoy."
    assert len(parse_action_cards(text)) == 2


def test_parse_accepts_bare_list():
    assert len(parse_action_cards(json.dumps(VALID["cards"]))) == 2


def test_parse_drops_invalid_names_durations_and_duplicates():
    data = {"version": "1.0", "cards": [
        {"name": "Walk Cycle", "prompt": "p", "duration_s": 4, "loop": True, "target_frames": 8, "fps": 12},
        {"name": "walk", "prompt": "p", "duration_s": 0, "loop": True, "target_frames": 8, "fps": 12},
        {"name": "walk", "prompt": "p", "duration_s": 16, "loop": True, "target_frames": 8, "fps": 12},
        {"name": "walk", "prompt": "p", "duration_s": 5, "loop": "true", "target_frames": 100, "fps": 13},
        {"name": "walk", "prompt": "dup", "duration_s": 5, "loop": True, "target_frames": 8, "fps": 12},
        {"name": "run", "prompt": "", "duration_s": 5, "loop": True, "target_frames": 8, "fps": 12},
    ]}
    cards = parse_action_cards(json.dumps(data))
    assert len(cards) == 1
    card = cards[0]
    assert card.name == "walk" and card.duration_s == 5 and card.loop is True
    assert card.target_frames == 64 and card.fps == 12


def test_parse_strips_forbidden_words_from_prompts():
    data = {"cards": [{"name": "idle", "prompt": "idle on a transparent 16:9 background",
                       "duration_s": 4, "loop": True, "target_frames": 8, "fps": 12}]}
    card = parse_action_cards(json.dumps(data))[0]
    assert "transparent" not in card.prompt and "16:9" not in card.prompt


def test_parse_raises_when_nothing_valid():
    with pytest.raises(ValueError):
        parse_action_cards("no json here")
    with pytest.raises(ValueError):
        parse_action_cards(json.dumps({"cards": []}))


def test_default_chat_model_resolves_per_provider():
    for provider in ("openai", "anthropic", "gemini", "google"):
        assert default_chat_model(provider)
    with pytest.raises(ValueError):
        default_chat_model("nope")


def test_generate_action_cards_logs_request_and_response(monkeypatch):
    calls = []
    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _response(json.dumps(VALID))
    seen = []
    cards = generate_action_cards("a knight", "sidescroller", provider="openai",
                                  model="gpt-4o", api_key="sk-test", plate_color="#00FF00",
                                  completion_fn=fake_completion, log=seen.append)
    assert [c.name for c in cards] == ["idle", "attack"]
    kwargs = calls[0]
    assert kwargs["model"] == "gpt-4o" and kwargs["api_key"] == "sk-test"
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["temperature"] == 0.2
    joined = "\n".join(seen)
    assert "=== LLM REQUEST" in joined and "=== LLM RESPONSE" in joined
    assert "sk-test" not in joined
    assert SYSTEM_PROMPT in joined
    assert json.dumps(VALID) in joined


def test_generate_action_cards_resolves_default_model(monkeypatch):
    monkeypatch.setattr("core.sprite.generation.action_cards.default_chat_model",
                        lambda provider: "resolved-model")
    calls = []
    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _response(json.dumps(VALID))
    generate_action_cards("a knight", "top_down", provider="openai", model=None,
                          api_key="k", plate_color="#00FF00", completion_fn=fake_completion)
    assert calls[0]["model"] == "resolved-model"


def test_generate_action_cards_classifies_provider_errors():
    def boom(**kwargs):
        raise RuntimeError("429 rate limit")
    with pytest.raises(QuotaExceeded):
        generate_action_cards("a knight", "fighting", provider="openai", model="gpt-4o",
                              api_key="k", plate_color="#00FF00", completion_fn=boom)


def test_generate_action_cards_wraps_malformed_response():
    def bad(**kwargs):
        return _response("not json")
    with pytest.raises(ProviderError, match="contract"):
        generate_action_cards("a knight", "fighting", provider="openai", model="gpt-4o",
                              api_key="k", plate_color="#00FF00", completion_fn=bad)


def test_draft_to_card():
    card = draft_to_card(ActionCardDraft("idle", "p", 4, True, 6, 12))
    assert card.name == "idle" and card.prompt == "p" and card.duration_s == 4
    assert card.loop is True and card.target_frames == 6 and card.fps == 12
    assert card.status == "draft" and len(card.id) == 32
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_action_cards.py -v`
Expected: `ModuleNotFoundError: No module named 'core.sprite.generation.action_cards'`.

- [ ] **Step 3: Implement `action_cards.py`**

```python
"""LLM contract "Sprite Action Cards — Strict v1.0" (design §4.2).

Turns a brief plus a genre checklist into action cards. Follows
``Docs/LLM-Contracts.md``: a versioned system prompt, a user prompt that
restates the constraints, and a strict validator with a tolerant parser.
Request and response are logged in full (``Docs/LLM-Logging-Full-Content.md``).
"""
import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from core.llm_models import resolve_model
from core.llm_params import LLMParams, build_completion_kwargs, normalize_provider
from core.llm_parsing import LLMResponseParser
from core.sprite.generation._common import emit
from core.sprite.generation.errors import ProviderError, classify_provider_error
from core.sprite.generation.prompts import color_name, normalize_hex, strip_render_terms
from core.sprite.project import ActionCard

logger = logging.getLogger(__name__)

CONTRACT_NAME = "Sprite Action Cards — Strict v1.0"
CONTRACT_VERSION = "1.0"
ALLOWED_FPS = (8, 12, 24)
MIN_DURATION_S, MAX_DURATION_S = 1, 15
MIN_FRAMES, MAX_FRAMES = 2, 64
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")

GENRE_CHECKLISTS: Dict[str, List[str]] = {
    "sidescroller": ["idle", "walk", "run", "jump", "fall", "attack", "hurt", "death"],
    "top_down": ["idle", "walk_down", "walk_up", "walk_side", "attack", "hurt", "death"],
    "fighting": ["idle", "walk_forward", "walk_back", "crouch", "jump", "light_punch",
                 "heavy_kick", "block", "hurt", "knockdown"],
}

ACTION_CARDS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["version", "cards"],
    "properties": {
        "version": {"type": "string", "const": CONTRACT_VERSION},
        "cards": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "prompt", "duration_s", "loop", "target_frames", "fps"],
                "properties": {
                    "name": {"type": "string", "pattern": _NAME_RE.pattern},
                    "prompt": {"type": "string", "minLength": 1},
                    "duration_s": {"type": "integer", "minimum": MIN_DURATION_S,
                                   "maximum": MAX_DURATION_S},
                    "loop": {"type": "boolean"},
                    "target_frames": {"type": "integer", "minimum": MIN_FRAMES,
                                      "maximum": MAX_FRAMES},
                    "fps": {"type": "integer", "enum": list(ALLOWED_FPS)},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

SYSTEM_PROMPT = f"""You are "{CONTRACT_NAME}".
You design animation action cards for a 2D game sprite.
Output must be a single JSON object that conforms exactly to the Sprite Action Cards Output Contract v{CONTRACT_VERSION}.
Do not include commentary, Markdown, or code fences.

Contract v{CONTRACT_VERSION}:
{{"version": "{CONTRACT_VERSION}", "cards": [{{"name": string, "prompt": string, "duration_s": integer, "loop": boolean, "target_frames": integer, "fps": integer}}]}}

Rules:
- name: snake_case ASCII, unique, 2-32 characters (examples: idle, walk, attack_heavy).
- prompt: one paragraph that describes the motion of the character only, in the present tense. Start with "the character". Never describe the background, the camera, the aspect ratio, the resolution, or transparency. Never use the words "transparent", "checkerboard", or "alpha".
- duration_s: integer {MIN_DURATION_S}..{MAX_DURATION_S}.
- loop: true for cycles (idle, walk, run), false for one-shot actions (attack, hurt, death).
- target_frames: integer {MIN_FRAMES}..{MAX_FRAMES}.
- fps: one of {", ".join(str(f) for f in ALLOWED_FPS)}.
- Cover every action in the genre checklist first, in the given order, then add up to 4 more that fit the brief.
"""

USER_PROMPT_TEMPLATE = """TASK: Create action cards for this character.
Return exactly one JSON object per the Sprite Action Cards Output Contract v{version}.

BRIEF: {brief}
GENRE: {genre}
GENRE CHECKLIST (required, in this order): {checklist}
CHARACTER NOTES: {character_notes}
BACKGROUND: the application appends the background instruction (a solid {color_name} plate) after your prompt. Do not mention the background.

CONSTRAINTS:
- One card per checklist item, then optional extras.
- name in snake_case; duration_s integer {min_s}..{max_s}; fps in [{fps_list}].
- No fields beyond the contract.
"""


@dataclass
class ActionCardDraft:
    name: str
    prompt: str
    duration_s: int
    loop: bool
    target_frames: int
    fps: int


def build_messages(brief: str, genre: str, plate_color: str,
                   character_notes: str) -> List[Dict[str, str]]:
    """System + user messages for the contract. Raises ``ValueError`` on an unknown genre."""
    if genre not in GENRE_CHECKLISTS:
        raise ValueError(f"Unknown genre {genre!r}. Use one of {sorted(GENRE_CHECKLISTS)}.")
    user = USER_PROMPT_TEMPLATE.format(
        version=CONTRACT_VERSION,
        brief=brief.strip(),
        genre=genre,
        checklist=", ".join(GENRE_CHECKLISTS[genre]),
        character_notes=character_notes.strip() or "(none)",
        color_name=color_name(normalize_hex(plate_color)),
        min_s=MIN_DURATION_S, max_s=MAX_DURATION_S,
        fps_list=", ".join(str(f) for f in ALLOWED_FPS),
    )
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user}]


def _extract_json(text: str) -> Optional[Any]:
    parsed = LLMResponseParser.parse_json_response(text, expected_type=dict)
    if parsed is None:
        parsed = LLMResponseParser.parse_json_response(text, expected_type=list)
    if parsed is not None:
        return parsed
    # Fences or prose around the object: take the outermost braces / brackets.
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if 0 <= start < end:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    return None


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return None


def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def parse_action_cards(text: str) -> List[ActionCardDraft]:
    """Validate a contract response. Tolerates fences and prose.

    Invalid cards are dropped with a logged warning: bad snake_case names,
    duration outside 1..15, empty prompts, duplicate names (first wins).
    ``target_frames`` is clamped to 2..64 and ``fps`` snaps to 8/12/24.
    Raises ``ValueError`` when no valid card remains.
    """
    data = _extract_json(text or "")
    if data is None:
        raise ValueError("Response contained no JSON object.")
    if isinstance(data, dict):
        version = data.get("version")
        if version is not None and str(version) != CONTRACT_VERSION:
            logger.warning("Action cards: contract version %r, expected %r", version, CONTRACT_VERSION)
        cards = data.get("cards")
    else:
        cards = data
    if not isinstance(cards, list):
        raise ValueError("Response JSON has no 'cards' list.")

    drafts: List[ActionCardDraft] = []
    seen = set()
    for index, item in enumerate(cards):
        if not isinstance(item, dict):
            logger.warning("Action card %d is not an object; dropped", index)
            continue
        name = str(item.get("name", "")).strip()
        if not _NAME_RE.match(name):
            logger.warning("Action card %d: name %r is not snake_case; dropped", index, name)
            continue
        if name in seen:
            logger.warning("Action card %d: duplicate name %r; dropped", index, name)
            continue
        prompt = strip_render_terms(str(item.get("prompt", "")))
        if not prompt:
            logger.warning("Action card %d (%s): empty prompt; dropped", index, name)
            continue
        duration = _as_int(item.get("duration_s"))
        if duration is None or not MIN_DURATION_S <= duration <= MAX_DURATION_S:
            logger.warning("Action card %d (%s): duration_s %r outside %d..%d; dropped",
                           index, name, item.get("duration_s"), MIN_DURATION_S, MAX_DURATION_S)
            continue
        loop = _as_bool(item.get("loop"))
        if loop is None:
            loop = True
            logger.warning("Action card %d (%s): loop missing; assumed true", index, name)
        frames = _as_int(item.get("target_frames"))
        if frames is None:
            frames = 8
        frames = max(MIN_FRAMES, min(MAX_FRAMES, frames))
        fps_value = _as_int(item.get("fps"))
        if fps_value is None:
            fps_value = 12
        fps_value = min(ALLOWED_FPS, key=lambda f: abs(f - fps_value))
        seen.add(name)
        drafts.append(ActionCardDraft(name=name, prompt=prompt, duration_s=duration,
                                      loop=loop, target_frames=frames, fps=fps_value))
    if not drafts:
        raise ValueError("Response contained no valid action card.")
    return drafts


# Registry family per chat provider; static defaults are offline fallbacks only.
_CHAT_FAMILY = {
    "openai": ("openai", "chat", "gpt-4o"),
    "anthropic": ("anthropic", "sonnet", "claude-sonnet-4-6"),
    "gemini": ("gemini", "flash", "gemini-2.5-flash"),
}


def default_chat_model(provider: str) -> str:
    """Current chat model id for ``provider`` via the model registry."""
    provider_id = normalize_provider(provider)
    if provider_id not in _CHAT_FAMILY:
        raise ValueError(f"No default chat model for provider {provider!r}.")
    registry_provider, family, static = _CHAT_FAMILY[provider_id]
    return resolve_model(registry_provider, family, static_default=static)


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            return str(message.get("content") or "")
        return ""
    choices = getattr(response, "choices", None) or []
    if choices:
        message = getattr(choices[0], "message", None)
        return str(getattr(message, "content", "") or "")
    return str(response)


def generate_action_cards(brief: str, genre: str, *, provider: str, model: Optional[str],
                          api_key: Optional[str], plate_color: str, character_notes: str = "",
                          auth_mode: Optional[str] = None,
                          completion_fn: Optional[Callable[..., Any]] = None,
                          log: Callable[[str], None] = logger.info) -> List[ActionCardDraft]:
    """Run the contract against a chat model and return validated drafts.

    ``completion_fn`` defaults to ``litellm.completion``. Kwargs come from
    ``build_completion_kwargs`` (temperature 0.2, max_tokens 4000, JSON mode
    where the model supports it). The model defaults to
    ``default_chat_model(provider)``.
    """
    provider_id = normalize_provider(provider)
    model_id = model or default_chat_model(provider_id)
    messages = build_messages(brief, genre, plate_color, character_notes)
    params = LLMParams(temperature=0.2, max_tokens=4000,
                       response_format={"type": "json_object"})
    kwargs = build_completion_kwargs(provider_id, model_id, messages, params,
                                     api_key=api_key, auth_mode=auth_mode,
                                     on_warning=lambda m: emit(logger, log, m, level="warning"))

    shown = {k: v for k, v in kwargs.items() if k not in ("messages", "api_key")}
    emit(logger, log, f"=== LLM REQUEST ({CONTRACT_NAME}) ===")
    emit(logger, log, f"provider={provider_id} model={kwargs['model']} params={json.dumps(shown, default=str)}")
    for message in messages:
        emit(logger, log, f"{message['role']} (FULL, {len(message['content'])} chars):\n{message['content']}")
    emit(logger, log, "=== END LLM REQUEST ===")

    if completion_fn is None:
        import litellm
        litellm.drop_params = True
        completion_fn = litellm.completion

    try:
        response = completion_fn(**kwargs)
    except Exception as exc:  # noqa: BLE001 - classified below
        err = classify_provider_error(exc, provider=provider_id)
        emit(logger, log, f"Action cards failed: {err.user_message}", level="error")
        raise err from exc

    text = _response_text(response)
    emit(logger, log, "=== LLM RESPONSE ===")
    emit(logger, log, f"Response length: {len(text)} characters")
    emit(logger, log, f"Full response:\n{text}")
    emit(logger, log, "=== END LLM RESPONSE ===")

    try:
        drafts = parse_action_cards(text)
    except ValueError as exc:
        err = ProviderError(f"The model did not follow the {CONTRACT_NAME} contract: {exc} "
                            "Try again or pick another model.")
        emit(logger, log, err.user_message, level="error")
        raise err from exc
    emit(logger, log, f"Action cards: {len(drafts)} valid card(s): "
                      f"{', '.join(d.name for d in drafts)}")
    return drafts


def draft_to_card(draft: ActionCardDraft) -> ActionCard:
    """Promote a draft to a project ``ActionCard`` with a fresh id."""
    return ActionCard(id=uuid.uuid4().hex, name=draft.name, prompt=draft.prompt,
                      duration_s=draft.duration_s, loop=draft.loop,
                      target_frames=draft.target_frames, fps=draft.fps)
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_action_cards.py -v`
Expected: 16 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/action_cards.py tests/sprite/generation/test_gen_action_cards.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): action cards LLM contract (Strict v1.0) with tolerant parser"
```

---

### Task 9: Client cancel hooks (`VeoClient`, `OmniClient`)

**Files:**
- Modify: `core/video/veo_client.py` — `VeoClient.__init__` (183–211), `generate_video_async` (325–610), `generate_video` (612–627), `_poll_for_completion` (793–904); add `VeoPollCancelled` after `VeoGenerationResult` (138–152).
- Modify: `core/video/omni_client.py` — `generate_video_async` (259–366), `generate_video` (368–376), `_await_terminal` (378–406); add `OmniPollCancelled` after `OmniGenerationResult` (194–204).
- Create: `tests/video/test_veo_cancel_hook.py`
- Create: `tests/video/test_omni_cancel_hook.py`

**Interfaces:**
- Consumes: existing client internals listed above.
- Produces:
  - `veo_client.VeoPollCancelled(Exception)`
  - `VeoClient.poll_interval: int = 10` (instance attribute; the poll loop reads it)
  - `VeoClient._poll_for_completion(self, operation, max_wait, cancel_check: Optional[Callable[[], bool]] = None)`
  - `VeoClient.generate_video_async(self, config, cancel_check: Optional[Callable[[], bool]] = None)`
  - `VeoClient.generate_video(self, config, cancel_check: Optional[Callable[[], bool]] = None)`
  - `omni_client.OmniPollCancelled(Exception)`
  - `OmniClient._await_terminal(self, interaction, cancel_check: Optional[Callable[[], bool]] = None)`
  - `OmniClient.generate_video_async(self, config, output_path, cancel_check: Optional[Callable[[], bool]] = None)`
  - `OmniClient.generate_video(self, config, output_path, cancel_check: Optional[Callable[[], bool]] = None)`
  - Contract: when `cancel_check()` returns `True`, the poll loop stops, the result has `success=False, error="cancelled"`, and `operation_id` / `interaction_id` is preserved. When the check is `True` before the provider call, no call is made.

- [ ] **Step 1: Write the failing tests**

`tests/video/test_veo_cancel_hook.py`:

```python
"""Cancel hook for VeoClient polling (sprite design §1.1)."""
import asyncio
import logging
from types import SimpleNamespace

import pytest

from core.video.veo_client import (
    VeoClient,
    VeoGenerationConfig,
    VeoModel,
    VeoPollCancelled,
)


def _client():
    # Bypass __init__: no network region lookup, no genai client required.
    client = VeoClient.__new__(VeoClient)
    client.logger = logging.getLogger("test.veo")
    client.poll_interval = 0
    client.person_generation_allowed = True
    client.region = "US"
    client.auth_mode = "api-key"
    client.api_key = "k"
    return client


def _pending_operation():
    return SimpleNamespace(name="op-1", done=False, error=None, response=None)


def test_poll_raises_when_cancel_fires():
    client = _client()
    op = _pending_operation()
    client.client = SimpleNamespace(operations=SimpleNamespace(get=lambda o: o))
    with pytest.raises(VeoPollCancelled):
        asyncio.run(client._poll_for_completion(op, max_wait=5, cancel_check=lambda: True))


def test_poll_finishes_when_cancel_never_fires():
    client = _client()
    video = SimpleNamespace(uri="https://example.invalid/v.mp4", video_bytes=None)
    done = SimpleNamespace(name="op-1", done=True, error=None,
                           response=SimpleNamespace(generated_videos=[SimpleNamespace(video=video)]))
    pending = _pending_operation()
    client.client = SimpleNamespace(operations=SimpleNamespace(get=lambda o: done))
    result = asyncio.run(client._poll_for_completion(pending, max_wait=5, cancel_check=lambda: False))
    assert result == "https://example.invalid/v.mp4"


def test_poll_returns_finished_video_even_if_cancel_fires_after_done():
    client = _client()
    video = SimpleNamespace(uri="https://example.invalid/v.mp4", video_bytes=None)
    done = SimpleNamespace(name="op-1", done=True, error=None,
                           response=SimpleNamespace(generated_videos=[SimpleNamespace(video=video)]))
    calls = {"n": 0}
    def cancel():
        calls["n"] += 1
        return calls["n"] > 1  # first check False, later True
    client.client = SimpleNamespace(operations=SimpleNamespace(get=lambda o: done))
    result = asyncio.run(client._poll_for_completion(done, max_wait=5, cancel_check=cancel))
    assert result == "https://example.invalid/v.mp4"


def test_generate_video_reports_cancelled_and_keeps_operation_id():
    pytest.importorskip("google.genai")
    client = _client()
    started = []
    def generate_videos(**kwargs):
        started.append(kwargs)
        return _pending_operation()
    client.client = SimpleNamespace(
        models=SimpleNamespace(generate_videos=generate_videos),
        operations=SimpleNamespace(get=lambda o: o),
    )
    cfg = VeoGenerationConfig(model=VeoModel.VEO_3_1_FAST, prompt="p", duration=4,
                              resolution="720p", include_audio=False)
    calls = {"n": 0}
    def cancel():
        calls["n"] += 1
        return calls["n"] > 1  # pre-flight check passes; the poll loop sees the cancel
    result = client.generate_video(cfg, cancel_check=cancel)
    assert result.success is False
    assert result.error == "cancelled"
    assert result.operation_id == "op-1"
    assert len(started) == 1


def test_generate_video_skips_provider_call_when_cancelled_before_start():
    pytest.importorskip("google.genai")
    client = _client()
    started = []
    client.client = SimpleNamespace(
        models=SimpleNamespace(generate_videos=lambda **kw: started.append(kw)),
        operations=SimpleNamespace(get=lambda o: o),
    )
    fired = {"n": 0}
    def cancel():
        fired["n"] += 1
        return True
    cfg = VeoGenerationConfig(model=VeoModel.VEO_3_1_FAST, prompt="p", duration=4,
                              resolution="720p", include_audio=False)
    # Fire before the request is sent: the pre-flight check runs first.
    result = client.generate_video(cfg, cancel_check=cancel)
    assert result.success is False and result.error == "cancelled"
    assert started == []
    assert result.operation_id is None


def test_generate_video_without_cancel_check_keeps_old_signature():
    pytest.importorskip("google.genai")
    client = _client()
    client.client = SimpleNamespace(
        models=SimpleNamespace(generate_videos=lambda **kw: SimpleNamespace(
            name="op-2", done=True, error="boom", response=None)),
        operations=SimpleNamespace(get=lambda o: o),
    )
    cfg = VeoGenerationConfig(model=VeoModel.VEO_3_1_FAST, prompt="p", duration=4,
                              resolution="720p", include_audio=False)
    result = client.generate_video(cfg)
    assert result.success is False and result.error != "cancelled"
```

`tests/video/test_omni_cancel_hook.py`:

```python
"""Cancel hook for OmniClient polling (sprite design §1.1)."""
import asyncio
import types as pytypes

import pytest

from core.video.omni_client import OmniClient, OmniGenerationConfig, OmniPollCancelled


class _Interaction:
    def __init__(self, id="int_1", status="in_progress"):
        self.id = id
        self.status = status
        self.steps = []
        self.output_video = None


class _Resource:
    def __init__(self, created, polled=None):
        self._created = created
        self._polled = polled or created
        self.create_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._created

    def get(self, interaction_id):
        return self._polled


def _client(resource):
    client = OmniClient(api_key="test-key")
    client.client = pytypes.SimpleNamespace(interactions=resource, files=None)
    client.polling_interval = 0
    return client


def test_await_terminal_raises_when_cancel_fires():
    client = _client(_Resource(_Interaction()))
    with pytest.raises(OmniPollCancelled):
        asyncio.run(client._await_terminal(_Interaction(), cancel_check=lambda: True))


def test_await_terminal_returns_terminal_interaction_without_cancel():
    done = _Interaction(status="completed")
    client = _client(_Resource(_Interaction(), polled=done))
    result = asyncio.run(client._await_terminal(_Interaction(), cancel_check=lambda: False))
    assert result is done


def test_generate_video_reports_cancelled_and_keeps_interaction_id(tmp_path):
    resource = _Resource(_Interaction(id="int_poll"))
    client = _client(resource)
    calls = {"n": 0}
    def cancel():
        calls["n"] += 1
        return calls["n"] > 1  # pre-flight check passes; the poll loop sees the cancel
    result = client.generate_video(OmniGenerationConfig(prompt="a sunset"),
                                   tmp_path / "out.mp4", cancel_check=cancel)
    assert result.success is False
    assert result.error == "cancelled"
    assert result.interaction_id == "int_poll"
    assert len(resource.create_calls) == 1
    assert not (tmp_path / "out.mp4").exists()


def test_generate_video_skips_create_when_cancelled_before_start(tmp_path):
    resource = _Resource(_Interaction())
    client = _client(resource)
    fired = {"n": 0}
    def cancel():
        fired["n"] += 1
        return True
    result = client.generate_video(OmniGenerationConfig(prompt="a sunset"),
                                   tmp_path / "out.mp4", cancel_check=cancel)
    assert result.success is False and result.error == "cancelled"
    assert resource.create_calls == []
    assert result.interaction_id is None


def test_generate_video_without_cancel_check_still_works(tmp_path):
    import base64
    done = _Interaction(status="completed")
    done.output_video = pytypes.SimpleNamespace(
        type="video", data=base64.b64encode(b"mp4bytes").decode("ascii"),
        uri=None, mime_type="video/mp4")
    client = _client(_Resource(done))
    result = client.generate_video(OmniGenerationConfig(prompt="a sunset"), tmp_path / "o.mp4")
    assert result.success is True
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/test_veo_cancel_hook.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/test_omni_cancel_hook.py -v`
Expected: `ImportError: cannot import name 'VeoPollCancelled'` and `ImportError: cannot import name 'OmniPollCancelled'`.

- [ ] **Step 3: Modify `core/video/veo_client.py`**

3a. Add `Callable` to the typing import on line 14:

```python
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
```

3b. Insert after the `VeoGenerationResult` dataclass (after line 152):

```python
class VeoPollCancelled(Exception):
    """Raised inside the poll loop when ``cancel_check`` returns True.

    The remote operation keeps running; the caller keeps the operation id.
    """
```

3c. In `VeoClient.__init__`, after `self.logger = logging.getLogger(__name__)` (line 200), add:

```python
        self.poll_interval = 10  # Google docs recommend 10-second polling
```

3d. Change the `generate_video_async` signature (line 325) and add a pre-flight cancel check. Replace:

```python
    async def generate_video_async(self, config: VeoGenerationConfig) -> VeoGenerationResult:
```

with:

```python
    async def generate_video_async(self, config: VeoGenerationConfig,
                                   cancel_check: Optional[Callable[[], bool]] = None
                                   ) -> VeoGenerationResult:
```

Immediately after the `is_valid` block (after the `return result` at line 342), add:

```python
        if cancel_check is not None and cancel_check():
            result.success = False
            result.error = "cancelled"
            self.logger.info("Veo generation cancelled before the request was sent")
            return result
```

3e. Thread the hook into the poll call inside `generate_video_async` (line 572). The same line also appears in `extend_video_async` (line 735); leave that one unchanged. Replace the first occurrence only:

```python
            video_result = await self._poll_for_completion(response, max_wait)
```

with:

```python
            video_result = await self._poll_for_completion(response, max_wait,
                                                           cancel_check=cancel_check)
```

3f. Add a cancel branch before the generic handler in `generate_video_async`. Replace lines 606–609:

```python
        except Exception as e:
            self.logger.error(f"Veo generation failed: {e}")
            result.success = False
            result.error = str(e)
```

with:

```python
        except VeoPollCancelled:
            result.success = False
            result.error = "cancelled"
            self.logger.info(f"Veo generation cancelled by the caller; operation "
                             f"{result.operation_id} keeps running remotely")
        except Exception as e:
            self.logger.error(f"Veo generation failed: {e}")
            result.success = False
            result.error = str(e)
```

3g. Change `generate_video` (612–627). Replace the signature and the `run_until_complete` line:

```python
    def generate_video(self, config: VeoGenerationConfig,
                       cancel_check: Optional[Callable[[], bool]] = None) -> VeoGenerationResult:
```

```python
            return loop.run_until_complete(self.generate_video_async(config, cancel_check=cancel_check))
```

3h. Rewrite `_poll_for_completion`'s signature, the interval, the loop head, the sleep, and the exception handler. Replace the signature (line 793):

```python
    async def _poll_for_completion(self, operation: Any, max_wait: int,
                                   cancel_check: Optional[Callable[[], bool]] = None
                                   ) -> Optional[Union[str, bytes]]:
```

Replace `poll_interval = 10  # Google docs recommend 10 second intervals` (line 804) with:

```python
        poll_interval = getattr(self, "poll_interval", 10)
```

Inside the `while` loop, replace the first lines of the `try:` block (lines 811–813):

```python
            try:
                elapsed = time.time() - start_time
                poll_count += 1
```

with:

```python
            try:
                if cancel_check is not None and cancel_check() and not operation.done:
                    self.logger.info(f"Poll cancelled by the caller; operation {operation.name} "
                                     f"keeps running remotely")
                    raise VeoPollCancelled(operation.name)
                elapsed = time.time() - start_time
                poll_count += 1
```

Replace `await asyncio.sleep(poll_interval)` (line 894) with:

```python
                await self._sleep_with_cancel(poll_interval, cancel_check)
```

Replace the loop's exception handler (lines 899–901):

```python
            except Exception as e:
                self.logger.error(f"Error polling for completion: {e}", exc_info=True)
                return None
```

with:

```python
            except VeoPollCancelled:
                raise
            except Exception as e:
                self.logger.error(f"Error polling for completion: {e}", exc_info=True)
                return None
```

3i. Add the sliced sleep helper right after `_poll_for_completion` (before `_download_video`):

```python
    async def _sleep_with_cancel(self, seconds: float,
                                 cancel_check: Optional[Callable[[], bool]]) -> None:
        """Sleep ``seconds`` in 1-second slices so a cancel is seen quickly."""
        end = time.time() + seconds
        while True:
            if cancel_check is not None and cancel_check():
                raise VeoPollCancelled()
            remaining = end - time.time()
            if remaining <= 0:
                return
            await asyncio.sleep(min(1.0, remaining))
```

- [ ] **Step 4: Modify `core/video/omni_client.py`**

4a. Add `Callable` to the typing import (line 31):

```python
from typing import Any, Callable, Dict, List, Optional, Tuple
```

4b. Insert after the `OmniGenerationResult` dataclass (after line 204):

```python
class OmniPollCancelled(Exception):
    """Raised inside the poll loop when ``cancel_check`` returns True.

    The remote interaction keeps running; the caller keeps the interaction id.
    """
```

4c. Change the `generate_video_async` signature (259–260):

```python
    async def generate_video_async(self, config: OmniGenerationConfig,
                                   output_path: Path,
                                   cancel_check: Optional[Callable[[], bool]] = None
                                   ) -> OmniGenerationResult:
```

After the `if not self.client:` block (after line 284), add the pre-flight check:

```python
        if cancel_check is not None and cancel_check():
            result.success = False
            result.error = "cancelled"
            self.logger.info("Omni generation cancelled before the request was sent")
            return result
```

Replace lines 305–310:

```python
            interaction = await asyncio.to_thread(
                self.client.interactions.create, **kwargs
            )

            interaction = await self._await_terminal(interaction)
            result.interaction_id = getattr(interaction, "id", None)
```

with:

```python
            interaction = await asyncio.to_thread(
                self.client.interactions.create, **kwargs
            )
            # Record the id before polling so a cancel keeps it.
            result.interaction_id = getattr(interaction, "id", None)

            interaction = await self._await_terminal(interaction, cancel_check=cancel_check)
            result.interaction_id = getattr(interaction, "id", None) or result.interaction_id
```

Replace the generic handler (360–364):

```python
        except Exception as e:
            result.success = False
            result.error = str(e)
            result.generation_time = time.time() - start_time
            self.logger.error(f"Omni generation failed: {e}", exc_info=True)
```

with:

```python
        except OmniPollCancelled:
            result.success = False
            result.error = "cancelled"
            result.generation_time = time.time() - start_time
            self.logger.info(f"Omni generation cancelled by the caller; interaction "
                             f"{result.interaction_id} keeps running remotely")
        except Exception as e:
            result.success = False
            result.error = str(e)
            result.generation_time = time.time() - start_time
            self.logger.error(f"Omni generation failed: {e}", exc_info=True)
```

4d. Change `generate_video` (368–376):

```python
    def generate_video(self, config: OmniGenerationConfig, output_path: Path,
                       cancel_check: Optional[Callable[[], bool]] = None
                       ) -> OmniGenerationResult:
        """Synchronous wrapper around :meth:`generate_video_async`."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.generate_video_async(config, output_path, cancel_check=cancel_check))
        finally:
            loop.close()
```

4e. Replace `_await_terminal` (378–406) in full:

```python
    async def _await_terminal(self, interaction: Any,
                              cancel_check: Optional[Callable[[], bool]] = None) -> Any:
        """Poll ``interactions.get`` until the interaction reaches a terminal state.

        Raises ``OmniPollCancelled`` when ``cancel_check`` returns True while
        the interaction is still running. A finished interaction is returned
        even if the check fires afterwards.
        """
        status = getattr(interaction, "status", None)
        if status in _TERMINAL_STATUSES:
            return interaction

        interaction_id = getattr(interaction, "id", None)
        if not interaction_id:
            return interaction

        deadline = time.time() + self.timeout
        while time.time() < deadline:
            if cancel_check is not None and cancel_check():
                self.logger.info(f"Omni poll cancelled by the caller; interaction "
                                 f"{interaction_id} keeps running remotely")
                raise OmniPollCancelled(interaction_id)
            await self._sleep_with_cancel(self.polling_interval, cancel_check)
            try:
                interaction = await asyncio.to_thread(
                    self.client.interactions.get, interaction_id
                )
            except Exception as e:
                self.logger.warning(f"Polling interactions.get failed: {e}")
                continue
            status = getattr(interaction, "status", None)
            self.logger.debug(f"Omni interaction {interaction_id} status={status}")
            if status in _TERMINAL_STATUSES:
                return interaction

        self.logger.warning(
            f"Omni interaction {interaction_id} did not finish within {self.timeout}s"
        )
        return interaction

    async def _sleep_with_cancel(self, seconds: float,
                                 cancel_check: Optional[Callable[[], bool]]) -> None:
        """Sleep ``seconds`` in 1-second slices so a cancel is seen quickly."""
        end = time.time() + seconds
        while True:
            if cancel_check is not None and cancel_check():
                raise OmniPollCancelled()
            remaining = end - time.time()
            if remaining <= 0:
                return
            await asyncio.sleep(min(1.0, remaining))
```

- [ ] **Step 5: Run the hook tests and the existing video tests**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/video -v`
Expected: all pass, including the 11 new tests and the existing `test_omni_client.py` suite.

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/video/veo_client.py core/video/omni_client.py tests/video/test_veo_cancel_hook.py tests/video/test_omni_cancel_hook.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(video): cancel_check hook for Veo and Omni polling loops"
```

---

### Task 10: Video route configs (`core/sprite/generation/video_route.py`, part 1)

**Files:**
- Create: `core/sprite/generation/video_route.py` (configs only; Task 11 adds render/refine/trim)
- Create: `tests/sprite/generation/test_gen_video_route.py` (config tests; Task 11 appends more)

**Interfaces:**
- Consumes: `core.video.omni_client.OmniGenerationConfig`, `OmniClient.MODEL_CONSTRAINTS`; `core.video.veo_client.VeoGenerationConfig`, `VeoModel`, `VeoClient.MODEL_CONSTRAINTS`; `prompts.inject_chroma`; `timing.snap_duration`; `errors.ProviderError`; `core.sprite.project.ActionCard`, `GenerationSettings`.
- Produces:
  - `RenderRequest(action: ActionCard, plate: Path, refs: List[Path], settings: GenerationSettings, out_mp4: Path)`
  - `build_omni_config(req: RenderRequest, *, log: Callable[[str], None] = logger.info) -> OmniGenerationConfig`
  - `build_veo_config(req: RenderRequest, *, log: Callable[[str], None] = logger.info) -> VeoGenerationConfig`
  - `omni_prompt(req: RenderRequest, duration_s: int) -> str`

- [ ] **Step 1: Write the failing tests**

`tests/sprite/generation/test_gen_video_route.py` (first part):

```python
"""Tests for core/sprite/generation/video_route.py (video-route-rendering)."""
from pathlib import Path

import pytest

from core.sprite.generation.errors import ProviderError
from core.sprite.generation.prompts import CHROMA_SUFFIX, LOOP_SUFFIX
from core.sprite.generation.video_route import (
    RenderRequest,
    build_omni_config,
    build_veo_config,
)
from core.sprite.project import GenerationSettings
from core.video.veo_client import VeoModel

VEO_STD = VeoModel.VEO_3_1_GENERATE.value
VEO_FAST = VeoModel.VEO_3_1_FAST.value


@pytest.fixture
def request_for(png_file, make_action, tmp_path):
    def _make(provider="omni", refs=2, **settings):
        plate = png_file("plate.png", color=(0, 255, 0, 255))
        ref_paths = [png_file(f"ref{i}.png") for i in range(refs)]
        gen = GenerationSettings(provider=provider, **settings)
        return RenderRequest(action=make_action(), plate=plate, refs=ref_paths,
                             settings=gen, out_mp4=tmp_path / "clips" / "a1.mp4")
    return _make


# --- Omni ---------------------------------------------------------------------

def test_omni_config_prompt_refs_and_aspect(request_for):
    req = request_for("omni", refs=1, aspect_ratio="9:16")
    cfg = build_omni_config(req)
    assert cfg.aspect_ratio == "9:16"
    assert cfg.reference_images[0] == req.plate
    assert cfg.reference_images[1:] == req.refs
    assert cfg.task == "reference_to_video"
    assert CHROMA_SUFFIX.format(color_name="green", hex="#00FF00") in cfg.prompt
    assert LOOP_SUFFIX in cfg.prompt
    assert "4 seconds" in cfg.prompt
    assert "9:16" not in cfg.prompt and "transparent" not in cfg.prompt.lower()


def test_omni_config_caps_reference_images_at_three(request_for):
    req = request_for("omni", refs=4)
    cfg = build_omni_config(req)
    assert len(cfg.reference_images) == 3
    assert cfg.reference_images[0] == req.plate


def test_omni_config_uses_settings_model_and_no_loop_suffix(request_for, make_action):
    req = request_for("omni", refs=0, model="omni-custom")
    req.action = make_action(loop=False, duration_s=12)
    cfg = build_omni_config(req)
    assert cfg.model == "omni-custom"
    assert cfg.task == "image_to_video"
    assert LOOP_SUFFIX not in cfg.prompt
    assert "10 seconds" in cfg.prompt   # snapped to the Omni maximum


def test_omni_config_rejects_unsupported_aspect(request_for):
    req = request_for("omni", aspect_ratio="4:3")
    with pytest.raises(ProviderError, match="aspect"):
        build_omni_config(req)


# --- Veo ----------------------------------------------------------------------

def test_veo_config_loop_conditioning_forces_first_last_and_8s(request_for):
    seen = []
    req = request_for("veo", model=VEO_FAST, duration_s=4, loop_conditioning=True,
                      include_audio=False, resolution="720p")
    cfg = build_veo_config(req, log=seen.append)
    assert cfg.model == VeoModel.VEO_3_1_FAST
    assert cfg.image == req.plate and cfg.last_frame == req.plate
    assert cfg.duration == 8
    assert cfg.include_audio is False
    assert cfg.reference_images == req.refs
    assert any("8" in line and "loop" in line.lower() for line in seen)


def test_veo_config_without_loop_conditioning_snaps_duration(request_for, make_action):
    req = request_for("veo", model=VEO_FAST, loop_conditioning=False, resolution="720p")
    req.action = make_action(duration_s=5)
    cfg = build_veo_config(req)
    assert cfg.image is None and cfg.last_frame is None
    assert cfg.duration == 6


def test_veo_config_default_model_and_resolution_fallback(request_for):
    req = request_for("veo", model="", resolution="1080p", loop_conditioning=False)
    cfg = build_veo_config(req)
    assert cfg.model == VeoModel.VEO_3_1_GENERATE
    assert cfg.duration == 8 and cfg.resolution == "1080p"
    fast = request_for("veo", model=VEO_FAST, resolution="1080p", loop_conditioning=False)
    cfg_fast = build_veo_config(fast)
    assert cfg_fast.resolution == "720p"     # Fast is 720p only; snapped with a log line


def test_veo_config_rejects_unknown_model(request_for):
    req = request_for("veo", model="veo-9-imaginary")
    with pytest.raises(ProviderError, match="Unknown Veo model"):
        build_veo_config(req)


def test_veo_config_prompt_has_chroma_and_no_sizes(request_for):
    cfg = build_veo_config(request_for("veo", model=VEO_STD, resolution="1080p"))
    assert CHROMA_SUFFIX.format(color_name="green", hex="#00FF00") in cfg.prompt
    assert "16:9" not in cfg.prompt and "px" not in cfg.prompt.lower()
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_video_route.py -v`
Expected: `ModuleNotFoundError: No module named 'core.sprite.generation.video_route'`.

- [ ] **Step 3: Implement the config half of `video_route.py`**

```python
"""Video generation route: Omni / Veo configs, render, refine, loop trim (design §4.2).

Route A of the sprite pipeline. ``render_action`` dispatches on
``GenerationSettings.provider`` and returns a ``ClipRecord`` with a sidecar.
"""
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from core.sprite.extract import extract_frames
from core.sprite.generation._common import emit, now_iso
from core.sprite.generation.cost import estimate_action, price_per_second
from core.sprite.generation.errors import ProviderError, classify_provider_error
from core.sprite.generation.prompts import inject_chroma
from core.sprite.pipeline import CancelToken, Cancelled, ProgressFn, no_progress
from core.sprite.project import ActionCard, ClipRecord, ExtractionSettings, GenerationSettings
from core.sprite.timing import snap_duration
from core.video.omni_client import OmniClient, OmniGenerationConfig
from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel

logger = logging.getLogger(__name__)

MAX_REFERENCE_IMAGES = 3  # both Omni and Veo 3.1 accept at most three


@dataclass
class RenderRequest:
    action: ActionCard
    plate: Path
    refs: List[Path]
    settings: GenerationSettings
    out_mp4: Path


def omni_prompt(req: RenderRequest, duration_s: int) -> str:
    """Chroma-injected prompt with a plain-language duration hint (Omni has no duration field)."""
    base = inject_chroma(req.action.prompt, req.settings.plate_color, loop=req.action.loop)
    return f"{base}, about {duration_s} seconds long"


def build_omni_config(req: RenderRequest, *,
                      log: Callable[[str], None] = logger.info) -> OmniGenerationConfig:
    """Omni config: plate first, then turnaround refs, capped at three."""
    duration = snap_duration(req.action.duration_s, "omni", req.settings.model)
    if duration != req.action.duration_s:
        emit(logger, log, f"Omni: duration {req.action.duration_s}s snapped to {duration}s "
                          f"(legal range {OmniClient.MODEL_CONSTRAINTS['duration_range']})")
    refs = [Path(req.plate)] + [Path(p) for p in req.refs]
    refs = refs[:MAX_REFERENCE_IMAGES]
    if len(req.refs) + 1 > MAX_REFERENCE_IMAGES:
        emit(logger, log, f"Omni: {len(req.refs)} reference image(s) plus the plate exceed "
                          f"{MAX_REFERENCE_IMAGES}; using the first {MAX_REFERENCE_IMAGES - 1} refs")
    kwargs: Dict[str, Any] = dict(prompt=omni_prompt(req, duration),
                                  aspect_ratio=req.settings.aspect_ratio,
                                  reference_images=refs)
    if req.settings.model:
        kwargs["model"] = req.settings.model
    try:
        return OmniGenerationConfig(**kwargs)
    except ValueError as exc:
        raise ProviderError(f"Omni settings are invalid: {exc}") from exc


def build_veo_config(req: RenderRequest, *,
                     log: Callable[[str], None] = logger.info) -> VeoGenerationConfig:
    """Veo config. Loop conditioning sets image=last_frame=plate and forces 8 s."""
    model_id = req.settings.model or VeoModel.VEO_3_1_GENERATE.value
    try:
        model = VeoModel(model_id)
    except ValueError as exc:
        choices = ", ".join(m.value for m in VeoModel)
        raise ProviderError(f"Unknown Veo model {model_id!r}. Choices: {choices}") from exc

    loop_conditioning = bool(req.settings.loop_conditioning)
    duration = snap_duration(req.action.duration_s, "veo", model.value,
                             loop_conditioning=loop_conditioning)
    if loop_conditioning:
        emit(logger, log, f"Veo: loop conditioning is on; the plate is the first and the last "
                          f"frame, so the clip duration is forced to 8s (requested "
                          f"{req.action.duration_s}s). Veo FIRST&LAST only works at 8s.")
    elif duration != req.action.duration_s:
        emit(logger, log, f"Veo: duration {req.action.duration_s}s snapped to {duration}s "
                          f"for {model.value}")

    allowed = VeoClient.MODEL_CONSTRAINTS[model]["resolutions"]
    resolution = req.settings.resolution
    if resolution not in allowed:
        emit(logger, log, f"Veo: resolution {resolution} not supported by {model.value}; "
                          f"using {allowed[0]}")
        resolution = allowed[0]

    refs = [Path(p) for p in req.refs][:MAX_REFERENCE_IMAGES]
    prompt = inject_chroma(req.action.prompt, req.settings.plate_color, loop=req.action.loop)
    try:
        return VeoGenerationConfig(
            model=model,
            prompt=prompt,
            aspect_ratio=req.settings.aspect_ratio,
            resolution=resolution,
            duration=duration,
            fps=req.settings.fps,
            include_audio=bool(req.settings.include_audio),
            image=Path(req.plate) if loop_conditioning else None,
            last_frame=Path(req.plate) if loop_conditioning else None,
            reference_images=refs or None,
        )
    except ValueError as exc:
        raise ProviderError(f"Veo settings are invalid: {exc}") from exc
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_video_route.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/video_route.py tests/sprite/generation/test_gen_video_route.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): Omni and Veo render configs with loop conditioning"
```

---

### Task 11: Render, refine, and loop trim (`video_route.py`, part 2)

**Files:**
- Modify: `core/sprite/generation/video_route.py` (append after `build_veo_config`)
- Modify: `tests/sprite/generation/test_gen_video_route.py` (append)

**Interfaces:**
- Consumes: `OmniClient.generate_video(config, output_path, cancel_check=)`, `VeoClient.generate_video(config, cancel_check=)` (Task 9); `core.sprite.extract.extract_frames`, `ExtractResult`; `core.video.ffmpeg_utils.get_ffmpeg_path`; `cost.estimate_action`, `cost.price_per_second`; `prompts.strip_render_terms`; `pipeline.Cancelled`, `CancelToken`, `no_progress`.
- Produces:
  - `clip_sidecar_path(mp4: Path) -> Path`
  - `write_clip_sidecar(mp4: Path, payload: Dict[str, Any]) -> Path`
  - `clip_record_payload(record: ClipRecord) -> Dict[str, Any]`
  - `render_action(req: RenderRequest, *, api_key: Optional[str], auth_mode: str = "api-key", progress: ProgressFn = no_progress, token: Optional[CancelToken] = None, log: Callable[[str], None] = logger.info) -> ClipRecord`
  - `refine_action(clip: ClipRecord, instruction: str, out_mp4: Path, *, api_key: Optional[str], log: Callable[[str], None] = logger.info) -> ClipRecord`
  - `seam_scores(frames: Sequence[Path]) -> List[float]`
  - `find_loop_seam(frames: Sequence[Path], *, search_from: float = 0.5) -> Tuple[int, float]`
  - `trim_to_loop(clip: Path, out_mp4: Path, *, seam_threshold: float = 0.08) -> Tuple[Path, float]`
  - Test seams (module-level, monkeypatchable): `_make_omni_client(api_key)`, `_make_veo_client(api_key, auth_mode)`, `_cut_video(src, dst, end_s)`, `extract_frames`.

- [ ] **Step 1: Append the failing tests**

Append to `tests/sprite/generation/test_gen_video_route.py`:

```python
# --- render / refine / trim ---------------------------------------------------
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
from PIL import Image

from core.sprite.extract import ExtractResult
from core.sprite.generation import video_route
from core.sprite.generation.errors import QuotaExceeded
from core.sprite.generation.video_route import (
    find_loop_seam,
    refine_action,
    render_action,
    seam_scores,
    trim_to_loop,
)
from core.sprite.pipeline import CancelToken, Cancelled
from core.sprite.project import ClipRecord


def _omni_client(monkeypatch, *, success=True, error=None, interaction_id="int-1"):
    """Install a fake Omni client factory; returns the MagicMock client."""
    client = MagicMock()
    captured = {}

    def generate_video(cfg, out_path, cancel_check=None):
        captured["cfg"] = cfg
        captured["cancel_check"] = cancel_check
        if success:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_bytes(b"omni-mp4")
        return SimpleNamespace(success=success, video_path=Path(out_path) if success else None,
                               interaction_id=interaction_id, error=error)
    client.generate_video.side_effect = generate_video
    client.captured = captured
    monkeypatch.setattr(video_route, "_make_omni_client", lambda api_key: client)
    return client


def test_render_omni_writes_clip_record_and_sidecar(request_for, monkeypatch):
    client = _omni_client(monkeypatch)
    req = request_for("omni", refs=1)
    seen, progress = [], []
    record = render_action(req, api_key="k", log=seen.append,
                           progress=lambda *a: progress.append(a))
    assert isinstance(record, ClipRecord)
    assert record.path == req.out_mp4 and req.out_mp4.read_bytes() == b"omni-mp4"
    assert record.provider == "omni" and record.operation_id == "int-1"
    assert record.params["aspect_ratio"] == "16:9" and record.params["duration_s"] == 4
    assert record.prompt == client.captured["cfg"].prompt
    assert record.actual_usd is None
    assert callable(client.captured["cancel_check"]) or client.captured["cancel_check"] is None
    sidecar = req.out_mp4.with_suffix(".json")
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    assert meta["status"] == "completed" and meta["operation_id"] == "int-1"
    assert meta["action_id"] == "a1" and meta["prompt"] == record.prompt
    assert "estimated_usd" in meta
    joined = "\n".join(seen)
    assert "=== Video render request" in joined and record.prompt in joined
    assert progress[0][0] == "render" and progress[-1][1:3] == (1, 1)


def test_render_veo_copies_native_file(request_for, monkeypatch, tmp_path):
    native = tmp_path / "veo_native.mp4"
    native.write_bytes(b"veo-mp4")
    client = MagicMock()
    client.generate_video.return_value = SimpleNamespace(
        success=True, video_path=native, operation_id="op-7", error=None)
    factory_args = {}
    def factory(api_key, auth_mode):
        factory_args.update(api_key=api_key, auth_mode=auth_mode)
        return client
    monkeypatch.setattr(video_route, "_make_veo_client", factory)
    req = request_for("veo", model=VEO_FAST, resolution="720p", loop_conditioning=True)
    record = render_action(req, api_key="k", auth_mode="api-key")
    assert factory_args == {"api_key": "k", "auth_mode": "api-key"}
    assert req.out_mp4.read_bytes() == b"veo-mp4"
    assert record.provider == "veo" and record.model == VEO_FAST
    assert record.operation_id == "op-7"
    assert record.params["duration_s"] == 8 and record.params["loop_conditioning"] is True
    assert record.params["last_frame"] == str(req.plate)
    assert "cancel_check" in client.generate_video.call_args.kwargs


def test_render_cancelled_raises_and_keeps_operation_id(request_for, monkeypatch):
    _omni_client(monkeypatch, success=False, error="cancelled", interaction_id="int-9")
    req = request_for("omni")
    seen = []
    with pytest.raises(Cancelled, match="int-9"):
        render_action(req, api_key="k", log=seen.append)
    meta = json.loads(req.out_mp4.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["status"] == "cancelled" and meta["operation_id"] == "int-9"
    assert any("int-9" in line for line in seen)


def test_render_failure_is_classified_with_operation_id(request_for, monkeypatch):
    _omni_client(monkeypatch, success=False, error="429 RESOURCE_EXHAUSTED", interaction_id="int-3")
    seen = []
    with pytest.raises(QuotaExceeded) as info:
        render_action(request_for("omni"), api_key="k", log=seen.append)
    assert info.value.operation_id == "int-3"
    assert any("failed" in line.lower() for line in seen)


def test_render_raw_exception_is_classified(request_for, monkeypatch):
    client = MagicMock()
    client.generate_video.side_effect = RuntimeError("blocked by safety filters")
    monkeypatch.setattr(video_route, "_make_omni_client", lambda api_key: client)
    from core.sprite.generation.errors import SafetyRefusal
    with pytest.raises(SafetyRefusal):
        render_action(request_for("omni"), api_key="k")


def test_render_checks_token_before_calling_provider(request_for, monkeypatch):
    client = _omni_client(monkeypatch)
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        render_action(request_for("omni"), api_key="k", token=token)
    client.generate_video.assert_not_called()


def test_render_cancel_check_reflects_token(request_for, monkeypatch):
    client = _omni_client(monkeypatch)
    token = CancelToken()
    render_action(request_for("omni"), api_key="k", token=token)
    check = client.captured["cancel_check"]
    assert check() is False
    token.cancel()
    assert check() is True


def test_render_unknown_provider(request_for):
    with pytest.raises(ProviderError, match="Unknown sprite video provider"):
        render_action(request_for("sora"), api_key="k")


def _clip(tmp_path, provider="omni", operation_id="int-1"):
    path = tmp_path / "clips" / "a1.mp4"
    return ClipRecord(path=path, provider=provider, model="omni-model", operation_id=operation_id,
                      params={"aspect_ratio": "9:16", "duration_s": 4}, prompt="p",
                      generated_at="2026-08-29T10:00:00", estimated_usd=0.4, actual_usd=None)


def test_refine_requires_omni_clip_with_interaction_id(tmp_path):
    with pytest.raises(ProviderError, match="Omni"):
        refine_action(_clip(tmp_path, provider="veo"), "longer cape", tmp_path / "r.mp4", api_key="k")
    with pytest.raises(ProviderError, match="interaction"):
        refine_action(_clip(tmp_path, operation_id=None), "longer cape", tmp_path / "r.mp4", api_key="k")


def test_refine_chains_previous_interaction(tmp_path, monkeypatch):
    client = _omni_client(monkeypatch, interaction_id="int-2")
    monkeypatch.setattr(video_route, "price_per_second", lambda *a, **k: 0.1)
    out = tmp_path / "clips" / "a1.r1.mp4"
    record = refine_action(_clip(tmp_path), "make the cape longer, transparent look",
                           out, api_key="k")
    cfg = client.captured["cfg"]
    assert cfg.previous_interaction_id == "int-1" and cfg.task == "edit"
    assert cfg.aspect_ratio == "9:16" and cfg.model == "omni-model"
    assert "transparent" not in cfg.prompt
    assert record.operation_id == "int-2" and record.path == out
    assert record.params["refined_from"].endswith("a1.mp4")
    assert record.params["previous_interaction_id"] == "int-1"
    assert record.estimated_usd == pytest.approx(0.4)
    meta = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["status"] == "completed" and meta["operation_id"] == "int-2"


def _square_frames(tmp_path, count=10, seam_at=7):
    """Frame k shows a square shifted by k px; frame ``seam_at`` repeats frame 0."""
    paths = []
    for k in range(count):
        shift = 0 if k == seam_at else k
        arr = np.zeros((32, 32, 3), dtype=np.uint8)
        arr[8:16, 4 + shift:12 + shift] = (255, 255, 255)
        path = tmp_path / f"{k:04d}.png"
        Image.fromarray(arr).save(path)
        paths.append(path)
    return paths


def test_seam_scores_and_find_loop_seam(tmp_path):
    frames = _square_frames(tmp_path)
    scores = seam_scores(frames)
    assert scores[0] == 0.0 and scores[7] == 0.0 and all(0.0 <= s <= 1.0 for s in scores)
    assert scores[9] > 0.0
    idx, score = find_loop_seam(frames)
    assert idx == 7 and score == 0.0
    # Search window starts at 50%; frame 0 is never a candidate.
    assert find_loop_seam(frames[:2]) == (1, scores[1])


def test_trim_to_loop_cuts_at_best_seam(tmp_path, monkeypatch):
    frames = _square_frames(tmp_path)
    monkeypatch.setattr(video_route, "extract_frames",
                        lambda video, out_dir, settings, **kw: ExtractResult(
                            frames=frames, source_fps=10.0, source_frames=10, duration_s=1.0))
    cuts = []
    def fake_cut(src, dst, end_s):
        cuts.append((Path(src), Path(dst), end_s))
        Path(dst).write_bytes(b"cut")
    monkeypatch.setattr(video_route, "_cut_video", fake_cut)
    clip = tmp_path / "a1.mp4"
    clip.write_bytes(b"full")
    out, score = trim_to_loop(clip, tmp_path / "a1.loop.mp4")
    assert cuts == [(clip, out, pytest.approx(0.8))]
    assert score == 0.0 and out.read_bytes() == b"cut"


def test_trim_to_loop_copies_when_tail_is_already_seamless(tmp_path, monkeypatch):
    frames = _square_frames(tmp_path, count=6, seam_at=5)
    monkeypatch.setattr(video_route, "extract_frames",
                        lambda video, out_dir, settings, **kw: ExtractResult(
                            frames=frames, source_fps=10.0, source_frames=6, duration_s=0.6))
    monkeypatch.setattr(video_route, "_cut_video",
                        lambda *a: (_ for _ in ()).throw(AssertionError("must not cut")))
    clip = tmp_path / "a1.mp4"
    clip.write_bytes(b"full")
    out, score = trim_to_loop(clip, tmp_path / "a1.loop.mp4", seam_threshold=0.08)
    assert out.read_bytes() == b"full" and score == 0.0
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_video_route.py -v`
Expected: `ImportError: cannot import name 'find_loop_seam' from 'core.sprite.generation.video_route'`.

- [ ] **Step 3: Append the render/refine/trim half to `video_route.py`**

Add `import subprocess` and `from core.sprite.generation.prompts import inject_chroma, strip_render_terms` to the imports, then append:

```python
# --- clients (module-level so tests can substitute them) ----------------------

def _make_omni_client(api_key: Optional[str]) -> OmniClient:
    return OmniClient(api_key=api_key)


def _make_veo_client(api_key: Optional[str], auth_mode: str) -> VeoClient:
    if auth_mode == "gcloud":
        return VeoClient(auth_mode="gcloud", project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    return VeoClient(api_key=api_key, auth_mode="api-key")


# --- sidecars -----------------------------------------------------------------

def clip_sidecar_path(mp4: Path) -> Path:
    """``clips/<id>.json`` beside ``clips/<id>.mp4`` (same shape as the video CLI)."""
    return Path(mp4).with_suffix(".json")


def write_clip_sidecar(mp4: Path, payload: Dict[str, Any]) -> Path:
    import json
    sidecar = clip_sidecar_path(mp4)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                       encoding="utf-8")
    return sidecar


def clip_record_payload(record: ClipRecord) -> Dict[str, Any]:
    return {
        "path": str(record.path),
        "provider": record.provider,
        "model": record.model,
        "operation_id": record.operation_id,
        "params": dict(record.params),
        "prompt": record.prompt,
        "generated_at": record.generated_at,
        "estimated_usd": record.estimated_usd,
        "actual_usd": record.actual_usd,
    }


def _log_request(log: Callable[[str], None], provider: str, model: str,
                 params: Dict[str, Any], prompt: str, action: ActionCard) -> None:
    import json
    emit(logger, log, f"=== Video render request: action '{action.name}' ({action.id}) ===")
    emit(logger, log, f"provider={provider} model={model}")
    emit(logger, log, f"params={json.dumps(params, default=str)}")
    emit(logger, log, f"Prompt (FULL, {len(prompt)} chars):\n{prompt}")
    emit(logger, log, "=== END video render request ===")


# --- render -------------------------------------------------------------------

def render_action(req: RenderRequest, *, api_key: Optional[str], auth_mode: str = "api-key",
                  progress: ProgressFn = no_progress, token: Optional[CancelToken] = None,
                  log: Callable[[str], None] = logger.info) -> ClipRecord:
    """Render one action card to ``req.out_mp4`` and return its ``ClipRecord``.

    Raises ``Cancelled`` when the token fires (the sidecar keeps the provider
    operation id), or a classified ``SpriteGenerationError`` on failure.
    """
    provider = (req.settings.provider or "").strip().lower()
    action = req.action
    if token is not None:
        token.raise_if_cancelled()
    cancel_check = (lambda: token.cancelled) if token is not None else None
    out_mp4 = Path(req.out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    if provider == "omni":
        cfg = build_omni_config(req, log=log)
        model_id = cfg.model
        params: Dict[str, Any] = {
            "provider": "omni",
            "model": cfg.model,
            "aspect_ratio": cfg.aspect_ratio,
            "task": cfg.task,
            "reference_images": [str(p) for p in cfg.reference_images],
            "delivery": cfg.delivery,
            "duration_s": snap_duration(action.duration_s, "omni", req.settings.model),
            "loop": action.loop,
        }
    elif provider == "veo":
        cfg = build_veo_config(req, log=log)
        model_id = cfg.model.value
        params = dict(cfg.to_dict())
        params.pop("prompt", None)
        params.update({
            "provider": "veo",
            "model": model_id,
            "duration_s": cfg.duration,
            "image": str(cfg.image) if cfg.image else None,
            "last_frame": str(cfg.last_frame) if cfg.last_frame else None,
            "reference_images": [str(p) for p in (cfg.reference_images or [])],
            "loop_conditioning": bool(req.settings.loop_conditioning),
            "loop": action.loop,
            "auth_mode": auth_mode,
        })
    else:
        raise ProviderError(f"Unknown sprite video provider {provider!r}. Use 'omni' or 'veo'.")

    _log_request(log, provider, model_id, params, cfg.prompt, action)
    progress("render", 0, 0, f"{provider}: rendering '{action.name}'")

    operation_id: Optional[str] = None
    try:
        if provider == "omni":
            client = _make_omni_client(api_key)
            result = client.generate_video(cfg, out_mp4, cancel_check=cancel_check)
            operation_id = getattr(result, "interaction_id", None)
        else:
            client = _make_veo_client(api_key, auth_mode)
            result = client.generate_video(cfg, cancel_check=cancel_check)
            operation_id = getattr(result, "operation_id", None)
    except Exception as exc:  # noqa: BLE001 - classified below
        err = classify_provider_error(exc, provider=provider, operation_id=operation_id)
        emit(logger, log, f"Render of '{action.name}' failed: {err.user_message}", level="error")
        raise err from exc

    base_payload = {"action_id": action.id, "action_name": action.name, "provider": provider,
                    "model": model_id, "operation_id": operation_id, "params": params,
                    "prompt": cfg.prompt, "generated_at": now_iso()}
    if not result.success:
        if result.error == "cancelled":
            sidecar = write_clip_sidecar(out_mp4, {**base_payload, "status": "cancelled"})
            emit(logger, log, f"Render of '{action.name}' cancelled; {provider} operation "
                              f"{operation_id} keeps running remotely. Id saved in {sidecar}.",
                 level="warning")
            raise Cancelled(f"render of '{action.name}' cancelled; {provider} operation "
                            f"{operation_id} keeps running remotely")
        err = classify_provider_error(RuntimeError(result.error or "unknown provider failure"),
                                      provider=provider, operation_id=operation_id)
        write_clip_sidecar(out_mp4, {**base_payload, "status": "failed", "error": result.error})
        emit(logger, log, f"Render of '{action.name}' failed ({provider}/{model_id}): "
                          f"{err.user_message}", level="error")
        raise err

    if provider == "veo":
        native = Path(result.video_path) if getattr(result, "video_path", None) else None
        if native is None or not native.exists():
            raise ProviderError("Veo reported success but saved no video file.",
                                operation_id=operation_id)
        if native.resolve() != out_mp4.resolve():
            shutil.copy2(native, out_mp4)
    if not out_mp4.exists():
        raise ProviderError(f"The provider reported success but {out_mp4} does not exist.",
                            operation_id=operation_id)

    record = ClipRecord(path=out_mp4, provider=provider, model=model_id,
                        operation_id=operation_id, params=params, prompt=cfg.prompt,
                        generated_at=base_payload["generated_at"],
                        estimated_usd=estimate_action(req.settings, action), actual_usd=None)
    write_clip_sidecar(out_mp4, {**clip_record_payload(record), "status": "completed",
                                 "action_id": action.id, "action_name": action.name})
    emit(logger, log, f"Clip saved: {out_mp4} (operation {operation_id}, "
                      f"estimated ${record.estimated_usd})")
    progress("render", 1, 1, f"{provider}: '{action.name}' rendered")
    return record


# --- refine (Omni conversational edit) ---------------------------------------

def refine_action(clip: ClipRecord, instruction: str, out_mp4: Path, *,
                  api_key: Optional[str],
                  log: Callable[[str], None] = logger.info) -> ClipRecord:
    """Conversational edit of an Omni clip via ``previous_interaction_id``."""
    if (clip.provider or "").lower() != "omni":
        raise ProviderError("Refine works only for Omni clips. Re-render Veo clips instead.")
    if not clip.operation_id:
        raise ProviderError("Refine needs the Omni interaction id of the clip, and this clip has none.")
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    prompt = strip_render_terms(instruction)
    aspect = clip.params.get("aspect_ratio", "16:9")
    try:
        cfg = OmniGenerationConfig(prompt=prompt, model=clip.model, aspect_ratio=aspect,
                                   previous_interaction_id=clip.operation_id)
    except ValueError as exc:
        raise ProviderError(f"Omni refine settings are invalid: {exc}") from exc
    params = {**clip.params, "provider": "omni", "task": cfg.task,
              "previous_interaction_id": clip.operation_id, "refined_from": str(clip.path)}

    import json
    emit(logger, log, f"=== Omni refine request (previous interaction {clip.operation_id}) ===")
    emit(logger, log, f"model={cfg.model} params={json.dumps(params, default=str)}")
    emit(logger, log, f"Instruction (FULL, {len(prompt)} chars):\n{prompt}")

    try:
        client = _make_omni_client(api_key)
        result = client.generate_video(cfg, out_mp4)
    except Exception as exc:  # noqa: BLE001 - classified below
        err = classify_provider_error(exc, provider="omni", operation_id=clip.operation_id)
        emit(logger, log, f"Refine failed: {err.user_message}", level="error")
        raise err from exc
    if not result.success:
        err = classify_provider_error(RuntimeError(result.error or "unknown provider failure"),
                                      provider="omni", operation_id=getattr(result, "interaction_id", None))
        emit(logger, log, f"Refine failed: {err.user_message}", level="error")
        raise err

    seconds = float(clip.params.get("duration_s", 0) or 0)
    rate = price_per_second("omni", clip.model, include_audio=False)
    estimated = round(rate * seconds, 4) if (rate is not None and seconds) else None
    record = ClipRecord(path=out_mp4, provider="omni", model=cfg.model,
                        operation_id=getattr(result, "interaction_id", None), params=params,
                        prompt=prompt, generated_at=now_iso(), estimated_usd=estimated,
                        actual_usd=None)
    write_clip_sidecar(out_mp4, {**clip_record_payload(record), "status": "completed"})
    emit(logger, log, f"Refined clip saved: {out_mp4} (interaction {record.operation_id})")
    return record


# --- loop seam trim -----------------------------------------------------------

def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0


def seam_scores(frames: Sequence[Path]) -> List[float]:
    """Mean absolute RGB difference (0..1) between each frame and the first frame."""
    if not frames:
        return []
    first = _load_rgb(Path(frames[0]))
    scores: List[float] = []
    for path in frames:
        arr = _load_rgb(Path(path))
        if arr.shape != first.shape:
            with Image.open(path) as img:
                resized = img.convert("RGB").resize((first.shape[1], first.shape[0]), Image.BILINEAR)
                arr = np.asarray(resized, dtype=np.float32) / 255.0
        scores.append(float(np.abs(arr - first).mean()))
    return scores


def _best_index(scores: Sequence[float], search_from: float) -> int:
    start = max(1, int(len(scores) * search_from))
    start = min(start, len(scores) - 1)
    return min(range(start, len(scores)), key=lambda i: scores[i])


def find_loop_seam(frames: Sequence[Path], *, search_from: float = 0.5) -> Tuple[int, float]:
    """Index (and score) of the frame in the tail half that best matches frame 0."""
    scores = seam_scores(frames)
    if len(scores) < 2:
        return (len(scores) - 1, scores[-1] if scores else 1.0)
    index = _best_index(scores, search_from)
    return index, scores[index]


def _cut_video(src: Path, dst: Path, end_s: float) -> None:
    from core.video.ffmpeg_utils import get_ffmpeg_path
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise ProviderError("ffmpeg is required to trim a clip. Install ffmpeg first.")
    cmd = [ffmpeg, "-y", "-i", str(src), "-t", f"{end_s:.3f}",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(dst)]
    logger.info("trim_to_loop: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ProviderError(f"ffmpeg trim failed: {proc.stderr[-400:]}")


def trim_to_loop(clip: Path, out_mp4: Path, *,
                 seam_threshold: float = 0.08) -> Tuple[Path, float]:
    """Tail-trim ``clip`` at the frame that best matches its first frame.

    Returns ``(out_mp4, seam_score)``. When the last frame already matches
    within ``seam_threshold`` (or no better seam exists), the clip is copied
    unchanged and the tail score is returned.
    """
    clip = Path(clip)
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    def _copy() -> None:
        if clip.resolve() != out_mp4.resolve():
            shutil.copy2(clip, out_mp4)

    with tempfile.TemporaryDirectory(prefix="sprite_seam_") as tmp:
        extracted = extract_frames(clip, Path(tmp), ExtractionSettings(mode="every_n", every_n=1))
        frames = list(extracted.frames)
        if not frames:
            raise ProviderError("No frames could be extracted for the loop seam search.")
        scores = seam_scores(frames)
        tail = scores[-1]
        if tail <= seam_threshold or len(frames) < 3:
            _copy()
            logger.info("trim_to_loop: tail seam %.3f within %.3f; no trim", tail, seam_threshold)
            return out_mp4, tail
        index = _best_index(scores, 0.5)
        best = scores[index]
        if index >= len(frames) - 1:
            _copy()
            logger.info("trim_to_loop: no better seam than the tail (%.3f)", tail)
            return out_mp4, tail
        fps = float(extracted.source_fps or 24.0)
        end_s = (index + 1) / fps
        _cut_video(clip, out_mp4, end_s)
        logger.info("trim_to_loop: cut at frame %d (%.3fs), seam %.3f (tail was %.3f)",
                    index, end_s, best, tail)
        return out_mp4, best
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_video_route.py -v`
Expected: 22 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/video_route.py tests/sprite/generation/test_gen_video_route.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): render_action, Omni refine, and loop-seam trim"
```

---

### Task 12: Action queue (`core/sprite/generation/queue.py`)

**Files:**
- Create: `core/sprite/generation/queue.py`
- Create: `tests/sprite/generation/test_gen_queue.py`

**Interfaces:**
- Consumes: `video_route.render_action`, `RenderRequest`; `cost.record_actual`; `errors.*`; `turnaround.VIEWS`; `core.sprite.pipeline.run_pipeline`, `CancelToken`, `Cancelled`, `ProgressFn`, `no_progress`; `core.sprite.project.SpriteProject` (`.actions`, `.plate_path`, `.turnaround`, `.generation`, `.project_dir`, `.save()`), `ActionCard`, `ClipRecord`.
- Produces:
  - `BACKOFF_SECONDS = (2.0, 4.0, 8.0)`, `MAX_RETRIES = 3`, `PIPELINE_UPTO = "stabilize"`
  - `QueueResult = Dict[str, Union[ClipRecord, SpriteGenerationError]]`
  - `ActionQueue(project, *, api_key, auth_mode, progress=no_progress, token=None, log=logger.info, max_concurrent=1)`
  - `ActionQueue.enqueue(action_ids: Sequence[str]) -> None`
  - `ActionQueue.run() -> QueueResult`
  - `ActionQueue.retry(action_id: str) -> None`
  - `ActionQueue.build_request(action: ActionCard) -> RenderRequest`
  - `ActionQueue.clip_path(action: ActionCard) -> Path`
  - `ActionQueue.pending: List[str]`, `ActionQueue.results: QueueResult`, `ActionQueue._sleep: Callable[[float], None]` (test seam)

Retry policy: one first try plus `MAX_RETRIES` retries, waiting `BACKOFF_SECONDS[i]` before retry `i + 1` (2 s, 4 s, 8 s). Only `retryable` errors are retried. `SafetyRefusal` is never retried. A cancel during a wait stops the queue.

- [ ] **Step 1: Write the failing tests**

`tests/sprite/generation/test_gen_queue.py`:

```python
"""Tests for core/sprite/generation/queue.py (batch queue, G6 retries, G2 cancel)."""
from pathlib import Path

import pytest

from core.sprite.generation import queue as queue_mod
from core.sprite.generation.errors import ProviderError, QuotaExceeded, SafetyRefusal
from core.sprite.generation.queue import BACKOFF_SECONDS, MAX_RETRIES, ActionQueue
from core.sprite.generation.video_route import RenderRequest
from core.sprite.pipeline import CancelToken, Cancelled
from core.sprite.project import ClipRecord, CostEntry


def _record(req: RenderRequest) -> ClipRecord:
    req.out_mp4.parent.mkdir(parents=True, exist_ok=True)
    req.out_mp4.write_bytes(b"mp4")
    return ClipRecord(path=req.out_mp4, provider=req.settings.provider, model="m",
                      operation_id=f"op-{req.action.id}",
                      params={"duration_s": req.action.duration_s}, prompt=req.action.prompt,
                      generated_at="2026-08-29T10:00:00", estimated_usd=0.4, actual_usd=None)


@pytest.fixture
def harness(monkeypatch, make_project, make_action):
    """Fake render/pipeline seams plus a builder for (project, queue)."""
    state = {"renders": [], "pipelines": [], "sleeps": [], "saves": 0, "logs": [],
             "outcomes": []}

    def fake_render(req, *, api_key, auth_mode, progress, token, log):
        state["renders"].append(req)
        outcome = state["outcomes"].pop(0) if state["outcomes"] else "ok"
        if isinstance(outcome, BaseException):
            raise outcome
        return _record(req)

    def fake_pipeline(project, action, *, upto="pixel", progress=None, token=None, force=False):
        state["pipelines"].append((action.id, upto))
        return {"stabilize": []}

    monkeypatch.setattr(queue_mod, "render_action", fake_render)
    monkeypatch.setattr(queue_mod, "run_pipeline", fake_pipeline)

    def build(actions=None, token=None, **project_kwargs):
        if actions is None:
            actions = [make_action(id="a1", name="walk"), make_action(id="a2", name="run")]
        project = make_project(actions=actions, **project_kwargs)

        def _save(path=None):
            state["saves"] += 1
            return project.project_dir
        project.save = _save
        q = ActionQueue(project, api_key="k", auth_mode="api-key", token=token,
                        log=state["logs"].append)
        q._sleep = state["sleeps"].append
        return project, q

    state["build"] = build
    return state


def test_constants():
    assert BACKOFF_SECONDS == (2.0, 4.0, 8.0) and MAX_RETRIES == 3


def test_enqueue_marks_queued_and_dedupes(harness):
    project, q = harness["build"]()
    q.enqueue(["a1", "a2", "a1"])
    assert q.pending == ["a1", "a2"]
    assert all(a.status == "queued" and a.error is None for a in project.actions)
    with pytest.raises(ValueError):
        q.enqueue(["missing"])


def test_run_renders_in_order_runs_pipeline_and_records_cost(harness):
    project, q = harness["build"]()
    q.enqueue(["a1", "a2"])
    results = q.run()
    assert [r.action.id for r in harness["renders"]] == ["a1", "a2"]
    assert harness["pipelines"] == [("a1", "stabilize"), ("a2", "stabilize")]
    assert set(results) == {"a1", "a2"}
    assert all(isinstance(r, ClipRecord) for r in results.values())
    for action in project.actions:
        assert action.status == "rendered" and action.clip is results[action.id]
        assert action.clip.path == project.project_dir / "clips" / f"{action.id}.mp4"
    assert [e.action_id for e in project.cost_ledger] == ["a1", "a2"]
    assert isinstance(project.cost_ledger[0], CostEntry)
    assert project.cost_ledger[0].estimated_usd == 0.4 and project.cost_ledger[0].actual_usd is None
    assert harness["saves"] == 2 and q.pending == []
    assert harness["renders"][0].plate == project.plate_path


def test_retries_retryable_errors_with_backoff(harness):
    project, q = harness["build"](actions=None)
    harness["outcomes"] = [QuotaExceeded("429"), ProviderError("503", retryable=True), "ok"]
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], ClipRecord)
    assert len([r for r in harness["renders"] if r.action.id == "a1"]) == 3
    assert harness["sleeps"] == [2.0, 4.0]
    assert any("retry in 2s" in line for line in harness["logs"])


def test_gives_up_after_max_retries(harness):
    project, q = harness["build"]()
    harness["outcomes"] = [QuotaExceeded("429")] * (MAX_RETRIES + 1)
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], QuotaExceeded)
    assert len(harness["renders"]) == MAX_RETRIES + 1
    assert harness["sleeps"] == list(BACKOFF_SECONDS)
    action = project.actions[0]
    assert action.status == "failed" and action.error == results["a1"].user_message


def test_safety_refusal_never_retried(harness):
    project, q = harness["build"]()
    harness["outcomes"] = [SafetyRefusal("RAI refused; try Veo")]
    q.enqueue(["a1", "a2"])
    results = q.run()
    assert isinstance(results["a1"], SafetyRefusal)
    assert harness["sleeps"] == []
    assert project.actions[0].status == "failed"
    assert project.actions[0].error == "RAI refused; try Veo"
    # The queue continues with the next card.
    assert isinstance(results["a2"], ClipRecord)


def test_non_retryable_provider_error_not_retried(harness):
    project, q = harness["build"]()
    harness["outcomes"] = [ProviderError("bad config")]
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], ProviderError) and harness["sleeps"] == []
    assert len(harness["renders"]) == 1


def test_raw_exception_is_classified_and_retried(harness):
    project, q = harness["build"]()
    harness["outcomes"] = [RuntimeError("503 Service Unavailable"), "ok"]
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], ClipRecord) and harness["sleeps"] == [2.0]


def test_cancel_before_run_leaves_actions_queued(harness):
    token = CancelToken()
    token.cancel()
    project, q = harness["build"](token=token)
    q.enqueue(["a1", "a2"])
    assert q.run() == {}
    assert harness["renders"] == []
    assert all(a.status == "queued" for a in project.actions)
    assert q.pending == ["a1", "a2"]


def test_cancel_inside_job_stops_queue_and_keeps_card_reusable(harness):
    token = CancelToken()
    project, q = harness["build"](token=token)
    harness["outcomes"] = [Cancelled("render of 'walk' cancelled; omni operation int-9 keeps running")]
    q.enqueue(["a1", "a2"])
    results = q.run()
    assert set(results) == {"a1"}
    assert isinstance(results["a1"], ProviderError) and results["a1"].retryable is True
    assert "int-9" in results["a1"].user_message
    walk, run = project.actions
    assert walk.status == "draft" and "int-9" in walk.error
    assert run.status == "queued" and q.pending == ["a2"]
    assert harness["saves"] == 1


def test_cancel_during_backoff_stops_before_next_try(harness):
    token = CancelToken()
    project, q = harness["build"](token=token)
    harness["outcomes"] = [QuotaExceeded("429"), "ok"]
    q._sleep = lambda seconds: token.cancel()
    q.enqueue(["a1"])
    results = q.run()
    assert len(harness["renders"]) == 1
    assert isinstance(results["a1"], ProviderError)
    assert project.actions[0].status == "draft"


def test_pipeline_failure_keeps_rendered_status(harness, monkeypatch):
    project, q = harness["build"]()
    def broken_pipeline(project, action, **kw):
        raise RuntimeError("ffmpeg missing")
    monkeypatch.setattr(queue_mod, "run_pipeline", broken_pipeline)
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], ClipRecord)
    action = project.actions[0]
    assert action.status == "rendered" and action.error.startswith("pipeline: ffmpeg missing")
    assert any("Pipeline for 'walk' failed" in line for line in harness["logs"])


def test_pipeline_cancel_after_render_keeps_clip(harness, monkeypatch):
    token = CancelToken()
    project, q = harness["build"](token=token)
    def cancelling_pipeline(project, action, **kw):
        raise Cancelled("stage cancelled")
    monkeypatch.setattr(queue_mod, "run_pipeline", cancelling_pipeline)
    q.enqueue(["a1", "a2"])
    results = q.run()
    assert isinstance(results["a1"], ClipRecord)
    assert project.actions[0].status == "rendered" and project.actions[0].clip is not None
    assert q.pending == ["a2"]


def test_missing_plate_fails_without_render(harness):
    project, q = harness["build"](plate=False)
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], ProviderError)
    assert "plate" in results["a1"].user_message.lower()
    assert harness["renders"] == [] and project.actions[0].status == "failed"


def test_turnaround_refs_follow_setting(harness):
    project, q = harness["build"](turnaround=True)
    project.generation.use_turnaround_refs = True
    q.enqueue(["a1"])
    q.run()
    assert harness["renders"][0].refs == [project.turnaround["front"], project.turnaround["side"]]
    project.generation.use_turnaround_refs = False
    q.enqueue(["a2"])
    q.run()
    assert harness["renders"][1].refs == []


def test_retry_requeues_failed_action(harness):
    project, q = harness["build"]()
    harness["outcomes"] = [ProviderError("bad")]
    q.enqueue(["a1"])
    q.run()
    assert project.actions[0].status == "failed"
    q.retry("a1")
    assert q.pending == ["a1"] and project.actions[0].status == "queued"
    results = q.run()
    assert isinstance(results["a1"], ClipRecord)


def test_max_concurrent_is_logged_and_ignored(harness):
    project, _ = harness["build"]()
    logs = []
    q = ActionQueue(project, api_key="k", auth_mode="api-key", log=logs.append, max_concurrent=4)
    assert q.max_concurrent == 1
    assert any("max_concurrent" in line for line in logs)
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_queue.py -v`
Expected: `ModuleNotFoundError: No module named 'core.sprite.generation.queue'`.

- [ ] **Step 3: Implement `queue.py`**

```python
"""Sequential action render queue (design §4.2, §1.3, §1.1).

Renders queued cards one at a time with ``render_action``, retries
retryable errors with exponential backoff, never retries a safety refusal,
runs the processing pipeline up to ``stabilize`` after each clip, writes a
``CostEntry`` row per rendered clip, and honors the cancel token between
jobs, inside jobs (through ``render_action``), and during backoff waits.
"""
import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Union

from core.sprite.generation._common import emit
from core.sprite.generation.cost import record_actual
from core.sprite.generation.errors import (
    ProviderError,
    SafetyRefusal,
    SpriteGenerationError,
    classify_provider_error,
)
from core.sprite.generation.turnaround import VIEWS
from core.sprite.generation.video_route import RenderRequest, render_action
from core.sprite.pipeline import CancelToken, Cancelled, ProgressFn, no_progress, run_pipeline
from core.sprite.project import ActionCard, ClipRecord, SpriteProject

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = (2.0, 4.0, 8.0)
MAX_RETRIES = len(BACKOFF_SECONDS)
PIPELINE_UPTO = "stabilize"

QueueResult = Dict[str, Union[ClipRecord, SpriteGenerationError]]


class ActionQueue:
    """Render queued action cards for one project."""

    def __init__(self, project: SpriteProject, *, api_key: Optional[str], auth_mode: str,
                 progress: ProgressFn = no_progress, token: Optional[CancelToken] = None,
                 log: Callable[[str], None] = logger.info, max_concurrent: int = 1) -> None:
        self.project = project
        self.api_key = api_key
        self.auth_mode = auth_mode
        self.progress = progress
        self.token = token
        self.log = log
        self.max_concurrent = 1
        if max_concurrent != 1:
            emit(logger, log, f"ActionQueue renders one clip at a time; "
                              f"max_concurrent={max_concurrent} is ignored")
        self.pending: List[str] = []
        self.results: QueueResult = {}
        self._sleep: Callable[[float], None] = time.sleep

    # -- lookup / requests ---------------------------------------------------

    def _action(self, action_id: str) -> ActionCard:
        for action in self.project.actions:
            if action.id == action_id:
                return action
        raise ValueError(f"No action with id {action_id!r} in project {self.project.name!r}")

    def clip_path(self, action: ActionCard) -> Path:
        """``<project_dir>/clips/<action_id>.mp4`` (design §1.6)."""
        if self.project.project_dir is None:
            raise ProviderError("Save the project before rendering so the clips folder has a home.")
        return Path(self.project.project_dir) / "clips" / f"{action.id}.mp4"

    def build_request(self, action: ActionCard) -> RenderRequest:
        plate = self.project.plate_path
        if not plate or not Path(plate).exists():
            raise ProviderError("Make the chroma plate before rendering (Character panel > Make chroma plate).")
        settings = self.project.generation
        refs: List[Path] = []
        if settings.use_turnaround_refs:
            refs = [Path(self.project.turnaround[view]) for view in VIEWS
                    if view in self.project.turnaround]
        return RenderRequest(action=action, plate=Path(plate), refs=refs,
                             settings=settings, out_mp4=self.clip_path(action))

    # -- queue operations ----------------------------------------------------

    def enqueue(self, action_ids: Sequence[str]) -> None:
        for action_id in action_ids:
            action = self._action(action_id)
            action.status = "queued"
            action.error = None
            self.results.pop(action_id, None)
            if action_id not in self.pending:
                self.pending.append(action_id)
        names = ", ".join(self._action(i).name for i in self.pending)
        emit(logger, self.log, f"Queue: {len(self.pending)} action(s) queued: {names}")

    def retry(self, action_id: str) -> None:
        self.enqueue([action_id])

    def _cancelled(self) -> bool:
        return self.token is not None and self.token.cancelled

    def run(self) -> QueueResult:
        """Render every pending card in order. Returns results for cards it touched."""
        while self.pending:
            if self._cancelled():
                emit(logger, self.log, f"Queue cancelled; {len(self.pending)} action(s) stay queued",
                     level="warning")
                break
            action_id = self.pending.pop(0)
            action = self._action(action_id)
            action.status = "rendering"
            action.error = None
            try:
                record = self._render_with_retries(action)
                action.clip = record
                action.status = "rendered"
                entry = record_actual(self.project, action, None, note="rendered")
                emit(logger, self.log, f"Cost: '{action.name}' estimated ${entry.estimated_usd} "
                                       f"({entry.seconds:.0f}s {entry.provider}/{entry.model})")
                self.results[action_id] = record
                self._post_process(action)
            except Cancelled as exc:
                if action.clip is None:
                    action.status = "draft"
                    action.error = f"cancelled: {exc}"
                    self.results[action_id] = ProviderError(
                        f"Render of '{action.name}' was cancelled. {exc}", retryable=True)
                else:
                    action.error = f"cancelled after render: {exc}"
                emit(logger, self.log, f"Queue stopped: {exc}", level="warning")
                self._save()
                break
            except SpriteGenerationError as err:
                action.status = "failed"
                action.error = err.user_message
                self.results[action_id] = err
                emit(logger, self.log, f"'{action.name}' failed: {err.user_message}", level="error")
            self._save()
        return dict(self.results)

    # -- internals -----------------------------------------------------------

    def _render_with_retries(self, action: ActionCard) -> ClipRecord:
        request = self.build_request(action)
        attempt = 0
        while True:
            attempt += 1
            try:
                return render_action(request, api_key=self.api_key, auth_mode=self.auth_mode,
                                     progress=self.progress, token=self.token, log=self.log)
            except Cancelled:
                raise
            except Exception as exc:  # noqa: BLE001 - classified below
                err = classify_provider_error(exc, provider=request.settings.provider)
                if isinstance(err, SafetyRefusal) or not err.retryable or attempt > MAX_RETRIES:
                    if err is exc:
                        raise
                    raise err from exc
                delay = BACKOFF_SECONDS[attempt - 1]
                emit(logger, self.log, f"'{action.name}' attempt {attempt} failed "
                                       f"({err.user_message}); retry in {delay:.0f}s",
                     level="warning")
                self._sleep(delay)
                if self._cancelled():
                    raise Cancelled(f"cancelled while waiting to retry '{action.name}'")

    def _post_process(self, action: ActionCard) -> None:
        try:
            run_pipeline(self.project, action, upto=PIPELINE_UPTO,
                         progress=self.progress, token=self.token)
        except Cancelled:
            raise
        except Exception as exc:  # noqa: BLE001 - the clip is safe; report and continue
            action.error = f"pipeline: {exc}"
            emit(logger, self.log, f"Pipeline for '{action.name}' failed after render: {exc}. "
                                   f"The clip is saved; run the pipeline again from the "
                                   f"processing panel.", level="error")
        else:
            emit(logger, self.log, f"Frames ready for '{action.name}' "
                                   f"(pipeline up to '{PIPELINE_UPTO}')")

    def _save(self) -> None:
        if self.project.project_dir is None:
            return
        try:
            self.project.save()
        except Exception as exc:  # noqa: BLE001 - never lose a rendered clip over a save error
            emit(logger, self.log, f"Could not save the project: {exc}", level="warning")
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_queue.py -v`
Expected: 17 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/queue.py tests/sprite/generation/test_gen_queue.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): sequential action queue with backoff, cancel, and cost rows"
```

---

### Task 13: Package exports and full-suite run

**Files:**
- Modify: `core/sprite/generation/__init__.py`
- Create: `tests/sprite/generation/test_gen_package.py`

**Interfaces:**
- Produces: `core.sprite.generation` re-exports listed below; `__all__`.

- [ ] **Step 1: Write the failing test**

`tests/sprite/generation/test_gen_package.py`:

```python
"""The generation package re-exports its public surface."""
import core.sprite.generation as gen


def test_public_exports():
    expected = {
        "SpriteGenerationError", "SafetyRefusal", "QuotaExceeded", "ProviderError",
        "classify_provider_error",
        "inject_chroma", "color_name", "CHROMA_SUFFIX", "LOOP_SUFFIX", "FORBIDDEN_WORDS",
        "make_chroma_plate",
        "generate_turnaround", "VIEWS",
        "ActionCardDraft", "GENRE_CHECKLISTS", "build_messages", "parse_action_cards",
        "generate_action_cards", "draft_to_card",
        "RenderRequest", "build_omni_config", "build_veo_config", "render_action",
        "refine_action", "trim_to_loop",
        "PRICE_TABLE_VERIFIED", "price_per_second", "estimate_action", "estimate_project",
        "record_actual",
        "ActionQueue",
    }
    assert expected <= set(gen.__all__)
    for name in expected:
        assert getattr(gen, name) is not None
```

- [ ] **Step 2: Run the test and watch it fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_package.py -v`
Expected: `AttributeError: module 'core.sprite.generation' has no attribute '__all__'`.

- [ ] **Step 3: Write the exports**

Replace `core/sprite/generation/__init__.py` with:

```python
"""Sprite generation routes: chroma plate, turnaround, action cards, video clips.

Route A (video) of the sprite pipeline — design §4.2. Everything here is
pure Python with injected provider clients and an injected ``log`` sink.
"""
from core.sprite.generation.action_cards import (
    ActionCardDraft,
    GENRE_CHECKLISTS,
    build_messages,
    draft_to_card,
    generate_action_cards,
    parse_action_cards,
)
from core.sprite.generation.cost import (
    PRICE_TABLE_VERIFIED,
    estimate_action,
    estimate_project,
    price_per_second,
    record_actual,
)
from core.sprite.generation.errors import (
    ProviderError,
    QuotaExceeded,
    SafetyRefusal,
    SpriteGenerationError,
    classify_provider_error,
)
from core.sprite.generation.plate import make_chroma_plate
from core.sprite.generation.prompts import (
    CHROMA_SUFFIX,
    FORBIDDEN_WORDS,
    LOOP_SUFFIX,
    color_name,
    inject_chroma,
)
from core.sprite.generation.queue import ActionQueue
from core.sprite.generation.turnaround import VIEWS, generate_turnaround
from core.sprite.generation.video_route import (
    RenderRequest,
    build_omni_config,
    build_veo_config,
    refine_action,
    render_action,
    trim_to_loop,
)

__all__ = [
    "SpriteGenerationError", "SafetyRefusal", "QuotaExceeded", "ProviderError",
    "classify_provider_error",
    "inject_chroma", "color_name", "CHROMA_SUFFIX", "LOOP_SUFFIX", "FORBIDDEN_WORDS",
    "make_chroma_plate",
    "generate_turnaround", "VIEWS",
    "ActionCardDraft", "GENRE_CHECKLISTS", "build_messages", "parse_action_cards",
    "generate_action_cards", "draft_to_card",
    "RenderRequest", "build_omni_config", "build_veo_config", "render_action",
    "refine_action", "trim_to_loop",
    "PRICE_TABLE_VERIFIED", "price_per_second", "estimate_action", "estimate_project",
    "record_actual",
    "ActionQueue",
]
```

- [ ] **Step 4: Run the package test, then the sub-project's tests, then the full suite**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/generation/test_gen_package.py -v`
Expected: 1 passed.

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite /mnt/d/Documents/Code/GitHub/ImageAI/tests/video -v`
Expected: every test passes (sub-project 1 tests plus 19 + 18 + 6 + 11 + 12 + 5 + 7 + 16 + 11 + 22 + 17 + 1 = 145 from this plan).

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests -q`
Expected: the whole suite is green, including `tests/test_no_hardcoded_paths.py` (no module in `core/sprite/generation` builds a platform data path).

- [ ] **Step 5: Lint the touched files**

Run: `$PY -m pyflakes /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/generation /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/source.py /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/timing.py /mnt/d/Documents/Code/GitHub/ImageAI/core/video/veo_client.py /mnt/d/Documents/Code/GitHub/ImageAI/core/video/omni_client.py`
Expected: no output. If `pyflakes` is not installed, run `$PY -m py_compile` on each file instead and expect no output.

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/__init__.py tests/sprite/generation/test_gen_package.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): export the generation package surface"
```

---

## Self-review

### Spec coverage (design §4.2, §1.3, §1.1)

| Design symbol | Task |
|---|---|
| §4.2 `SourceAnalysis`, `normalize_source`, `analyze_source` | 3 |
| §4.2 `CHROMA_SUFFIX`, `LOOP_SUFFIX`, `FORBIDDEN_WORDS`, `inject_chroma`, `color_name` | 2 |
| §4.2 `make_chroma_plate` (edit_image, prompt text, sidecar with `plate_color`) | 6 |
| §4.2 `VIEWS`, `generate_turnaround` (do-not-change list, `token`) | 7 |
| §4.2 `ActionCardDraft`, `GENRE_CHECKLISTS`, `build_messages`, `parse_action_cards`, `generate_action_cards` (`completion_fn`, `build_completion_kwargs`, `resolve_model`, full logging) | 8 |
| §4.2 `loop_seconds`, `suggest_clip_duration`, `frames_per_clip`, `ms_to_fps` | 4 |
| §4.2 `RenderRequest`, `build_omni_config`, `build_veo_config` (loop conditioning → `image`+`last_frame`=plate, forced 8 s with a logged reason) | 10 |
| §4.2 `render_action`, `refine_action` (`previous_interaction_id`), `trim_to_loop` (seam score) | 11 |
| §4.2 `PRICE_TABLE_VERIFIED`, `price_per_second` (Veo via `VeoClient.estimate_cost`, Omni constant, `sprite.price_overrides`), `estimate_action`, `estimate_project`, `record_actual` | 5 |
| §4.2 `ActionQueue.enqueue/run/retry` (sequential, backoff 2/4/8 s, no retry on `SafetyRefusal`, `run_pipeline(upto="stabilize")`, `CostEntry` rows, token between and inside jobs) | 12 |
| §1.3 `SpriteGenerationError.user_message/retryable`, `SafetyRefusal`, `QuotaExceeded`, `ProviderError`, `classify_provider_error` (RAI/safety/person_generation → `SafetyRefusal`; 429/RESOURCE_EXHAUSTED/quota → `QuotaExceeded`) | 1 |
| §1.3 every failure logged with provider, model, params, prompt, and full error text | 6, 7, 8, 11, 12 |
| §1.1 `cancel_check` on `VeoClient._poll_for_completion` and `OmniClient._await_terminal`; `success=False, error="cancelled"`; operation id preserved | 9 |
| Sidecars for every artifact (`.png.json` for images, `.json` for clips) | 3, 6, 7, 11 |
| Package exports for 5a (GUI) and 7 (CLI) | 13 |

### Placeholder scan

- No "TBD", "add error handling", or "similar to Task N" in any code step. Every code block is complete.
- The only value the implementer fills in is the Omni rate in Task 5 Step 1, and the instructions say exactly what to do when it cannot be verified (`None` + `"unverified"`).

### Type consistency

- `log` is `Callable[[str], None]` everywhere with default `logger.info`; `emit()` dedupes the module logger.
- `token` is `Optional[CancelToken]`; `cancel_check` is `Optional[Callable[[], bool]]` and is derived as `lambda: token.cancelled` in `render_action` only.
- `ClipRecord.params` is a `Dict[str, Any]` with string paths (JSON-safe); `ClipRecord.path` is a `Path`.
- `ActionQueue.run()` returns `Dict[str, ClipRecord | SpriteGenerationError]` as in the design.
- `price_per_second`/`estimate_action`/`estimate_project` return `Optional[float]` (`None` = unknown), never a guessed number.
- Test basenames are unique across `tests/` (no `__init__.py` in the tree).

## Deviations from the design

1. **`log` default and duplicate lines.** The design writes `log=logger.info`. A bound method compares unequal to itself on each access, so `_common.emit()` skips the sink when it is a bound method of the same module logger. Behavior matches the design (file logger plus optional sink) without double lines. Reason: `logger.info is logger.info` is `False` in CPython.
2. **Extra keyword-only parameters (all optional, defaulted):** `make_chroma_plate(..., aspect_ratio="16:9")` and `generate_turnaround(..., aspect_ratio="1:1")` — the design text says `edit_image(..., aspect_ratio=...)` but does not list the parameter; `build_omni_config(req, *, log=...)` / `build_veo_config(req, *, log=...)` so the forced-8 s reason reaches the status console; `generate_action_cards(..., character_notes="", auth_mode=None)` so Gemini routes to `gemini/` vs `vertex_ai/` correctly; `record_actual(..., *, provider=None, model=None, seconds=None, estimated_usd=None)` so the image route (sub-project 6) records its own provider, model, and unit count instead of inheriting the video settings. Reason: the design's logging and routing rules need these inputs, and the ledger must not show a video estimate for an image-route render.
3. **`resolve_model(provider, "chat")`.** The registry snapshot only has a `chat` family for OpenAI (`anthropic`: opus/fable/sonnet/haiku; `gemini`: pro/flash/flash-lite). `default_chat_model()` maps openai→`chat`, anthropic→`sonnet`, gemini→`flash`, each with a static offline fallback, the same pattern as `core/styles/analyzer.py`. Reason: a literal `"chat"` family would fall back to the string `"chat"` for two of three providers.
4. **Additional public helpers, all additive:** `timing.legal_durations`, `timing.snap_duration` (shared by cost and configs), `prompts.strip_render_terms`, `prompts.normalize_hex`, `turnaround.VIEW_PHRASES`, `turnaround.build_view_prompt`, `action_cards.default_chat_model`, `action_cards.draft_to_card`, `video_route.omni_prompt`, `video_route.seam_scores`, `video_route.find_loop_seam`, `video_route.clip_sidecar_path`, `video_route.write_clip_sidecar`, `video_route.clip_record_payload`, `ActionQueue.build_request`, `ActionQueue.clip_path`, plus the private `_common.py`. Reason: testability and reuse by 5a/7; no design signature changes.
5. **Cancel inside a render.** `render_action` raises `pipeline.Cancelled` after it writes the clip sidecar with the provider operation id. The queue turns that into a `ProviderError(retryable=True)` result entry, sets the card back to `draft` with the id in `error`, and stops. Reason: the design says the queue "records the operation id so the user can recover the clip later" but gives `Cancelled` no attributes; the sidecar and the card's `error` carry the id.
6. **Retry count.** "2 s, 4 s, 8 s; 3 tries" is implemented as one first try plus three retries (four calls, three waits) so every backoff value is used. Reason: with only three calls the 8 s wait would never run.
7. **`SpriteGenerationError.operation_id`** is an extra optional attribute so a classified failure keeps the provider job id. Reason: §1.1 asks for the id to be kept on cancel and failure.
8. **Client hooks also check `cancel_check` before the provider call** and return `error="cancelled"` with no operation id. Reason: a cancel that arrives before submission should not spend money.
