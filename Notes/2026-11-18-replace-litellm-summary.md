# Replacing LiteLLM with `chameleon_llm` — session summary

Date: 2026-11-18. Pull request: lelandg/ImageAI#73.

## What changed

- `litellm` is gone from `requirements.txt` and `requirements-security.txt`,
  with its six `.snyk` exceptions.
- `core/chameleon_llm/` is a small vendored package with one function,
  `completion()`, in LiteLLM's call and response shape. It routes by model
  prefix to three adapters over SDKs the app already installed: `openai`
  (also Ollama and LM Studio, plus the Responses API for the pro models),
  `anthropic`, and `google-genai` (API key and Vertex AI).
- Every chat call site builds its arguments through
  `core.llm_params.build_completion_kwargs`.
- `jsonschema` and `tqdm` are declared directly; they had only been installed
  because LiteLLM depended on them.

Design, with every deviation made during the build:
`Plans/2026-11-18-replace-litellm-design.md`. Plan:
`Plans/2026-11-18-replace-litellm-plan.md`. How to run the tests:
`Docs/Testing-LLM.md`.

## Rules the code now follows

- **Routing is by prefix only.** A bare `claude…` or `gemini…` id with no
  base URL is refused with an error naming the prefix to add.
- **A key goes only to its own provider.** `build_completion_kwargs` drops a
  key when the model's prefix names another provider, and local servers never
  receive `OPENAI_API_KEY` from the environment.
- **Google settings travel together.** Auth mode, project and key come from
  one live config (`google_provider_config`). Google Cloud login always means
  Vertex AI with the saved project and no key. API-key mode with no key is an
  authentication error, never a fall-back to Vertex. The app no longer writes
  the Google key to `GEMINI_API_KEY`.
- **Nothing is dropped silently.** A dropped parameter logs a WARNING, an
  approximation logs at DEBUG. Base URLs are logged without user info or
  query strings.

## How it was verified

In a clean environment built from `requirements.txt` (openai 3.49.0,
anthropic 2.8.0, google-genai 2.34.0):

- Offline suite: passes apart from three failures that also occur on `main`
  (`test_ml_install` mediapipe pin, `test_certifi_dependency_security`,
  `test_logging_redaction`).
- Paid cloud tier: 30 passed, 4 skipped, 0 failed, rerun after each of the
  five review-fix rounds.
- `snyk test`: 90 dependencies, no vulnerable paths. `osv-scanner` and
  `pip-audit`: nothing in application dependencies.

Reviews: per-task reviews, a whole-branch review, Codex (GPT-6 Astra) before
the PR (3 findings), CodeRabbit (19 findings), then five Codex passes over
the fixes (4, 2, 1, 1, 1 findings). All fixed. Details are in the PR body.

## Not verified

- **LM Studio and Ollama against a real server.** Neither was running; the
  local tier only ever skipped. Runbook item rb-0045.
- **Google Cloud login in the running app.** The Vertex route is proven live;
  the screens' handling of mode, project and key is proven against fakes.
- **`openai>=2.0.0`.** Proven on 3.49.0 and 2.54.0 only.
- **Ollama and `top_k`.** Dropped on the Ollama routes on the strength of
  Ollama's published request type, not a server.

## Lessons

- The repo's `.venv` had SDKs whole major versions behind what
  `requirements.txt` resolves to. Every offline test passed there and the
  first paid run in a clean environment failed 15 of 34. Build a clean
  environment before trusting dependency or SDK work.
- Removing a dependency removes its transitive packages. Two that the app
  imported directly disappeared with LiteLLM.
- An environment variable used as a hand-off between objects (the exported
  Google key) hid three separate defects. Passing settings on each request
  removed all of them.

## Open items

On the runbook: rb-0045 (run the local tier with servers up), rb-0046 (remove
six LiteLLM ignores in the hosted Snyk project), rb-0047 (decision: remove two
retired Claude models from the model list), rb-0048 (decision: archive
Heimdallr and PromptAlchemy).

Known issues left in the code, all older than this work:

- OpenAI and Anthropic keys are still exported to environment variables by
  `UnifiedLLMProvider`, so two provider objects with different keys affect
  each other.
- Start Prompt stops Ollama and LM Studio at "API Key Missing".
- Ask AI has no Anthropic branch.
- `cli/runner.py` refuses lyrics generation without an API key, so the CLI
  cannot use Google Cloud login for it.
- `gui/video/workspace_widget.py` passes a string (one site) or `None` (three
  sites) where `EndPromptGenerator` expects a provider object.
- Settings also writes API keys to `config.json` in plain text when the
  keyring works.
- `core/video/veo_client.py` and `providers/google.py` still suggest
  `pip install google-generativeai`.
- `Docs/CodeMap.md` was not regenerated; its generator indexes scratch
  folders.

ChatMaster still uses LiteLLM. Moving it needs async, streaming, tool calls
and embeddings in the package first.
