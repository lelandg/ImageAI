# Gemini Omni Video Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Source issue:** [#28 — Support Gemini Omni Flash](https://github.com/lelandg/ImageAI/issues/28). Reporter asked for a *plan* with open questions documented; brainstorming is explicitly deferred to the reporter. This plan is therefore staged behind a **Phase 0 verification gate** because the target model is *preview* and the SDK surface is new.

**Last Updated:** 2026-06-30 15:20

## Implementation status (2026-06-30)

**Implemented on branch `feat/gemini-omni-video`** (suite 410 green):

- ✅ `core/video/omni_client.py` — `OmniClient` / `OmniGenerationConfig` /
  `OmniGenerationResult` / `OmniModel`, built against the **verified** SDK 2.8.0
  shape (request via `response_modalities=['video']`; read output by walking
  `interaction.steps → ModelOutputStep → VideoContent`; inline-base64 and
  Files-API-URI delivery; `previous_interaction_id` for edits). 12 mocked unit
  tests.
- ✅ Model ID via `resolve_model('google','omni', static_default='gemini-omni-flash-preview')` (no hardcode).
- ✅ `core/video/config.py` `omni_settings` + `get_omni_model_config`; `__init__.py` `OMNI_AVAILABLE` export; `requirements.txt` floor → `google-genai>=2.3.0`.
- ✅ Video-tab UI: combo entry + Omni model/aspect widgets + visibility toggle + kwargs packing (`workspace_widget.py`).
- ✅ Dispatch + `_generate_video_clip_omni` on `VideoGenerationThread` (`video_project_tab.py`); FFmpeg path concatenates clips (mirrors Sora — no `_render_video` branch needed).
- ✅ Conversational editing plumbing (interaction id saved on scene; reused as `previous_interaction_id` only when an explicit `omni_edit` is requested).
- ✅ Fixed the pre-existing **"Google Veo" vs "Gemini Veo"** save/restore mismatch + added Sora/Omni restore branches; `test_video_provider_persistence.py` locks the label contract.
- ✅ Auth: Omni uses the existing `google_api_key` (API-key) path — no `providers/google.py` change. README updated.

**⚠️ NOT YET VERIFIED LIVE (the Phase 0 gate):** no Google API key reaches the WSL
run env, so no real `client.interactions.create` call has been made. Two pieces
are coded to best-understanding and need a real call (run from PowerShell with a
key + confirmed Omni access) to confirm/adjust:
1. **Aspect-ratio request shape** — sent best-effort as `response_format=[{"type":"video","aspect_ratio":...}]` via the SDK's `object` escape-hatch (no typed `VideoResponseFormat`). The server may ignore or reject it.
2. **Output delivery** — whether the MP4 returns inline on the step, as a Files-API `uri`, or via `background=True`. The client handles inline + uri; if Omni only returns via background, `_await_terminal` polling covers it, but the exact `VideoContent` location in `steps` should be confirmed against a real response.

**Remaining (deferred):** dedicated "Refine" UI button (plumbing is ready — it just
needs to pass `omni_edit=True`); uploaded-video editing; `background`/`webhook`;
SynthID surfacing. See "Deferred / out of scope".

**Goal:** Add "Gemini Omni" as a fourth video provider on the Video tab — text/image/reference-to-video plus conversational editing — driven through Google's new **Interactions API** (`client.interactions.create`, model `gemini-omni-flash-preview`).

**Architecture:** Mirror the existing per-provider video-client pattern (`core/video/veo_client.py`, `core/video/sora_client.py`) with a new `core/video/omni_client.py`, then wire it through the four special-cased integration points the Video tab uses for every provider: the provider combo + visibility toggles (`workspace_widget.py`), worker-kwargs packing, the generation dispatch (`video_project_tab.py`), and project save/restore. Omni's video output is a **submit→(inline | poll-URI)→download** job, so it slots into the Veo/Sora "generator" slot — but on the Interactions API SDK surface, *not* Veo's `generate_videos`.

**Tech Stack:** Python 3.12, PySide6, `google-genai` SDK (**Interactions API requires `>=2.3.0`**; repo currently pins `>=1.49.0` — see Global Constraints), `pytest`.

---

## Global Constraints

- **SDK floor:** Interactions API + Omni require `google-genai >= 2.3.0`. `requirements.txt:3` currently pins `google-genai>=1.49.0`. The bump from 1.x → 2.x is a **major version change** — Task 1 must verify the existing Gemini *image* path (`providers/google/`, `image_config`/`generate_content`) still works on 2.x before anything else proceeds.
- **Min release age:** Per house rules, do not adopt a `google-genai` 2.x release published <7 days ago without explicit approval. Verify the publish date via the PyPI JSON API before bumping the pin.
- **Model IDs are NOT hardcoded (AGENTS.md §8):** `gemini-omni-flash-preview` must be resolved at runtime via `core/llm_models.py` `resolve_model()` / the registry JSON, never written as a literal in client/UI/config code.
- **Provider is `preview` and possibly gated:** Google's GA blog lists Omni as "(soon)" while the doc pages show it live as "preview." Treat availability as unconfirmed until a live `client.interactions.create` call succeeds (Phase 0).
- **All LLM/API interactions must be logged (AGENTS.md §8):** every Omni request (model, task, aspect ratio, prompt, `previous_interaction_id`) and full response/error goes to both the file logger and the status console.
- **Images scaled, not cropped** (AGENTS.md §3) — applies to any reference-image preprocessing.
- **No `cd`; absolute paths only.** Linux venv `.venv_linux` + `python3`; do not run `.venv` from WSL.

---

## What Gemini Omni actually is (research summary)

Verified against the live Google docs (sources listed at the end of this plan). Bottom line that drives the whole design:

- **Model ID:** `gemini-omni-flash-preview` (preview). "Flash" is the tier.
- **It generates video.** Input: text, image, and/or video (≤10s for editing). Output: **MP4, 720p, 24 FPS, 3–10s, with audio.** This resolves the prior investigation's "Branch A vs Branch B" fork firmly to **Branch A — it is a job-style video generator**, comparable in shape to Veo.
- **Driven via the Interactions API**, not `generate_content`/`generate_videos`. Call `client.interactions.create(model="gemini-omni-flash-preview", input=...)`. The reporter's instinct ("we can use interactions api when Omni model is used") is **correct**.
- **Two delivery modes:** small clips return inline base64 (`interaction.output_video.data`); clips >4MB return a URI (`interaction.output_video.uri`) you poll via the **Files API** (`client.files.get` until `state.name == "ACTIVE"`, then `client.files.download`) — the Veo-like submit→poll→download pattern.
- **Stateful conversational editing** via `previous_interaction_id` — the headline feature: generate a clip, then refine with natural language ("make the violin invisible"), each turn building on the last.
- **Aspect ratios:** `16:9` (default) and `9:16` only — set in `response_format`, **not** in prompt text (matches the existing Gemini rule in AGENTS.md §9).
- **`task` values** (in `generation_config.video_config`): `text_to_video`, `image_to_video`, `reference_to_video`, `edit`.
- **Auth:** all examples use a plain API key (`GOOGLE_API_KEY`). Vertex/ADC support is undocumented for Omni (open question).
- **Explicitly unsupported:** system instructions, `temperature`, `top_p`, multi-video prompting, voice editing, video extension/interpolation, provisioned throughput. **Regional:** uploaded-video editing is unavailable in EEA / Switzerland / UK.

### "All features of Omni" — the full scope the issue asks for
1. Text-to-video · 2. Image-to-video · 3. Reference-to-video · 4. Edit a generated video · 5. **Conversational/stateful editing** (`previous_interaction_id`) · 6. Uploaded-video editing (Files API; geo-gated) · 7. Aspect-ratio select (16:9 / 9:16) · 8. Both delivery modes (inline + poll-URI) · 9. Audio in output (promptable) · 10. Sync / `background=true` / `stream=True` execution + `webhook_config` · 11. SynthID watermark awareness.

This plan covers **1–4, 7, 8, 9** as the core feature (parity with how Veo/Sora behave today), implements **5 (conversational editing)** as the distinguishing capability, and **scopes 6, 10, 11 as follow-ups** (see "Deferred / out of scope"). Each is called out so nothing is silently dropped.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `requirements.txt` | dependency pins | Bump `google-genai` floor to the verified 2.x release |
| `core/video/omni_client.py` | **NEW** — Omni Interactions-API client | `OmniModel`, `OmniGenerationConfig`, `OmniGenerationResult`, `OmniClient` with `MODEL_CONSTRAINTS`, `validate_config()`, `generate_video_async()` |
| `core/video/__init__.py` | lazy provider exports | Add `OMNI_AVAILABLE` try/except block + `__all__` entries (mirror Sora at `:14-47`) |
| `core/video/config.py` | video config | Add `omni_settings.models`, allow `default_video_provider="omni"`, optional legacy-migration map |
| `core/llm_models.py` + registry JSON | model-ID resolution | Register `gemini-omni-flash-preview` so `resolve_model()` returns it (no hardcoding) |
| `gui/video/workspace_widget.py` | provider UI + kwargs + persistence | Combo item, Omni model/aspect widgets, visibility toggle, kwargs packing, save/restore |
| `gui/video/video_project_tab.py` | generation dispatch | `_generate_video_clip_omni()` + routing at `:731` and `:1485` |
| `providers/google.py` | auth requirements | Add Omni auth entry only if it differs from Veo |
| `tests/video/test_omni_client.py` | **NEW** — client unit tests | Config validation, request-dict shape, delivery-mode branching (mock SDK) |
| `tests/video/test_video_provider_persistence.py` | **NEW** — persistence regression | Round-trip save/restore for all four providers; locks the Veo-label fix |
| `Docs/CodeMap.md`, `README.md` | docs | Update on ship |

**Pre-existing bug folded into this work (Task 7):** the provider combo emits `"Gemini Veo"` (`workspace_widget.py:1628`), but save/restore checks for `"Google Veo"` (`:7385`, `:7580`). Result: **any saved project with Veo selected silently restores to FFmpeg Slideshow.** Confirmed against current code. Fixing it here prevents Omni from inheriting the same drift and is covered by a regression test.

---

## Phase 0 — Verification Gate (BLOCKING; do this first, no UI work until it passes)

### Task 0: Confirm Omni is callable and characterize its real responses

**Files:**
- Create: `scratch/omni_probe.py` (throwaway probe; **not** committed)

**Goal:** Prove the model exists for this account and capture the *actual* shapes of `output_video.data`, `output_video.uri`, the polling lifecycle, and error envelopes — the docs are preview-grade and have at least one internal inconsistency (audio listed in the guide but not the model spec page).

- [ ] **Step 1: Install the SDK floor in the Linux venv**

Run:
```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python3 -m pip index versions google-genai
```
Confirm a `>=2.3.0` release exists and is **≥7 days old**. Record the exact version. If the only 2.x release is <7 days old, STOP and ask Leland.

- [ ] **Step 2: Probe the four core tasks + delivery modes**

Write `scratch/omni_probe.py` that, using `client.interactions.create(model="gemini-omni-flash-preview", ...)`, runs: (a) text-to-video inline; (b) text-to-video with `response_format={"delivery":"uri"}` and polls Files API; (c) image-to-video with `generation_config={"video_config":{"task":"image_to_video"}}`; (d) a `previous_interaction_id` edit turn. Print the full response object structure, `interaction.id`, `usage`, and the type/size of `output_video.data` vs `.uri` for each.

- [ ] **Step 3: Record findings in this plan**

Fill in the "Phase 0 results" block below with: confirmed model ID/availability, exact attribute path for inline bytes vs URI, the polling terminal states, error-envelope shape, whether audio is actually present, and any auth surprises. **If the model is NOT available to this account, STOP** — the feature is blocked upstream; record that and close the loop with Leland rather than building UI against an uncallable model.

> **Phase 0 results — SDK introspection done 2026-06-30 (live API call still BLOCKED, see below):**
>
> Installed: `google-genai 2.8.0` (PyPI has up to 2.10.0; floor 2.3.0+ confirmed). `client.interactions` is present but emits `UserWarning: Interactions usage is experimental and may change`. Verified the **actual** `create()` signature and types — several plan assumptions (from web docs) are WRONG against the installed SDK and are corrected here:
>
> - **`create()` real kwargs:** `input`, `model`, `background`, `generation_config`, `previous_interaction_id`, `response_format`, `response_mime_type`, `response_modalities`, `service_tier`, `store`, `stream`, `system_instruction`, `tools`, `webhook_config`, `agent`, `agent_config`. Returns `Interaction | Stream[InteractionSSEEvent]`.
> - **No `VideoResponseFormat`.** `response_format` ∈ {Audio, Text, Image, `object`}. Video output must be requested via **`response_modalities=['video']`** (valid literal), NOT a `response_format={"type":"video"}`. **There is no video aspect-ratio field anywhere in the SDK** (only `ImageResponseFormat.aspect_ratio`). → the plan's aspect-ratio handling and `delivery` key for video are unconfirmed; `VideoContent.resolution` is `low|medium|high|ultra_high`, not "720p".
> - **No `interaction.output_video`.** Response is `Interaction{ id, created, status∈[in_progress,requires_action,completed,failed,cancelled,incomplete,budget_exceeded], steps[], usage }`. Generated video arrives as a **`VideoContent` inside a `ModelOutputStep.content[]` within `interaction.steps`** (`VideoContent.data` base64 / `.uri` / `.mime_type`). Client code must walk `steps`, not read `output_video`.
> - **No `generation_config.video_config.task`.** `GenerationConfig` = `{image_config, speech_config, seed, temperature, top_p, max_output_tokens, stop_sequences, thinking_level, thinking_summaries, tool_choice}`. The plan's `task=text_to_video|image_to_video|reference_to_video|edit` mechanism does not exist in this SDK — task is inferred from the input content shape (text-only vs image+text vs video+text).
> - **Model not enumerated:** the `model` Literal lists gemini-2.5/3/3.1/3.5, lyria-3, deep-research — **no `gemini-omni-flash-preview`**. It is accepted only as a free `str`, i.e. the SDK has no first-class knowledge of it.
> - Model callable: **UNVERIFIED — BLOCKED.** No `GOOGLE_API_KEY`/`GEMINI_API_KEY` in env and `config.get_api_key("google")` returns empty in the Linux venv, so the live probe could not run. Combined with the model's absence from the SDK's known list, availability for this account is unconfirmed.
>
> **Consequence for the plan:** the Interactions-API *direction* is correct (real `create`, `previous_interaction_id`, `VideoContent`, inline/uri delivery), but Tasks 3–4's concrete request/response shape must be rewritten to: request video via `response_modalities=['video']`; read output by walking `interaction.steps → ModelOutputStep.content → VideoContent`; drop `video_config.task` and the `response_format` video keys. **Do not implement until (a) a Google API key is available to the run environment and (b) a live `create()` confirms the model is callable and reveals the real output shape** (whether video comes back inline on the step, via a `uri` needing a Files-API poll, or via `background=True`).

---

## Phase 1 — Client (`core/video/omni_client.py`)

### Task 1: Bump the SDK and confirm the existing Gemini image path still works

**Files:**
- Modify: `requirements.txt:3`

**Interfaces:**
- Produces: a `google-genai >= <verified 2.x>` environment that the rest of the plan assumes.

- [ ] **Step 1: Bump the pin**

Change `requirements.txt:3` from `google-genai>=1.49.0  # ...` to the verified 2.x floor, keeping a comment explaining *both* reasons:
```
google-genai>=2.3.0  # 2.3.0+: Interactions API (Gemini Omni video). NBP image_size still supported.
```

- [ ] **Step 2: Install and smoke-test the EXISTING image path (regression guard)**

Run:
```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python3 -m pip install -r requirements.txt
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python3 main.py --provider google -p "a single red apple on white" -o /tmp/omni_sdk_smoke.png
```
Expected: an image is produced (or a clean auth/key error — **not** an `ImportError`/`AttributeError` from the SDK bump). If the 2.x SDK broke `image_config`/`generate_content`, STOP and resolve the image path before continuing.

- [ ] **Step 3: Run the existing test suite**

Run: `cd /mnt/d/Documents/Code/GitHub/ImageAI && /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python3 -m pytest -q`
Expected: same green baseline as before the bump (no SDK-related regressions).

- [ ] **Step 4: Commit**
```bash
git add requirements.txt
git commit -m "chore(deps): bump google-genai floor to 2.x for Interactions API (Gemini Omni)"
```

### Task 2: Register the Omni model ID in the registry

**Files:**
- Modify: `core/llm_models.py` (+ the registry JSON it reads)

**Interfaces:**
- Produces: `resolve_model("gemini-omni-flash-preview")` (or the project's logical key) returns the canonical Omni ID, so no client/UI code hardcodes it.

- [ ] **Step 1: Write the failing test**

Create `tests/video/test_omni_model_registry.py`:
```python
from core.llm_models import resolve_model

def test_omni_model_resolves():
    resolved = resolve_model("gemini-omni-flash-preview")
    assert "omni" in resolved.lower()
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `.venv_linux/bin/python3 -m pytest tests/video/test_omni_model_registry.py -v`
Expected: FAIL (model unknown to registry).

- [ ] **Step 3: Add the model to the registry**

Add `gemini-omni-flash-preview` to the registry JSON / `core/llm_models.py` fallback table following the existing Gemini-model entries (capability: video; tier: flash; status: preview). Match the surrounding schema exactly.

- [ ] **Step 4: Run it, confirm it passes**

Run: same as Step 2 → PASS.

- [ ] **Step 5: Commit**
```bash
git add core/llm_models.py tests/video/test_omni_model_registry.py
git commit -m "feat(models): register gemini-omni-flash-preview for resolve_model"
```

### Task 3: `OmniGenerationConfig` + validation

**Files:**
- Create: `core/video/omni_client.py`
- Test: `tests/video/test_omni_client.py`

**Interfaces:**
- Produces:
  - `class OmniModel(Enum)` — single member resolved via `resolve_model()` at construction (value not a literal in the enum body; resolve in a classmethod/factory if the registry requires it).
  - `@dataclass OmniGenerationConfig(model, prompt, task="text_to_video", aspect_ratio="16:9", duration=None, reference_image: Optional[Path]=None, previous_interaction_id: Optional[str]=None, delivery="auto")` with `__post_init__()` validation + `to_interaction_kwargs() -> dict`.
  - `OmniClient.MODEL_CONSTRAINTS: dict` — `{"aspect_ratios": ["16:9","9:16"], "tasks": ["text_to_video","image_to_video","reference_to_video","edit"], "duration_range": (3,10), "fps": 24, "resolution": "720p", "supports_audio": True}`.

- [ ] **Step 1: Write the failing tests**
```python
import pytest
from pathlib import Path
from core.video.omni_client import OmniGenerationConfig, OmniClient

def test_valid_config_builds_interaction_kwargs():
    cfg = OmniGenerationConfig(model="gemini-omni-flash-preview",
                               prompt="a marble rolling down a track",
                               task="text_to_video", aspect_ratio="16:9")
    kw = cfg.to_interaction_kwargs()
    assert kw["model"] == "gemini-omni-flash-preview"
    assert kw["response_format"]["aspect_ratio"] == "16:9"
    assert kw["generation_config"]["video_config"]["task"] == "text_to_video"
    # aspect ratio must NOT be embedded in the prompt text (AGENTS.md §9)
    assert "16:9" not in kw["input"]

def test_invalid_aspect_ratio_rejected():
    with pytest.raises(ValueError, match="aspect_ratio"):
        OmniGenerationConfig(model="gemini-omni-flash-preview",
                             prompt="x", aspect_ratio="4:3")

def test_invalid_task_rejected():
    with pytest.raises(ValueError, match="task"):
        OmniGenerationConfig(model="gemini-omni-flash-preview",
                             prompt="x", task="audio_to_video")

def test_image_to_video_requires_reference_image():
    with pytest.raises(ValueError, match="reference_image"):
        OmniGenerationConfig(model="gemini-omni-flash-preview",
                             prompt="x", task="image_to_video")
```

- [ ] **Step 2: Run, confirm fail** — `.venv_linux/bin/python3 -m pytest tests/video/test_omni_client.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement config + constraints**

Create `core/video/omni_client.py` with the imports, `OmniModel`, `MODEL_CONSTRAINTS`, and `OmniGenerationConfig` (with `__post_init__` validating aspect ratio ∈ constraints, task ∈ constraints, and `image_to_video`/`reference_to_video` requiring `reference_image`). `to_interaction_kwargs()` builds the `client.interactions.create` kwargs: `model`, `input` (text-only string, or a `[{"type":"image",...},{"type":"text",...}]` list when a reference image is present), `response_format={"type":"video","aspect_ratio":...}` (+ `"delivery":"uri"` when configured), `generation_config={"video_config":{"task":...}}`, and `previous_interaction_id` when set. Mirror the structure of `VeoGenerationConfig`/`SoraGenerationConfig`.

- [ ] **Step 4: Run, confirm pass** → PASS.

- [ ] **Step 5: Commit**
```bash
git add core/video/omni_client.py tests/video/test_omni_client.py
git commit -m "feat(video): OmniGenerationConfig with validation for Interactions API"
```

### Task 4: `OmniClient.generate_video_async()` with inline + poll-URI delivery

**Files:**
- Modify: `core/video/omni_client.py`
- Test: `tests/video/test_omni_client.py`

**Interfaces:**
- Consumes: `OmniGenerationConfig` from Task 3.
- Produces:
  - `@dataclass OmniGenerationResult(success: bool, video_path: Optional[Path], interaction_id: Optional[str], error: Optional[str], generation_time: float, metadata: dict)` — `interaction_id` is essential so the UI can chain conversational edits.
  - `async def generate_video_async(self, config, output_path: Path) -> OmniGenerationResult`.

- [ ] **Step 1: Write failing tests (mock the SDK — no network)**

Add tests that patch the `google.genai` client so `client.interactions.create(...)` returns (a) an object with `output_video.data` (base64) and (b) an object with `output_video.uri` plus a `client.files.get` that transitions `PROCESSING → ACTIVE` and a `client.files.download` returning bytes. Assert both write a valid MP4 to `output_path`, both populate `interaction_id`, and a `FAILED` files state yields `success=False` with a logged error.

- [ ] **Step 2: Run, confirm fail.**

- [ ] **Step 3: Implement the method**

Implement `generate_video_async`: validate config, build kwargs via `to_interaction_kwargs()`, **log the full request** (model, task, aspect, prompt, `previous_interaction_id`) to file + console, call `interactions.create`, then branch on delivery — inline: `base64.b64decode(interaction.output_video.data)`; URI: poll `client.files.get` until `state.name == "ACTIVE"` (bail on `FAILED`), then `client.files.download`. Write bytes to `output_path`, capture `interaction.id`, **log the full response/usage**, and return `OmniGenerationResult`. Wrap everything so any exception → `success=False` + logged error (AGENTS.md §8). Use the polling interval/timeout from `omni_settings` (Task 5).

- [ ] **Step 4: Run, confirm pass.**

- [ ] **Step 5: Add the lazy export**

In `core/video/__init__.py`, add an `OMNI_AVAILABLE` try/except importing `OmniClient, OmniModel, OmniGenerationConfig, OmniGenerationResult` (mirror the Sora block at `:14-29`) and extend `__all__` (`:31-47`).

- [ ] **Step 6: Run the video test subset** — `.venv_linux/bin/python3 -m pytest tests/video/ -v` → PASS.

- [ ] **Step 7: Commit**
```bash
git add core/video/omni_client.py core/video/__init__.py tests/video/test_omni_client.py
git commit -m "feat(video): OmniClient.generate_video_async with inline+URI delivery"
```

### Task 5: Omni config block

**Files:**
- Modify: `core/video/config.py`
- Test: `tests/video/test_omni_client.py` (extend)

**Interfaces:**
- Produces: `omni_settings` with `models` (constraints mirror), `polling_interval`, `timeout`; `default_video_provider` accepts `"omni"`.

- [ ] **Step 1: Write failing test** — assert the loaded video config exposes `omni_settings` with the Omni model and a `polling_interval`. Run → FAIL.
- [ ] **Step 2: Implement** — add `omni_settings` to `core/video/config.py` parallel to `veo_settings`/`sora_settings` (`:36-66`); allow `default_video_provider="omni"`; if Phase 0 surfaced any preview→GA ID change, add a one-line entry to the legacy-migration map (`:68-137`).
- [ ] **Step 3: Run → PASS.**
- [ ] **Step 4: Commit** — `git commit -m "feat(video): add omni_settings to video config"`

---

## Phase 2 — Video-tab wiring (GUI; manual verification, GUI is not unit-testable headless)

> GUI changes can't run TDD headlessly (AGENTS.md §6 — GUI needs a display). Each task ends with a **scripted manual check** the implementer runs from PowerShell where the GUI actually launches (Leland's run env). Keep edits minimal and mirror the Veo/Sora code exactly.

### Task 6: Provider combo, Omni widgets, visibility, kwargs

**Files:**
- Modify: `gui/video/workspace_widget.py` — `:1628`, `:1639-1692`, `:6048-6051`, `:6233-6275`, `:6309-6310`, `:2998`

- [ ] **Step 1:** Add `"Gemini Omni"` to the combo at `:1628` → `addItems(["FFmpeg Slideshow", "Gemini Veo", "OpenAI Sora", "Gemini Omni"])`; extend the tooltip at `:1630`.
- [ ] **Step 2:** After the Veo widgets (`:1639-1662`), add `self.omni_model_combo` (populated from `omni_settings.models`) and `self.omni_aspect_combo` (`["16:9","9:16"]`). Connect a new `on_omni_model_changed` if cost/feature display is needed.
- [ ] **Step 3:** In `on_video_provider_changed()` (`:6233`), add `is_omni = provider == "Gemini Omni"`, set `self.omni_model_combo.setVisible(is_omni)` / `self.omni_aspect_combo.setVisible(is_omni)`, and make sure the Veo/Sora widgets hide when Omni is active (extend the existing show/hide block).
- [ ] **Step 4:** Pack kwargs at `:6048`: add `'omni_model'` and `'omni_aspect_ratio'` (guard with `hasattr`). Extend the render-method resolver at `:2998` with an `elif video_provider == "Gemini Omni" and omni_model:` branch, and the cost-visibility check at `:6310` to include Omni (`!= "Gemini Veo" and != "Gemini Omni"`).
- [ ] **Step 5: Manual check (PowerShell):** launch `python main.py`, open the Video tab, select **Gemini Omni** → only Omni model/aspect widgets show; Veo/Sora widgets hide; switching back to Veo restores Veo widgets. Confirm no traceback in `imageai_current.log`.
- [ ] **Step 6: Commit** — `git commit -m "feat(video-ui): add Gemini Omni provider combo, widgets, kwargs"`

### Task 7: Generation dispatch + the Veo-label persistence fix

**Files:**
- Modify: `gui/video/video_project_tab.py` — `:731-732`, new `_generate_video_clip_omni()`, `:1485-1488`
- Modify: `gui/video/workspace_widget.py` — `:7385`, `:7580`
- Test: `tests/video/test_video_provider_persistence.py` (**new**)

- [ ] **Step 1: Write the failing persistence regression test**

Create `tests/video/test_video_provider_persistence.py` that round-trips a project's `video_provider`/`video_model` through the save/restore helpers for **all four** providers and asserts Veo restores to `"Gemini Veo"` (this currently FAILS because of the `"Google Veo"` mismatch and locks the fix). Use the existing project-IO test pattern as a template; mock the combo if a full widget can't instantiate headlessly.

- [ ] **Step 2: Run → FAIL** on the Veo round-trip (mismatch) and on Omni (not handled yet).

- [ ] **Step 3: Fix the Veo label + add Omni dispatch.**
  - `workspace_widget.py:7385`: `"Google Veo"` → `"Gemini Veo"`.
  - `workspace_widget.py:7579-7582`: add an `elif self.current_project.video_provider == "gemini omni":` branch using `findText("Gemini Omni")` and restoring `omni_model_combo`; and correct the Veo `findText("Google Veo")` → `findText("Gemini Veo")` at `:7580`. Save block (`:7385`) gets a parallel `elif ... == "Gemini Omni":` storing `omni_model_combo.currentText()`.
  - `video_project_tab.py:731`: insert before the Veo fall-through:
    ```python
    if video_provider == 'OpenAI Sora':
        return self._generate_video_clip_sora()
    if video_provider == 'Gemini Omni':
        return self._generate_video_clip_omni()
    # Default to Veo
    ```
  - Add `_generate_video_clip_omni()` (mirror `_generate_video_clip_sora` at `:1295`): build `OmniGenerationConfig` from kwargs, run `OmniClient.generate_video_async` on the worker's event loop, emit progress/results like the Sora path.
  - `video_project_tab.py:1485`: add `elif self.kwargs.get('video_provider') == 'Gemini Omni':` — Omni returns a finished MP4, so route to the same "use the rendered clip directly" path Veo uses (`_render_with_veo`-style), **not** `_render_with_ffmpeg`.

- [ ] **Step 4: Run → PASS** (all four providers round-trip; Veo restores correctly).

- [ ] **Step 5: Manual check (PowerShell):** generate one short clip with **Gemini Omni** (text-to-video); confirm an MP4 lands in the project and the full request/response is in `imageai_current.log`. Save the project, reload it, confirm the provider restores to **Gemini Omni** (and, separately, that a Veo project now restores to **Gemini Veo**, not Slideshow).
- [ ] **Step 6: Commit** — `git commit -m "feat(video): dispatch Gemini Omni generation; fix Veo provider-restore label"`

### Task 8: Conversational editing (the headline Omni capability)

**Files:**
- Modify: `gui/video/workspace_widget.py` (small "Refine this clip" affordance on an Omni-generated clip), `gui/video/video_project_tab.py` (thread `previous_interaction_id` through)

**Interfaces:**
- Consumes: `OmniGenerationResult.interaction_id` from Task 4.

- [ ] **Step 1:** Persist the returned `interaction_id` on the generated clip's metadata sidecar (AGENTS.md §3 — every image/clip gets a `.json` sidecar) so refinement survives reload.
- [ ] **Step 2:** Add a minimal "Refine" entry point for an Omni clip that prompts for an edit instruction and re-dispatches `_generate_video_clip_omni()` with `previous_interaction_id` set to the prior clip's id and `task="edit"`.
- [ ] **Step 3: Manual check (PowerShell):** generate a clip, refine it ("make it night"), confirm the second clip references the first via `previous_interaction_id` in the log and the result reflects the edit.
- [ ] **Step 4: Commit** — `git commit -m "feat(video): conversational refine for Gemini Omni clips"`

---

## Phase 3 — Auth, docs, ship

### Task 9: Auth requirements

**Files:** Modify `providers/google.py` (`MODEL_AUTH_REQUIREMENTS` `:54-67`) only if Phase 0 showed Omni's auth differs from the existing Gemini path. If API-key-only (as docs suggest), confirm the existing Gemini key resolution (`config.get_api_key()`) already covers it and add a one-line note. Commit only if changed.

### Task 10: Docs + CodeMap

**Files:** `Docs/CodeMap.md` (new `omni_client.py` symbols + line refs — use the `update-code-map` skill), `README.md` (feature note + provider list). Commit: `docs: document Gemini Omni video provider`.

---

## Deferred / out of scope (record so nothing is silently dropped)

- **Uploaded-video editing** (Files-API `document` input) — geo-gated (EEA/CH/UK); larger UI surface (file upload + processing-state poll). Follow-up.
- **`background=true` + `webhook_config`** async execution — current Veo/Sora flow long-polls on a worker thread; adopt only if Omni latency makes it necessary.
- **`stream=True`** incremental events — not needed for finished-MP4 delivery.
- **SynthID watermark surfacing** in the UI — note-only for now.
- **Multimodal Omni features beyond video** (audio-in/out as an LLM provider, scene analysis) — out of scope for the Video tab per the reporter; would need the deferred brainstorming pass.

---

## Open Questions (the issue explicitly asks to document these)

1. **Availability/gating:** Google's GA blog says Omni is "(soon)" while the doc pages show it "preview." Is `gemini-omni-flash-preview` callable for this account *today*? → **Phase 0 Task 0 answers this; the whole plan is gated on it.**
2. **Exact `google-genai` 2.x version** that ships `interactions` + Omni, and whether the 1.x→2.x bump breaks the existing NBP image path (`image_config`/`generate_content`). → Task 1 Step 2 guards this.
3. **Audio output specifics:** the guide says audio is generated by default and promptable; the model-spec page omits audio. Format/channels/sample-rate? Can it be disabled? → Phase 0 probe.
4. **Pricing/quota/rate limits** for Omni (per-second-of-video vs per-token) — not on the fetched pages. Affects cost display (`:6310` area). → check `/docs/pricing`.
5. **Vertex AI / ADC auth:** only API-key auth is documented. Does ADC/service-account work with `client.interactions.create`? Is Omni on Vertex? → Phase 0 + Task 9.
6. **`reference_to_video` and `edit` input shapes** are listed but not shown with example code. → Phase 0 probe.
7. **Interactions-API storage retention** (55 days paid / 1 day free) interacts with conversational editing — if a project is reloaded after the `previous_interaction_id` expires, refinement must fail gracefully and fall back to a fresh generation. → handle in Task 8.
8. **Duration control:** docs say 3–10s but don't show a duration parameter in the examples — is duration promptable, fixed, or a config field? → Phase 0 probe.
9. **`min_release_age` approval:** if the only 2.x SDK is <7 days old at implementation time, Leland's explicit approval is required before bumping the pin.

---

## Self-Review (against the issue + research)

- **Spec coverage:** Issue asks to "support all features of Gemini Omni on the Video tab" + "document open questions." Core features 1–4/7/8/9 → Phase 1–2; conversational editing (5) → Task 8; features 6/10/11 explicitly deferred with rationale; open questions → dedicated section. ✓
- **Branch resolved:** prior investigation's Branch-A/Branch-B fork is resolved to Branch A (Omni *is* a video generator) by the research, but on the Interactions-API surface — captured in Architecture + Task 4. ✓
- **No hardcoded model IDs:** Task 2 routes the ID through `resolve_model()`. ✓
- **Pre-existing Veo-label bug:** confirmed against live code (`:1628` emits "Gemini Veo"; `:7385`/`:7580` check "Google Veo") and folded into Task 7 with a regression test. ✓
- **Type consistency:** `OmniGenerationConfig` (Task 3) → consumed by `generate_video_async` (Task 4) → `OmniGenerationResult.interaction_id` (Task 4) → used in Task 8. Names match across tasks. ✓

---

## Sources (Google docs, fetched 2026-06-30 with explicit authorization)

- https://ai.google.dev/gemini-api/docs/omni — "Generate and edit videos with Gemini Omni Flash"
- https://ai.google.dev/gemini-api/docs/models/gemini-omni-flash — model spec (ID, 720p/24fps/3–10s, 16:9/9:16, preview)
- https://ai.google.dev/gemini-api/docs/interactions-overview — Interactions API (state, `previous_interaction_id`, `google-genai>=2.3.0`)
- https://ai.google.dev/api/interactions-api — API reference (`POST /v1beta/interactions`, `client.interactions.create`)
- https://blog.google/innovation-and-ai/technology/developers-tools/interactions-api-general-availability/ — GA announcement (lists Omni "soon")
