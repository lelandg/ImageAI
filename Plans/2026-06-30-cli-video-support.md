# CLI Video Generation Support (single-clip: Gemini Omni + Veo)

**Status:** ✅ Implemented
**Last Updated:** 2026-06-30 17:38
**Branch:** `feat/cli-video`
**Related:** Omni provider (PR #29), Omni Refine UI (PR #31), Sora removal (issue #32)

---

## 1. Problem & Goal

Video generation is currently **GUI-only** (the Video tab orchestrates it). The
CLI (`python main.py ...`) can generate and edit **images** across providers but
has no video path.

**Goal:** Add a single-clip video-generation path to the CLI, oriented to be
**useful to agents** (scriptable, predictable, machine-readable output). Scope is
deliberately bounded to one prompt → one clip, with reference inputs and Veo's
"extend an existing video." The full project pipeline (lyrics/MIDI → storyboard →
multi-scene render) is **out of scope** for this feature.

### In scope
- Text → video, image/reference → video (single clip).
- Reference **images** (Omni: 1; Veo 3.1: ≤3) and optional Veo frame-to-frame
  interpolation (`--last-frame`).
- Reference **video** → **extend** an existing clip (Veo 3.1 only).
- Providers: **Gemini Omni** and **Veo** only.
- Agent-friendly reporting: human text + progress on **stderr**; `--json` →
  single structured result object on **stdout**; `.json` sidecar beside the
  `.mp4`.

### Out of scope (recorded so nothing is silently dropped)
- Full video-project render (storyboard/timing/audio-sync/ffmpeg) from the CLI.
- **Sora** — deprecated; removal tracked separately in **issue #32** (not exposed
  by the CLI).
- `--duration` control — clip length is model-fixed (~8s) on both providers in
  v1; no knob is exposed rather than implying control we don't have.
- Omni conversational "Refine" from the CLI (the GUI has it; chaining on an
  interaction id from a stateless CLI invocation is a possible follow-up).
- Async/background submission + webhooks; streaming events; SynthID badge.

---

## 2. Architecture & Files

Mirrors the existing **layout-CLI** routing pattern
(`cli/runner.py` → `cli/commands/layout.py`).

- **`cli/commands/video.py`** (new) — `run_video_cmd(args) -> int`. Owns:
  arg→config mapping, provider dispatch, output + sidecar writing, JSON
  reporting, and validation. A small internal `_dispatch(provider, args, ...)`
  builds the correct config and calls the correct client. No heavy registry
  abstraction.
- **`cli/runner.py`** — in `run_cli()`, after the layout-command routing block,
  add:
  ```python
  if getattr(args, "video", False):
      from cli.commands.video import run_video_cmd
      return run_video_cmd(args)
  ```
- **`cli/parser.py`** — new "video generation" argument group (see §3).

Reuses without change: `resolve_api_key()` (runner), `OmniClient`/
`OmniGenerationConfig` (`core/video/omni_client.py`), `VeoClient`/
`VeoGenerationConfig` (`core/video/veo_client.py`).

---

## 3. CLI Surface

```
--video                       enable video mode (store_true)
--video-provider {omni,veo}   default: veo
--video-model ID              optional model id override; else resolved/client default
--aspect RATIO                e.g. 16:9, 9:16 (validated per provider)
--ref-image PATH              repeatable (omni: exactly 1; veo: ≤3)
--last-frame PATH             veo only — frame-to-frame interpolation end frame
--extend PATH                 veo only — extend this existing video; implies extend mode
--json                        emit a single machine-readable JSON result on stdout
```

Reuses existing global flags: `-p/--prompt`, `-o/--output`,
`--api-key`, `--api-key-file`, `--auth-mode`.

- `--provider` remains the **image** provider; video selection is the separate
  `--video-provider` to avoid a clash.
- Default `--video-provider` is `veo` (GA flagship; full reference/extend matrix).

### Example invocations
```bash
# Text → video (Veo, default)
python main.py --video -p "a fox running through snow" -o fox.mp4

# Gemini Omni, portrait, fast
python main.py --video --video-provider omni --aspect 9:16 \
    -p "neon city at night" -o city.mp4

# Image/reference → video (Veo, up to 3 refs)
python main.py --video -p "she walks toward camera" -o walk.mp4 \
    --ref-image style.png --ref-image character.png

# Extend an existing clip (Veo only)
python main.py --video --extend fox.mp4 -p "the fox leaps over a log" -o fox2.mp4

# Agent-friendly machine-readable result
python main.py --video -p "a fox in snow" -o fox.mp4 --json
```

---

## 4. Provider Dispatch & Execution

- **omni** → build `OmniGenerationConfig` (task inferred: `text_to_video`, or
  `image_to_video` / `reference_to_video` when `--ref-image` is supplied),
  then `OmniClient(api_key).generate_video(config, output_path)`.
- **veo (generate)** → build `VeoGenerationConfig`, then
  `VeoClient(...).generate_video(config)`.
- **veo (extend)** → when `--extend PATH` is set, call
  `extend_video_async(previous_video_path=PATH, prompt=<-p>, config=...)` through
  the synchronous wrapper.

Execution is **synchronous**: the command blocks on the clients' existing
long-poll (`interactions.get` for Omni; operation polling for Veo) and streams
progress to **stderr**. Exit code is `0` on success, non-zero on failure.

### Auth
Both providers authenticate with the **Google** key, resolved via the existing
layered `resolve_api_key()` (CLI > key file > config > env).
- **Veo** also supports `--auth-mode gcloud` (ADC: `auth_mode`, `project_id`,
  `region`).
- **Omni** is **api-key only**; `--auth-mode gcloud` with `--video-provider omni`
  is an error (§6).

---

## 5. Output & Reporting

- Writes the `.mp4` to `-o`. If `-o` is omitted, derive a sanitized filename from
  the prompt into the current directory (consistent with the image CLI).
- Writes a **`<output>.json` sidecar** with: prompt, video-provider, resolved
  model, aspect ratio, status, operation/interaction id, and timestamps
  (consistent with the image CLI's metadata sidecars).
- **Default reporting:** friendly progress + the final path on **stderr**.
- **`--json` mode:** a single JSON object on **stdout** and nothing else, so an
  agent can parse it cleanly:
  ```json
  {
    "status": "completed",
    "output_path": "fox.mp4",
    "provider": "veo",
    "model": "veo-3.1-generate-001",
    "aspect_ratio": "16:9",
    "operation_id": "operations/abc123",
    "error": null
  }
  ```
  Progress/log lines always go to **stderr** so stdout stays pure in `--json`
  mode.

---

## 6. Validation & Errors (agent-friendly)

All failures log via the platform-independent logger (AGENTS.md §8) and return a
non-zero exit code; in `--json` mode the error is also reported in the `error`
field with `status` set to a failure value.

- `--extend` or `--last-frame` with `--video-provider omni` → clear error (Omni
  cannot file-extend / interpolate).
- `--ref-image` count exceeding the provider max (omni 1, veo 3) → error.
- Unsupported `--aspect` for the chosen provider → surfaced from the client's
  existing config validation.
- `--extend` model that doesn't support scene extension → surfaced from Veo's
  existing extension validation.
- Missing API key, or `--auth-mode gcloud` requested for Omni → error.

---

## 7. Testing

New `tests/video/test_cli_video_*.py` (following the layout convention, where
CLI tests live in the feature's test dir as `tests/layout/test_cli_layout_*.py`),
**fully mocked** (no real API calls), mirroring the existing
`tests/video/test_omni_client.py` style:

- Arg parsing: `--video` flags populate `args` correctly.
- Provider dispatch: omni vs veo build the right config and call the right client.
- Extend path: `--extend` routes to Veo `extend_video_async` with the prompt.
- Guards: `--extend`/`--last-frame` + omni → error; `--ref-image` over max →
  error; gcloud + omni → error.
- `--json` output: exactly one JSON object on stdout with the documented keys.
- Sidecar written with the expected fields.
- Exit codes: `0` success, non-zero on each error path.

Existing suites (`tests/video`, `tests/layout`) must stay green.

---

## 8. Implementation Status

_(Updated during implementation.)_

- ✅ Phase 1 — parser flags + runner routing
- ✅ Phase 2 — `cli/commands/video.py` dispatch + config mapping
- ✅ Phase 3 — output + sidecar + `--json` reporting
- ✅ Phase 4 — validation/error paths
- ✅ Phase 5 — tests (mocked) + docs (README CLI section, imageai-cli skill note)
