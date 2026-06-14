# Model Registry — Install + Migrate (2026-06-14 09:24)

Wired ImageAI to the ChameleonLabs model registry so cloud LLM model IDs resolve at
runtime instead of being hardcoded and going stale.

## Install
- Vendored the canonical, stdlib-only client (reviewed line-by-line) at
  `core/model_registry/client.py`.
- Added a project wrapper `core/model_registry/__init__.py` that auto-wires the bundled
  fallback so callers never pass a path; never raises while the snapshot exists.
- Snapshotted the registry to `core/model-registry.fallback.json` (beside `llm_models.py`).
- Refresh via `/model-registry refresh-fallback` or
  `curl -sf <registry-url> -o core/model-registry.fallback.json`.

## Migrate
Central helpers added to `core/llm_models.py`:
- `resolve_model(provider, family, static_default=...)` — runtime resolution, accepts app
  aliases (`google`→gemini, `claude`→anthropic), offline-safe, falls back to `static_default`.
- `_provider_models(...)` — builds picker lists at import time from the **bundled snapshot**
  (synchronous, no network): current family IDs lead, curated older models follow.

Lists now lead with current IDs (e.g. `gpt-5.5`, `claude-opus-4-8`, `gemini-3.1-pro-preview`).
`available()` was deliberately NOT used wholesale — OpenAI's list includes non-chat models
(tts/transcribe/image/codex/search) that don't belong in an LLM picker.

Repointed hardcoded defaults to `resolve_model(...)`:
- `cli/runner.py` (lyrics default) — was `gpt-4o`
- `core/lyrics_to_prompts.py` — `generate(model=None)`, resolves `openai/gpt`
- `core/prompt_enhancer_llm.py` — per-provider defaults (google/flash, openai/gpt-mini, anthropic/haiku)
- `core/video/end_prompt_generator.py` — both methods, `gemini/flash`
- `core/video/style_analyzer.py` — vision defaults per provider
- `core/video/prompt_engine.py` — vision default `openai/gpt`
- `gui/prompt_generation_dialog.py` — was invalid `claude-sonnet-4-5` → `anthropic/sonnet`
- `gui/prompt_question_dialog.py` — `gemini/flash`
- `core/font_generator/glyph_identifier.py` — `anthropic/opus`, `gemini/pro` (static dict kept as fallbacks)

## Bonus bug fix
`core/prompt_enhancer_llm.py` `provider_prefixes` had `'anthropic': 'claude-3-haiku-20240307'`
(a stale model ID, not a prefix) and the inner logic only prefixed `google` — so anthropic
models never got the required `anthropic/` LiteLLM prefix. Fixed to `'anthropic': 'anthropic/'`
with the prefix actually applied.

## Left alone (correct)
Image models in `core/constants.py` (gemini/gpt-image/dall-e), the `GPT_IMAGE_2_SNAPSHOT`
reproducibility pin, and `ollama`/`lmstudio` local providers. Docstring/help-text examples
mentioning `gpt-4o` were left as illustrative.

## Verification
- `py_compile` passes on all 12 touched files.
- Live resolve + offline (bad URL → bundled snapshot) both confirmed.
- Pyright "unknown import symbol" flags on the new package are stale-index false positives
  (runtime imports succeed). Other diagnostics are pre-existing (missing optional deps:
  PySide6 / litellm / google.* / cv2 not installed in WSL).

## Not committed
Per project rule "Never add files to git" — new files (`core/model_registry/`,
`core/model-registry.fallback.json`) are left untracked for manual staging. They DO need
committing for the app to work on other machines.
